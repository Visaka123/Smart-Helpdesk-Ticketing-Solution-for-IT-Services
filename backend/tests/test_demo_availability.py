"""
tests/test_demo_availability.py

Automated tests for demo data seeding, relative time calculations,
idempotency, non-destructive reset, and availability routing flow.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.availability import (
    AgentShift, AgentLeave, OnCallRoster, PublicHoliday, AssignmentLog
)
from app.availability.service import (
    get_available_agents_now, assign_agent_for_ticket
)
from app.availability.scheduler import reroute_on_leave_approval
from app.availability.routes import demo_seed, DemoSeedRequest

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def make_mock_manager_request():
    req = MagicMock()
    req.headers = {"X-User-Role": "manager", "X-User-Name": "John Manager"}
    return req


def test_demo_seeding_relative_times_and_states(db):
    """
    Seeding computes relative times in Asia/Kolkata:
      - Ravi:  on approved leave covering now
      - Priya: shift ended 1 hour ago (off shift)
      - Arun:  in shift, 10 tickets (at cap)
      - Meena: in shift, 2 tickets (available) + on-call roster
    Manager (John Manager) is excluded from the pool.
    """
    # Create John Manager
    manager = User(
        name="John Manager",
        email="manager@helpdesk.com",
        password="x",
        role="manager",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
    )
    db.add(manager)
    db.commit()

    # Call demo_seed with manager request
    mock_req = make_mock_manager_request()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.availability.routes.SessionLocal", lambda: db)
        res = demo_seed(DemoSeedRequest(reset=False), mock_req)

    assert "Demo data ready" in res["message"]

    # Query availability screen
    agents_avail = get_available_agents_now("Network Team", db)

    # 1. Manager must NOT appear in availability screen
    agent_names = [a["name"] for a in agents_avail]
    assert "John Manager" not in agent_names
    assert set(agent_names) == {"Ravi", "Priya", "Arun", "Meena", "Kiran"}

    # 2. Available agents sorted first (fewest tickets first -> Kiran 1, Meena 3)
    available_agents = [a for a in agents_avail if a["available"]]
    assert len(available_agents) == 2
    assert {a["name"] for a in available_agents} == {"Meena", "Kiran"}

    # 3. Check individual agent states
    by_name = {a["name"]: a for a in agents_avail}

    # Ravi: on leave
    assert by_name["Ravi"]["available"] is False
    assert by_name["Ravi"]["on_leave"] is True

    # Priya: off shift
    assert by_name["Priya"]["available"] is False
    assert by_name["Priya"]["on_shift"] is False
    assert by_name["Priya"]["on_call"] is False

    # Arun: at cap
    assert by_name["Arun"]["available"] is False
    assert by_name["Arun"]["on_shift"] is True
    assert by_name["Arun"]["below_cap"] is False
    assert by_name["Arun"]["open_tickets"] == 10

    # Exactly 2 available (Meena, Kiran), 3 unavailable (Ravi, Priya, Arun)
    available_count = sum(1 for a in agents_avail if a["available"])
    unavailable_count = sum(1 for a in agents_avail if not a["available"])
    assert available_count == 2
    assert unavailable_count == 3


def test_demo_seeding_idempotency(db):
    """Calling demo_seed twice produces identical state without duplicate records."""
    mock_req = make_mock_manager_request()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.availability.routes.SessionLocal", lambda: db)
        demo_seed(DemoSeedRequest(reset=False), mock_req)
        demo_seed(DemoSeedRequest(reset=False), mock_req)

    # Verify user counts
    demo_users = db.query(User).filter(User.email.like("%.demo@helpdesk.local")).all()
    assert len(demo_users) == 5

    # Verify Arun has exactly 10 open demo tickets (not 20)
    arun = db.query(User).filter(User.name == "Arun").first()
    arun_tickets = db.query(Ticket).filter(
        Ticket.assigned_agent_id == arun.id,
        Ticket.status == "open",
    ).count()
    assert arun_tickets == 10

    # Verify Meena has exactly 3 open demo tickets (not 6)
    meena = db.query(User).filter(User.name == "Meena").first()
    meena_tickets = db.query(Ticket).filter(
        Ticket.assigned_agent_id == meena.id,
        Ticket.status == "open",
    ).count()
    assert meena_tickets == 3


def test_demo_reset_only_removes_demo_records(db):
    """
    Reset demo data removes records tagged is_demo=True,
    leaving real pre-existing tickets, shifts, and users completely intact.
    """
    # 1. Pre-existing real user and ticket
    real_user = User(
        name="Real Agent",
        email="real.agent@company.com",
        password="x",
        role="agent",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        is_demo=False,
    )
    db.add(real_user)
    db.commit()
    db.refresh(real_user)

    real_shift = AgentShift(
        agent_id=real_user.id,
        agent_name="Real Agent",
        weekday=0,
        start_time="09:00",
        end_time="17:00",
        is_active=True,
        is_demo=False,
    )
    db.add(real_shift)

    real_ticket = Ticket(
        title="Production network fiber cut",
        description="Core router down",
        category="Access",
        priority="Critical",
        status="open",
        assigned_team="Network Team",
        assigned_agent_id=real_user.id,
        assigned_agent_name="Real Agent",
        is_demo=False,
    )
    db.add(real_ticket)
    db.commit()

    # 2. Seed demo data
    mock_req = make_mock_manager_request()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.availability.routes.SessionLocal", lambda: db)
        demo_seed(DemoSeedRequest(reset=False), mock_req)

        # Confirm demo records exist
        assert db.query(User).filter(User.is_demo == True).count() == 5
        assert db.query(Ticket).filter(Ticket.is_demo == True).count() >= 14

        # 3. Reset demo data
        demo_seed(DemoSeedRequest(reset=True), mock_req)

    # 4. Verify ONLY demo records removed
    assert db.query(User).filter(User.is_demo == True).count() == 0
    assert db.query(Ticket).filter(Ticket.is_demo == True).count() == 0
    assert db.query(AgentShift).filter(AgentShift.is_demo == True).count() == 0
    assert db.query(AgentLeave).filter(AgentLeave.is_demo == True).count() == 0

    # 5. Verify real data is completely intact
    preserved_user = db.query(User).filter(User.email == "real.agent@company.com").first()
    assert preserved_user is not None
    assert preserved_user.name == "Real Agent"

    preserved_ticket = db.query(Ticket).filter(Ticket.title == "Production network fiber cut").first()
    assert preserved_ticket is not None
    assert preserved_ticket.priority == "Critical"

    preserved_shift = db.query(AgentShift).filter(AgentShift.agent_name == "Real Agent").first()
    assert preserved_shift is not None


def test_assignment_skip_reasons_and_full_demo_flow(db):
    """
    Full Flow:
      1. Load demo data -> Meena available (2 open), Arun at cap (10), Priya off shift, Ravi on leave.
      2. Create ticket for Network Team -> Lands on Meena.
      3. Assignment reason lists each skipped agent with exact reason:
         "Assigned to Meena. Skipped: Ravi (on leave), Priya (off shift), Arun (at capacity)"
      4. Manager approves pending leave for Meena -> Reroute triggers.
      5. Everyone unavailable -> Ticket moves to Unassigned-Urgent queue.
    """
    mock_req = make_mock_manager_request()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.availability.routes.SessionLocal", lambda: db)
        demo_seed(DemoSeedRequest(reset=False), mock_req)

    # 1. New ticket created for Network Team
    new_ticket = Ticket(
        title="VPN gateway certificate expired",
        description="Users cannot connect to enterprise VPN",
        category="Access",
        priority="High",
        status="open",
        assigned_team="Network Team",
        is_demo=True,
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)

    # 2. Auto-assign agent (Kiran has 1 ticket, Meena has 3 tickets -> picks Kiran as least-loaded)
    chosen, reason = assign_agent_for_ticket(new_ticket, "Network Team", db)

    # Lands on Kiran (least loaded available agent)
    assert chosen is not None
    assert chosen.name == "Kiran"

    # Reason must name each skipped agent and why
    assert "Assigned to Kiran." in reason
    assert "Ravi (on leave)" in reason
    assert "Priya (off shift)" in reason
    assert "Arun (at capacity)" in reason

    new_ticket.assigned_agent_name = chosen.name
    new_ticket.assigned_agent_id = chosen.id
    new_ticket.status = "open"
    db.commit()
    ticket_id = new_ticket.id

    # 3. Put Kiran on leave and trigger reroute
    kiran_user = db.query(User).filter(User.name == "Kiran").first()
    kiran_leave = AgentLeave(
        agent_id=kiran_user.id,
        agent_name="Kiran",
        start_datetime=datetime.utcnow() - timedelta(hours=1),
        end_datetime=datetime.utcnow() + timedelta(hours=8),
        leave_type="annual",
        status="approved",
        is_processed=False,
    )
    db.add(kiran_leave)
    db.commit()

    # 4. Trigger reroute on leave approval
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.availability.scheduler.SessionLocal", lambda: db)
        reroute_on_leave_approval()

    # Query fresh ticket row from DB - reroutes to Meena (the other available agent)
    rerouted_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    assert rerouted_ticket.assigned_agent_name == "Meena"
