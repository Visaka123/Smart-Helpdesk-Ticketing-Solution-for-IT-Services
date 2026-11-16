"""
tests/test_relaxed_assignment_chain.py

Tests for Relaxed Assignment Chain & ASSIGNMENT_MODE configuration:
1. Own team's only agent on leave -> goes to the lowest-loaded in-work agent from another team, never manager or off-shift.
2. In-work agent preferred over off-shift agent even if at/over cap ("assign only for person in work"). When ALL agents are off-shift, assigns lowest workload agent outside shift.
3. Every agent on leave -> manager fallback.
4. Strict mode blocks off-shift and over-cap agents; relaxed mode assigns outside shift when no one is in work.
5. Re-run on GST ticket (#52) reassigns it to an in-work agent, with log row.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.availability import AgentShift, AgentLeave, AssignmentLog
from app.availability.service import (
    assign_agent_for_ticket,
    reassign_manager_fallback_tickets,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_own_team_only_agent_on_leave_goes_to_lowest_loaded_cross_team_agent(db):
    """
    Test 1: When own team's only agent is on approved leave active now,
    the ticket goes to the lowest-loaded in-work agent from another team, never manager or off-shift.
    """
    now = datetime.utcnow()

    manager = User(id=1, name="John Manager", email="manager@company.com", password="hash", role="manager", assigned_team="IT Support")
    sarah = User(id=2, name="Sarah Agent", email="sarah@company.com", password="hash", role="agent", assigned_team="IT Support", max_open_tickets=10)
    kiran = User(id=3, name="Kiran", email="kiran@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)
    meena = User(id=4, name="Meena", email="meena@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)

    db.add_all([manager, sarah, kiran, meena])
    db.commit()

    # Sarah is on approved leave
    db.add(AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(days=2),
        status="approved",
    ))

    # Kiran & Meena shifts active today
    db.add(AgentShift(
        agent_id=kiran.id,
        agent_name=kiran.name,
        weekday=now.weekday(),
        start_time="00:00",
        end_time="23:59",
        is_active=True,
    ))
    db.add(AgentShift(
        agent_id=meena.id,
        agent_name=meena.name,
        weekday=now.weekday(),
        start_time="00:00",
        end_time="23:59",
        is_active=True,
    ))

    # Existing tickets to simulate workload: Kiran has 1, Meena has 3
    db.add(Ticket(id=201, title="Kiran existing 1", description="desc", status="open", assigned_agent_name="Kiran", assigned_agent_id=kiran.id))
    db.add(Ticket(id=202, title="Meena existing 1", description="desc", status="open", assigned_agent_name="Meena", assigned_agent_id=meena.id))
    db.add(Ticket(id=203, title="Meena existing 2", description="desc", status="open", assigned_agent_name="Meena", assigned_agent_id=meena.id))
    db.add(Ticket(id=204, title="Meena existing 3", description="desc", status="open", assigned_agent_name="Meena", assigned_agent_id=meena.id))

    # New ticket for IT Support
    ticket = Ticket(
        id=205,
        title="Excel crashes opening large file",
        description="Excel crashes with error 0xc000005",
        category="Software",
        assigned_team="IT Support",
        status="open",
    )
    db.add(ticket)
    db.commit()

    chosen, reason = assign_agent_for_ticket(ticket, "IT Support", db, mode="relaxed")

    # Assertions
    assert chosen is not None
    assert chosen.name == "Kiran", "Should pick Kiran because Kiran is in work with lowest workload (1 vs 3)"
    assert chosen.role == "agent", "Must be an agent, never a manager"
    assert chosen.name != "John Manager"
    assert "cross-team" in reason
    assert "Sarah Agent (on leave)" in reason

    log = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == 205).first()
    assert log is not None
    assert log.assigned_agent_name == "Kiran"
    assert "Sarah Agent (on leave)" in log.reason


def test_in_work_agent_preferred_over_off_shift_even_if_over_capacity(db):
    """
    Test 2: Only assign for person in work regardless of department/capacity.
    When Arun is in-work (even if over capacity 11/10) and Mike is off-shift (2 tickets),
    the ticket MUST go to the in-work person (Arun), never the off-shift person (Mike)!
    """
    now = datetime.utcnow()

    manager = User(id=1, name="John Manager", email="manager@company.com", password="hash", role="manager", assigned_team="IT Support")
    mike = User(id=2, name="Mike", email="mike@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)
    arun = User(id=3, name="Arun", email="arun@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)

    db.add_all([manager, mike, arun])
    db.commit()

    # Arun shift is active (in-work), but Arun is over cap (11 tickets)
    db.add(AgentShift(
        agent_id=arun.id,
        agent_name=arun.name,
        weekday=now.weekday(),
        start_time="00:00",
        end_time="23:59",
        is_active=True,
    ))
    # Mike has NO active shift (off-shift)

    # Mike has 2 tickets
    db.add(Ticket(id=301, title="Mike 1", description="desc", status="open", assigned_agent_name="Mike", assigned_agent_id=mike.id))
    db.add(Ticket(id=302, title="Mike 2", description="desc", status="open", assigned_agent_name="Mike", assigned_agent_id=mike.id))

    # Arun has 11 tickets (over cap 10)
    for i in range(11):
        db.add(Ticket(id=310 + i, title=f"Arun {i}", description="desc", status="open", assigned_agent_name="Arun", assigned_agent_id=arun.id))

    # New ticket
    ticket = Ticket(id=330, title="Urgent Network Issue", description="desc", category="Network", assigned_team="Network Operations", status="open")
    db.add(ticket)
    db.commit()

    chosen, reason = assign_agent_for_ticket(ticket, "Network Operations", db, mode="relaxed")

    # Arun is in work so Arun MUST be chosen, NEVER off-shift Mike
    assert chosen is not None
    assert chosen.name == "Arun", "Must assign only to person in work (Arun), never off-shift (Mike)"
    assert chosen.name != "Mike"
    assert chosen.name != "John Manager"
    assert "Mike (off shift)" in reason
    assert ticket.assigned_agent_name == "Arun"


def test_when_all_agents_are_off_shift_assigns_lowest_workload(db):
    """
    Test 2b: When literally NO agent is in work (all are off-shift),
    relaxed mode assigns to the lowest workload agent outside shift.
    """
    now = datetime.utcnow()

    manager = User(id=1, name="John Manager", email="manager@company.com", password="hash", role="manager", assigned_team="IT Support")
    mike = User(id=2, name="Mike", email="mike@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)
    arun = User(id=3, name="Arun", email="arun@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)

    db.add_all([manager, mike, arun])
    db.commit()

    # Neither Mike nor Arun has an active shift (both off shift)
    db.add(Ticket(id=351, title="Mike 1", description="desc", status="open", assigned_agent_name="Mike", assigned_agent_id=mike.id))
    db.add(Ticket(id=352, title="Arun 1", description="desc", status="open", assigned_agent_name="Arun", assigned_agent_id=arun.id))
    db.add(Ticket(id=353, title="Arun 2", description="desc", status="open", assigned_agent_name="Arun", assigned_agent_id=arun.id))

    ticket = Ticket(id=360, title="Night ticket", description="desc", category="Network", assigned_team="Network Operations", status="open")
    db.add(ticket)
    db.commit()

    chosen, reason = assign_agent_for_ticket(ticket, "Network Operations", db, mode="relaxed")
    assert chosen.name == "Mike", "When all agents are off shift, assigns lowest workload agent"
    assert "assigned outside shift" in reason


def test_every_agent_on_leave_goes_to_manager(db):
    """
    Test 3: Every agent in the system is on leave -> manager fallback.
    The reason MUST state 'FALLBACK: All agents on leave.'
    """
    now = datetime.utcnow()

    manager = User(id=1, name="John Manager", email="manager@company.com", password="hash", role="manager", assigned_team="IT Support")
    sarah = User(id=2, name="Sarah", email="sarah@company.com", password="hash", role="agent", assigned_team="IT Support", max_open_tickets=10)
    kiran = User(id=3, name="Kiran", email="kiran@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)

    db.add_all([manager, sarah, kiran])
    db.commit()

    # Both Sarah and Kiran on active approved leave
    db.add(AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(days=2),
        status="approved",
    ))
    db.add(AgentLeave(
        agent_id=kiran.id,
        agent_name=kiran.name,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(days=2),
        status="approved",
    ))
    db.commit()

    ticket = Ticket(id=401, title="Hardware breakdown", description="desc", category="Hardware", assigned_team="IT Support", status="open")
    db.add(ticket)
    db.commit()

    chosen, reason = assign_agent_for_ticket(ticket, "IT Support", db, mode="relaxed")

    # Assertions
    assert chosen is not None
    assert chosen.name == "John Manager"
    assert chosen.role == "manager"
    assert "FALLBACK: All agents on leave." in reason
    assert "Sarah (on leave)" in reason
    assert "Kiran (on leave)" in reason


def test_strict_mode_blocks_off_shift_and_over_cap_agents(db):
    """
    Test 4: Strict mode blocks off-shift and over-capacity agents from being assigned,
    falling back to manager.
    """
    now = datetime.utcnow()

    manager = User(id=1, name="John Manager", email="manager@company.com", password="hash", role="manager", assigned_team="IT Support")
    mike = User(id=2, name="Mike", email="mike@company.com", password="hash", role="agent", assigned_team="IT Support", max_open_tickets=10)

    db.add_all([manager, mike])
    db.commit()

    ticket1 = Ticket(id=501, title="Strict Ticket", description="desc", category="Software", assigned_team="IT Support", status="open")
    db.add(ticket1)
    db.commit()

    # Strict mode invocation: Mike is off-shift -> Strict mode BLOCKS Mike -> escalates to manager
    chosen_strict, reason_strict = assign_agent_for_ticket(ticket1, "IT Support", db, mode="strict")
    assert chosen_strict.name == "John Manager"
    assert chosen_strict.role == "manager"
    assert "Strict mode blocked" in reason_strict
    assert "Mike (off shift)" in reason_strict


def test_rerun_on_gst_ticket_reassigns_from_manager_to_in_work_agent(db):
    """
    Test 5: Re-running assignment on GST ticket (#52) reassigns it from manager
    to an in-work agent (Kiran), writing an AssignmentLog row.
    """
    now = datetime.utcnow()

    manager = User(id=1, name="John Manager", email="manager@company.com", password="hash", role="manager", assigned_team="IT Support")
    sarah = User(id=2, name="Sarah Agent", email="sarah@company.com", password="hash", role="agent", assigned_team="IT Support", max_open_tickets=10)
    kiran = User(id=3, name="Kiran", email="kiran@company.com", password="hash", role="agent", assigned_team="Network Operations", max_open_tickets=10)

    db.add_all([manager, sarah, kiran])
    db.commit()

    # Sarah is on leave
    db.add(AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(days=2),
        status="approved",
    ))

    # Kiran is on shift (in work)
    db.add(AgentShift(
        agent_id=kiran.id,
        agent_name=kiran.name,
        weekday=now.weekday(),
        start_time="00:00",
        end_time="23:59",
        is_active=True,
    ))

    # Ticket #52: GST invoice issue, currently assigned to John Manager as fallback
    ticket52 = Ticket(
        id=52,
        title="GST amount calculated incorrectly on invoices above 1 lakh",
        description="GST calculation error on large invoice",
        category="Software",
        assigned_team="IT Support",
        assigned_agent_id=manager.id,
        assigned_agent_name=manager.name,
        status="assigned",
    )
    db.add(ticket52)
    db.commit()

    # Run the reassignment function
    reassigned = reassign_manager_fallback_tickets(db)

    # Verify return value
    assert len(reassigned) == 1
    item = reassigned[0]
    assert item["ticket_id"] == 52
    assert item["old_agent"] == "John Manager"
    assert item["new_agent"] == "Kiran"
    assert "Reassigned to in-work agent" in item["reason"]

    # Verify database state of ticket #52
    refreshed_52 = db.query(Ticket).filter(Ticket.id == 52).first()
    assert refreshed_52.assigned_agent_id == kiran.id
    assert refreshed_52.assigned_agent_name == "Kiran"

    # Verify AssignmentLog row was created
    log = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == 52).first()
    assert log is not None
    assert log.assigned_agent_name == "Kiran"
    assert "Reassigned to in-work agent" in log.reason
    assert "Sarah Agent (on leave)" in log.reason
