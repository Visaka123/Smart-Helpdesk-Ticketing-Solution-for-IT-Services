"""
backend/tests/test_agent_workspace_fixes.py

Tests for Agent Workspace Ticket Dialog Bug Fixes:
1. Status normalization and unknown status handling:
   - "OPEN", "Open", "new" normalizes to canonical "open" (label "Open").
   - Unknown status (e.g. "investigating") gracefully normalizes and provides fallback label instead of empty field.
2. Status change audit log:
   - Status change writes audit entry: "Status changed from Open to In Progress by <agent>".
3. Resolve action flow:
   - Resolving saves root cause and resolution summary, marking ticket as resolved.
4. Assigned engineer availability & reassignment:
   - On-leave agent assignment is rejected (HTTP 400).
   - Manager reassignment requires reason and logs to AssignmentLog.
5. Title cleanup:
   - Stray punctuation, quotes, dashes, colons and leading ticket numbers are stripped.
   - Database cleanup function cleans existing titles.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.availability import AgentLeave, AgentShift, AssignmentLog
from app.agent.routes import (
    change_status_endpoint,
    assign_engineer_endpoint,
    resolve_ticket,
    normalize_status,
    get_status_display,
    ChangeStatusRequest,
    AssignEngineerRequest,
    ResolveTicketRequest,
)
from app.tickets.service import clean_ticket_title, cleanup_existing_ticket_titles

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)


def dummy_request(user_id=1, user_role="agent", user_name="Sarah Agent"):
    req = MagicMock()
    req.headers = {
        "X-User-Id": str(user_id),
        "X-User-Role": user_role,
        "X-User-Name": user_name,
        "X-User-Email": f"{user_name.lower().replace(' ', '.')}@company.com",
    }
    return req


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr("app.agent.routes.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.availability.routes.SessionLocal", TestingSessionLocal)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_status_normalization_and_unknown_status():
    """Verify canonical mapping for legacy/cased values and unknown status fallback."""
    # Canonical mappings
    assert normalize_status("OPEN") == "open"
    assert normalize_status("Open") == "open"
    assert normalize_status("new") == "open"
    assert normalize_status("assigned") == "open"

    assert normalize_status("In Progress") == "in_progress"
    assert normalize_status("in-progress") == "in_progress"
    assert normalize_status("working") == "in_progress"

    assert normalize_status("on_hold") == "pending_user"
    assert normalize_status("waiting_for_user") == "pending_user"

    assert normalize_status("RESOLVED") == "resolved"
    assert normalize_status("closed") == "closed"
    assert normalize_status("cancelled") == "closed"

    # Display labels
    assert get_status_display("open") == "Open"
    assert get_status_display("OPEN") == "Open"
    assert get_status_display("in_progress") == "In Progress"
    assert get_status_display("pending_user") == "Pending User"
    assert get_status_display("resolved") == "Resolved"
    assert get_status_display("closed") == "Closed"

    # Unknown status retains identifier and renders capitalized label
    assert normalize_status("investigating") == "investigating"
    assert get_status_display("investigating") == "Investigating"
    assert get_status_display("vendor_review") == "Vendor Review"


def test_status_change_writes_audit_entry():
    """Verify status change calls update, persists canonical status, and writes exact audit entry."""
    db = TestingSessionLocal()
    sarah = User(
        name="Sarah Agent",
        email="sarah.agent@company.com",
        password="dummy",
        role="agent",
        assigned_team="Network Operations",
    )
    ticket = Ticket(
        title="Email sync failing on mobile device",
        description="Exchange account not pulling inbox updates.",
        category="Email Support",
        priority="Medium",
        status="open",
        requester_name="Bob User",
        requester_department="Sales",
        assigned_agent_name="Sarah Agent",
    )
    db.add_all([sarah, ticket])
    db.commit()
    t_id = ticket.id
    sarah_id = sarah.id
    db.close()

    req = dummy_request(user_id=sarah_id, user_role="agent", user_name="Sarah Agent")
    payload = ChangeStatusRequest(new_status="in_progress")
    res = change_status_endpoint(ticket_id=t_id, req=payload, request=req)

    assert "in_progress" in res["message"]

    db = TestingSessionLocal()
    updated = db.query(Ticket).filter(Ticket.id == t_id).first()
    assert updated.status == "in_progress"

    comment = db.query(TicketComment).filter(TicketComment.ticket_id == t_id).first()
    assert comment is not None
    assert "Status changed from Open to In Progress by Sarah Agent." in comment.content
    assert comment.author_name == "Sarah Agent"
    assert not comment.is_internal
    db.close()


def test_resolved_action_flow():
    """Verify resolve endpoint requires root cause & resolution summary and marks ticket resolved."""
    db = TestingSessionLocal()
    ticket = Ticket(
        title="VPN connection drops intermittently",
        description="User experiencing dropped tunnels during meetings.",
        status="in_progress",
        requester_name="Carol Employee",
        requester_department="Marketing",
        assigned_agent_name="Sarah Agent",
    )
    db.add(ticket)
    db.commit()
    t_id = ticket.id
    db.close()

    req = dummy_request(user_id=10, user_role="agent", user_name="Sarah Agent")
    res_payload = ResolveTicketRequest(
        resolution_summary="Reconfigured MTU packet sizing to 1350 and reinstalled AnyConnect client.",
        resolution_detail="Changed local adapter MTU from 1500 to 1350 to prevent ISP fragmentation.",
        root_cause="Network Degradation",
    )
    res = resolve_ticket(ticket_id=t_id, req=res_payload, request=req)

    assert "resolved" in res["message"]

    db = TestingSessionLocal()
    resolved_ticket = db.query(Ticket).filter(Ticket.id == t_id).first()
    assert resolved_ticket.status == "resolved"
    assert resolved_ticket.root_cause == "Network Degradation"
    assert "MTU packet sizing" in resolved_ticket.resolution_summary
    assert resolved_ticket.resolved_at is not None
    db.close()


def test_on_leave_agent_disabled_and_reassignment_history():
    """Verify on-leave agents are blocked from assignment, and manager reassignment logs reason."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    # Agent 1: Sarah Agent (on active approved leave)
    sarah = User(
        name="Sarah Agent",
        email="sarah@company.com",
        password="dummy",
        role="agent",
        assigned_team="Network Operations",
    )
    # Agent 2: Ravi Kumar (active, on shift)
    ravi = User(
        name="Ravi Kumar",
        email="ravi@company.com",
        password="dummy",
        role="agent",
        assigned_team="Network Operations",
    )
    # Manager: John Manager
    manager = User(
        name="John Manager",
        email="john@company.com",
        password="dummy",
        role="manager",
        assigned_team="Network Operations",
    )
    db.add_all([sarah, ravi, manager])
    db.commit()

    # Create approved leave for Sarah covering right now
    leave = AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=now - timedelta(days=1),
        end_datetime=now + timedelta(days=2),
        leave_type="annual",
        status="approved",
    )
    db.add(leave)

    ticket = Ticket(
        title="Core router BGP session flap",
        description="BGP neighbor reset detected on edge peer.",
        status="open",
        assigned_team="Network Operations",
        assigned_agent_name="Sarah Agent",
        assigned_agent_id=sarah.id,
    )
    db.add(ticket)
    db.commit()
    t_id = ticket.id
    db.close()

    manager_req = dummy_request(user_id=manager.id, user_role="manager", user_name="John Manager")

    # 1. Attempting to assign on-leave Sarah must raise HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        assign_engineer_endpoint(
            ticket_id=t_id,
            req=AssignEngineerRequest(agent_name="Sarah Agent", reason="Reassign test"),
            request=manager_req,
        )
    assert exc_info.value.status_code == 400
    assert "currently on leave" in exc_info.value.detail

    # 2. Assigning active Ravi with reason succeeds and creates AssignmentLog entry
    reassign_reason = "Specialized expertise with BGP routing protocols"
    res = assign_engineer_endpoint(
        ticket_id=t_id,
        req=AssignEngineerRequest(agent_name="Ravi Kumar", reason=reassign_reason),
        request=manager_req,
    )
    assert "Ravi Kumar" in res["message"]

    db = TestingSessionLocal()
    updated_ticket = db.query(Ticket).filter(Ticket.id == t_id).first()
    assert updated_ticket.assigned_agent_name == "Ravi Kumar"
    assert updated_ticket.assigned_agent_id == ravi.id

    # Check AssignmentLog
    log = db.query(AssignmentLog).filter(AssignmentLog.ticket_id == t_id).first()
    assert log is not None
    assert log.assigned_agent_name == "Ravi Kumar"
    assert reassign_reason in log.reason
    assert log.override_by == "John Manager"
    db.close()


def test_title_cleanup():
    """Verify title cleanup handles leading ticket prefixes, colons, dashes, and quotes."""
    # Test individual string cleanups
    assert clean_ticket_title("#54: : CI pipeline failing at the Docker build step for the inventory service") == \
        "CI pipeline failing at the Docker build step for the inventory service"

    assert clean_ticket_title(": CI pipeline failing at step 3") == "CI pipeline failing at step 3"
    assert clean_ticket_title("- Excel crash on startup") == "Excel crash on startup"
    assert clean_ticket_title('"VPN connection drops"') == "VPN connection drops"
    assert clean_ticket_title("'Printer offline'") == "Printer offline"
    assert clean_ticket_title("   #12 - : Network lag in Delhi office   ") == "Network lag in Delhi office"

    # Test database batch cleanup function
    db = TestingSessionLocal()
    t1 = Ticket(title="#54: : CI pipeline failing at the Docker build step", description="Build error")
    t2 = Ticket(title=": Database replica lag high", description="Replication error")
    t3 = Ticket(title="Clean Title Already", description="Normal title")
    db.add_all([t1, t2, t3])
    db.commit()

    cleaned_count = cleanup_existing_ticket_titles(db)
    assert cleaned_count == 2

    db.refresh(t1)
    db.refresh(t2)
    db.refresh(t3)
    assert t1.title == "CI pipeline failing at the Docker build step"
    assert t2.title == "Database replica lag high"
    assert t3.title == "Clean Title Already"
    db.close()
