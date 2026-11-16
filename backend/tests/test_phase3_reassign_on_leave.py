"""
tests/test_phase3_reassign_on_leave.py

Tests for Phase 3: Reassign On Leave
- When approved leave becomes active, reassign ALL agent's open & in-progress tickets
- Same assignment chain excluding that agent
- Never touch resolved/closed tickets
- Handover comment: "Reassigned from <agent> (on leave)"
- Idempotent: rerun does not reassign twice or duplicate comments
- Workspace empty when agent is on leave (my-status returns is_on_leave=True, queue is empty)
- On-leave agent cannot be assigned via override or assign-engineer
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.team import Team
from app.models.availability import AgentLeave, AgentShift, AssignmentLog
from app.availability.scheduler import reroute_on_leave_approval
from app.availability.routes import manual_override, ManualOverrideRequest
from app.agent.routes import get_agent_queue, get_my_status, assign_engineer_endpoint, AssignEngineerRequest

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    # Prevent session from becoming detached when code under test calls db.close()
    real_close = session.close
    session.close = lambda: None

    # Team
    team = Team(name="Network Team")
    session.add(team)

    # Agents
    ravi = User(
        id=1,
        name="Ravi",
        email="ravi@company.com",
        password="hash",
        role="agent",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        max_open_tickets=10,
    )
    meena = User(
        id=2,
        name="Meena",
        email="meena@company.com",
        password="hash",
        role="agent",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        max_open_tickets=10,
    )
    manager = User(
        id=3,
        name="John Manager",
        email="manager@company.com",
        password="hash",
        role="manager",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        max_open_tickets=20,
    )
    session.add_all([ravi, meena, manager])
    session.commit()

    # Meena is on shift (00:00 to 23:59 all week)
    for day in range(7):
        session.add(AgentShift(
            agent_id=meena.id,
            agent_name=meena.name,
            weekday=day,
            start_time="00:00",
            end_time="23:59",
            is_active=True,
        ))

    # Ravi is on active approved leave
    now = datetime.utcnow()
    leave = AgentLeave(
        id=1,
        agent_id=ravi.id,
        agent_name="Ravi",
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(days=2),
        leave_type="vacation",
        status="approved",
        is_processed=False,
    )
    session.add(leave)
    session.commit()

    yield session
    real_close()
    Base.metadata.drop_all(bind=engine)


def test_reassign_open_and_in_progress_tickets(db):
    """Open and in-progress tickets are reassigned to Meena with handover comments and logs."""
    t_open = Ticket(
        id=101,
        title="Router down",
        description="Core router down in office",
        category="Network",
        assigned_team="Network Team",
        assigned_agent_id=1,
        assigned_agent_name="Ravi",
        status="open",
    )
    t_prog = Ticket(
        id=102,
        title="VPN failure",
        description="VPN gateway failing for remote employees",
        category="Network",
        assigned_team="Network Team",
        assigned_agent_id=1,
        assigned_agent_name="Ravi",
        status="in_progress",
    )
    db.add_all([t_open, t_prog])
    db.commit()

    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        reroute_on_leave_approval()

    db.refresh(t_open)
    db.refresh(t_prog)

    # Both tickets moved to Meena (and NOT Ravi)
    assert t_open.assigned_agent_name == "Meena"
    assert t_prog.assigned_agent_name == "Meena"

    # Comments added for each ticket
    c_open = db.query(TicketComment).filter(TicketComment.ticket_id == 101).first()
    c_prog = db.query(TicketComment).filter(TicketComment.ticket_id == 102).first()
    assert c_open is not None
    assert "Reassigned from Ravi (on leave)" in c_open.content
    assert c_prog is not None
    assert "Reassigned from Ravi (on leave)" in c_prog.content

    # AssignmentLog records created with Reassigned due to leave
    logs = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == 101).all()
    assert len(logs) >= 1
    assert any("Reassigned due to leave" in (l.reason or "") for l in logs)
    assert any(l.fallback_used == "Reassigned due to leave" for l in logs)


def test_resolved_and_closed_tickets_untouched(db):
    """Resolved and closed tickets must never be touched."""
    t_resolved = Ticket(
        id=103,
        title="DNS config",
        description="Updated DNS resolver records",
        category="Network",
        assigned_team="Network Team",
        assigned_agent_id=1,
        assigned_agent_name="Ravi",
        status="resolved",
    )
    t_closed = Ticket(
        id=104,
        title="Old switch replacement",
        description="Old switch decommissioned",
        category="Network",
        assigned_team="Network Team",
        assigned_agent_id=1,
        assigned_agent_name="Ravi",
        status="closed",
    )
    db.add_all([t_resolved, t_closed])
    db.commit()

    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        reroute_on_leave_approval()

    db.refresh(t_resolved)
    db.refresh(t_closed)

    assert t_resolved.assigned_agent_name == "Ravi"
    assert t_closed.assigned_agent_name == "Ravi"
    assert db.query(TicketComment).filter(TicketComment.ticket_id.in_([103, 104])).count() == 0


def test_rerun_does_not_reassign_twice(db):
    """Idempotency: rerunning the job produces no duplicate reassignments or comments."""
    t = Ticket(
        id=105,
        title="Firewall drop",
        description="Port 443 blocked on firewall",
        category="Network",
        assigned_team="Network Team",
        assigned_agent_id=1,
        assigned_agent_name="Ravi",
        status="open",
    )
    db.add(t)
    db.commit()

    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        reroute_on_leave_approval()
        db.refresh(t)
        assert t.assigned_agent_name == "Meena"
        first_comment_count = db.query(TicketComment).filter(TicketComment.ticket_id == 105).count()
        assert first_comment_count == 1

        # Second run
        reroute_on_leave_approval()
        db.refresh(t)
        assert t.assigned_agent_name == "Meena"
        second_comment_count = db.query(TicketComment).filter(TicketComment.ticket_id == 105).count()
        assert second_comment_count == 1  # No duplicate comment!


def test_workspace_empty_when_agent_on_leave(db):
    """On-leave agent workspace returns empty ticket queue and status showing on-leave until date."""
    req = MagicMock()
    req.headers = {
        "X-User-Id": "1",
        "X-User-Role": "agent",
        "X-User-Email": "ravi@company.com",
    }

    with patch("app.agent.routes.SessionLocal", return_value=db):
        status_info = get_my_status(req)
        assert status_info["is_on_leave"] is True
        assert status_info["leave_until"] is not None

        queue = get_agent_queue(request=req)
        assert queue == []


def test_cannot_assign_to_agent_on_leave(db):
    """Reassigning / overriding to an agent on leave is rejected."""
    t = Ticket(
        id=106,
        title="Switch port dead",
        description="Switch port flapping",
        category="Network",
        assigned_team="Network Team",
        assigned_agent_id=2,
        assigned_agent_name="Meena",
        status="open",
    )
    db.add(t)
    db.commit()

    req = MagicMock()
    req.headers = {"X-User-Role": "manager"}

    # Attempt manual override to Ravi
    with patch("app.availability.routes.SessionLocal", return_value=db):
        with pytest.raises(HTTPException) as exc_info:
            manual_override(
                ticket_id=106,
                req=ManualOverrideRequest(new_agent_name="Ravi", override_by="Manager"),
                request=req,
            )
        assert exc_info.value.status_code == 400
        assert "currently on leave" in exc_info.value.detail

    # Attempt assign_engineer to Ravi
    with patch("app.agent.routes.SessionLocal", return_value=db):
        with pytest.raises(HTTPException) as exc_info2:
            assign_engineer_endpoint(
                ticket_id=106,
                req=AssignEngineerRequest(agent_name="Ravi"),
            )
        assert exc_info2.value.status_code == 400
        assert "currently on leave" in exc_info2.value.detail
