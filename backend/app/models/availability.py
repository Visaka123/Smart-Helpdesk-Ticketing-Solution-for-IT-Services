"""
app/models/availability.py
New tables for agent availability: Shift, Leave, OnCallRoster, PublicHoliday, AssignmentLog.
Backward compatible — adds new tables only, touches nothing existing.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, func, UniqueConstraint
from app.database.database import Base


class AgentShift(Base):
    """
    Weekly recurring shift for an agent.
    weekday: 0=Monday ... 6=Sunday
    start_time / end_time: "HH:MM" strings in agent's local timezone.
    Overnight shifts supported: end_time < start_time (e.g. 22:00 -> 06:00).
    """
    __tablename__ = "agent_shifts"
    __table_args__ = (
        UniqueConstraint("agent_id", "weekday", "start_time", "end_time", name="uq_agent_shift_window"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    agent_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    weekday    = Column(Integer, nullable=False)          # 0=Mon, 6=Sun
    start_time = Column(String(5), nullable=False)        # "HH:MM"
    end_time   = Column(String(5), nullable=False)        # "HH:MM"
    is_active  = Column(Boolean, default=True)
    is_demo    = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=func.now())


class AgentLeave(Base):
    """
    Leave record for an agent.
    leave_type: annual / sick / half_day_am / half_day_pm / public_holiday
    status: pending / approved / cancelled
    Half-day: start_datetime and end_datetime span only half the working day.
    """
    __tablename__ = "agent_leaves"

    id             = Column(Integer, primary_key=True, index=True)
    agent_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_name     = Column(String(100), nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime   = Column(DateTime, nullable=False)
    leave_type     = Column(String(50), default="annual")   # annual/sick/half_day_am/half_day_pm
    status         = Column(String(20), default="pending")  # pending/approved/cancelled
    notes          = Column(Text, nullable=True)
    approved_by    = Column(String(100), nullable=True)
    is_processed   = Column(Boolean, default=False)  # True after reroute_on_leave_approval ran
    source         = Column(String(20), default="manual", nullable=False)   # "hr_sync" or "manual"
    external_id    = Column(String(100), nullable=True, index=True)         # unique ID from external HR system
    last_synced_at = Column(DateTime, nullable=True)                        # timestamp when last synced from HR
    is_demo        = Column(Boolean, default=False, nullable=True)
    created_at     = Column(DateTime, default=func.now())
    updated_at     = Column(DateTime, default=func.now(), onupdate=func.now())


class OnCallRoster(Base):
    """
    On-call coverage for a team during a specific window.
    Used as fallback when no shift agent is available.
    """
    __tablename__ = "oncall_roster"

    id         = Column(Integer, primary_key=True, index=True)
    agent_id   = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    team_name  = Column(String(100), nullable=False, index=True)
    start_dt   = Column(DateTime, nullable=False)
    end_dt     = Column(DateTime, nullable=False)
    is_demo    = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=func.now())


class PublicHoliday(Base):
    """
    Public holidays — agents are treated as on leave on these dates.
    region: optional, e.g. "IN", "US" — if blank applies to all.
    """
    __tablename__ = "public_holidays"

    id         = Column(Integer, primary_key=True, index=True)
    date       = Column(String(10), nullable=False)   # "YYYY-MM-DD"
    name       = Column(String(100), nullable=False)
    region     = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=func.now())


class AssignmentLog(Base):
    """
    Human-readable decision log for every ticket assignment.
    reason example: "Assigned to Ravi: on shift, Network skill, 2 open tickets"
    override_by: set when a team lead manually reassigns.
    """
    __tablename__ = "assignment_logs"

    id                  = Column(Integer, primary_key=True, index=True)
    ticket_id           = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    assigned_agent_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_agent_name = Column(String(100), nullable=True)
    candidates_json     = Column(Text, nullable=True)   # JSON list of all agents considered
    reason              = Column(Text, nullable=False)
    fallback_used       = Column(String(50), nullable=True)  # None / "skill_match" / "oncall" / "urgent_queue"
    override_by         = Column(String(100), nullable=True) # team lead name if manual override
    created_at          = Column(DateTime, default=func.now())
