"""
tests/test_phase4_demo_and_view_as.py

Tests for Phase 4 & Phase 4B:
- Seed twice gives the same row counts (idempotent)
- No shifts for managers; create_shift rejects manager role with 400
- All 7 days covered by shifts (09:00-17:00 for Meena, Kiran, Arun)
- Reset removes only demo rows; Sarah, Mike, John Manager untouched
- View-as returns 403 for non-managers and non-demo targets
- Ravi workspace is empty with leave banner
- Meena workspace shows only her tickets
"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.team import Team
from app.models.availability import AgentLeave, AgentShift, OnCallRoster, AssignmentLog
from app.availability.routes import demo_seed, DemoSeedRequest, create_shift, ShiftCreate, view_as_agent, ViewAsRequest
from app.availability.service import get_available_agents_now
from app.agent.routes import get_agent_queue, get_my_status, resolve_ticket, ResolveTicketRequest, add_ticket_comment, AddCommentRequest
from app.auth.hashing import verify_password

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    session.close = lambda: None

    # Real team
    team = Team(name="Network Team")
    session.add(team)

    # Real users (must remain untouched)
    sarah = User(
        id=3,
        name="Sarah Agent",
        email="agent@helpdesk.com",
        password="real_hash",
        role="agent",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        max_open_tickets=10,
        is_demo=False,
    )
    mike = User(
        id=4,
        name="Mike Network Agent",
        email="mike.agent@helpdesk.com",
        password="real_hash",
        role="agent",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        max_open_tickets=10,
        is_demo=False,
    )
    manager = User(
        id=2,
        name="John Manager",
        email="manager@helpdesk.com",
        password="real_hash",
        role="manager",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        max_open_tickets=20,
        is_demo=False,
    )
    admin = User(
        id=1,
        name="Admin User",
        email="admin@helpdesk.com",
        password="real_hash",
        role="admin",
        assigned_team="Network Team",
        timezone="Asia/Kolkata",
        max_open_tickets=20,
        is_demo=False,
    )
    employee = User(
        id=5,
        name="Alice Employee",
        email="alice@company.com",
        password="real_hash",
        role="employee",
        is_demo=False,
    )
    session.add_all([sarah, mike, manager, admin, employee])

    # Real shifts for Sarah and Mike
    shift_sarah = AgentShift(
        id=3,
        agent_id=3,
        agent_name="Sarah Agent",
        weekday=0,
        start_time="09:00",
        end_time="17:00",
        is_active=True,
        is_demo=False,
    )
    shift_mike = AgentShift(
        id=4,
        agent_id=4,
        agent_name="Mike Network Agent",
        weekday=0,
        start_time="09:00",
        end_time="17:00",
        is_active=True,
        is_demo=False,
    )
    session.add_all([shift_sarah, shift_mike])

    # Real ticket (must remain untouched)
    real_ticket = Ticket(
        id=999,
        title="Real user laptop failure",
        description="Blue screen error",
        category="Hardware",
        status="open",
        assigned_agent_id=3,
        assigned_agent_name="Sarah Agent",
        is_demo=False,
    )
    session.add(real_ticket)
    session.commit()

    yield session
    Base.metadata.drop_all(bind=engine)


def test_seed_twice_gives_same_row_counts(db):
    """Calling demo_seed multiple times gives identical row counts (idempotent upsert)."""
    req = MagicMock()
    req.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}

    with patch("app.availability.routes.SessionLocal", return_value=db):
        res1 = demo_seed(DemoSeedRequest(reset=False), request=req)
        assert res1["demo_mode"] is True
        assert len(res1["agents"]) == 5

        # Counts after first seed
        users1 = db.query(User).filter(User.is_demo == True).count()
        shifts1 = db.query(AgentShift).filter(AgentShift.is_demo == True).count()
        tickets1 = db.query(Ticket).filter(Ticket.is_demo == True).count()
        leaves1 = db.query(AgentLeave).filter(AgentLeave.is_demo == True).count()
        oncall1 = db.query(OnCallRoster).filter(OnCallRoster.is_demo == True).count()

        assert users1 == 5
        assert tickets1 == 14  # 10 Arun + 3 Meena + 1 Kiran
        assert leaves1 == 1    # Ravi approved leave
        assert oncall1 == 1    # Kiran on-call

        # Run seed a second time
        res2 = demo_seed(DemoSeedRequest(reset=False), request=req)
        assert res2["demo_mode"] is True

        # Counts after second seed must be identical
        users2 = db.query(User).filter(User.is_demo == True).count()
        shifts2 = db.query(AgentShift).filter(AgentShift.is_demo == True).count()
        tickets2 = db.query(Ticket).filter(Ticket.is_demo == True).count()
        leaves2 = db.query(AgentLeave).filter(AgentLeave.is_demo == True).count()
        oncall2 = db.query(OnCallRoster).filter(OnCallRoster.is_demo == True).count()

        assert users1 == users2
        assert shifts1 == shifts2
        assert tickets1 == tickets2
        assert leaves1 == leaves2
        assert oncall1 == oncall2

        # Verify toast message format
        assert f"{users1} agents" in res2["message"]
        assert f"{shifts1} shifts" in res2["message"]
        assert f"{tickets1} demo tickets" in res2["message"]


def test_no_shifts_for_managers(db):
    """Managers never receive shifts; create_shift rejects manager role with 400."""
    req = MagicMock()
    req.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}

    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req)

        # Check in DB: no manager or admin has any shift
        manager_user_ids = [u.id for u in db.query(User).filter(User.role.in_(["manager", "admin", "team_lead"])).all()]
        mgr_shifts = db.query(AgentShift).filter(AgentShift.agent_id.in_(manager_user_ids)).all()
        assert len(mgr_shifts) == 0

        # Attempt to create shift for John Manager (id=2)
        with pytest.raises(HTTPException) as exc_mgr:
            create_shift(ShiftCreate(agent_id=2, weekday=1, start_time="09:00", end_time="17:00"), request=req)
        assert exc_mgr.value.status_code == 400
        assert "Manager-role users cannot be assigned shifts" in exc_mgr.value.detail

        # Attempt to create shift for Admin User (id=1)
        with pytest.raises(HTTPException) as exc_admin:
            create_shift(ShiftCreate(agent_id=1, weekday=1, start_time="09:00", end_time="17:00"), request=req)
        assert exc_admin.value.status_code == 400


def test_all_7_days_covered_by_shifts(db):
    """Shifts cover all 7 days (0 to 6) for demo agents (Meena, Kiran, Arun)."""
    req = MagicMock()
    req.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}

    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req)

        # For every weekday 0 through 6, verify shifts exist
        covered_weekdays = {s.weekday for s in db.query(AgentShift).filter(AgentShift.is_active == True).all()}
        assert covered_weekdays == {0, 1, 2, 3, 4, 5, 6}

        # Arun, Meena, Kiran each have shifts for all 7 days
        for name in ["Arun", "Meena", "Kiran"]:
            agent = db.query(User).filter(User.name == name).first()
            agent_weekdays = {s.weekday for s in db.query(AgentShift).filter(AgentShift.agent_id == agent.id, AgentShift.is_active == True).all()}
            assert agent_weekdays == {0, 1, 2, 3, 4, 5, 6}


def test_reset_removes_only_demo_records(db):
    """Demo reset deletes only demo records, preserving real tickets, users, and shifts."""
    req = MagicMock()
    req.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}

    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req)
        assert db.query(Ticket).filter(Ticket.is_demo == True).count() > 0

        # Now reset
        res = demo_seed(DemoSeedRequest(reset=True), request=req)
        assert res["demo_mode"] is False

    # Demo tickets, users, shifts, leaves are gone
    assert db.query(Ticket).filter(Ticket.is_demo == True).count() == 0
    assert db.query(User).filter(User.is_demo == True).count() == 0
    assert db.query(AgentShift).filter(AgentShift.is_demo == True).count() == 0
    assert db.query(AgentLeave).filter(AgentLeave.is_demo == True).count() == 0

    # Real data is completely intact (Sarah, Mike, John Manager, Alice, real ticket, real shifts)
    assert db.query(Ticket).filter(Ticket.id == 999).first() is not None
    assert db.query(User).filter(User.name == "Sarah Agent").first() is not None
    assert db.query(User).filter(User.name == "Mike Network Agent").first() is not None
    assert db.query(User).filter(User.name == "John Manager").first() is not None
    assert db.query(AgentShift).filter(AgentShift.id == 3).first() is not None
    assert db.query(AgentShift).filter(AgentShift.id == 4).first() is not None


def test_view_as_returns_403_for_non_managers(db):
    """View-as impersonation returns 403 for non-managers, non-agents, and when demo mode is off."""
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}

    # 1. Non-manager caller (employee) calling view_as_agent -> 403
    req_emp = MagicMock()
    req_emp.headers = {"X-User-Role": "employee", "X-User-Email": "alice@company.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        with pytest.raises(HTTPException) as exc_emp:
            view_as_agent(ViewAsRequest(agent_name="Meena"), request=req_emp)
        assert exc_emp.value.status_code == 403

    # 2. Non-manager caller (agent) calling view_as_agent -> 403
    req_agent = MagicMock()
    req_agent.headers = {"X-User-Role": "agent", "X-User-Email": "agent@helpdesk.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        with pytest.raises(HTTPException) as exc_ag:
            view_as_agent(ViewAsRequest(agent_name="Meena"), request=req_agent)
        assert exc_ag.value.status_code == 403

    # Seed demo data
    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req_mgr)

    # 3. Manager calling view_as when DEMO_MODE is off ("false") -> 403
    with patch("app.availability.routes.SessionLocal", return_value=db), \
         patch.dict("os.environ", {"DEMO_MODE": "false"}):
        with pytest.raises(HTTPException) as exc_demo_off:
            view_as_agent(ViewAsRequest(agent_name="Meena"), request=req_mgr)
        assert exc_demo_off.value.status_code == 403
        assert "DEMO_MODE is on" in exc_demo_off.value.detail

    # 4. Manager calling view_as for non-agent target (Alice Employee) -> 403
    with patch("app.availability.routes.SessionLocal", return_value=db):
        with pytest.raises(HTTPException) as exc_non_agent:
            view_as_agent(ViewAsRequest(agent_name="Alice Employee"), request=req_mgr)
        assert exc_non_agent.value.status_code == 403
        assert "Can only impersonate support agents" in exc_non_agent.value.detail

    # 5. Manager calling view_as for support agents (Meena, Sarah Agent) -> 200 OK
    with patch("app.availability.routes.SessionLocal", return_value=db):
        res_meena = view_as_agent(ViewAsRequest(agent_name="Meena"), request=req_mgr)
        assert res_meena["success"] is True
        assert res_meena["agent"]["name"] == "Meena"

        res_sarah = view_as_agent(ViewAsRequest(agent_name="Sarah Agent"), request=req_mgr)
        assert res_sarah["success"] is True
        assert res_sarah["agent"]["name"] == "Sarah Agent"

    # 6. Non-manager sending X-View-As-Agent header to agent queue -> 403
    req_emp_impersonate = MagicMock()
    req_emp_impersonate.headers = {
        "X-User-Role": "employee",
        "X-User-Email": "alice@company.com",
        "X-View-As-Agent": "Meena",
    }
    with patch("app.agent.routes.SessionLocal", return_value=db):
        with pytest.raises(HTTPException) as exc_hdr:
            get_agent_queue(request=req_emp_impersonate)
        assert exc_hdr.value.status_code == 403


def test_ravi_workspace_is_empty_with_leave_banner(db):
    """Ravi workspace shows empty queue and leave status with end date."""
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req_mgr)

    req_ravi = MagicMock()
    req_ravi.headers = {
        "X-User-Role": "agent",
        "X-User-Email": "ravi@smartdesk.com",
    }
    with patch("app.agent.routes.SessionLocal", return_value=db):
        ravi_status = get_my_status(request=req_ravi)
        assert ravi_status["name"] == "Ravi"
        assert ravi_status["is_on_leave"] is True
        assert ravi_status["leave_until"] is not None

        ravi_queue = get_agent_queue(request=req_ravi)
        assert len(ravi_queue) == 0


def test_meena_shows_only_her_tickets(db):
    """Meena workspace shows only her 3 tickets, In Shift, and cap 10."""
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req_mgr)

    req_meena = MagicMock()
    req_meena.headers = {
        "X-User-Role": "agent",
        "X-User-Email": "meena@smartdesk.com",
    }
    with patch("app.agent.routes.SessionLocal", return_value=db):
        meena_status = get_my_status(request=req_meena)
        assert meena_status["name"] == "Meena"
        assert meena_status["is_on_leave"] is False
        assert meena_status["open_tickets"] == 3
        assert meena_status["ticket_cap"] == 10
        assert meena_status["shift_status"] == "In Shift"

        meena_queue = get_agent_queue(request=req_meena)
        assert len(meena_queue) == 3
        assert all(t["assigned_agent_name"] == "Meena" for t in meena_queue)


def test_mocked_clock_availability_at_03_11_22_ist(db):
    """
    Clock mocked at 03:00, 11:00, and 22:00 IST:
    Assert Meena and Kiran are always Available (True).
    Assert Ravi, Priya, and Arun are never Available (False).
    - Ravi is on shift and on approved leave.
    - Priya's shift ended 1 hour ago (off shift).
    - Arun is on shift but at open-ticket capacity (10/10).
    """
    ist = ZoneInfo("Asia/Kolkata")
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}

    for hour in [3, 11, 22]:
        t_ist = datetime(2026, 11, 16, hour, 0, 0, tzinfo=ist)
        t_utc = t_ist.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

        MockDT = type(
            "MockDT",
            (datetime,),
            {
                "now": classmethod(lambda cls, tz=None: t_ist if tz else t_ist.replace(tzinfo=None)),
                "utcnow": classmethod(lambda cls: t_utc),
            },
        )

        with patch("app.availability.routes.SessionLocal", return_value=db), \
             patch("app.availability.routes.datetime", MockDT), \
             patch("app.availability.service.datetime", MockDT):
            # Seed at mocked time
            demo_seed(DemoSeedRequest(reset=False), request=req_mgr)

            # Query availability for Network Team
            agents = get_available_agents_now("Network Team", db)
            agent_map = {a["name"]: a for a in agents}

            # 1. Meena: ALWAYS available
            assert "Meena" in agent_map
            assert agent_map["Meena"]["available"] is True, f"Meena was not available at {hour}:00 IST"
            assert agent_map["Meena"]["on_shift"] is True
            assert agent_map["Meena"]["open_tickets"] == 3

            # 2. Kiran: ALWAYS available (in shift + on-call)
            assert "Kiran" in agent_map
            assert agent_map["Kiran"]["available"] is True, f"Kiran was not available at {hour}:00 IST"
            assert agent_map["Kiran"]["on_shift"] is True
            assert agent_map["Kiran"]["on_call"] is True
            assert agent_map["Kiran"]["open_tickets"] == 1

            # 3. Ravi: NEVER available (approved leave covering now)
            assert "Ravi" in agent_map
            assert agent_map["Ravi"]["available"] is False, f"Ravi was available at {hour}:00 IST"
            assert agent_map["Ravi"]["on_leave"] is True

            # 4. Priya: NEVER available (shift ended 1 hour ago)
            assert "Priya" in agent_map
            assert agent_map["Priya"]["available"] is False, f"Priya was available at {hour}:00 IST"
            assert agent_map["Priya"]["on_shift"] is False

            # 5. Arun: NEVER available (at capacity 10/10)
            assert "Arun" in agent_map
            assert agent_map["Arun"]["available"] is False, f"Arun was available at {hour}:00 IST"
            assert agent_map["Arun"]["on_shift"] is True
            assert agent_map["Arun"]["below_cap"] is False
            assert agent_map["Arun"]["open_tickets"] == 10


def test_view_as_audit_logging_on_ticket_actions(db):
    """
    Impersonated actions are audit-logged with the real manager as actor and
    'viewing as <agent>' as context. Non-manager caller gets 403.
    """
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req_mgr)

    # Pick one of Meena's tickets
    ticket = db.query(Ticket).filter(Ticket.assigned_agent_name == "Meena").first()
    assert ticket is not None

    # Manager impersonating Meena adds a comment
    req_impersonate = MagicMock()
    req_impersonate.headers = {
        "X-User-Role": "manager",
        "X-User-Email": "manager@helpdesk.com",
        "X-View-As-Agent": "Meena",
        "X-Demo-Mode": "true",
    }
    with patch("app.agent.routes.SessionLocal", return_value=db):
        res_comment = add_ticket_comment(
            ticket.id,
            AddCommentRequest(content="Testing audit trail from impersonated session", is_internal=False),
            request=req_impersonate,
        )
        assert res_comment["message"] == "Comment added"

        # Check comment in DB
        cmt = db.query(TicketComment).filter(
            TicketComment.ticket_id == ticket.id,
            TicketComment.content.like("%Testing audit trail%"),
        ).first()
        assert cmt is not None
        assert "John Manager" in cmt.author_name
        assert "viewing as Meena" in cmt.author_name
        assert cmt.author_role == "manager"
        assert "[Audit: John Manager, context: viewing as Meena]" in cmt.content

    # Manager impersonating Meena resolves the ticket
    with patch("app.agent.routes.SessionLocal", return_value=db):
        res_resolve = resolve_ticket(
            ticket.id,
            ResolveTicketRequest(
                resolution_summary="Resolved via manager impersonation",
                root_cause="Configuration verified",
            ),
            request=req_impersonate,
        )
        assert "resolved" in res_resolve["message"]

        # Check resolve comment
        res_cmt = db.query(TicketComment).filter(
            TicketComment.ticket_id == ticket.id,
            TicketComment.content.like("%TICKET RESOLVED%"),
        ).first()
        assert res_cmt is not None
        assert "John Manager" in res_cmt.author_name
        assert "viewing as Meena" in res_cmt.author_name
        assert "[Audit: John Manager, context: viewing as Meena]" in res_cmt.content

    # Non-manager (Alice Employee) attempting impersonation receives 403
    req_unauth = MagicMock()
    req_unauth.headers = {
        "X-User-Role": "employee",
        "X-User-Email": "alice@company.com",
        "X-View-As-Agent": "Meena",
        "X-Demo-Mode": "true",
    }
    with patch("app.agent.routes.SessionLocal", return_value=db):
        with pytest.raises(HTTPException) as exc:
            add_ticket_comment(
                ticket.id,
                AddCommentRequest(content="Unauthorized attempt"),
                request=req_unauth,
            )
        assert exc.value.status_code == 403


def test_no_user_facing_demo_strings_in_frontend():
    """Scan all frontend source files to assert that no user-facing string contains 'demo', 'Demo', or 'DEMO'."""
    import os
    import re

    frontend_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src"))
    assert os.path.exists(frontend_src), f"Frontend src directory not found at {frontend_src}"

    # Patterns indicating user-facing text
    user_facing_patterns = [
        re.compile(r'>[^<>\n]*\b(?i:demo)\b[^<>\n]*<'),                      # JSX children text: >...demo...<
        re.compile(r'label=["\'][^"\']*\b(?i:demo)\b[^"\']*["\']'),          # label="...demo..."
        re.compile(r'title=["\'][^"\']*\b(?i:demo)\b[^"\']*["\']'),          # title="...demo..."
        re.compile(r'placeholder=["\'][^"\']*\b(?i:demo)\b[^"\']*["\']'),    # placeholder="...demo..."
        re.compile(r'alt=["\'][^"\']*\b(?i:demo)\b[^"\']*["\']'),            # alt="...demo..."
        re.compile(r'toast\.[a-z]+\([^)]*\b(?i:demo)\b[^)]*\)'),              # toast("...demo...")
        re.compile(r'<Alert[^>]*>[^<>\n]*\b(?i:demo)\b', re.IGNORECASE),      # <Alert>...demo...
    ]

    violations = []
    for root, _, files in os.walk(frontend_src):
        for f in files:
            if f.endswith((".tsx", ".jsx", ".html")):
                filepath = os.path.join(root, f)
                with open(filepath, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    for pat in user_facing_patterns:
                        matches = pat.findall(content)
                        if matches:
                            violations.append((f, matches))

    assert len(violations) == 0, f"Found user-facing demo strings in frontend: {violations}"


def test_team_column_never_empty(db):
    """Every ticket in the agent queue has a valid, non-empty assigned_team."""
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req_mgr)

    req_meena = MagicMock()
    req_meena.headers = {"X-User-Role": "agent", "X-User-Email": "meena@smartdesk.com"}
    with patch("app.agent.routes.SessionLocal", return_value=db):
        queue = get_agent_queue(request=req_meena)
        assert len(queue) > 0
        for t in queue:
            assert t.get("assigned_team") is not None
            assert len(str(t["assigned_team"]).strip()) > 0
            assert t["assigned_team"] == "Network Operations"


def test_dashboard_counts_consistent(db):
    """get_ticket_stats total and open counts are strictly consistent with get_all_tickets."""
    from app.tickets.routes import get_ticket_stats, get_all_tickets

    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        demo_seed(DemoSeedRequest(reset=False), request=req_mgr)

    with patch("app.tickets.routes.SessionLocal", return_value=db):
        all_tickets = get_all_tickets(request=req_mgr)
        stats = get_ticket_stats(include_demo=True)

        assert stats["total_tickets"] == len(all_tickets)
        active_statuses = {"open", "in_progress", "escalated"}
        expected_active = len([t for t in all_tickets if t["status"] in active_statuses])
        assert stats["open_tickets"] == expected_active


def test_mike_availability_and_over_capacity(db):
    """
    Mike Network Agent is in shift on Monday 09:00-17:00 in Asia/Kolkata timezone.
    With 22 tickets against cap 10, he is at/over capacity and skipped in assignment.
    """
    from app.availability.service import is_available, assign_agent_for_ticket, _get_agent_skip_reason

    mike = db.query(User).filter(User.name == "Mike Network Agent").first()
    assert mike is not None
    assert mike.timezone == "Asia/Kolkata"

    # Add 22 tickets for Mike
    now_utc = datetime.utcnow()
    for i in range(22):
        db.add(Ticket(
            title=f"Mike ticket {i}",
            description="desc",
            category="Network",
            status="open",
            assigned_team="Network Team",
            assigned_agent_id=mike.id,
            assigned_agent_name=mike.name,
            created_at=now_utc,
            is_demo=False,
        ))
    db.commit()

    # Check skip reason
    skip_reason = _get_agent_skip_reason(mike, now_utc, 22, db)
    assert skip_reason == "over capacity"

    # Test assignment skips Mike
    new_ticket = Ticket(
        title="Emergency Switch Failure",
        description="Core Switch Down",
        category="Network",
        status="open",
        assigned_team="Network Team",
        is_demo=False,
    )
    db.add(new_ticket)
    db.commit()

    chosen, reason = assign_agent_for_ticket(new_ticket, "Network Team", db)
    # Mike must NOT be chosen
    assert chosen is None or chosen.id != mike.id
    assert "Mike Network Agent (over capacity)" in reason


def test_get_agent_status_leave_overrides_shift(db):
    """
    Test 1: leave + in-shift time -> status 'on_leave' (leave ALWAYS wins over shift).
    Sarah has Monday 09:00-17:00 shift, but approved leave covering now.
    Assert status == 'on_leave', return_date == 'Nov 18', next_shift == 'Returns Nov 18'.
    """
    from app.availability.service import get_agent_status

    sarah = db.query(User).filter(User.name == "Sarah Agent").first()
    assert sarah is not None

    # Monday 14:00 IST (in shift 09:00-17:00)
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime(2026, 11, 16, 14, 0, 0, tzinfo=ist)
    now_utc = now_ist.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    # Approved leave from Nov 15 to Nov 17 23:59:59
    leave = AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=datetime(2026, 11, 15, 0, 0, 0),
        end_datetime=datetime(2026, 11, 17, 23, 59, 59),
        leave_type="annual",
        status="approved",
        source="hr_sync",
    )
    db.add(leave)
    db.commit()

    st = get_agent_status(sarah, now_utc, db)
    assert st == "on_leave"
    assert st.status == "on_leave"
    assert st.return_date == "Nov 18"
    assert st.next_shift == "Returns Nov 18"


def test_leave_ended_yesterday_not_on_leave(db):
    """
    Test 2: leave ended yesterday -> not on leave.
    If leave ended on Nov 15 and now is Nov 16 14:00 IST:
    Sarah is in shift 09:00-17:00, so status is 'available'.
    """
    from app.availability.service import get_agent_status

    sarah = db.query(User).filter(User.name == "Sarah Agent").first()
    assert sarah is not None

    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime(2026, 11, 16, 14, 0, 0, tzinfo=ist)
    now_utc = now_ist.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    # Leave ended yesterday (Nov 15)
    leave = AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=datetime(2026, 11, 10, 0, 0, 0),
        end_datetime=datetime(2026, 11, 15, 23, 59, 59),
        leave_type="annual",
        status="approved",
        source="manual",
    )
    db.add(leave)
    db.commit()

    st = get_agent_status(sarah, now_utc, db, open_count=0)
    assert st != "on_leave"
    assert st == "available"
    assert st.status == "available"


def test_pending_leave_not_on_leave(db):
    """
    Test 3: pending leave covering now -> not on leave (only approved leave blocks).
    """
    from app.availability.service import get_agent_status

    sarah = db.query(User).filter(User.name == "Sarah Agent").first()
    assert sarah is not None

    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime(2026, 11, 16, 14, 0, 0, tzinfo=ist)
    now_utc = now_ist.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    # Pending leave covering now
    leave = AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=datetime(2026, 11, 15, 0, 0, 0),
        end_datetime=datetime(2026, 11, 17, 23, 59, 59),
        leave_type="annual",
        status="pending",
        source="manual",
    )
    db.add(leave)
    db.commit()

    st = get_agent_status(sarah, now_utc, db, open_count=0)
    assert st != "on_leave"
    assert st == "available"


def test_workspace_api_returns_on_leave_and_return_date(db):
    """
    Test 4: The Agent Workspace API (GET /agent/my-status) returns on_leave and matching return date.
    Sarah has Monday shift and approved leave covering Nov 15-17.
    Assert shift_status == 'On Leave' (not 'In Shift'), next_shift == 'Returns Nov 18', return_date == 'Nov 18'.
    """
    sarah = db.query(User).filter(User.name == "Sarah Agent").first()
    assert sarah is not None

    # Approved leave covering now
    now_utc = datetime.utcnow()
    db.add(AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=now_utc - timedelta(days=1),
        end_datetime=datetime(2026, 11, 17, 23, 59, 59),
        leave_type="annual",
        status="approved",
        source="hr_sync",
    ))
    db.commit()

    req = MagicMock()
    req.headers = {"X-User-Role": "agent", "X-User-Email": "agent@helpdesk.com"}
    with patch("app.agent.routes.SessionLocal", return_value=db):
        status = get_my_status(request=req)
        assert status["status"] == "on_leave"
        assert status["is_on_leave"] is True
        assert status["shift_status"] == "On Leave"
        assert status["shift_status"] != "In Shift"
        assert status["return_date"] == "Nov 18"
        assert status["next_shift"] == "Returns Nov 18"


def test_no_screen_shows_leave_agent_as_in_shift_or_available(db):
    """
    Test 5: Assert that an agent with approved leave covering now is NEVER shown as In Shift or Available
    across screens/APIs:
      - Dashboard availability cards API (/availability/available-now)
      - Agent Workspace status card API (/agent/my-status)
      - Leave requests listing (/availability/leave)
    """
    from app.availability.routes import who_is_available, list_leaves

    sarah = db.query(User).filter(User.name == "Sarah Agent").first()
    assert sarah is not None

    now_utc = datetime.utcnow()
    db.add(AgentLeave(
        agent_id=sarah.id,
        agent_name=sarah.name,
        start_datetime=now_utc - timedelta(days=1),
        end_datetime=datetime(2026, 11, 17, 23, 59, 59),
        leave_type="annual",
        status="approved",
        source="hr_sync",
    ))
    db.commit()

    # 1. Dashboard availability API
    req_mgr = MagicMock()
    req_mgr.headers = {"X-User-Role": "manager", "X-User-Email": "manager@helpdesk.com"}
    with patch("app.availability.routes.SessionLocal", return_value=db):
        agents = who_is_available(req_mgr)
        sarah_avail = next((a for a in agents if a["name"] == "Sarah Agent"), None)
        assert sarah_avail is not None
        assert sarah_avail["status"] == "on_leave"
        assert sarah_avail["available"] is False
        assert sarah_avail["on_shift"] is False  # Overridden by leave!
        assert sarah_avail["shift_end"] is None   # No active shift end shown when on leave

    # 2. Workspace status API
    req_sarah = MagicMock()
    req_sarah.headers = {"X-User-Role": "agent", "X-User-Email": "agent@helpdesk.com"}
    with patch("app.agent.routes.SessionLocal", return_value=db):
        my_st = get_my_status(request=req_sarah)
        assert my_st["shift_status"] == "On Leave"
        assert my_st["shift_status"] != "In Shift"
        assert my_st["next_shift"] == "Returns Nov 18"

    # 3. Leave Requests API returns approved leave covering now
    with patch("app.availability.routes.SessionLocal", return_value=db):
        leaves = list_leaves(agent_id=sarah.id, request=req_mgr)
        approved_leaves = [l for l in leaves if l["status"] == "approved"]
        assert len(approved_leaves) > 0
        assert any(l["source"] == "hr_sync" for l in approved_leaves)



