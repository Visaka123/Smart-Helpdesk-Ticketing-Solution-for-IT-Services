"""
tests/test_hr_leave_sync.py

Tests for external HR leave synchronization:
1. No duplicates on repeated sync (idempotency by external_id)
2. Cancel in source cancels locally
3. Pending leave does not block / is ignored
4. Bad records do not break the batch
5. Store only dates, never a leave reason
"""
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.user import User
from app.models.availability import AgentLeave
from app.availability.providers import LeaveProvider
from app.availability.sync import sync_leaves

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=engine)


class DummyLeaveProvider(LeaveProvider):
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records

    def set_records(self, records: List[Dict[str, Any]]):
        self.records = records

    def fetch_approved_leave(self) -> List[Dict[str, Any]]:
        return self.records


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    # Seed test agents
    agent1 = User(
        id=1,
        name="Sarah Agent",
        email="agent@helpdesk.com",
        password="hash",
        role="agent",
        assigned_team="IT Support",
        timezone="Asia/Kolkata",
    )
    agent2 = User(
        id=2,
        name="Mike Network Agent",
        email="mike.agent@helpdesk.com",
        password="hash",
        role="agent",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
    )
    session.add_all([agent1, agent2])
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_no_duplicates_on_repeated_sync(db):
    """Syncing the same external_id multiple times should upsert, creating no duplicates."""
    provider = DummyLeaveProvider([
        {
            "external_id": "HR-SYNC-101",
            "user_email": "agent@helpdesk.com",
            "start": "2026-11-20 09:00:00",
            "end": "2026-11-22 17:00:00",
            "half_day": False,
            "status": "approved",
            "reason": "Personal medical leave",  # Should be ignored!
        }
    ])

    # First sync
    res1 = sync_leaves(provider, db)
    assert res1["synced"] == 1
    assert db.query(AgentLeave).count() == 1

    leave = db.query(AgentLeave).filter_by(external_id="HR-SYNC-101").first()
    assert leave is not None
    assert leave.status == "approved"
    assert leave.source == "hr_sync"
    assert leave.notes is None  # Requirement: Store only dates, never a leave reason

    # Second sync with same external_id
    res2 = sync_leaves(provider, db)
    assert res2["synced"] == 1
    assert db.query(AgentLeave).count() == 1  # No duplicate row created


def test_cancel_in_source_cancels_locally(db):
    """When an approved HR leave is removed from the source, it should be marked cancelled locally."""
    provider = DummyLeaveProvider([
        {
            "external_id": "HR-SYNC-102",
            "user_email": "agent@helpdesk.com",
            "start": "2026-11-20 09:00:00",
            "end": "2026-11-22 17:00:00",
            "half_day": False,
            "status": "approved",
        }
    ])

    sync_leaves(provider, db)
    leave = db.query(AgentLeave).filter_by(external_id="HR-SYNC-102").first()
    assert leave.status == "approved"

    # Source no longer returns HR-SYNC-102 (e.g. employee cancelled it in HR)
    provider.set_records([])
    res2 = sync_leaves(provider, db)

    assert res2["cancelled"] == 1
    db.refresh(leave)
    assert leave.status == "cancelled"


def test_pending_leave_does_not_block_and_is_ignored(db):
    """Pending leave records from HR must be ignored and not created/approved locally."""
    provider = DummyLeaveProvider([
        {
            "external_id": "HR-SYNC-103",
            "user_email": "agent@helpdesk.com",
            "start": "2026-11-20 09:00:00",
            "end": "2026-11-22 17:00:00",
            "half_day": False,
            "status": "pending",  # Pending in HR
        },
        {
            "external_id": "HR-SYNC-104",
            "user_email": "mike.agent@helpdesk.com",
            "start": "2026-11-20 09:00:00",
            "end": "2026-11-22 17:00:00",
            "half_day": False,
            "status": "approved",
        }
    ])

    res = sync_leaves(provider, db)
    assert res["synced"] == 1

    # Pending record was not inserted
    pending_leave = db.query(AgentLeave).filter_by(external_id="HR-SYNC-103").first()
    assert pending_leave is None

    # Approved record was inserted
    approved_leave = db.query(AgentLeave).filter_by(external_id="HR-SYNC-104").first()
    assert approved_leave is not None
    assert approved_leave.status == "approved"


def test_bad_record_does_not_break_batch(db):
    """Malformed or invalid records must be skipped without crashing the entire batch."""
    provider = DummyLeaveProvider([
        {
            # Valid record 1
            "external_id": "HR-SYNC-GOOD-1",
            "user_email": "agent@helpdesk.com",
            "start": "2026-11-20 09:00:00",
            "end": "2026-11-22 17:00:00",
            "status": "approved",
        },
        {
            # Bad record: User email does not exist in helpdesk
            "external_id": "HR-SYNC-BAD-1",
            "user_email": "nonexistent@company.com",
            "start": "2026-11-20 09:00:00",
            "end": "2026-11-22 17:00:00",
            "status": "approved",
        },
        {
            # Bad record: Corrupted date string
            "external_id": "HR-SYNC-BAD-2",
            "user_email": "agent@helpdesk.com",
            "start": "not-a-valid-date",
            "end": "not-a-valid-date",
            "status": "approved",
        },
        {
            # Bad record: End date earlier than start date
            "external_id": "HR-SYNC-BAD-3",
            "user_email": "agent@helpdesk.com",
            "start": "2026-11-25 09:00:00",
            "end": "2026-11-20 17:00:00",
            "status": "approved",
        },
        {
            # Bad record: Missing external_id
            "user_email": "agent@helpdesk.com",
            "start": "2026-11-20 09:00:00",
            "end": "2026-11-22 17:00:00",
            "status": "approved",
        },
        {
            # Valid record 2
            "external_id": "HR-SYNC-GOOD-2",
            "user_email": "mike.agent@helpdesk.com",
            "start": "2026-11-21 09:00:00",
            "end": "2026-11-23 17:00:00",
            "status": "approved",
        },
    ])

    res = sync_leaves(provider, db)

    # 2 valid records synced, 4 bad records safely skipped
    assert res["synced"] == 2
    assert res["skipped"] == 4
    assert len(res["errors"]) >= 3

    assert db.query(AgentLeave).filter_by(external_id="HR-SYNC-GOOD-1").first() is not None
    assert db.query(AgentLeave).filter_by(external_id="HR-SYNC-GOOD-2").first() is not None
