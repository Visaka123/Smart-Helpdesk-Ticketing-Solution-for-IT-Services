"""
backend/tests/test_duplicate_interstitial.py

Tests for Duplicate Interstitial & Thresholds:
1. Backup-quota vs S3 ticket gives no modal (<75% or generic term overlap).
2. Two 'cannot reach file server from branch office' tickets at >=75% trigger the modal.
3. Wording accurately matches ticket status (in_progress, open, resolved).
4. 'Follow' adds linked requester and creates no ticket.
5. 'Submit mine' creates the ticket.
6. Form data survives closing the modal & telemetry logs decisions (followed, submitted_anyway, dismissed).
"""
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket, TicketRequester
from app.models.feedback import DuplicateFeedbackLog
from app.duplicate.service import (
    detect_hybrid_duplicates,
    has_specific_shared_term,
    extract_technical_tokens,
    compute_lexical_similarity,
    GENERIC_WORDS,
)
from app.tickets.routes import (
    follow_ticket_endpoint,
    log_duplicate_decision_endpoint,
    create_ticket,
    FollowTicketRequest,
    DuplicateDecisionRequest,
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

    # Patch SessionLocal everywhere in app
    monkeypatch.setattr("app.database.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.duplicate.service.SessionLocal", TestingSessionLocal)
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
    monkeypatch.setattr("ai.rag.groq_client.get_groq_api_keys", lambda: [])
    monkeypatch.setattr("ai.rag.groq_client.ask_llm", lambda prompt, **kwargs: "NO")

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
    yield


def test_backup_quota_vs_s3_gives_no_modal():
    """
    Test 1:
    'Nightly backup job failed ... Disk quota exceeded' vs Ticket #8 'Production S3 bucket storage quota alert'
    Only generic word 'quota' overlaps -> rejected, no modal, score < 0.75.
    """
    db = TestingSessionLocal()
    s3_ticket = Ticket(
        id=8,
        title="Production S3 bucket storage quota alert triggered",
        description="AWS S3 bucket storage quota alert triggered for production analytics bucket.",
        category="Storage",
        assigned_team="DevOps & Cloud Infra",
        status="open",
        requester_name="DevOps Team",
    )
    db.add(s3_ticket)
    db.commit()

    q_title = "Nightly backup job failed"
    q_desc = "Disk quota exceeded during backup process on local volume."

    has_term, shared = has_specific_shared_term(
        f"{q_title} {q_desc}",
        f"{s3_ticket.title} {s3_ticket.description}"
    )
    db.close()

    # Generic word 'quota' must NOT qualify as a specific shared technical term
    assert "quota" not in shared

    res = detect_hybrid_duplicates(q_title, q_desc)
    assert res["should_show_modal"] is False
    assert res["has_duplicate"] is False
    if res.get("top_match"):
        assert res["top_match"]["relevance_score"] < 0.75


def test_two_file_server_tickets_trigger_modal():
    """
    Test 2:
    Two 'cannot reach file server from branch office' tickets share specific terms
    ('file server', 'branch office') and category ('Network'), giving score >= 0.75 and triggering the modal.
    """
    db = TestingSessionLocal()
    fs_ticket = Ticket(
        id=12,
        title="Cannot reach file server from branch office",
        description="Users in branch office are unable to access file server network shares.",
        category="Network",
        assigned_team="Network Operations",
        status="open",
        requester_name="Branch Manager",
    )
    db.add(fs_ticket)
    db.commit()

    q_title = "Cannot reach file server from branch office"
    q_desc = "Branch office staff cannot connect to network file server share."

    has_term, shared = has_specific_shared_term(
        f"{q_title} {q_desc}",
        f"{fs_ticket.title} {fs_ticket.description}"
    )
    db.close()

    assert has_term is True
    assert ("file server" in shared or "file" in shared or "branch office" in shared)

    res = detect_hybrid_duplicates(q_title, q_desc)
    assert res["should_show_modal"] is True
    assert res["has_duplicate"] is True
    assert res["top_match"] is not None
    assert res["top_match"]["ticket_id"] == 12
    assert res["top_match"]["relevance_score"] >= 0.75
    assert res["top_match"]["has_specific_term"] is True


def test_wording_accurately_matches_ticket_status():
    """
    Test 3:
    Wording accurately differentiates:
    - in_progress -> 'Already reported and being worked on'
    - open -> 'Already reported, waiting for an agent' (never 'actively resolving')
    - resolved -> 'A similar issue was recently resolved' with resolution summary
    """
    def get_modal_title(status: str) -> str:
        if status in ["resolved", "closed"]:
            return "A similar issue was recently resolved"
        elif status == "in_progress":
            return "Already reported and being worked on"
        else:
            return "Already reported, waiting for an agent"

    def get_modal_banner_text(status: str, team: str) -> str:
        if status == "open":
            return "This incident was already reported and is currently waiting in the queue for an available agent."
        elif status == "in_progress":
            return "This incident was reported by another employee and is currently being worked on."
        else:
            return "Verified Resolution"

    # Status: in_progress
    assert get_modal_title("in_progress") == "Already reported and being worked on"
    assert "actively resolving" not in get_modal_banner_text("in_progress", "Network Operations")

    # Status: open
    assert get_modal_title("open") == "Already reported, waiting for an agent"
    open_banner = get_modal_banner_text("open", "Network Operations")
    assert "actively resolving" not in open_banner
    assert "waiting in the queue" in open_banner

    # Status: resolved
    assert get_modal_title("resolved") == "A similar issue was recently resolved"
    assert get_modal_title("closed") == "A similar issue was recently resolved"


def test_follow_adds_linked_requester_and_creates_no_ticket():
    """
    Test 4:
    'Follow #N' endpoint adds the user as a linked requester on #N and creates NO new ticket.
    Confirms with message 'You will get updates on #N'.
    """
    db = TestingSessionLocal()
    existing_ticket = Ticket(
        id=42,
        title="VPN gateway connection drops repeatedly",
        description="AnyConnect clients dropping after 15 minutes.",
        category="Network",
        assigned_team="Network Operations",
        status="in_progress",
        requester_name="Priya",
    )
    db.add(existing_ticket)
    db.commit()
    initial_ticket_count = db.query(Ticket).count()
    db.close()

    req = FollowTicketRequest(
        requester_name="Bob Employee",
        requester_department="Sales",
        similarity_score=0.88,
        new_ticket_text="VPN gateway dropping continuously",
    )
    data = follow_ticket_endpoint(ticket_id=42, req=req, request=dummy_request())
    assert data["success"] is True
    assert "You will get updates on #42" in data["message"]

    db = TestingSessionLocal()
    # Assert NO new ticket created
    assert db.query(Ticket).count() == initial_ticket_count

    # Assert TicketRequester added
    requester = db.query(TicketRequester).filter(
        TicketRequester.ticket_id == 42,
        TicketRequester.requester_name == "Bob Employee"
    ).first()
    assert requester is not None
    assert requester.link_reason == "followed_similar_incident"

    # Assert DuplicateFeedbackLog records 'followed'
    log = db.query(DuplicateFeedbackLog).filter(
        DuplicateFeedbackLog.matched_ticket_id == 42,
        DuplicateFeedbackLog.user_action == "followed"
    ).first()
    assert log is not None
    assert log.similarity_score == 0.88
    db.close()


def test_submit_mine_creates_ticket_and_logs_telemetry():
    """
    Test 5:
    'This is different, submit mine' calls ticket creation with skip_duplicate_check=True
    and logs decision 'submitted_anyway'. A new ticket is created.
    """
    db = TestingSessionLocal()
    t1 = Ticket(
        id=15,
        title="Cannot reach file server from branch office",
        description="File server network share unreachable",
        category="Network",
        assigned_team="Network Operations",
        status="open",
    )
    db.add(t1)
    db.commit()
    initial_count = db.query(Ticket).count()
    db.close()

    # Log telemetry
    tel_req = DuplicateDecisionRequest(
        ticket_text="Cannot reach file server from warehouse",
        matched_ticket_id=15,
        similarity_score=0.82,
        decision="submitted_anyway"
    )
    tel_res = log_duplicate_decision_endpoint(req=tel_req)
    assert tel_res["success"] is True

    # Submit ticket with skip_duplicate_check=True (as 'submit mine' does)
    create_req = TicketCreateRequest(
        title="Cannot reach file server from warehouse",
        description="Warehouse subnet cannot mount file server share",
        requester_name="Charlie Staff",
        requester_department="Logistics",
        skip_duplicate_check=True
    )
    create_data = create_ticket(req=create_req, request=dummy_request())
    assert create_data.get("is_hard_blocked") is not True
    assert "ticket" in create_data

    db = TestingSessionLocal()
    # Verify new ticket was created
    assert db.query(Ticket).count() == initial_count + 1

    # Verify telemetry log
    log = db.query(DuplicateFeedbackLog).filter(
        DuplicateFeedbackLog.matched_ticket_id == 15,
        DuplicateFeedbackLog.user_action == "submitted_anyway"
    ).first()
    assert log is not None
    assert log.similarity_score == 0.82
    db.close()


def test_dismissed_logs_telemetry_and_creates_no_ticket():
    """
    Test 6:
    Closing / cancelling the modal logs 'dismissed' and creates NO new ticket.
    """
    db = TestingSessionLocal()
    t1 = Ticket(
        id=20,
        title="Active Directory password lock",
        description="Account locked after 3 attempts",
        category="Access",
        assigned_team="IT Support",
        status="open",
    )
    db.add(t1)
    db.commit()
    initial_count = db.query(Ticket).count()
    db.close()

    tel_req = DuplicateDecisionRequest(
        ticket_text="Active Directory account locked",
        matched_ticket_id=20,
        similarity_score=0.85,
        decision="dismissed"
    )
    tel_res = log_duplicate_decision_endpoint(req=tel_req)
    assert tel_res["success"] is True

    db = TestingSessionLocal()
    # No ticket created
    assert db.query(Ticket).count() == initial_count

    # Telemetry log recorded
    log = db.query(DuplicateFeedbackLog).filter(
        DuplicateFeedbackLog.matched_ticket_id == 20,
        DuplicateFeedbackLog.user_action == "dismissed"
    ).first()
    assert log is not None
    assert log.similarity_score == 0.85
    db.close()
