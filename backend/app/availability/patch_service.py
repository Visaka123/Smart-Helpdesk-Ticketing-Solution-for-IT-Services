"""
Patch script: replaces get_available_agents_now and _shift_end_local in service.py
with a batched version (4 total queries vs O(3*N)).
Run once from D:\\smart_help_desk\\smart-helpdesk\\backend
"""
import re
import sys

src_path = "app/availability/service.py"
with open(src_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the start of "# -- Who is available now" section and replace to end of file
marker = "# \u2500\u2500 Who is available now (admin screen) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"

idx = content.find(marker)
if idx == -1:
    # Try fallback
    idx = content.find("def _shift_end_local(")
    if idx == -1:
        print("ERROR: Could not find section to replace")
        sys.exit(1)
    # Walk back to include any comment before it
    block_start = content.rfind("\n\n", 0, idx) + 2
else:
    block_start = content.rfind("\n\n", 0, idx) + 2

keep = content[:block_start]

replacement = '''

# \u2500\u2500 Who is available now (admin screen) \u2014 BATCHED \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _shift_end_local_batched(agent, utc_aware, shifts_for_agent):
    """Returns shift-end label (e.g. "18:00 IST") from pre-fetched shifts. No DB hit."""
    try:
        tz = ZoneInfo(agent.timezone or "UTC")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    local_now = utc_aware.astimezone(tz)
    weekday   = local_now.weekday()
    t_now     = local_now.strftime("%H:%M")
    for shift in shifts_for_agent:
        s, e = shift.start_time, shift.end_time
        on_this = False
        if e < s:  # overnight
            pw = (weekday - 1) % 7
            if shift.weekday == weekday and t_now >= s:
                on_this = True
            elif shift.weekday == pw and t_now <= e:
                on_this = True
        else:
            if shift.weekday == weekday and s <= t_now <= e:
                on_this = True
        if on_this:
            try:
                h, m = map(int, e.split(":"))
                end_dt = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
                return f"{e} {end_dt.strftime(\'%Z\') or (agent.timezone or \'UTC\')}"
            except Exception:
                return e
    return None


def _on_shift_batched(agent, utc_aware, shifts_for_agent):
    """Check if agent is on shift using pre-fetched list. No DB hit."""
    try:
        tz = ZoneInfo(agent.timezone or "UTC")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    local_now = utc_aware.astimezone(tz)
    weekday   = local_now.weekday()
    t_now     = local_now.strftime("%H:%M")
    for sh in shifts_for_agent:
        s, e = sh.start_time, sh.end_time
        if e < s:
            pw = (weekday - 1) % 7
            if (sh.weekday == weekday and t_now >= s) or (sh.weekday == pw and t_now <= e):
                return True
        else:
            if sh.weekday == weekday and s <= t_now <= e:
                return True
    return False


def get_available_agents_now(team_name: str, db) -> list:
    """
    BATCHED: 4 queries total regardless of agent count.
    Previously ran 3 queries per agent (O(3*N)) causing slow role-switch loads.
    Now pre-fetches shifts, leave, oncall in bulk then processes in-memory.
    """
    utc_now   = datetime.utcnow()
    naive_now = utc_now  # naive (no tzinfo)
    utc_aware = utc_now.replace(tzinfo=ZoneInfo("UTC"))

    # 1. Load all agents
    query = db.query(User).filter(User.role.in_(["agent", "manager"]))
    if team_name:
        query = query.filter(User.assigned_team == team_name)
    agents = query.all()
    if not agents:
        return []

    agent_ids   = [a.id   for a in agents]
    agent_names = [a.name for a in agents]

    # 2. Open ticket counts (already batched)
    counts = _open_ticket_counts(agent_names, db)

    # 3. Approved leave windows covering right now
    leave_agent_ids = {
        row[0] for row in db.query(AgentLeave.agent_id).filter(
            AgentLeave.agent_id.in_(agent_ids),
            AgentLeave.status         == "approved",
            AgentLeave.start_datetime <= naive_now,
            AgentLeave.end_datetime   >= naive_now,
        ).all()
    }

    # 3b. Holidays for today
    date_str = naive_now.strftime("%Y-%m-%d")
    holidays = db.query(PublicHoliday).filter(PublicHoliday.date == date_str).all()
    global_holiday   = any((h.region or "").strip() == "" for h in holidays)
    holiday_regions  = {(h.region or "").strip() for h in holidays if (h.region or "").strip()}

    # 4. Active shifts for all agents (single query)
    all_shifts = db.query(AgentShift).filter(
        AgentShift.agent_id.in_(agent_ids),
        AgentShift.is_active == True,
    ).all()
    shifts_by_agent: dict = {aid: [] for aid in agent_ids}
    for s in all_shifts:
        shifts_by_agent[s.agent_id].append(s)

    # 5. On-call now
    oncall_agent_ids = {
        row[0] for row in db.query(OnCallRoster.agent_id).filter(
            OnCallRoster.agent_id.in_(agent_ids),
            OnCallRoster.start_dt <= naive_now,
            OnCallRoster.end_dt   >= naive_now,
        ).all()
    }

    # 6. Build result in-memory
    def _is_on_leave(a):
        if a.id in leave_agent_ids:
            return True
        if global_holiday:
            return True
        a_tz_prefix = (a.timezone or "").split("/")[0].upper()
        return (a.timezone or "") in holiday_regions or a_tz_prefix in holiday_regions

    result = []
    for a in agents:
        open_count = counts.get(a.name, 0)
        on_leave   = _is_on_leave(a)
        agent_shifts = shifts_by_agent.get(a.id, [])
        on_shift   = _on_shift_batched(a, utc_aware, agent_shifts)
        on_call    = a.id in oncall_agent_ids
        cap        = a.max_open_tickets if a.max_open_tickets is not None else DEFAULT_TICKET_CAP
        below_cap  = open_count < cap
        available  = not on_leave and (on_shift or on_call) and below_cap
        shift_end  = _shift_end_local_batched(a, utc_aware, agent_shifts) if (on_shift or on_call) else None
        result.append({
            "id":           a.id,
            "name":         a.name,
            "team":         a.assigned_team,
            "timezone":     a.timezone or "UTC",
            "skills":       a.department or "",
            "shift_end":    shift_end,
            "available":    available,
            "on_shift":     on_shift,
            "on_call":      on_call,
            "on_leave":     on_leave,
            "below_cap":    below_cap,
            "open_tickets": open_count,
            "ticket_cap":   cap,
        })
    return result
'''

new_content = keep.rstrip() + replacement
with open(src_path, "w", encoding="utf-8") as f:
    f.write(new_content)

# Quick sanity check
with open(src_path, "r", encoding="utf-8") as f:
    final = f.read()

if "def get_available_agents_now" in final and "BATCHED" in final:
    print("[OK] service.py patched successfully.")
    print(f"     Total lines: {len(final.splitlines())}")
else:
    print("[ERROR] Patch may not have applied correctly.")
