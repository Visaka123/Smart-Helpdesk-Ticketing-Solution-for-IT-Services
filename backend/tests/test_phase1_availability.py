"""
tests/test_phase1_availability.py

Tests for Phase 1: Bug Fixes
- On leave only if status=approved AND start <= now <= end (timezone-aware).
- Pending, cancelled, and future leave never block.
- Half-day blocks only its own window.
- Exclude manager-role users from assignment pool and availability panel.
- Manager-only access to /availability/available-now (403 for employee/agent).
"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database.database import Base
from app.models.user import User
from app.models.availability import AgentLeave, AgentShift
from app.availability.service import (
    _is_on_leave, get_available_agents_now, _is_on_shift, _is_below_cap, _agent_local_now
)
from app.availability.routes import who_is_available

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    agent1 = User(
        id=1,
        name="Sarah Agent",
        email="sarah@helpdesk.com",
        password="hash",
        role="agent",
        assigned_team="IT Support",
        department="IT Operations",
        timezone="Asia/Kolkata",
    )
    agent2 = User(
        id=2,
        name="Mike Network Agent",
        email="mike@helpdesk.com",
        password="hash",
        role="agent",
        assigned_team="Network Team",
        department="Network Operations",
        timezone="Asia/Kolkata",
    )
    manager = User(
        id=3,
        name="John Manager",
        email="manager@helpdesk.com",
        password="hash",
        role="manager",
        assigned_team="IT Support",
        department="Management",
        timezone="Asia/Kolkata",
    )
    session.add_all([agent1, agent2, manager])
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_pending_leave_never_blocks(db):
    """Pending leave covering right now must never block an agent."""
    now = datetime.utcnow()
    agent = db.query(User).filter_by(name="Sarah Agent").first()

    leave = AgentLeave(
        agent_id=agent.id,
        agent_name=agent.name,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(hours=4),
        leave_type="annual",
        status="pending",  # Pending!
    )
    db.add(leave)
    db.commit()

    assert _is_on_leave(agent, now, db) is False


def test_future_approved_leave_never_blocks(db):
    """Approved leave starting in the future (e.g. tomorrow or Nov 19) must never block now."""
    now = datetime.utcnow()
    agent = db.query(User).filter_by(name="Mike Network Agent").first()

    leave = AgentLeave(
        agent_id=agent.id,
        agent_name=agent.name,
        start_datetime=now + timedelta(days=3),
        end_datetime=now + timedelta(days=6),
        leave_type="annual",
        status="approved",
    )
    db.add(leave)
    db.commit()

    assert _is_on_leave(agent, now, db) is False


def test_cancelled_leave_never_blocks(db):
    """Cancelled leave covering right now must never block."""
    now = datetime.utcnow()
    agent = db.query(User).filter_by(name="Sarah Agent").first()

    leave = AgentLeave(
        agent_id=agent.id,
        agent_name=agent.name,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(hours=4),
        leave_type="annual",
        status="cancelled",
    )
    db.add(leave)
    db.commit()

    assert _is_on_leave(agent, now, db) is False


def test_active_approved_leave_blocks(db):
    """Approved leave currently in progress must block."""
    now = datetime.utcnow()
    agent = db.query(User).filter_by(name="Sarah Agent").first()

    leave = AgentLeave(
        agent_id=agent.id,
        agent_name=agent.name,
        start_datetime=now - timedelta(hours=2),
        end_datetime=now + timedelta(hours=4),
        leave_type="annual",
        status="approved",
    )
    db.add(leave)
    db.commit()

    assert _is_on_leave(agent, now, db) is True


def test_half_day_blocks_only_its_window(db):
    """Half day leaves (AM vs PM) must block only during their respective hours."""
    agent = db.query(User).filter_by(name="Sarah Agent").first()

    # Base date today in agent timezone
    tz = ZoneInfo("Asia/Kolkata")
    today_morning = datetime.now(tz).replace(hour=10, minute=0, second=0, microsecond=0)
    today_afternoon = datetime.now(tz).replace(hour=15, minute=0, second=0, microsecond=0)

    # Convert to UTC
    morning_utc = today_morning.astimezone(ZoneInfo("UTC"))
    afternoon_utc = today_afternoon.astimezone(ZoneInfo("UTC"))

    # Add half_day_am leave
    am_leave = AgentLeave(
        agent_id=agent.id,
        agent_name=agent.name,
        start_datetime=today_morning.replace(hour=0, minute=0),
        end_datetime=today_morning.replace(hour=23, minute=59),
        leave_type="half_day_am",
        status="approved",
    )
    db.add(am_leave)
    db.commit()

    # Morning (10:00 IST): should block
    assert _is_on_leave(agent, morning_utc, db) is True

    # Afternoon (15:00 IST): should NOT block
    assert _is_on_leave(agent, afternoon_utc, db) is False


def test_manager_excluded_from_availability_panel(db):
    """Managers must never appear in the availability panel."""
    agents = get_available_agents_now(None, db)
    names = [a["name"] for a in agents]

    assert "Sarah Agent" in names
    assert "Mike Network Agent" in names
    assert "John Manager" not in names


def test_available_now_endpoint_rbac(db):
    """Only managers/admins can query /availability/available-now. Employees and agents receive 403."""
    # Manager request
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager"}
    res = who_is_available(req_mgr)
    assert len(res) == 2  # Sarah and Mike

    # Agent request -> 403
    req_agent = MagicMock()
    req_agent.headers = {"X-User-Role": "agent"}
    with pytest.raises(HTTPException) as exc_info:
        who_is_available(req_agent)
    assert exc_info.value.status_code == 403

    # Employee request -> 403
    req_emp = MagicMock()
    req_emp.headers = {"X-User-Role": "employee"}
    with pytest.raises(HTTPException) as exc_info_emp:
        who_is_available(req_emp)
    assert exc_info_emp.value.status_code == 403


def test_cap_boundary_allows_9_blocks_10(db):
    """Cap boundary: with cap=10, 9 open tickets allows new assignment, 10 blocks."""
    agent = db.query(User).filter_by(name="Sarah Agent").first()
    agent.max_open_tickets = 10
    db.commit()

    assert _is_below_cap(agent, open_count=9) is True
    assert _is_below_cap(agent, open_count=10) is False


def test_overnight_shift(db):
    """Overnight shifts (e.g. 22:00 to 06:00) correctly span across midnight."""
    agent = db.query(User).filter_by(name="Mike Network Agent").first()
    agent.timezone = "UTC"
    db.commit()

    # Add overnight shift on Monday (weekday=0) from 22:00 to 06:00
    db.add(AgentShift(
        agent_id=agent.id,
        agent_name=agent.name,
        weekday=0,
        start_time="22:00",
        end_time="06:00",
        is_active=True,
    ))
    db.commit()

    # Monday 23:00 UTC -> in shift
    mon_night = datetime(2026, 11, 16, 23, 0, 0)
    assert _is_on_shift(agent, mon_night, db) is True

    # Tuesday 03:00 UTC -> in shift (wraps past midnight from Monday shift)
    tue_early = datetime(2026, 11, 17, 3, 0, 0)
    assert _is_on_shift(agent, tue_early, db) is True

    # Tuesday 12:00 UTC -> off shift
    tue_noon = datetime(2026, 11, 17, 12, 0, 0)
    assert _is_on_shift(agent, tue_noon, db) is False


def test_asia_kolkata_agent_on_utc_server(db):
    """Asia/Kolkata agent evaluated properly using UTC timestamps."""
    agent = db.query(User).filter_by(name="Sarah Agent").first()
    agent.timezone = "Asia/Kolkata"
    db.commit()

    # Shift 09:00 to 18:00 IST on Monday (weekday=0)
    db.add(AgentShift(
        agent_id=agent.id,
        agent_name=agent.name,
        weekday=0,
        start_time="09:00",
        end_time="18:00",
        is_active=True,
    ))
    db.commit()

    # 04:00 UTC on Monday is 09:30 IST -> in shift
    utc_in_shift = datetime(2026, 11, 16, 4, 0, 0)
    assert _is_on_shift(agent, utc_in_shift, db) is True

    # 14:00 UTC on Monday is 19:30 IST -> off shift
    utc_off_shift = datetime(2026, 11, 16, 14, 0, 0)
    assert _is_on_shift(agent, utc_off_shift, db) is False
