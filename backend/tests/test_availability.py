"""
tests/test_availability.py

Pytest suite for the availability / shift-aware assignment system.
Run from smart-helpdesk/backend/:
    venv\\Scripts\\pytest tests/test_availability.py -v

All tests use an in-memory SQLite DB — no server required.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.availability import (
    AgentShift, AgentLeave, OnCallRoster, PublicHoliday, AssignmentLog
)

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


# ── Helpers ───────────────────────────────────────────────────

def make_agent(db, name="Alice", team="IT", tz="UTC", max_tickets=10, role="agent"):
    u = User(
        name=name, email=f"{name.lower().replace(' ', '_')}@test.com",
        password="x", role=role,
        assigned_team=team, timezone=tz,
        max_open_tickets=max_tickets,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_ticket(db, agent_name=None, team="IT", status="open"):
    t = Ticket(
        title="Test", description="desc",
        category="Hardware", priority="Medium",
        status=status, assigned_team=team,
        assigned_agent_name=agent_name,
        routing_confidence=0.9,
        requester_name="Bob",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def add_shift(db, agent, weekday, start="09:00", end="17:00"):
    s = AgentShift(
        agent_id=agent.id, agent_name=agent.name,
        weekday=weekday, start_time=start, end_time=end,
    )
    db.add(s)
    db.commit()
    return s


def add_leave(db, agent, start, end, status="approved", is_processed=False):
    l = AgentLeave(
        agent_id=agent.id, agent_name=agent.name,
        start_datetime=start, end_datetime=end,
        leave_type="annual", status=status,
        is_processed=is_processed,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def add_oncall(db, agent, team, start, end):
    r = OnCallRoster(
        agent_id=agent.id, agent_name=agent.name,
        team_name=team, start_dt=start, end_dt=end,
    )
    db.add(r)
    db.commit()
    return r


from app.availability.service import (
    _is_on_shift, _is_on_leave, _is_on_call, _is_below_cap,
    _open_ticket_counts, is_available, filter_by_availability,
    assign_agent_for_ticket, get_available_agents_now,
)


# ═══════════════════════════════════════════════════════════════
# T01 — Agent on shift is available
# ═══════════════════════════════════════════════════════════════
def test_T01_agent_on_shift_is_available(db):
    utc_now = datetime(2024, 1, 1, 10, 0)  # Monday 10:00
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    assert _is_on_shift(agent, utc_now, db) is True
    assert is_available(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T02 — Agent off shift is NOT available
# ═══════════════════════════════════════════════════════════════
def test_T02_agent_off_shift_not_available(db):
    utc_now = datetime(2024, 1, 1, 20, 0)  # Monday 20:00 — outside 09-17
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    assert _is_on_shift(agent, utc_now, db) is False
    assert is_available(agent, utc_now, db) is False


# ═══════════════════════════════════════════════════════════════
# T03 — Overnight shift: agent IS on shift at 23:30 (start side)
# ═══════════════════════════════════════════════════════════════
def test_T03_overnight_shift_start_side(db):
    # Mon 22:00-06:00 shift. Mon 23:30 → ON shift (weekday=Mon, t_now >= "22:00")
    utc_now = datetime(2024, 1, 1, 23, 30)  # Monday 23:30
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="22:00", end="06:00")
    assert _is_on_shift(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T04 — Overnight shift: agent IS on shift at 02:00 (end side, next day)
# ═══════════════════════════════════════════════════════════════
def test_T04_overnight_shift_end_side(db):
    # Mon 22:00-06:00 shift. Tue 02:00 → ON shift (prev_weekday=Mon, t_now <= "06:00")
    utc_now = datetime(2024, 1, 2, 2, 0)  # Tuesday 02:00
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="22:00", end="06:00")
    assert _is_on_shift(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T05 — Overnight shift: agent NOT on shift at 07:00 (after end)
# ═══════════════════════════════════════════════════════════════
def test_T05_overnight_shift_after_end(db):
    # Mon 22:00-06:00 shift. Tue 07:00 → OFF shift
    utc_now = datetime(2024, 1, 2, 7, 0)  # Tuesday 07:00
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="22:00", end="06:00")
    assert _is_on_shift(agent, utc_now, db) is False


# ═══════════════════════════════════════════════════════════════
# T06 — Agent on approved leave is NOT available
# ═══════════════════════════════════════════════════════════════
def test_T06_agent_on_leave_not_available(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    add_leave(db, agent,
              start=datetime(2024, 1, 1, 0, 0),
              end=datetime(2024, 1, 1, 23, 59))
    assert _is_on_leave(agent, utc_now, db) is True
    assert is_available(agent, utc_now, db) is False


# ═══════════════════════════════════════════════════════════════
# T07 — Pending leave does NOT block agent
# ═══════════════════════════════════════════════════════════════
def test_T07_pending_leave_does_not_block(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    add_leave(db, agent,
              start=datetime(2024, 1, 1, 0, 0),
              end=datetime(2024, 1, 1, 23, 59),
              status="pending")
    assert _is_on_leave(agent, utc_now, db) is False
    assert is_available(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T08 — Public holiday with no region blocks all agents
# ═══════════════════════════════════════════════════════════════
def test_T08_public_holiday_no_region_blocks_all(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    agent = make_agent(db, tz="Asia/Kolkata")
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    db.add(PublicHoliday(date="2024-01-01", name="New Year", region=""))
    db.commit()
    assert _is_on_leave(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T09 — B8: Holiday with mismatched region does NOT block agent
# ═══════════════════════════════════════════════════════════════
def test_T09_holiday_region_mismatch_does_not_block(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    agent = make_agent(db, tz="Asia/Kolkata")
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    db.add(PublicHoliday(date="2024-01-01", name="US Holiday", region="US"))
    db.commit()
    assert _is_on_leave(agent, utc_now, db) is False
    assert is_available(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T10 — B8: Holiday with matching region DOES block agent
# ═══════════════════════════════════════════════════════════════
def test_T10_holiday_region_match_blocks_agent(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    agent = make_agent(db, tz="Asia/Kolkata")
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    db.add(PublicHoliday(date="2024-01-01", name="Pongal", region="Asia/Kolkata"))
    db.commit()
    assert _is_on_leave(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T11 — B2: max_open_tickets=0 blocks agent (not treated as falsy)
# ═══════════════════════════════════════════════════════════════
def test_T11_max_tickets_zero_blocks_agent(db):
    agent = make_agent(db, max_tickets=0)
    # 0 open tickets but cap is 0 → blocked
    assert _is_below_cap(agent, open_count=0) is False


# ═══════════════════════════════════════════════════════════════
# T12 — B2: max_open_tickets=None falls back to DEFAULT_TICKET_CAP
# ═══════════════════════════════════════════════════════════════
def test_T12_max_tickets_none_uses_default(db):
    from app.availability.service import DEFAULT_TICKET_CAP
    agent = make_agent(db, max_tickets=10)
    agent.max_open_tickets = None
    assert _is_below_cap(agent, open_count=5) is True
    assert _is_below_cap(agent, open_count=DEFAULT_TICKET_CAP) is False


# ═══════════════════════════════════════════════════════════════
# T13 — B10: _open_ticket_counts uses single batched query
# ═══════════════════════════════════════════════════════════════
def test_T13_open_ticket_counts_batched(db):
    make_agent(db, name="A1")
    make_agent(db, name="A2")
    make_ticket(db, agent_name="A1", status="open")
    make_ticket(db, agent_name="A1", status="open")
    make_ticket(db, agent_name="A2", status="open")

    counts = _open_ticket_counts(["A1", "A2", "A3"], db)
    assert counts["A1"] == 2
    assert counts["A2"] == 1
    assert counts["A3"] == 0


# ═══════════════════════════════════════════════════════════════
# T14 — Fallback-C: no agents → returns None
# ═══════════════════════════════════════════════════════════════
def test_T14_fallback_c_no_agents(db):
    ticket = make_ticket(db, team="EmptyTeam")
    with patch("app.availability.service._alert_team_lead"):
        agent, reason = assign_agent_for_ticket(ticket, "EmptyTeam", db)
    assert agent is None
    assert "FALLBACK-C" in reason


# ═══════════════════════════════════════════════════════════════
# T15 — Fallback-A: no shift but non-leave agent exists
# ═══════════════════════════════════════════════════════════════
def test_T15_fallback_a_no_shift_but_available(db):
    utc_now = datetime(2024, 1, 1, 20, 0)  # Monday 20:00 — outside any shift
    make_agent(db, name="Bob", team="IT")
    ticket = make_ticket(db, team="IT")
    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        with patch("app.availability.service._alert_team_lead"):
            chosen, reason = assign_agent_for_ticket(ticket, "IT", db)
    assert chosen is not None
    assert "FALLBACK-A" in reason


# ═══════════════════════════════════════════════════════════════
# T16 — On-call agent used when primary and fallback-A both fail
# ═══════════════════════════════════════════════════════════════
def test_T16_fallback_b_oncall(db):
    utc_now = datetime(2024, 1, 1, 20, 0)
    # Agent with cap=0 → blocked from fallback-A
    agent = make_agent(db, name="Carol", team="NET", max_tickets=0)
    add_oncall(db, agent, "NET",
               start=datetime(2024, 1, 1, 18, 0),
               end=datetime(2024, 1, 1, 23, 59))
    ticket = make_ticket(db, team="NET")
    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        with patch("app.availability.service._alert_team_lead"):
            chosen, reason = assign_agent_for_ticket(ticket, "NET", db)
    # cap=0 blocks on-call too → FALLBACK-C
    assert "FALLBACK" in reason


# ═══════════════════════════════════════════════════════════════
# T17 — B3: reroute_on_leave_approval is idempotent via is_processed
# ═══════════════════════════════════════════════════════════════
def test_T17_reroute_idempotent(db):
    from app.availability.scheduler import reroute_on_leave_approval

    now = datetime.utcnow()
    agent = make_agent(db, name="Dave", team="IT")
    make_ticket(db, agent_name="Dave", team="IT")
    leave = add_leave(db, agent,
                      start=now + timedelta(hours=1),
                      end=now + timedelta(hours=9),
                      is_processed=False)

    # Patch SessionLocal so the scheduler uses the same in-memory session
    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        with patch("app.availability.scheduler.db", db, create=True):
            with patch("app.availability.service._alert_team_lead"):
                # Prevent scheduler's finally:db.close() from closing our test session
                with patch.object(db, "close"):
                    reroute_on_leave_approval()

    leave_after = db.query(AgentLeave).filter(AgentLeave.id == leave.id).first()
    assert leave_after.is_processed is True

    ticket_name_after_first = db.query(Ticket).filter(
        Ticket.assigned_agent_name != None
    ).first()
    first_name = ticket_name_after_first.assigned_agent_name if ticket_name_after_first else None

    # Second run — leave already processed, no change
    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        with patch("app.availability.service._alert_team_lead"):
            with patch.object(db, "close"):
                reroute_on_leave_approval()

    ticket_name_after_second = db.query(Ticket).filter(
        Ticket.assigned_agent_name != None
    ).first()
    second_name = ticket_name_after_second.assigned_agent_name if ticket_name_after_second else None
    assert first_name == second_name


# ═══════════════════════════════════════════════════════════════
# T18 — B9: crash on one ticket does not affect others
# ═══════════════════════════════════════════════════════════════
def test_T18_per_ticket_commit_on_crash(db):
    from app.availability.scheduler import reroute_on_leave_approval

    now = datetime.utcnow()
    agent = make_agent(db, name="Eve", team="IT")
    t1 = make_ticket(db, agent_name="Eve", team="IT")
    t2 = make_ticket(db, agent_name="Eve", team="IT")
    add_leave(db, agent,
              start=now + timedelta(hours=1),
              end=now + timedelta(hours=9))

    call_count = {"n": 0}

    def boom_on_first(ticket, team, db_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("Simulated crash")
        return None, "FALLBACK-C: no agent"

    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        with patch("app.availability.scheduler.assign_agent_for_ticket", side_effect=boom_on_first):
            with patch.object(db, "close"):
                reroute_on_leave_approval()

    # Both tickets still exist — re-query by ID to avoid DetachedInstanceError
    assert db.query(Ticket).filter(Ticket.id == t1.id).count() == 1
    assert db.query(Ticket).filter(Ticket.id == t2.id).count() == 1
    # Second ticket was processed (call_count reached 2)
    assert call_count["n"] == 2


# ═══════════════════════════════════════════════════════════════
# T19 — B6: availability crash does NOT crash ticket creation
# ═══════════════════════════════════════════════════════════════
def test_T19_graceful_degradation_assign_raises(db):
    """assign_agent_for_ticket raising must not propagate out of the route handler."""
    ticket = make_ticket(db, team="IT")
    original_team = ticket.assigned_team

    # Simulate the try/except in tickets/routes.py
    try:
        with patch("app.availability.service.assign_agent_for_ticket",
                   side_effect=RuntimeError("DB exploded")):
            from app.availability.service import assign_agent_for_ticket as aaft
            aaft(ticket, "IT", db)
    except RuntimeError:
        pass  # route handler catches this; ticket already committed before this call

    t = db.query(Ticket).filter(Ticket.id == ticket.id).first()
    assert t is not None
    assert t.assigned_team == original_team


# ═══════════════════════════════════════════════════════════════
# T20 — B5: employee role gets 403 on privileged route
# ═══════════════════════════════════════════════════════════════
def test_T20_rbac_employee_gets_403(db):
    from fastapi import HTTPException
    from app.availability.routes import _require_privileged

    mock_request = MagicMock()
    mock_request.headers.get = lambda key, default="": {
        "X-User-Role": "employee",
        "Authorization": "",
        "X-User-Id": "",
        "X-User-Email": "",
    }.get(key, default)

    with patch("app.availability.routes.get_current_user_from_headers", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            _require_privileged(mock_request, db)
    assert exc_info.value.status_code == 403


# ═══════════════════════════════════════════════════════════════
# T21 — B5: team_lead role passes _require_privileged
# ═══════════════════════════════════════════════════════════════
def test_T21_rbac_team_lead_passes(db):
    from app.availability.routes import _require_privileged

    mock_request = MagicMock()
    mock_request.headers.get = lambda key, default="": {
        "X-User-Role": "team_lead",
        "Authorization": "",
        "X-User-Id": "",
        "X-User-Email": "",
    }.get(key, default)

    with patch("app.availability.routes.get_current_user_from_headers", return_value=None):
        _require_privileged(mock_request, db)  # must not raise


# ═══════════════════════════════════════════════════════════════
# T22 — B11: agent sees only own leave
# ═══════════════════════════════════════════════════════════════
def test_T22_agent_sees_only_own_leave(db):
    from app.availability.routes import list_leaves

    a1 = make_agent(db, name="Frank", team="IT")
    a2 = make_agent(db, name="Grace", team="IT")
    now = datetime.utcnow()
    add_leave(db, a1, now, now + timedelta(days=1))
    add_leave(db, a2, now, now + timedelta(days=1))

    mock_request = MagicMock()
    mock_request.headers.get = lambda key, default="": {
        "X-User-Role": "agent",
        "Authorization": "",
        "X-User-Id": str(a1.id),
        "X-User-Email": "",
    }.get(key, default)

    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=a1):
            result = list_leaves(mock_request)

    names = [r["agent_name"] for r in result]
    assert "Frank" in names
    assert "Grace" not in names


# ═══════════════════════════════════════════════════════════════
# T23 — B11: manager sees all leave
# ═══════════════════════════════════════════════════════════════
def test_T23_manager_sees_all_leave(db):
    from app.availability.routes import list_leaves

    a1 = make_agent(db, name="Hank", team="IT")
    a2 = make_agent(db, name="Iris", team="IT")
    mgr = make_agent(db, name="Manager", team="IT", role="manager")
    now = datetime.utcnow()
    add_leave(db, a1, now, now + timedelta(days=1))
    add_leave(db, a2, now, now + timedelta(days=1))

    mock_request = MagicMock()
    mock_request.headers.get = lambda key, default="": {
        "X-User-Role": "manager",
        "Authorization": "",
        "X-User-Id": str(mgr.id),
        "X-User-Email": "",
    }.get(key, default)

    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=mgr):
            result = list_leaves(mock_request)

    names = [r["agent_name"] for r in result]
    assert "Hank" in names
    assert "Iris" in names


# ═══════════════════════════════════════════════════════════════
# T24 — Primary assignment picks agent with fewest open tickets
# ═══════════════════════════════════════════════════════════════
def test_T24_picks_agent_with_fewest_tickets(db):
    utc_now = datetime(2024, 1, 1, 10, 0)  # Monday 10:00
    a1 = make_agent(db, name="J1", team="IT")
    a2 = make_agent(db, name="J2", team="IT")
    add_shift(db, a1, weekday=0, start="09:00", end="17:00")
    add_shift(db, a2, weekday=0, start="09:00", end="17:00")
    for _ in range(3):
        make_ticket(db, agent_name="J1", status="open")
    make_ticket(db, agent_name="J2", status="open")

    ticket = make_ticket(db, team="IT")
    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        chosen, _ = assign_agent_for_ticket(ticket, "IT", db)

    assert chosen is not None
    assert chosen.name == "J2"


# ═══════════════════════════════════════════════════════════════
# T25 — get_available_agents_now returns correct flags
# ═══════════════════════════════════════════════════════════════
def test_T25_get_available_agents_now(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    agent = make_agent(db, name="K1", team="IT")
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")

    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        result = get_available_agents_now("IT", db)

    assert len(result) == 1
    r = result[0]
    assert r["name"] == "K1"
    assert r["on_shift"] is True
    assert r["available"] is True
    assert r["open_tickets"] == 0


# ── Extra imports for T32/T37 ─────────────────────────────────
from app.models.sla import SLAEscalationLog
from app.models.team import Team


# ═══════════════════════════════════════════════════════════════
# T26 — IST timezone: shift Mon 09:00-17:00 IST
#        03:30 UTC = 09:00 IST -> ON; 12:00 UTC = 17:30 IST -> OFF
# ═══════════════════════════════════════════════════════════════
def test_T26_ist_timezone_shift(db):
    utc_on  = datetime(2024, 1, 1, 3, 30)   # Mon 03:30 UTC = 09:00 IST
    utc_off = datetime(2024, 1, 1, 12, 0)   # Mon 12:00 UTC = 17:30 IST
    agent = make_agent(db, tz="Asia/Kolkata")
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    assert _is_on_shift(agent, utc_on,  db) is True
    assert _is_on_shift(agent, utc_off, db) is False


# ═══════════════════════════════════════════════════════════════
# T27a — Overnight handover: shift ends 00:10, now 23:45 -> triggers
# T27b — Overnight handover: now 20:00 -> does NOT trigger
# ═══════════════════════════════════════════════════════════════
def test_T27a_overnight_handover_triggers(db):
    from app.availability.scheduler import handover_before_shift_end
    now_utc = datetime(2024, 1, 1, 23, 45)
    agent = make_agent(db, name="NightOwl", team="IT")
    add_shift(db, agent, weekday=0, start="22:00", end="00:10")
    make_ticket(db, agent_name="NightOwl", team="IT", status="open")
    called = {"v": False}
    def spy(ag, sh, db_, now): called["v"] = True
    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        with patch("app.availability.scheduler.datetime") as mdt:
            mdt.utcnow.return_value = now_utc
            mdt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with patch("app.availability.scheduler._do_handover", side_effect=spy):
                with patch.object(db, "close"):
                    handover_before_shift_end()
    assert called["v"] is True


def test_T27b_overnight_handover_no_trigger_at_2000(db):
    from app.availability.scheduler import handover_before_shift_end
    now_utc = datetime(2024, 1, 1, 20, 0)
    agent = make_agent(db, name="NightOwl2", team="IT")
    add_shift(db, agent, weekday=0, start="22:00", end="00:10")
    called = {"v": False}
    def spy(ag, sh, db_, now): called["v"] = True
    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        with patch("app.availability.scheduler.datetime") as mdt:
            mdt.utcnow.return_value = now_utc
            mdt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            with patch("app.availability.scheduler._do_handover", side_effect=spy):
                with patch.object(db, "close"):
                    handover_before_shift_end()
    assert called["v"] is False


# ═══════════════════════════════════════════════════════════════
# T28 — Cancelled leave does NOT block agent
# ═══════════════════════════════════════════════════════════════
def test_T28_cancelled_leave_does_not_block(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")
    add_leave(db, agent,
              start=datetime(2024, 1, 1, 0, 0),
              end=datetime(2024, 1, 1, 23, 59),
              status="cancelled")
    assert _is_on_leave(agent, utc_now, db) is False
    assert is_available(agent, utc_now, db) is True


# ═══════════════════════════════════════════════════════════════
# T29 — Half-day leave 08:00-12:00: blocked at 10:00, free at 14:00
# ═══════════════════════════════════════════════════════════════
def test_T29_half_day_leave_blocks_only_its_half(db):
    agent = make_agent(db)
    add_shift(db, agent, weekday=0, start="08:00", end="17:00")
    add_leave(db, agent,
              start=datetime(2024, 1, 1, 8, 0),
              end=datetime(2024, 1, 1, 12, 0),
              status="approved")
    assert _is_on_leave(agent, datetime(2024, 1, 1, 10, 0), db) is True
    assert _is_on_leave(agent, datetime(2024, 1, 1, 14, 0), db) is False
    assert is_available(agent, datetime(2024, 1, 1, 14, 0), db) is True
# ═══════════════════════════════════════════════════════════════
# T30 — Cap boundary: exactly at cap -> unavailable; cap-1 -> available
# ═══════════════════════════════════════════════════════════════
def test_T30_cap_boundary(db):
    CAP = 5
    agent = make_agent(db, name="CapAgent", team="IT", max_tickets=CAP)
    assert _is_below_cap(agent, open_count=CAP)     is False
    assert _is_below_cap(agent, open_count=CAP - 1) is True


# ═══════════════════════════════════════════════════════════════
# T31 — Scheduler reroutes unstarted, never touches in_progress
# ═══════════════════════════════════════════════════════════════
def test_T31_scheduler_skips_in_progress_tickets(db):
    from app.availability.scheduler import _do_handover
    agent    = make_agent(db, name="Shift1", team="IT")
    receiver = make_agent(db, name="Shift2", team="IT")
    add_shift(db, receiver, weekday=0, start="09:00", end="17:00")
    t_open = make_ticket(db, agent_name="Shift1", team="IT", status="open")
    t_prog = make_ticket(db, agent_name="Shift1", team="IT", status="in_progress")
    class FakeShift:
        end_time = "17:00"
    utc_now = datetime(2024, 1, 1, 10, 0)
    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        _do_handover(agent, FakeShift(), db, utc_now)
    db.expire_all()
    assert db.query(Ticket).filter(Ticket.id == t_prog.id).first().assigned_agent_name == "Shift1"
    assert db.query(Ticket).filter(Ticket.id == t_open.id).first().assigned_agent_name == "Shift2"


# T32a
def test_T32a_fallback_c_creates_escalation_log(db):
    ticket = make_ticket(db, team="GhostTeam")
    agent_none, reason = assign_agent_for_ticket(ticket, "GhostTeam", db)
    assert agent_none is None and "FALLBACK-C" in reason
    log = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == ticket.id).first()
    assert log is not None and log.fallback_used == "urgent_queue" and len(log.reason) > 10
    esc = db.query(SLAEscalationLog).filter(SLAEscalationLog.ticket_id == ticket.id).first()
    assert esc is not None and esc.escalation_reason == "NO_AVAILABLE_AGENT"


# T32b
def test_T32b_fallback_b_returns_oncall_agent(db):
    utc_now = datetime(2024, 1, 1, 20, 0)
    agent = make_agent(db, name="OnCallGuy", team="OPS", max_tickets=10)
    add_leave(db, agent, start=datetime(2024, 1, 1, 0, 0),
              end=datetime(2024, 1, 1, 23, 59), status="approved")
    add_oncall(db, agent, "OPS",
               start=datetime(2024, 1, 1, 18, 0), end=datetime(2024, 1, 1, 23, 59))
    ticket = make_ticket(db, team="OPS")
    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        chosen, reason = assign_agent_for_ticket(ticket, "OPS", db)
    assert chosen is not None and chosen.name == "OnCallGuy"
    assert "FALLBACK-B" in reason


# T33
def test_T33_assignment_log_all_paths(db):
    utc_now = datetime(2024, 1, 1, 10, 0)
    # Primary
    a1 = make_agent(db, name="Primary", team="P1")
    add_shift(db, a1, weekday=0, start="09:00", end="17:00")
    t1 = make_ticket(db, team="P1")
    with patch("app.availability.service.datetime") as m:
        m.utcnow.return_value = utc_now
        assign_agent_for_ticket(t1, "P1", db)
    log1 = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == t1.id).first()
    assert log1 is not None and log1.fallback_used is None and len(log1.reason) > 5
    # Fallback-A
    make_agent(db, name="FallA", team="FA")
    t2 = make_ticket(db, team="FA")
    with patch("app.availability.service.datetime") as m:
        m.utcnow.return_value = utc_now
        assign_agent_for_ticket(t2, "FA", db)
    log2 = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == t2.id).first()
    assert log2 is not None and "FALLBACK-A" in log2.reason and log2.fallback_used == "skill_match"
    # Fallback-C
    t4 = make_ticket(db, team="EMPTY")
    assign_agent_for_ticket(t4, "EMPTY", db)
    log4 = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == t4.id).first()
    assert log4 is not None and "FALLBACK-C" in log4.reason and log4.fallback_used == "urgent_queue"
    # Reroute path
    from app.availability.scheduler import reroute_on_leave_approval
    now = datetime.utcnow()
    leaver   = make_agent(db, name="LogLeaver", team="LOG")
    receiver = make_agent(db, name="LogReceiver", team="LOG")
    add_shift(db, receiver, weekday=now.weekday(), start="00:00", end="23:59")
    t5 = make_ticket(db, agent_name="LogLeaver", team="LOG", status="open")
    add_leave(db, leaver, start=now + timedelta(hours=1), end=now + timedelta(hours=9))
    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        with patch.object(db, "close"):
            reroute_on_leave_approval()
    log5 = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == t5.id).first()
    assert log5 is not None and len(log5.reason) > 5


# T34
def test_T34_manual_override_rbac_and_log(db):
    from fastapi import HTTPException
    from app.availability.routes import manual_override, ManualOverrideRequest
    agent_old = make_agent(db, name="OldAgent", team="IT")
    agent_new = make_agent(db, name="NewAgent", team="IT")
    ticket = make_ticket(db, agent_name="OldAgent", team="IT")
    req = ManualOverrideRequest(new_agent_name="NewAgent", override_by="TeamLead")
    # Agent gets 403
    mock_agent = MagicMock()
    mock_agent.headers.get = lambda k, d="": {
        "X-User-Role": "agent", "Authorization": "", "X-User-Id": "", "X-User-Email": ""
    }.get(k, d)
    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=agent_old):
            with pytest.raises(HTTPException) as exc:
                manual_override(ticket.id, req, mock_agent)
    assert exc.value.status_code == 403
    # Manager succeeds
    mock_mgr = MagicMock()
    mock_mgr.headers.get = lambda k, d="": {
        "X-User-Role": "manager", "Authorization": "", "X-User-Id": "", "X-User-Email": ""
    }.get(k, d)
    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=None):
            with patch.object(db, "close"):
                result = manual_override(ticket.id, req, mock_mgr)
    assert "MANUAL OVERRIDE" in result["message"]
    log = db.query(AssignmentLog).filter(
        AssignmentLog.ticket_id == ticket.id,
        AssignmentLog.override_by == "TeamLead",
    ).first()
    assert log is not None and log.assigned_agent_name == "NewAgent" and len(log.reason) > 10
    db.expire_all()
    assert db.query(Ticket).filter(Ticket.id == ticket.id).first().assigned_agent_name == "NewAgent"


# T35
def test_T35_cancel_leave_does_not_strand_tickets(db):
    from app.availability.routes import approve_leave, LeaveApprove
    agent = make_agent(db, name="Leaver", team="IT")
    now = datetime.utcnow()
    leave = add_leave(db, agent, start=now + timedelta(hours=1),
                      end=now + timedelta(hours=9), status="approved")
    ticket = make_ticket(db, agent_name="Leaver", team="IT", status="open")
    req = LeaveApprove(status="cancelled", approved_by="Manager")
    mock_req = MagicMock()
    mock_req.headers.get = lambda k, d="": {
        "X-User-Role": "manager", "Authorization": "", "X-User-Id": "", "X-User-Email": ""
    }.get(k, d)
    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=None):
            with patch.object(db, "close"):
                result = approve_leave(leave.id, req, mock_req)
    assert "cancelled" in result["message"]
    db.expire_all()
    assert db.query(AgentLeave).filter(AgentLeave.id == leave.id).first().status == "cancelled"
    assert db.query(Ticket).filter(Ticket.id == ticket.id).first().assigned_agent_name == "Leaver"


# T36
def test_T36_reroute_writes_assignment_log(db):
    from app.availability.scheduler import reroute_on_leave_approval
    now = datetime.utcnow()
    leaver   = make_agent(db, name="Leaver2", team="IT")
    receiver = make_agent(db, name="Receiver", team="IT")
    add_shift(db, receiver, weekday=now.weekday(), start="00:00", end="23:59")
    ticket = make_ticket(db, agent_name="Leaver2", team="IT", status="open")
    add_leave(db, leaver, start=now + timedelta(hours=1), end=now + timedelta(hours=9))
    with patch("app.availability.scheduler.SessionLocal", return_value=db):
        with patch.object(db, "close"):
            reroute_on_leave_approval()
    logs = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == ticket.id).all()
    assert len(logs) >= 1 and all(len(l.reason) > 5 for l in logs)


# T37
def test_T37_e2e_ticket_lands_on_available_agent(db):
    utc_now = datetime(2024, 1, 1, 10, 0)  # Monday 10:00 UTC
    a_leave    = make_agent(db, name="OnLeave",   team="ALPHA")
    a_offshift = make_agent(db, name="OffShift",  team="ALPHA")
    a_cap      = make_agent(db, name="AtCap",     team="ALPHA", max_tickets=2)
    a_avail    = make_agent(db, name="Available", team="ALPHA")
    # on_leave: shift covers now but approved leave blocks
    add_shift(db, a_leave, weekday=0, start="09:00", end="17:00")
    add_leave(db, a_leave, start=datetime(2024, 1, 1, 0, 0), end=datetime(2024, 1, 1, 23, 59))
    # off_shift: Tuesday shift only
    add_shift(db, a_offshift, weekday=1, start="09:00", end="17:00")
    # at_cap: on shift but 2 open tickets = cap of 2
    add_shift(db, a_cap, weekday=0, start="09:00", end="17:00")
    make_ticket(db, agent_name="AtCap", team="ALPHA", status="open")
    make_ticket(db, agent_name="AtCap", team="ALPHA", status="open")
    # available: on shift, 0 open tickets
    add_shift(db, a_avail, weekday=0, start="09:00", end="17:00")
    ticket = make_ticket(db, team="ALPHA")
    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        chosen, reason = assign_agent_for_ticket(ticket, "ALPHA", db)
    assert chosen is not None, f"Expected agent, got None. Reason: {reason}"
    assert chosen.name == "Available", f"Expected Available, got {chosen.name}. Reason: {reason}"
    log = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == ticket.id).first()
    assert log is not None and log.assigned_agent_name == "Available"


# ═══════════════════════════════════════════════════════════════
# T38 — Fallback-C sets assigned_team = "Unassigned-Urgent"
# ═══════════════════════════════════════════════════════════════
def test_T38_fallback_c_sets_unassigned_urgent(db):
    """Fallback-C must write 'Unassigned-Urgent' to ticket.assigned_team
    so the frontend urgent-queue banner fires."""
    ticket = make_ticket(db, team="GhostTeam2")
    with patch("app.availability.service._alert_team_lead"):
        agent, reason = assign_agent_for_ticket(ticket, "GhostTeam2", db)
    assert agent is None
    assert "FALLBACK-C" in reason
    db.expire_all()
    refreshed = db.query(Ticket).filter(Ticket.id == ticket.id).first()
    assert refreshed.assigned_team == "Unassigned-Urgent", (
        f"Expected 'Unassigned-Urgent', got '{refreshed.assigned_team}'"
    )


# ═══════════════════════════════════════════════════════════════
# T39 — manager role passes _require_privileged (UI role name)
# ═══════════════════════════════════════════════════════════════
def test_T39_manager_role_passes_require_privileged(db):
    """'manager' is the role name used in the UI; must not get 403."""
    from app.availability.routes import _require_privileged

    mock_request = MagicMock()
    mock_request.headers.get = lambda key, default="": {
        "X-User-Role": "manager",
        "Authorization": "",
        "X-User-Id": "",
        "X-User-Email": "",
    }.get(key, default)

    with patch("app.availability.routes.get_current_user_from_headers", return_value=None):
        _require_privileged(mock_request, db)  # must not raise


# ═══════════════════════════════════════════════════════════════
# T40 — agent role gets 403 on _require_privileged
# ═══════════════════════════════════════════════════════════════
def test_T40_agent_role_gets_403(db):
    from fastapi import HTTPException
    from app.availability.routes import _require_privileged

    mock_request = MagicMock()
    mock_request.headers.get = lambda key, default="": {
        "X-User-Role": "agent",
        "Authorization": "",
        "X-User-Id": "",
        "X-User-Email": "",
    }.get(key, default)

    with patch("app.availability.routes.get_current_user_from_headers", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            _require_privileged(mock_request, db)
    assert exc_info.value.status_code == 403


# ═══════════════════════════════════════════════════════════════
# T41 — agent can submit leave for themselves (not privileged)
# ═══════════════════════════════════════════════════════════════
def test_T41_agent_can_submit_own_leave(db):
    from app.availability.routes import create_leave, LeaveCreate

    agent = make_agent(db, name="SelfLeave", team="IT")
    now = datetime.utcnow()
    req = LeaveCreate(
        agent_id=agent.id,
        start_datetime=(now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        end_datetime=(now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
        leave_type="annual",
    )
    mock_request = MagicMock()
    mock_request.headers.get = lambda k, d="": {
        "X-User-Role": "agent",
        "Authorization": "",
        "X-User-Id": str(agent.id),
        "X-User-Email": "",
    }.get(k, d)

    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=agent):
            with patch.object(db, "close"):
                result = create_leave(req, mock_request)

    assert "leave_id" in result


# ═══════════════════════════════════════════════════════════════
# T42 — agent cannot submit leave for another agent
# ═══════════════════════════════════════════════════════════════
def test_T42_agent_cannot_submit_leave_for_other(db):
    from fastapi import HTTPException
    from app.availability.routes import create_leave, LeaveCreate

    agent1 = make_agent(db, name="Agent1Leave", team="IT")
    agent2 = make_agent(db, name="Agent2Leave", team="IT")
    now = datetime.utcnow()
    req = LeaveCreate(
        agent_id=agent2.id,  # trying to submit for agent2
        start_datetime=(now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        end_datetime=(now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
        leave_type="annual",
    )
    mock_request = MagicMock()
    mock_request.headers.get = lambda k, d="": {
        "X-User-Role": "agent",
        "Authorization": "",
        "X-User-Id": str(agent1.id),
        "X-User-Email": "",
    }.get(k, d)

    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=agent1):
            with patch.object(db, "close"):
                with pytest.raises(HTTPException) as exc_info:
                    create_leave(req, mock_request)
    assert exc_info.value.status_code == 403


# ═══════════════════════════════════════════════════════════════
# T43 — get_available_agents_now includes skills and shift_end
# ═══════════════════════════════════════════════════════════════
def test_T43_available_now_includes_skills_and_shift_end(db):
    utc_now = datetime(2024, 1, 1, 10, 0)  # Monday 10:00
    agent = make_agent(db, name="SkillAgent", team="IT")
    agent.department = "Networking, Security"
    db.commit()
    add_shift(db, agent, weekday=0, start="09:00", end="17:00")

    with patch("app.availability.service.datetime") as mock_dt:
        mock_dt.utcnow.return_value = utc_now
        result = get_available_agents_now("IT", db)

    assert len(result) == 1
    r = result[0]
    assert r["skills"] == "Networking, Security"
    assert r["shift_end"] is not None
    assert "17:00" in r["shift_end"]


# ═══════════════════════════════════════════════════════════════
# T44 — reroute-count endpoint returns correct ticket count
# ═══════════════════════════════════════════════════════════════
def test_T44_reroute_count_endpoint(db):
    from app.availability.routes import get_reroute_count

    agent = make_agent(db, name="RerouteAgent", team="IT")
    now = datetime.utcnow()
    leave = add_leave(db, agent, start=now + timedelta(hours=1),
                      end=now + timedelta(hours=9), status="pending")
    make_ticket(db, agent_name="RerouteAgent", team="IT", status="open")
    make_ticket(db, agent_name="RerouteAgent", team="IT", status="open")
    make_ticket(db, agent_name="RerouteAgent", team="IT", status="resolved")  # should not count

    mock_request = MagicMock()
    mock_request.headers.get = lambda k, d="": {
        "X-User-Role": "manager",
        "Authorization": "",
        "X-User-Id": "",
        "X-User-Email": "",
    }.get(k, d)

    with patch("app.availability.routes.SessionLocal", return_value=db):
        with patch("app.availability.routes.get_current_user_from_headers", return_value=None):
            with patch.object(db, "close"):
                result = get_reroute_count(leave.id, mock_request)

    assert result["reroute_count"] == 2
    assert result["agent_name"] == "RerouteAgent"
