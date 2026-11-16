"""
app/availability/routes.py
Admin/manager API for managing shifts, leave, on-call roster,
manual override, and the "who is available now" screen.

RBAC (B5):
  - team_lead / admin only: create shift, approve/cancel leave, override,
    holidays, on-call.
  - Agents: 403 on those routes.
  - GET /leave: agents see only their own leave; team_lead/admin see all.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.database.database import SessionLocal
from app.models.user import User
from app.models.team import Team
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.availability import (
    AgentShift, AgentLeave, OnCallRoster, PublicHoliday, AssignmentLog
)
from app.availability.service import (
    assign_agent_for_ticket, get_available_agents_now, _is_on_leave
)
from app.auth.rbac import get_current_user_from_headers

router = APIRouter()

PRIVILEGED_ROLES = {"team_lead", "admin", "manager"}


# ── RBAC helpers ──────────────────────────────────────────────

def _require_privileged(request: Request, db):
    """Raises 403 if caller is not team_lead / admin / manager."""
    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "") if user else "")
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden: team_lead or admin required")
    return user, role


def _get_caller_identity(request: Request, db):
    """Returns (user_or_None, role_str)."""
    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "employee") if user else "employee")
    return user, role


# ── Schemas ───────────────────────────────────────────────────

class ShiftCreate(BaseModel):
    agent_id:   int
    weekday:    int          # 0=Mon, 6=Sun
    start_time: str          # "HH:MM"
    end_time:   str          # "HH:MM"

class LeaveCreate(BaseModel):
    agent_id:       int
    start_datetime: str      # "YYYY-MM-DD HH:MM"
    end_datetime:   str      # "YYYY-MM-DD HH:MM"
    leave_type:     str = "annual"
    notes:          Optional[str] = ""

class LeaveApprove(BaseModel):
    status:      str         # approved / cancelled
    approved_by: Optional[str] = "Manager"

class OnCallCreate(BaseModel):
    agent_id:   int
    team_name:  str
    start_dt:   str          # "YYYY-MM-DD HH:MM"
    end_dt:     str          # "YYYY-MM-DD HH:MM"

class HolidayCreate(BaseModel):
    date:   str              # "YYYY-MM-DD"
    name:   str
    region: Optional[str] = ""

class ManualOverrideRequest(BaseModel):
    new_agent_name: str
    override_by:    str      # team lead name

class DemoSeedRequest(BaseModel):
    reset: bool = False

class CsvUploadRequest(BaseModel):
    csv_content: str


# ── Shifts ────────────────────────────────────────────────────

@router.post("/shifts")
def create_shift(req: ShiftCreate, request: Request):
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        agent = db.query(User).filter(User.id == req.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if agent.role in PRIVILEGED_ROLES:
            raise HTTPException(status_code=400, detail="Manager-role users cannot be assigned shifts")

        existing = db.query(AgentShift).filter(
            AgentShift.agent_id == req.agent_id,
            AgentShift.weekday == req.weekday,
            AgentShift.start_time == req.start_time,
            AgentShift.end_time == req.end_time,
        ).first()
        if existing:
            existing.is_active = True
            existing.agent_name = agent.name
            db.commit()
            db.refresh(existing)
            return {"message": "Shift updated", "shift_id": existing.id}

        shift = AgentShift(
            agent_id   = req.agent_id,
            agent_name = agent.name,
            weekday    = req.weekday,
            start_time = req.start_time,
            end_time   = req.end_time,
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)
        return {"message": "Shift created", "shift_id": shift.id}
    finally:
        db.close()


@router.get("/shifts")
def list_shifts(agent_id: Optional[int] = None):
    db = SessionLocal()
    try:
        q = db.query(AgentShift).filter(AgentShift.is_active == True)
        if agent_id:
            q = q.filter(AgentShift.agent_id == agent_id)
        shifts = q.all()
        return [
            {"id": s.id, "agent_id": s.agent_id, "agent_name": s.agent_name,
             "weekday": s.weekday, "start_time": s.start_time, "end_time": s.end_time}
            for s in shifts
        ]
    finally:
        db.close()


@router.delete("/shifts/{shift_id}")
def delete_shift(shift_id: int, request: Request):
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        shift = db.query(AgentShift).filter(AgentShift.id == shift_id).first()
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")
        shift.is_active = False
        db.commit()
        return {"message": f"Shift {shift_id} deactivated"}
    finally:
        db.close()


# ── Leave ─────────────────────────────────────────────────────

@router.post("/leave")
def create_leave(req: LeaveCreate, request: Request):
    """Any authenticated user (agent or above) can submit leave for themselves.
    Privileged users can submit on behalf of any agent_id."""
    db = SessionLocal()
    try:
        caller, role = _get_caller_identity(request, db)
        # Non-privileged users may only submit leave for themselves
        if role not in PRIVILEGED_ROLES:
            if caller is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            if req.agent_id != caller.id:
                raise HTTPException(status_code=403, detail="You may only submit leave for yourself")

        agent = db.query(User).filter(User.id == req.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        start = datetime.strptime(req.start_datetime, "%Y-%m-%d %H:%M")
        end   = datetime.strptime(req.end_datetime,   "%Y-%m-%d %H:%M")
        overlap = db.query(AgentLeave).filter(
            AgentLeave.agent_id       == req.agent_id,
            AgentLeave.status         != "cancelled",
            AgentLeave.start_datetime <  end,
            AgentLeave.end_datetime   >  start,
        ).first()
        if overlap:
            raise HTTPException(status_code=400,
                detail=f"Overlapping leave already exists (ID {overlap.id})")

        leave = AgentLeave(
            agent_id       = req.agent_id,
            agent_name     = agent.name,
            start_datetime = start,
            end_datetime   = end,
            leave_type     = req.leave_type,
            notes          = req.notes,
            status         = "pending",
        )
        db.add(leave)
        db.commit()
        db.refresh(leave)
        return {"message": "Leave request submitted", "leave_id": leave.id}
    finally:
        db.close()


@router.get("/leave")
def list_leaves(request: Request, agent_id: Optional[int] = None, status: Optional[str] = None):
    db = SessionLocal()
    try:
        caller, role = _get_caller_identity(request, db)

        q = db.query(AgentLeave)

        # B11: agents see only their own leave
        if role not in PRIVILEGED_ROLES:
            if caller is None:
                return []
            q = q.filter(AgentLeave.agent_id == caller.id)
        else:
            if agent_id:
                q = q.filter(AgentLeave.agent_id == agent_id)

        if status:
            q = q.filter(AgentLeave.status == status)

        leaves = q.order_by(AgentLeave.start_datetime.desc()).all()
        return [
            {
                "id": l.id,
                "agent_name": l.agent_name,
                "start": str(l.start_datetime),
                "end": str(l.end_datetime),
                "type": l.leave_type,
                "status": l.status,
                "notes": l.notes,
                "source": getattr(l, "source", "manual") or "manual",
                "external_id": getattr(l, "external_id", None),
                "last_synced_at": str(l.last_synced_at) if getattr(l, "last_synced_at", None) else None,
            }
            for l in leaves
        ]
    finally:
        db.close()


@router.patch("/leave/{leave_id}/approve")
def approve_leave(leave_id: int, req: LeaveApprove, request: Request):
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        leave = db.query(AgentLeave).filter(AgentLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=404, detail="Leave not found")

        leave.status      = req.status
        leave.approved_by = req.approved_by
        db.commit()

        # B7: if reroute raises, return 500 with a clear message
        if req.status == "approved":
            try:
                from app.availability.scheduler import reroute_on_leave_approval
                reroute_on_leave_approval()
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Leave approved but rerouting failed: {e}"
                )
            return {"message": f"Leave {leave_id} approved and tickets rerouted"}

        return {"message": f"Leave {leave_id} status set to '{req.status}'"}
    finally:
        db.close()


# ── On-call roster ────────────────────────────────────────────

@router.post("/oncall")
def create_oncall(req: OnCallCreate, request: Request):
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        agent = db.query(User).filter(User.id == req.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        entry = OnCallRoster(
            agent_id   = req.agent_id,
            agent_name = agent.name,
            team_name  = req.team_name,
            start_dt   = datetime.strptime(req.start_dt, "%Y-%m-%d %H:%M"),
            end_dt     = datetime.strptime(req.end_dt,   "%Y-%m-%d %H:%M"),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {"message": "On-call entry created", "id": entry.id}
    finally:
        db.close()


@router.get("/oncall")
def list_oncall(team_name: Optional[str] = None):
    db = SessionLocal()
    try:
        q = db.query(OnCallRoster)
        if team_name:
            q = q.filter(OnCallRoster.team_name == team_name)
        entries = q.order_by(OnCallRoster.start_dt.desc()).all()
        return [
            {"id": e.id, "agent_name": e.agent_name, "team": e.team_name,
             "start": str(e.start_dt), "end": str(e.end_dt)}
            for e in entries
        ]
    finally:
        db.close()


# ── Public holidays ───────────────────────────────────────────

@router.post("/holidays")
def create_holiday(req: HolidayCreate, request: Request):
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        holiday = PublicHoliday(date=req.date, name=req.name, region=req.region)
        db.add(holiday)
        db.commit()
        db.refresh(holiday)
        return {"message": "Holiday added", "id": holiday.id}
    finally:
        db.close()


@router.get("/holidays")
def list_holidays():
    db = SessionLocal()
    try:
        holidays = db.query(PublicHoliday).order_by(PublicHoliday.date).all()
        return [{"id": h.id, "date": h.date, "name": h.name, "region": h.region}
                for h in holidays]
    finally:
        db.close()


# ── Who is available now ──────────────────────────────────────

@router.get("/available-now")
def who_is_available(request: Request, team: Optional[str] = None):
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        return get_available_agents_now(team, db)
    finally:
        db.close()


# ── Reroute count (read-only, for leave approval confirmation) ─

@router.get("/leave/{leave_id}/reroute-count")
def get_reroute_count(leave_id: int, request: Request):
    """Returns how many unstarted tickets would be rerouted if this leave is approved."""
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        leave = db.query(AgentLeave).filter(AgentLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=404, detail="Leave not found")
        from app.availability.service import UNSTARTED_STATUSES
        count = db.query(Ticket).filter(
            Ticket.assigned_agent_name == leave.agent_name,
            Ticket.status.in_(UNSTARTED_STATUSES),
        ).count()
        return {"agent_name": leave.agent_name, "reroute_count": count}
    finally:
        db.close()


# ── Demo seed & View-As ────────────────────────────────────────

class DemoSeedRequest(BaseModel):
    reset: bool = False

class ViewAsRequest(BaseModel):
    agent_name: str

class CsvUploadRequest(BaseModel):
    csv_content: str


@router.post("/view-as")
def view_as_agent(req: ViewAsRequest, request: Request):
    """
    Impersonate an agent in Agent Workspace.
    Allowed ONLY for real managers when DEMO_MODE is on, and for support agents only.
    Returns 403 otherwise.
    """
    import os
    db = SessionLocal()
    try:
        # 1. Caller must be a manager (admin, manager, team_lead)
        caller = get_current_user_from_headers(request, db, bypass_view_as=True)
        caller_role = request.headers.get("X-Real-User-Role") or (caller.role if caller else "") or request.headers.get("X-User-Role", "")
        if caller_role not in PRIVILEGED_ROLES:
            raise HTTPException(status_code=403, detail="Forbidden: Impersonation only allowed for managers")

        # 2. DEMO_MODE env variable must be on (default 'true')
        demo_mode_env = os.environ.get("DEMO_MODE", "true").lower() == "true"
        if not demo_mode_env:
            raise HTTPException(status_code=403, detail="Forbidden: Impersonation only allowed when DEMO_MODE is on")

        # 3. Target must be a support agent (role == 'agent')
        target = db.query(User).filter(
            (User.name == req.agent_name) | (User.name.like(f"%{req.agent_name}%"))
        ).first()
        if not target or target.role != "agent":
            raise HTTPException(status_code=403, detail="Forbidden: Can only impersonate support agents")

        return {
            "success": True,
            "message": f"Viewing as agent {target.name}",
            "agent": {
                "id": target.id,
                "name": target.name,
                "email": target.email,
                "role": target.role,
                "department": target.department,
                "timezone": target.timezone,
                "max_open_tickets": target.max_open_tickets,
                "is_demo": target.is_demo,
            }
        }
    finally:
        db.close()


@router.post("/demo-seed")
def demo_seed(req: DemoSeedRequest, request: Request):
    """
    Creates 5 demo agents with skill 'Network' in Asia/Kolkata timezone:
      - Ravi:  approved leave covering now (on leave)
      - Priya: shift ended 1 hour ago (off shift)
      - Arun:  in shift, exactly 10 open demo tickets (at cap)
      - Meena: in shift, 3 open demo tickets (available)
      - Kiran: in shift, 1 open demo ticket (available) + on-call roster
    All shift and leave times are computed dynamically relative to current time in Asia/Kolkata.
    Shifts cover ALL 7 days (09:00-17:00 for Meena, Kiran, Arun; Priya's shift is the one that ended an hour ago today).
    Manager-role users NEVER receive shifts.
    Safe to run twice (idempotent upsert by stable key).
    With reset=True, removes ONLY demo records (tagged is_demo=True), preserving Sarah, Mike, and all real data.
    """
    from app.auth.hashing import hash_password
    db = SessionLocal()
    try:
        _require_privileged(request, db)

        DEMO_AGENTS_SPEC = [
            {"name": "Ravi",  "email": "ravi@smartdesk.com",  "team": "Network Operations", "tz": "Asia/Kolkata", "cap": 10, "skill": "Network Operations"},
            {"name": "Priya", "email": "priya@smartdesk.com", "team": "Network Operations", "tz": "Asia/Kolkata", "cap": 10, "skill": "Network Operations"},
            {"name": "Arun",  "email": "arun@smartdesk.com",  "team": "Network Operations", "tz": "Asia/Kolkata", "cap": 10, "skill": "Network Operations"},
            {"name": "Meena", "email": "meena@smartdesk.com", "team": "Network Operations", "tz": "Asia/Kolkata", "cap": 10, "skill": "Network Operations"},
            {"name": "Kiran", "email": "kiran@smartdesk.com", "team": "Network Operations", "tz": "Asia/Kolkata", "cap": 10, "skill": "Network Operations"},
        ]
        DEMO_EMAILS = [d["email"] for d in DEMO_AGENTS_SPEC] + [
            "ravi.demo@helpdesk.local", "priya.demo@helpdesk.local", "arun.demo@helpdesk.local",
            "meena.demo@helpdesk.local", "kiran.demo@helpdesk.local"
        ]
        DEMO_NAMES  = [d["name"]  for d in DEMO_AGENTS_SPEC]

        # ── RESET FLOW: Delete ONLY demo records tagged is_demo=True ──
        if req.reset:
            demo_ticket_ids = [t[0] for t in db.query(Ticket.id).filter(Ticket.is_demo == True).all()]
            if demo_ticket_ids:
                db.query(TicketComment).filter(TicketComment.ticket_id.in_(demo_ticket_ids)).delete(synchronize_session=False)
            db.query(AssignmentLog).filter(
                (AssignmentLog.assigned_agent_name.in_(DEMO_NAMES)) |
                (AssignmentLog.ticket_id.in_(demo_ticket_ids))
            ).delete(synchronize_session=False)
            db.query(Ticket).filter(Ticket.is_demo == True).delete(synchronize_session=False)
            db.query(AgentShift).filter(
                (AgentShift.is_demo == True) | (AgentShift.agent_name.in_(DEMO_NAMES))
            ).delete(synchronize_session=False)
            db.query(AgentLeave).filter(
                (AgentLeave.is_demo == True) | (AgentLeave.agent_name.in_(DEMO_NAMES))
            ).delete(synchronize_session=False)
            db.query(OnCallRoster).filter(
                (OnCallRoster.is_demo == True) | (OnCallRoster.agent_name.in_(DEMO_NAMES))
            ).delete(synchronize_session=False)
            db.query(User).filter(
                (User.is_demo == True) | (User.email.in_(DEMO_EMAILS))
            ).delete(synchronize_session=False)
            db.commit()
            return {"message": "Data reset complete. Only flagged records were removed.", "demo_mode": False}

        # ── SEED FLOW: Idempotent upsert & relative time calculations ──
        # Ensure Network Operations team exists
        net_team = db.query(Team).filter(Team.name == "Network Operations").first()
        if not net_team:
            mgr = db.query(User).filter(User.role == "manager").first()
            net_team = Team(
                name="Network Operations",
                manager_id=mgr.id if mgr else None,
                manager_name=mgr.name if mgr else "John Manager",
                manager_email=mgr.email if mgr else "manager@helpdesk.com",
            )
            db.add(net_team)
            db.commit()

        # Fix Mike Network Agent and Sarah Agent in DB
        mike = db.query(User).filter(User.name.like("%Mike%")).first()
        if mike:
            mike.timezone = "Asia/Kolkata"
            mike.assigned_team = "Network Operations"
            mike_shift = db.query(AgentShift).filter(AgentShift.agent_id == mike.id).first()
            if mike_shift:
                mike_shift.is_active = True
                mike_shift.weekday = 0
                mike_shift.start_time = "09:00"
                mike_shift.end_time = "17:00"
            else:
                db.add(AgentShift(
                    agent_id=mike.id,
                    agent_name=mike.name,
                    weekday=0,
                    start_time="09:00",
                    end_time="17:00",
                    is_active=True,
                    is_demo=False,
                ))

        sarah = db.query(User).filter(User.name.like("%Sarah%")).first()
        if sarah:
            sarah.timezone = "Asia/Kolkata"
        db.commit()

        # 1. Clean up previous demo tickets/shifts/leaves/oncall for demo users
        demo_user_ids = [u[0] for u in db.query(User.id).filter(User.email.in_(DEMO_EMAILS)).all()]
        if demo_user_ids:
            db.query(AgentShift).filter(AgentShift.agent_id.in_(demo_user_ids)).delete(synchronize_session=False)
            db.query(AgentLeave).filter(AgentLeave.agent_id.in_(demo_user_ids)).delete(synchronize_session=False)
            db.query(OnCallRoster).filter(OnCallRoster.agent_id.in_(demo_user_ids)).delete(synchronize_session=False)
        db.query(Ticket).filter(Ticket.is_demo == True).delete(synchronize_session=False)
        db.commit()

        # 2. Upsert 5 demo users with password hash
        demo_pw_hash = hash_password("HelpDesk@2026")
        user_map = {}
        for spec in DEMO_AGENTS_SPEC:
            u = db.query(User).filter(User.email == spec["email"]).first()
            if not u:
                u = User(
                    name=spec["name"],
                    email=spec["email"],
                    password=demo_pw_hash,
                    role="agent",
                    assigned_team=spec["team"],
                    department=spec["skill"],
                    timezone=spec["tz"],
                    max_open_tickets=spec["cap"],
                    is_demo=True,
                )
                db.add(u)
                db.commit()
                db.refresh(u)
            else:
                u.name = spec["name"]
                u.password = demo_pw_hash
                u.role = "agent"
                u.assigned_team = spec["team"]
                u.department = spec["skill"]
                u.timezone = spec["tz"]
                u.max_open_tickets = spec["cap"]
                u.is_demo = True
                db.commit()
            user_map[spec["name"]] = u

        # 3. Dynamic Relative Times in Asia/Kolkata
        try:
            kolkata_tz = ZoneInfo("Asia/Kolkata")
        except Exception:
            kolkata_tz = ZoneInfo("UTC")
        now_ist = datetime.now(kolkata_tz)
        now_utc = datetime.utcnow()
        today_wd = now_ist.weekday()

        # Shift helper for idempotent upsert
        def upsert_shift(agent_id, agent_name, weekday, start_time, end_time):
            shift = db.query(AgentShift).filter(
                AgentShift.agent_id == agent_id,
                AgentShift.weekday == weekday,
                AgentShift.start_time == start_time,
                AgentShift.end_time == end_time,
            ).first()
            if shift:
                shift.is_active = True
                shift.is_demo = True
                shift.agent_name = agent_name
            else:
                shift = AgentShift(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                    is_active=True,
                    is_demo=True,
                )
                db.add(shift)
            return shift

        # In-shift window covering NOW in Asia/Kolkata (now minus 2h to now plus 6h)
        # Handles past-midnight overnight windows gracefully (start_dt.weekday() may be previous day)
        active_start_dt = now_ist - timedelta(hours=2)
        active_end_dt   = now_ist + timedelta(hours=6)
        active_start_str = active_start_dt.strftime("%H:%M")
        active_end_str   = active_end_dt.strftime("%H:%M")
        active_weekday   = active_start_dt.weekday()

        # Ravi: Shift covering NOW AND approved leave covering NOW -> shows "On leave", not "Off shift"
        upsert_shift(user_map["Ravi"].id, "Ravi", active_weekday, active_start_str, active_end_str)
        for d in range(7):
            if d != active_weekday:
                upsert_shift(user_map["Ravi"].id, "Ravi", d, "09:00", "17:00")

        db.add(AgentLeave(
            agent_id=user_map["Ravi"].id,
            agent_name="Ravi",
            start_datetime=now_utc - timedelta(hours=4),
            end_datetime=now_utc + timedelta(hours=20),
            leave_type="annual",
            status="approved",
            is_processed=True,
            notes="Demo: Approved leave covering now",
            is_demo=True,
        ))

        # Priya: Shift ended exactly 1 hour ago (if crossing midnight, overnight window that is clearly over)
        priya_end_dt = now_ist - timedelta(hours=1)
        priya_start_dt = priya_end_dt - timedelta(hours=8)
        priya_start_str = priya_start_dt.strftime("%H:%M")
        priya_end_str = priya_end_dt.strftime("%H:%M")
        priya_weekday = priya_start_dt.weekday()
        upsert_shift(user_map["Priya"].id, "Priya", priya_weekday, priya_start_str, priya_end_str)

        # Arun, Meena, Kiran: in-shift window covering now, plus 09:00-17:00 on other six days
        for ag_name in ["Arun", "Meena", "Kiran"]:
            upsert_shift(user_map[ag_name].id, ag_name, active_weekday, active_start_str, active_end_str)
            for d in range(7):
                if d != active_weekday:
                    upsert_shift(user_map[ag_name].id, ag_name, d, "09:00", "17:00")

        # Arun: Exactly 10 open realistic tickets (at cap 10/10)
        ARUN_TICKETS = [
            ("VPN disconnects every 10 minutes", "Remote employees report intermittent SSL-VPN dropouts every 10 minutes during peak hours.", "Access", "High", "Devon Vance", "Finance"),
            ("Wi-Fi drops in conference room 3", "AP-304 in Executive Boardroom 3 drops 5GHz signal under high client density.", "Network", "Medium", "Priya Sharma", "Marketing"),
            ("Switch port down on floor 2", "Port Gi1/0/24 on Access Switch SW-FL2 went into err-disabled state after continuous broadcast storms.", "Hardware", "High", "Rajesh Gupta", "Operations"),
            ("Cannot reach file server from branch office", "Site-to-site IPsec tunnel Phase 2 SA expired between branch and datacenter.", "Network", "High", "Carlos Rivera", "Legal"),
            ("Firewall rule request for the new CRM", "Allow outbound HTTPS (TCP 443) from internal subnet to external vendor API endpoints.", "Security", "Medium", "Sunita Nair", "Sales"),
            ("Slow internet in the Finance area", "Finance workstation cluster experiencing packet loss and high DNS latency on default gateway.", "Network", "Medium", "Marcus Brody", "Accounting"),
            ("IP address conflict on VLAN 10", "DHCP snooping detected rogue static IP conflicting with critical payroll print server.", "Network", "High", "Emily Chen", "Engineering"),
            ("Core switch redundant power supply fault", "Datacenter Core Switch chassis reports PSU-2 voltage alert and amber fault LED.", "Hardware", "Critical", "Farhan Akhtar", "Facilities"),
            ("DNS resolution failing for internal portal", "Secondary internal DNS forwarder timing out on lookups for dev.portal.smartdesk.local.", "Network", "High", "Ananya Deshmukh", "Customer Support"),
            ("Guest Wi-Fi portal SSL certificate expired", "Captive portal redirect triggers untrusted certificate warnings on visitor mobile devices.", "Security", "Medium", "Vikram Malhotra", "Executive"),
        ]
        for title, desc, cat, prio, req_name, dept in ARUN_TICKETS:
            db.add(Ticket(
                title=title,
                description=desc,
                category=cat,
                priority=prio,
                status="open",
                assigned_team="Network Operations",
                assigned_agent_id=user_map["Arun"].id,
                assigned_agent_name="Arun",
                routing_confidence=0.98,
                requester_name=req_name,
                requester_department=dept,
                created_at=now_utc - timedelta(hours=2),
                sla_due_at=now_utc + timedelta(hours=24),
                is_demo=True,
            ))

        # Meena: Exactly 3 open realistic tickets (3/10)
        MEENA_TICKETS = [
            ("Latency spike on primary MPLS circuit", "WAN link ping times jumped from 18ms to 240ms between offices.", "Network", "High", "Sneha Iyer", "Quality Assurance"),
            ("Bandwidth saturation on 4th floor access point", "802.11ax AP on 4th floor showing 98% channel utilization on 2.4GHz spectrum.", "Network", "Medium", "David Miller", "Product"),
            ("BGP route flap with upstream transit provider", "Autonomous system border router logged 6 peering session resets.", "Network", "Critical", "Pooja Reddy", "IT"),
        ]
        for title, desc, cat, prio, req_name, dept in MEENA_TICKETS:
            db.add(Ticket(
                title=title,
                description=desc,
                category=cat,
                priority=prio,
                status="open",
                assigned_team="Network Operations",
                assigned_agent_id=user_map["Meena"].id,
                assigned_agent_name="Meena",
                routing_confidence=0.98,
                requester_name=req_name,
                requester_department=dept,
                created_at=now_utc - timedelta(hours=2),
                sla_due_at=now_utc + timedelta(hours=24),
                is_demo=True,
            ))

        # Kiran: Exactly 1 open realistic ticket (1/10)
        db.add(Ticket(
            title="Out-of-band management console unreachable",
            description="Dedicated terminal server interface on 192.168.100.12 not responding to SSH requests.",
            category="Access",
            priority="Medium",
            status="open",
            assigned_team="Network Operations",
            assigned_agent_id=user_map["Kiran"].id,
            assigned_agent_name="Kiran",
            routing_confidence=0.98,
            requester_name="Deepak Joshi",
            requester_department="Human Resources",
            created_at=now_utc - timedelta(hours=2),
            sla_due_at=now_utc + timedelta(hours=24),
            is_demo=True,
        ))

        # Kiran: On-call roster entry
        db.add(OnCallRoster(
            agent_id=user_map["Kiran"].id,
            agent_name="Kiran",
            team_name="Network Operations",
            start_dt=now_utc - timedelta(hours=2),
            end_dt=now_utc + timedelta(hours=22),
            is_demo=True,
        ))

        db.commit()

        shifts_count = db.query(AgentShift).filter(AgentShift.is_demo == True, AgentShift.is_active == True).count()
        tickets_count = db.query(Ticket).filter(Ticket.is_demo == True).count()
        agents_count = len(DEMO_AGENTS_SPEC)

        return {
            "message": f"Demo data ready: {agents_count} agents, {shifts_count} shifts, {tickets_count} demo tickets",
            "agents": [d["name"] for d in DEMO_AGENTS_SPEC],
            "states": {
                "Ravi": "On leave (approved leave covering now)",
                "Priya": "Off shift (shift ended 1 hour ago)",
                "Arun": "At capacity (in shift, 10/10 tickets)",
                "Meena": f"Available (in shift, 3/10 tickets, shift ends {active_end_str} IST)",
                "Kiran": f"Available (in shift, 1/10 tickets, on-call, shift ends {active_end_str} IST)",
            },
            "demo_mode": True,
        }
    finally:
        db.close()


# ── Assignment log ────────────────────────────────────────────

@router.get("/assignment-log/{ticket_id}")
def get_assignment_log(ticket_id: int):
    db = SessionLocal()
    try:
        logs = db.query(AssignmentLog).filter(
            AssignmentLog.ticket_id == ticket_id
        ).order_by(AssignmentLog.created_at.desc()).all()
        return [
            {"id": l.id, "assigned_to": l.assigned_agent_name,
             "reason": l.reason, "fallback": l.fallback_used,
             "override_by": l.override_by, "at": str(l.created_at)}
            for l in logs
        ]
    finally:
        db.close()


# ── Manual override ───────────────────────────────────────────

@router.post("/override/{ticket_id}")
def manual_override(ticket_id: int, req: ManualOverrideRequest, request: Request):
    """Team lead manually reassigns a ticket. Override is logged."""
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        new_agent = db.query(User).filter(User.name == req.new_agent_name).first()
        if not new_agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        if _is_on_leave(new_agent, datetime.utcnow(), db):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reassign: Agent '{new_agent.name}' is currently on leave."
            )

        old_name = ticket.assigned_agent_name
        ticket.assigned_agent_name = new_agent.name

        reason = (f"MANUAL OVERRIDE by {req.override_by}: "
                  f"reassigned from '{old_name}' to '{new_agent.name}'")

        db.add(AssignmentLog(
            ticket_id           = ticket_id,
            assigned_agent_id   = new_agent.id,
            assigned_agent_name = new_agent.name,
            candidates_json     = "[]",
            reason              = reason,
            fallback_used       = None,
            override_by         = req.override_by,
        ))
        db.add(TicketComment(
            ticket_id   = ticket_id,
            author_name = req.override_by,
            author_role = "manager",
            content     = reason,
            is_internal = True,
        ))
        db.commit()
        return {"message": reason}
    finally:
        db.close()


# ── HR Leave Sync Endpoints ────────────────────────────────────

@router.post("/sync-now")
def trigger_sync_now(request: Request):
    """Triggers an immediate sync from external HR provider (manager only)."""
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        from app.availability.providers import MockHRProvider
        from app.availability.sync import sync_leaves
        provider = MockHRProvider()
        result = sync_leaves(provider, db)
        return result
    finally:
        db.close()


@router.get("/sync-status")
def get_sync_status_endpoint():
    """Returns the current HR sync status, last sync timestamp, and whether it's stale (>60m)."""
    db = SessionLocal()
    try:
        from app.availability.sync import get_sync_status
        return get_sync_status(db)
    finally:
        db.close()


@router.post("/upload-csv")
def upload_csv_sync(req: CsvUploadRequest, request: Request):
    """Import leave records via CSV and synchronize (manager only)."""
    db = SessionLocal()
    try:
        _require_privileged(request, db)
        from app.availability.providers import CsvImportProvider
        from app.availability.sync import sync_leaves
        provider = CsvImportProvider(req.csv_content)
        result = sync_leaves(provider, db)
        return result
    finally:
        db.close()


@router.post("/emergency-unavailable")
def mark_emergency_unavailable(request: Request):
    """Allows an agent to manually mark themselves unavailable for a same-day emergency."""
    db = SessionLocal()
    try:
        caller, role = _get_caller_identity(request, db)
        if not caller:
            raise HTTPException(status_code=401, detail="Authentication required")

        now = datetime.utcnow()
        end_of_day = now.replace(hour=23, minute=59, second=59)

        # Check if active leave already covers today
        existing = db.query(AgentLeave).filter(
            AgentLeave.agent_id == caller.id,
            AgentLeave.status == "approved",
            AgentLeave.start_datetime <= end_of_day,
            AgentLeave.end_datetime >= now,
        ).first()

        if existing:
            return {"message": "You are already marked unavailable or on leave for today."}

        emergency_leave = AgentLeave(
            agent_id=caller.id,
            agent_name=caller.name,
            start_datetime=now,
            end_datetime=end_of_day,
            leave_type="emergency",
            status="approved",
            source="manual",
            notes="Same-day emergency",
            approved_by="Self (Emergency)",
            is_processed=False,
        )
        db.add(emergency_leave)
        db.commit()

        try:
            from app.availability.scheduler import reroute_on_leave_approval
            reroute_on_leave_approval()
        except Exception as e:
            print(f"[EMERGENCY REROUTE WARN] {e}")

        return {"message": "You have been marked unavailable for today. Unstarted tickets have been rerouted."}
    finally:
        db.close()
