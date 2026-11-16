"""
app/availability/service.py

Availability filter layer — wraps existing routing without touching it.

Public API:
  assign_agent_for_ticket(ticket, team_name, db) -> (agent | None, reason_str)
  is_available(agent, now_utc, db) -> bool
  filter_by_availability(agents, now_utc, db) -> list[User]
  get_available_agents_now(team_name, db) -> list[dict]
"""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func

from app.models.user import User
from app.models.ticket import Ticket
from app.models.availability import (
    AgentShift, AgentLeave, OnCallRoster, PublicHoliday, AssignmentLog
)

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────
DEFAULT_TICKET_CAP  = 10
HANDOVER_MINUTES    = 30
OPEN_STATUSES       = ["open", "new", "assigned"]
UNSTARTED_STATUSES  = ["open", "new", "assigned"]


# ── Timezone helper ───────────────────────────────────────────

def _agent_local_now(agent: User, utc_now: datetime) -> datetime:
    tz_str = agent.timezone
    if not tz_str or tz_str == "UTC":
        tz_str = "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Asia/Kolkata")
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=ZoneInfo("UTC"))
    return utc_now.astimezone(tz)


# ── Shift check ───────────────────────────────────────────────

def _is_on_shift(agent: User, utc_now: datetime, db) -> bool:
    """
    True if agent has an active shift covering utc_now.
    Handles overnight shifts (end_time < start_time).
    """
    local_now = _agent_local_now(agent, utc_now)
    weekday   = local_now.weekday()
    t_now     = local_now.strftime("%H:%M")

    shifts = db.query(AgentShift).filter(
        AgentShift.agent_id  == agent.id,
        AgentShift.is_active == True,
    ).all()

    for shift in shifts:
        s = shift.start_time
        e = shift.end_time
        if e < s:  # overnight
            prev_weekday = (weekday - 1) % 7
            if shift.weekday == weekday and t_now >= s:
                return True
            if shift.weekday == prev_weekday and t_now <= e:
                return True
        else:
            if shift.weekday == weekday and s <= t_now <= e:
                return True
    return False


# ── On-call check ─────────────────────────────────────────────

def _is_on_call(agent: User, utc_now: datetime, db) -> bool:
    naive_utc = utc_now.replace(tzinfo=None) if utc_now.tzinfo else utc_now
    local_now = _agent_local_now(agent, utc_now).replace(tzinfo=None)
    return db.query(OnCallRoster).filter(
        OnCallRoster.agent_id == agent.id,
        (
            ((OnCallRoster.start_dt <= naive_utc) & (OnCallRoster.end_dt >= naive_utc)) |
            ((OnCallRoster.start_dt <= local_now) & (OnCallRoster.end_dt >= local_now))
        )
    ).first() is not None


# ── Leave check ───────────────────────────────────────────────

def _is_leave_window_active(leave: AgentLeave, local_now: datetime, utc_now: datetime) -> bool:
    """
    Checks if an approved leave is currently active at this exact moment.
    Handles half-day windows (half_day_am: 09:00-13:00, half_day_pm: 13:00-18:00).
    """
    if leave.status != "approved":
        return False

    naive_local = local_now.replace(tzinfo=None) if local_now.tzinfo else local_now
    naive_utc = utc_now.replace(tzinfo=None) if utc_now.tzinfo else utc_now

    # Active range check
    in_range = (
        (leave.start_datetime <= naive_local <= leave.end_datetime) or
        (leave.start_datetime <= naive_utc <= leave.end_datetime)
    )
    if not in_range:
        return False

    # Check half-day restrictions if applicable
    lt = (leave.leave_type or "").lower()
    t_now_str = naive_local.strftime("%H:%M")

    if lt == "half_day_am":
        start_time_str = leave.start_datetime.strftime("%H:%M")
        end_time_str = leave.end_datetime.strftime("%H:%M")
        if start_time_str == "00:00" and end_time_str in ["00:00", "23:59"]:
            return "09:00" <= t_now_str <= "13:00"
    elif lt == "half_day_pm":
        start_time_str = leave.start_datetime.strftime("%H:%M")
        end_time_str = leave.end_datetime.strftime("%H:%M")
        if start_time_str == "00:00" and end_time_str in ["00:00", "23:59"]:
            return "13:00" <= t_now_str <= "18:00"

    return True


def _is_on_leave(agent: User, utc_now: datetime, db) -> bool:
    """
    True only if the agent has an APPROVED leave actively covering NOW (timezone-aware).
    Pending, cancelled, and future leaves NEVER block.
    Half-day leaves block only during their specific window.
    """
    local_now = _agent_local_now(agent, utc_now)
    naive_local = local_now.replace(tzinfo=None) if local_now.tzinfo else local_now
    naive_utc = utc_now.replace(tzinfo=None) if utc_now.tzinfo else utc_now

    candidate_leaves = db.query(AgentLeave).filter(
        AgentLeave.agent_id == agent.id,
        AgentLeave.status == "approved",
        (
            ((AgentLeave.start_datetime <= naive_utc) & (AgentLeave.end_datetime >= naive_utc)) |
            ((AgentLeave.start_datetime <= naive_local) & (AgentLeave.end_datetime >= naive_local))
        )
    ).all()

    for leave in candidate_leaves:
        if _is_leave_window_active(leave, local_now, utc_now):
            return True

    # Regional public holiday check (matches agent's timezone or region prefix)
    date_str = naive_local.strftime("%Y-%m-%d")
    agent_tz = (agent.timezone or "Asia/Kolkata").upper()
    agent_region = agent_tz.split("/")[0]

    holidays = db.query(PublicHoliday).filter(PublicHoliday.date == date_str).all()
    for h in holidays:
        h_reg = (h.region or "").strip().upper()
        if h_reg and (h_reg == agent_tz or h_reg == agent_region):
            return True

    return False


# ── Ticket cap check (B10: batched) ───────────────────────────

def _open_ticket_counts(agent_names: list, db) -> dict:
    """
    Single grouped query returning {agent_name: count} for all names at once.
    Fixes N+1 (B10).
    """
    if not agent_names:
        return {}
    rows = (
        db.query(Ticket.assigned_agent_name, func.count(Ticket.id))
        .filter(
            Ticket.assigned_agent_name.in_(agent_names),
            Ticket.status.in_(OPEN_STATUSES),
        )
        .group_by(Ticket.assigned_agent_name)
        .all()
    )
    counts = {name: cnt for name, cnt in rows}
    # agents with zero open tickets won't appear in rows — default to 0
    return {name: counts.get(name, 0) for name in agent_names}


def _open_ticket_count(agent: User, db) -> int:
    """Single-agent convenience wrapper (used in log helpers)."""
    return _open_ticket_counts([agent.name], db).get(agent.name, 0)


def _is_below_cap(agent: User, open_count: int) -> bool:
    # B2: use `is None` so max_open_tickets=0 means "accept no new tickets"
    cap = agent.max_open_tickets if agent.max_open_tickets is not None else DEFAULT_TICKET_CAP
    return open_count < cap


# ── Core availability check & Agent Status ─────────────────────────

class AgentStatusResult:
    """
    Result returned by get_agent_status(agent, now).
    Can be compared directly to strings (e.g. res == 'on_leave'),
    unpacked as (status, on_call), or accessed via attributes/keys.
    """
    def __init__(self, status: str, on_call: bool, leave_rec=None, return_date: str = None, next_shift: str = None, open_count: int = 0, cap: int = 10):
        self.status = status
        self.on_call = on_call
        self.leave_rec = leave_rec
        self.return_date = return_date
        self.next_shift = next_shift
        self.open_count = open_count
        self.cap = cap

    def __eq__(self, other):
        if isinstance(other, str):
            return self.status == other
        if isinstance(other, AgentStatusResult):
            return self.status == other.status and self.on_call == other.on_call
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.status

    def __repr__(self):
        return f"AgentStatusResult(status='{self.status}', on_call={self.on_call})"

    def __getitem__(self, item):
        return getattr(self, item)

    def __iter__(self):
        yield self.status
        yield self.on_call

    def to_dict(self):
        return {
            "status": self.status,
            "on_call": self.on_call,
            "return_date": self.return_date,
            "next_shift": self.next_shift,
            "open_count": self.open_count,
            "ticket_cap": self.cap,
        }


def get_agent_status(agent: User, now: datetime = None, db = None, open_count: int = None) -> AgentStatusResult:
    """
    ONE shared function that returns the canonical status of an agent in strict priority order:
      on_leave > off_shift > at_capacity > available
    plus on_call as a boolean flag.
    Leave ALWAYS wins over shift.
    """
    from app.database.database import SessionLocal
    from sqlalchemy.orm import object_session
    from datetime import timedelta
    
    close_db = False
    if db is None:
        db = object_session(agent)
        if db is None:
            db = SessionLocal()
            close_db = True

    try:
        if now is None:
            now = datetime.utcnow()
        elif now.tzinfo is not None:
            now = now.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

        # 1. On-Call flag
        on_call = _is_on_call(agent, now, db)

        # 2. Workload & cap
        cap = agent.max_open_tickets if agent.max_open_tickets is not None else DEFAULT_TICKET_CAP
        if open_count is None:
            open_count = _open_ticket_count(agent, db)

        # ── PRIORITY 1: ON_LEAVE (Leave always wins over shift) ───────────
        if _is_on_leave(agent, now, db):
            local_now = _agent_local_now(agent, now)
            naive_local = local_now.replace(tzinfo=None) if local_now.tzinfo else local_now

            # Find active approved leave
            active_leave = db.query(AgentLeave).filter(
                AgentLeave.agent_id == agent.id,
                AgentLeave.status == "approved",
                (
                    ((AgentLeave.start_datetime <= now) & (AgentLeave.end_datetime >= now)) |
                    ((AgentLeave.start_datetime <= naive_local) & (AgentLeave.end_datetime >= naive_local))
                )
            ).order_by(AgentLeave.end_datetime.desc()).first()

            if not active_leave:
                active_leave = db.query(AgentLeave).filter(
                    AgentLeave.agent_id == agent.id,
                    AgentLeave.status == "approved",
                    AgentLeave.end_datetime >= now,
                ).order_by(AgentLeave.end_datetime.desc()).first()

            return_date = ""
            next_shift_str = "On leave"
            if active_leave:
                end_d = active_leave.end_datetime.date()
                ret_d = end_d + timedelta(days=1)
                return_date = f"{ret_d.strftime('%b')} {ret_d.day}"
                next_shift_str = f"Returns {return_date}"

            return AgentStatusResult(
                status="on_leave",
                on_call=on_call,
                leave_rec=active_leave,
                return_date=return_date,
                next_shift=next_shift_str,
                open_count=open_count,
                cap=cap,
            )

        # ── PRIORITY 2: OFF_SHIFT ──────────────────────────────────────────
        on_shift = _is_on_shift(agent, now, db)
        if not on_shift and not on_call:
            shifts = db.query(AgentShift).filter(
                AgentShift.agent_id == agent.id,
                AgentShift.is_active == True,
            ).all()
            next_shift_str = "Tomorrow at 09:00 IST"
            if shifts:
                local_now = _agent_local_now(agent, now)
                today_wd = local_now.weekday()
                today_shift = next((s for s in shifts if s.weekday == today_wd), None)
                target = today_shift or shifts[0]
                next_shift_str = f"Next shift starts {target.start_time} IST"

            return AgentStatusResult(
                status="off_shift",
                on_call=on_call,
                leave_rec=None,
                return_date=None,
                next_shift=next_shift_str,
                open_count=open_count,
                cap=cap,
            )

        # ── PRIORITY 3: AT_CAPACITY ────────────────────────────────────────
        if open_count >= cap:
            shifts = db.query(AgentShift).filter(
                AgentShift.agent_id == agent.id,
                AgentShift.is_active == True,
            ).all()
            local_now = _agent_local_now(agent, now)
            today_wd = local_now.weekday()
            today_shift = next((s for s in shifts if s.weekday == today_wd), None)
            shift_end_time = today_shift.end_time if today_shift else "17:00"
            next_shift_str = f"Current shift ends {shift_end_time} IST"

            return AgentStatusResult(
                status="at_capacity",
                on_call=on_call,
                leave_rec=None,
                return_date=None,
                next_shift=next_shift_str,
                open_count=open_count,
                cap=cap,
            )

        # ── PRIORITY 4: AVAILABLE ──────────────────────────────────────────
        shifts = db.query(AgentShift).filter(
            AgentShift.agent_id == agent.id,
            AgentShift.is_active == True,
        ).all()
        local_now = _agent_local_now(agent, now)
        today_wd = local_now.weekday()
        today_shift = next((s for s in shifts if s.weekday == today_wd), None)
        shift_end_time = today_shift.end_time if today_shift else "17:00"
        next_shift_str = f"Current shift ends {shift_end_time} IST"

        return AgentStatusResult(
            status="available",
            on_call=on_call,
            leave_rec=None,
            return_date=None,
            next_shift=next_shift_str,
            open_count=open_count,
            cap=cap,
        )
    finally:
        if close_db:
            db.close()


def is_available(agent: User, utc_now: datetime, db, open_count: int = None) -> bool:
    """
    True only if:
      1. Not on approved leave / public holiday
      2. On shift OR on call
      3. Below open-ticket cap
    Pass open_count to avoid redundant DB hits when called in a loop.
    """
    res = get_agent_status(agent, utc_now, db, open_count=open_count)
    return res.status == "available"


# ── Filter + pick ─────────────────────────────────────────────

def filter_by_availability(agents: list, utc_now: datetime, db) -> list:
    if not agents:
        return []
    counts = _open_ticket_counts([a.name for a in agents], db)
    return [a for a in agents if is_available(a, utc_now, db, open_count=counts[a.name])]


def _pick_best_agent(eligible: list, counts: dict) -> User:
    return min(eligible, key=lambda a: counts.get(a.name, 0))


# ── Fallback chain ────────────────────────────────────────────

def _fallback_any_skill_match(team_name: str, utc_now: datetime, db):
    agents = db.query(User).filter(
        User.assigned_team == team_name,
        User.role.in_(["agent", "manager"]),
    ).all()
    counts = _open_ticket_counts([a.name for a in agents], db)
    eligible = [
        a for a in agents
        if not _is_on_leave(a, utc_now, db) and _is_below_cap(a, counts[a.name])
    ]
    return _pick_best_agent(eligible, counts) if eligible else None


def _fallback_oncall(team_name: str, utc_now: datetime, db):
    naive_utc = utc_now.replace(tzinfo=None) if utc_now.tzinfo else utc_now
    rosters = db.query(OnCallRoster).filter(
        OnCallRoster.team_name == team_name,
    ).all()
    for roster in rosters:
        agent = db.query(User).filter(User.id == roster.agent_id, User.role == "agent").first()
        if agent:
            local_now = _agent_local_now(agent, utc_now).replace(tzinfo=None)
            if (roster.start_dt <= naive_utc <= roster.end_dt) or (roster.start_dt <= local_now <= roster.end_dt):
                if not _is_on_leave(agent, utc_now, db):
                    count = _open_ticket_count(agent, db)
                    if _is_below_cap(agent, count):
                        return agent
    return None


# ── Assignment log ────────────────────────────────────────────

def _log_assignment(ticket_id: int, agent, candidates: list,
                    reason: str, fallback_used, override_by, db):
    counts = _open_ticket_counts([a.name for a in candidates], db)
    candidates_data = [
        {"id": a.id, "name": a.name, "open_tickets": counts.get(a.name, 0)}
        for a in candidates
    ]
    db.add(AssignmentLog(
        ticket_id           = ticket_id,
        assigned_agent_id   = agent.id if agent else None,
        assigned_agent_name = agent.name if agent else None,
        candidates_json     = json.dumps(candidates_data),
        reason              = reason,
        fallback_used       = fallback_used,
        override_by         = override_by,
    ))


# ── Team lead alert ───────────────────────────────────────────

def _alert_team_lead(ticket: Ticket, team_name: str, reason: str, db):
    from app.models.sla import SLAEscalationLog
    from app.models.team import Team
    team = db.query(Team).filter(Team.name == team_name).first()
    db.add(SLAEscalationLog(
        ticket_id            = ticket.id,
        team_name            = team_name,
        manager_id           = team.manager_id if team else None,
        manager_name         = team.manager_name if team else "Team Lead",
        escalation_reason    = "NO_AVAILABLE_AGENT",
        time_overdue_minutes = 0.0,
    ))
    print(f"[AVAILABILITY ALERT] {reason}")


# ── Skip Reason Helper ─────────────────────────────────────────

def _get_agent_skip_reason(agent: User, utc_now: datetime, count: int, db) -> str:
    """Returns human-readable reason why an agent was not assigned."""
    res = get_agent_status(agent, utc_now, db, open_count=count)
    if res.status == "on_leave":
        return "on leave"
    if res.status == "off_shift":
        return "off shift"
    if res.status == "at_capacity":
        cap = agent.max_open_tickets if agent.max_open_tickets is not None else DEFAULT_TICKET_CAP
        return "over capacity" if count > cap else "at capacity"
    return f"{count} open tickets"


# ── Main entry point ──────────────────────────────────────────

def assign_agent_for_ticket(ticket: Ticket, team_name: str, db,
                             override_by: str = None,
                             exclude_agent_id: int = None,
                             reason_prefix: str = "") -> tuple:
    """
    Called after routing determines team_name.
    Guarantees ticket assignment across the 3-step chain:
      (a) available skilled agent, lowest workload;
      (b) skilled agent not on leave even if off shift (log "queued until shift start");
      (c) manager as last resort + notification.
    
    Every path writes an AssignmentLog row naming each skipped agent and why.
    Never sets assigned_team to 'Unassigned-Urgent'.
    """
    utc_now = datetime.utcnow()

    # Find skilled agents for this team (role == 'agent')
    query = db.query(User).filter(User.role == "agent")
    if exclude_agent_id:
        query = query.filter(User.id != exclude_agent_id)
    if team_name and team_name not in ["Unassigned-Urgent", "Unassigned/Triage"]:
        if team_name in ["Network Operations", "Network Team", "Network & Security", "Network"]:
            query = query.filter(User.assigned_team.in_(["Network Operations", "Network Team", "Network & Security", "Network"]))
        else:
            query = query.filter(User.assigned_team == team_name)
    all_agents = query.all()

    # If no agents in that specific team, consider all active agents
    if not all_agents:
        q_all = db.query(User).filter(User.role == "agent")
        if exclude_agent_id:
            q_all = q_all.filter(User.id != exclude_agent_id)
        all_agents = q_all.all()

    counts = _open_ticket_counts([a.name for a in all_agents], db)

    # ── (a) Available skilled agent (not on leave, on shift/call, below cap) ────
    eligible = [a for a in all_agents if is_available(a, utc_now, db, open_count=counts.get(a.name, 0))]
    if eligible:
        chosen = _pick_best_agent(eligible, counts)
        skipped = [
            f"{a.name} ({_get_agent_skip_reason(a, utc_now, counts.get(a.name, 0), db)})"
            for a in all_agents if a.id != chosen.id
        ]
        skip_str = f" Skipped: {', '.join(skipped)}" if skipped else ""
        reason = f"{reason_prefix}Assigned to {chosen.name}.{skip_str}"
        fallback = "Reassigned due to leave" if "Reassigned due to leave" in reason_prefix else None
        _log_assignment(ticket.id, chosen, all_agents, reason, fallback, override_by, db)
        ticket.assigned_agent_id = chosen.id
        ticket.assigned_agent_name = chosen.name
        db.commit()
        return chosen, reason

    # ── (b) Skilled agent not on leave and below cap, even if off shift ──────────
    not_on_leave = [
        a for a in all_agents
        if not _is_on_leave(a, utc_now, db) and _is_below_cap(a, counts.get(a.name, 0))
    ]
    if not_on_leave:
        chosen = min(not_on_leave, key=lambda a: counts.get(a.name, 0))
        skipped = [
            f"{a.name} ({_get_agent_skip_reason(a, utc_now, counts.get(a.name, 0), db)})"
            for a in all_agents if a.id != chosen.id
        ]
        skip_str = f" Skipped: {', '.join(skipped)}" if skipped else ""
        reason = f"{reason_prefix}Assigned to {chosen.name} (queued until shift start).{skip_str}"
        fallback = "Reassigned due to leave" if "Reassigned due to leave" in reason_prefix else "queued_off_shift"
        _log_assignment(ticket.id, chosen, all_agents, reason, fallback, override_by, db)
        ticket.assigned_agent_id = chosen.id
        ticket.assigned_agent_name = chosen.name
        db.commit()
        return chosen, reason

    # ── (c) Manager as last resort + notification ────────────────────────────────
    manager = None
    if team_name:
        manager = db.query(User).filter(
            User.assigned_team == team_name,
            User.role.in_(["manager", "team_lead", "admin"])
        ).first()
    if not manager:
        manager = db.query(User).filter(User.role == "manager").first()
    if not manager:
        manager = db.query(User).filter(User.role == "admin").first()

    skipped = [
        f"{a.name} ({_get_agent_skip_reason(a, utc_now, counts.get(a.name, 0), db)})"
        for a in all_agents
    ]
    skip_str = f" Skipped: {', '.join(skipped)}." if skipped else ""

    mgr_name = manager.name if manager else "Team Lead"
    mgr_id = manager.id if manager else None
    reason = f"{reason_prefix}FALLBACK: All agents on leave. Assigned to Manager {mgr_name} as last resort.{skip_str}"
    fallback = "Reassigned due to leave" if "Reassigned due to leave" in reason_prefix else "manager_last_resort"

    _log_assignment(ticket.id, manager, all_agents, reason, fallback, override_by, db)
    _alert_team_lead(ticket, team_name or "General", reason, db)

    ticket.assigned_agent_id = mgr_id
    ticket.assigned_agent_name = mgr_name
    db.commit()
    return manager, reason


# ── Who is available now (admin screen) ───────────────────────

# ── Who is available now (admin screen) — BATCHED ────────────────────────────

def _shift_end_local_batched(agent, utc_aware, shifts_for_agent):
    """Returns shift-end label (e.g. "18:00 IST") from pre-fetched shifts. No DB hit."""
    tz_str = agent.timezone
    if not tz_str or tz_str == "UTC":
        tz_str = "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("Asia/Kolkata")
    local_now = utc_aware.astimezone(tz)
    weekday   = local_now.weekday()
    t_now     = local_now.strftime("%H:%M")
    tz_label  = "IST" if tz_str in ["Asia/Kolkata", "Asia/Calcutta", "IST"] else (local_now.strftime("%Z") or tz_str)

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
            return f"{e} {tz_label}"
    return None


def _on_shift_batched(agent, utc_aware, shifts_for_agent):
    """Check if agent is on shift using pre-fetched list. No DB hit."""
    tz_str = agent.timezone
    if not tz_str or tz_str == "UTC":
        tz_str = "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Asia/Kolkata")
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

    # 1. Load all agents (strictly agent role - excludes managers)
    query = db.query(User).filter(User.role == "agent")
    if team_name:
        if team_name in ["Network Operations", "Network Team", "Network & Security", "Network"]:
            query = query.filter(User.assigned_team.in_(["Network Operations", "Network Team", "Network & Security", "Network"]))
        else:
            query = query.filter(User.assigned_team == team_name)
    agents = query.all()
    if not agents:
        return []

    agent_ids   = [a.id   for a in agents]
    agent_names = [a.name for a in agents]

    # 2. Open ticket counts (already batched)
    counts = _open_ticket_counts(agent_names, db)

    # 3. Approved leave windows covering right now
    candidate_leaves = db.query(AgentLeave).filter(
        AgentLeave.agent_id.in_(agent_ids),
        AgentLeave.status == "approved",
    ).all()

    agent_map = {a.id: a for a in agents}
    active_leaves_by_agent = {}
    for l in candidate_leaves:
        ag = agent_map.get(l.agent_id)
        if ag:
            local_ag_now = _agent_local_now(ag, utc_now)
            if _is_leave_window_active(l, local_ag_now, utc_now):
                active_leaves_by_agent[l.agent_id] = l

    leave_agent_ids = set(active_leaves_by_agent.keys())
    leave_info_by_agent = active_leaves_by_agent

    # 3b. Regional holidays for today
    date_str = naive_now.strftime("%Y-%m-%d")
    holidays = db.query(PublicHoliday).filter(PublicHoliday.date == date_str).all()

    def _agent_has_holiday(a):
        a_tz = (a.timezone or "Asia/Kolkata").upper()
        a_reg = a_tz.split("/")[0]
        for h in holidays:
            h_reg = (h.region or "").strip().upper()
            if h_reg and (h_reg == a_tz or h_reg == a_reg):
                return True
        return False

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
        return (a.id in leave_agent_ids) or _agent_has_holiday(a)

    result = []
    for a in agents:
        open_count = counts.get(a.name, 0)
        st = get_agent_status(a, utc_now, db, open_count=open_count)
        agent_shifts = shifts_by_agent.get(a.id, [])
        on_shift_raw = _on_shift_batched(a, utc_aware, agent_shifts)
        on_call_flag = a.id in oncall_agent_ids
        shift_end = None
        if st.status != "on_leave" and (on_shift_raw or on_call_flag):
            shift_end = _shift_end_local_batched(a, utc_aware, agent_shifts)
        leave_rec = st.leave_rec or leave_info_by_agent.get(a.id)
        leave_until = leave_rec.end_datetime.strftime("%Y-%m-%d") if leave_rec else None
        leave_source = getattr(leave_rec, "source", "manual") if leave_rec else None
        result.append({
            "id":           a.id,
            "name":         a.name,
            "team":         a.assigned_team,
            "timezone":     a.timezone or "UTC",
            "skills":       a.department or "",
            "status":       st.status,
            "shift_end":    shift_end,
            "available":    st.status == "available",
            "on_shift":     False if st.status == "on_leave" else on_shift_raw,
            "on_call":      st.on_call,
            "on_leave":     st.status == "on_leave",
            "leave_until":  leave_until,
            "leave_source": leave_source,
            "return_date":  st.return_date,
            "below_cap":    open_count < st.cap,
            "open_tickets": open_count,
            "ticket_cap":   st.cap,
        })
    # Sort available agents first, then by fewest open tickets, then name
    result.sort(key=lambda x: (not x["available"], x["open_tickets"], x["name"]))
    return result
