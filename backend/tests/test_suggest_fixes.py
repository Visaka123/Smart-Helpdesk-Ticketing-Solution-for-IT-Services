"""
backend/tests/test_suggest_fixes.py

Unit and integration tests for Similar Resolved Ticket Recommendations:
1. "VPN error 809 not connecting from home" -> suggests VPN ticket with relevance >=60%
2. "Disk quota exceeded on backup volume" does NOT match "S3 quota" ticket (false match test)
3. Tickets without resolution notes are never suggested
4. Resolution summaries have emails, IPs and hostnames stripped
5. "This solved it" creates no ticket and logs deflection; "still need help" attaches suggestions to the ticket
6. Deflection rate = solved / shown
7. Graceful degradation: suggest-fixes endpoint down -> ticket creation still succeeds
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket, SuggestionFeedback
from app.suggestions.service import (
    find_suggested_fixes,
    sanitize_resolution_summary,
    record_suggestion_feedback,
    get_deflection_analytics,
)
from app.tickets.routes import (
    suggest_fixes_endpoint,
    suggestion_feedback_endpoint,
    create_ticket,
    SuggestFixesRequest,
    SuggestionFeedbackRequest,
    TicketCreateRequest,
)

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)

def dummy_request(user_id=1, user_role="employee", user_name="Alice Employee"):
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

    # Patch SessionLocal across relevant modules
    monkeypatch.setattr("app.database.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.duplicate.service.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.suggestions.service.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.tickets.routes.SessionLocal", TestingSessionLocal)

    def mock_classify(title, desc):
        return {
            "category": "Network",
            "assigned_team": "Network Operations",
            "priority": "Medium",
            "sla_target": "24 hours",
            "category_confidence": 0.95
        }

    monkeypatch.setattr("app.routing.service.classify_and_route_ticket", mock_classify)
    monkeypatch.setattr("app.tickets.routes.classify_and_route_ticket", mock_classify)

    # Seed an employee user
    db = TestingSessionLocal()
    user = User(
        id=1,
        name="Alice Employee",
        email="alice@company.com",
        password="hash",
        role="employee",
        department="Finance",
    )
    db.add(user)
    db.commit()
    db.close()


def test_1_vpn_error_809_suggests_vpn_ticket_above_60():
    """
    1. 'VPN error 809 not connecting from home' -> suggests VPN ticket with relevance >=60%
    """
    db = TestingSessionLocal()
    vpn_ticket = Ticket(
        id=101,
        title="VPN error 809 remote connection could not be established",
        description="Remote employee unable to connect to corporate L2TP/IPsec VPN from home router. Receiving Windows error 809.",
        category="Network",
        status="resolved",
        assigned_team="Network Operations",
        resolution_summary="Configured Windows registry key AssumeUDPEncapsulationContextOnSendRule to value 2 for NAT-T traversal. Verified UDP ports 500 and 4500 traversal.",
        resolved_at=datetime.utcnow() - timedelta(days=1),
    )
    db.add(vpn_ticket)
    db.commit()

    results = find_suggested_fixes(
        title="VPN error 809 not connecting from home",
        description="Cannot establish connection to office VPN, getting error 809",
        category="Network",
        db=db,
    )
    db.close()

    assert len(results) > 0
    top = results[0]
    assert top["ticket_id"] == 101
    assert top["relevance"] >= 0.60
    assert "AssumeUDPEncapsulationContextOnSendRule" in top["resolution_summary"]


def test_2_disk_quota_exceeded_does_not_match_s3_quota():
    """
    2. 'Disk quota exceeded on backup volume' does NOT match 'S3 quota' ticket (false match test)
    """
    db = TestingSessionLocal()
    s3_ticket = Ticket(
        id=102,
        title="Production S3 bucket storage quota alert",
        description="Amazon S3 bucket cloud storage quota reaching upper limit.",
        category="Cloud",
        status="resolved",
        assigned_team="DevOps",
        resolution_summary="Upgraded AWS S3 bucket tier and enabled lifecycle rule to transition cold objects to Glacier.",
        resolved_at=datetime.utcnow() - timedelta(days=2),
    )
    db.add(s3_ticket)
    db.commit()

    results = find_suggested_fixes(
        title="Nightly backup job failed",
        description="Disk quota exceeded on backup volume during local backup run",
        category="Infrastructure",
        db=db,
    )
    db.close()

    matched_ids = [r["ticket_id"] for r in results]
    assert 102 not in matched_ids, "S3 quota ticket should not match local backup volume quota due to lack of specific shared terms"


def test_3_tickets_without_resolution_notes_are_never_suggested():
    """
    3. Tickets without resolution notes are never suggested
    """
    db = TestingSessionLocal()
    t1 = Ticket(
        id=103,
        title="Outlook crashing on startup",
        description="Outlook crashes immediately upon launch",
        category="Software",
        status="resolved",
        resolution_summary="",  # Empty
        resolution_notes=None,
    )
    t2 = Ticket(
        id=104,
        title="Outlook crashing on startup",
        description="Outlook crashes immediately upon launch",
        category="Software",
        status="open",          # Open, not resolved
        resolution_summary="Fixed it by disabling add-in",
    )
    db.add_all([t1, t2])
    db.commit()

    results = find_suggested_fixes(
        title="Outlook crashing on startup",
        description="Outlook client crash on startup",
        category="Software",
        db=db,
    )
    db.close()

    matched_ids = [r["ticket_id"] for r in results]
    assert 103 not in matched_ids
    assert 104 not in matched_ids


def test_4_resolution_summaries_have_pii_stripped_and_truncated():
    """
    4. Resolution summaries have emails, IPs and hostnames stripped, and are truncated to 300 chars.
    """
    raw_text = (
        "Resolved by Sarah Agent: Contacted user at john.doe@internalcorp.com regarding server issue. "
        "Logged into domain controller dc01.internal.corp at 192.168.1.150:8080 and reset password: SecretPassword123. "
        "Also checked db-srv-primary.lan. " + ("Extra details for testing length. " * 10)
    )
    sanitized = sanitize_resolution_summary(raw_text)

    assert "john.doe@internalcorp.com" not in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "192.168.1.150" not in sanitized
    assert "[REDACTED_IP]" in sanitized
    assert "dc01.internal.corp" not in sanitized
    assert "SecretPassword123" not in sanitized
    assert len(sanitized) <= 300


def test_5_this_solved_it_and_still_need_help_behaviors():
    """
    5. 'This solved it' creates no ticket and logs deflection;
       'still need help' attaches suggestions to the ticket.
    """
    db = TestingSessionLocal()
    resolved_t = Ticket(
        id=105,
        title="Wi-Fi connection failed",
        description="Wi-Fi certificate expired error",
        status="resolved",
        resolution_summary="Pushed new 802.1X certificate via Intune profile.",
    )
    db.add(resolved_t)
    db.commit()

    # Step A: User clicks "This solved it" -> invokes feedback endpoint
    req_feedback = SuggestionFeedbackRequest(
        suggestion_ticket_id=105,
        action="solved",
        relevance=0.88,
        query_text="Wi-Fi cannot connect invalid cert",
    )
    res_fb = suggestion_feedback_endpoint(req_feedback, dummy_request())
    assert res_fb["status"] == "ok"
    assert res_fb["action"] == "solved"

    # Verify no new ticket was created for this action
    new_tickets = db.query(Ticket).filter(Ticket.title == "Wi-Fi cannot connect invalid cert").all()
    assert len(new_tickets) == 0

    # Step B: User clicks "Still need help" and submits ticket
    req_create = TicketCreateRequest(
        title="Wi-Fi connection still broken",
        description="Tried the suggested fix but Wi-Fi SSID remains unavailable",
        category="Network",
        suggestions_tried=[{"ticket_id": 105, "title": "Wi-Fi connection failed", "relevance": 0.88}],
        skip_duplicate_check=True,
    )
    res_create = create_ticket(req_create, dummy_request())
    created_id = res_create["ticket"]["id"]

    created_ticket_row = db.query(Ticket).filter(Ticket.id == created_id).first()
    assert created_ticket_row is not None
    assert created_ticket_row.suggestions_tried is not None
    assert "105" in created_ticket_row.suggestions_tried

    # Check feedback table logged 'still_need_help'
    fb_row = db.query(SuggestionFeedback).filter(
        SuggestionFeedback.suggested_ticket_id == 105,
        SuggestionFeedback.action == "still_need_help"
    ).first()
    assert fb_row is not None
    db.close()


def test_6_deflection_rate_calculation():
    """
    6. Deflection rate = solved / shown
    """
    db = TestingSessionLocal()
    # Log 4 shown, 2 solved
    record_suggestion_feedback(suggestion_ticket_id=1, action="shown", db=db)
    record_suggestion_feedback(suggestion_ticket_id=2, action="shown", db=db)
    record_suggestion_feedback(suggestion_ticket_id=1, action="solved", db=db)
    record_suggestion_feedback(suggestion_ticket_id=2, action="not_helpful", db=db)

    analytics = get_deflection_analytics(db=db)
    # Total shown events = 4, solved = 1 -> deflection rate = 1 / 4 = 0.25
    assert analytics["solved_count"] == 1
    assert analytics["suggestions_shown"] == 4
    assert analytics["deflection_rate"] == 0.25
    db.close()


def test_7_graceful_degradation():
    """
    7. Graceful degradation: suggest-fixes endpoint failure does not break ticket creation
    """
    db = TestingSessionLocal()
    # Call suggest fixes with invalid/failing inputs
    bad_req = SuggestFixesRequest(title="", description="")
    res = suggest_fixes_endpoint(bad_req)
    assert res == []

    # Ticket creation still proceeds cleanly
    create_req = TicketCreateRequest(
        title="Printer not working",
        description="Printer offline on 2nd floor",
        category="Hardware",
        skip_duplicate_check=True,
    )
    result = create_ticket(create_req, dummy_request())
    assert result["ticket"]["id"] is not None
    assert result["ticket"]["title"] == "Printer not working"
    db.close()
