import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.availability import AgentShift, AgentLeave, AssignmentLog
from app.routing.service import classify_and_route_ticket, rule_based_classify
from app.availability.service import assign_agent_for_ticket, agent_has_skill, CATEGORY_CONFIG


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()

    # Network Agent
    net_agent = User(
        id=10,
        name="Meena",
        email="meena@company.com",
        password="hash",
        role="agent",
        assigned_team="Network Operations",
        department="Network Operations",
        timezone="Asia/Kolkata",
        max_open_tickets=10,
    )
    # IT Support / Software Agent
    sw_agent = User(
        id=20,
        name="Sarah Agent",
        email="sarah@company.com",
        password="hash",
        role="agent",
        assigned_team="IT Support",
        department="IT Operations, Software, Hardware, Access, Email, Application/Backend, Printer",
        timezone="Asia/Kolkata",
        max_open_tickets=10,
    )
    # Manager
    manager = User(
        id=1,
        name="John Manager",
        email="manager@company.com",
        password="hash",
        role="manager",
        assigned_team="IT Support",
        department="IT Management",
        timezone="Asia/Kolkata",
    )
    session.add_all([net_agent, sw_agent, manager])
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


# ══════════════════════════════════════════════════════════════════════════════
# TASK 5 SAMPLE TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_sample_1_file_server_unreachable_network(db):
    """Sample 1: file server unreachable -> Network category & Network Operations team."""
    res = classify_and_route_ticket(
        title="File server unreachable from branch office",
        description="Users on 3rd floor cannot reach corporate file server at 10.0.1.5.",
    )
    assert res["category"] == "Network"
    assert res["assigned_team"] == "Network Operations"

    # Availability-aware assignment matches Meena (Network skill), never Sarah
    now_utc = datetime.utcnow()
    db.add(AgentShift(
        agent_id=10,
        agent_name="Meena",
        weekday=now_utc.weekday(),
        start_time="00:00",
        end_time="23:59",
        is_active=True,
    ))
    db.commit()

    ticket = Ticket(
        id=101,
        title="File server unreachable from branch office",
        description="Users cannot reach file server",
        category=res["category"],
        assigned_team=res["assigned_team"],
    )
    db.add(ticket)
    db.commit()

    chosen, reason = assign_agent_for_ticket(ticket, res["assigned_team"], db)
    assert chosen is not None
    assert chosen.name == "Meena"
    assert "Assigned to Meena" in reason


def test_sample_2_excel_crash_software(db):
    """Sample 2: Excel crash -> Software category."""
    res = classify_and_route_ticket(
        title="Excel crashes when opening large budget spreadsheet",
        description="Microsoft Excel crashes with error code 0xc0000005 every time I open the Q3 file.",
    )
    assert res["category"] in ["Software", "Software/Desktop Application"]
    assert res["assigned_team"] == "IT Support"


def test_sample_3_password_locked_access(db):
    """Sample 3: password locked -> Access category."""
    res = classify_and_route_ticket(
        title="Active Directory password locked after multiple attempts",
        description="User account locked out, need password reset and MFA verification.",
    )
    assert res["category"] in ["Access", "Access/Accounts"]
    assert res["assigned_team"] == "IT Support"


def test_erp_purchase_module_access_role(db):
    """Need access to ERP purchase module for a new role -> Access category."""
    res = classify_and_route_ticket(
        title="Need access to the ERP purchase module for a new role",
        description="I moved to the Procurement team on Monday and need access to the Purchase Orders module in the ERP system, with create and approve rights up to 5 lakh. Please grant the access.",
    )
    assert res["category"] in ["Access", "Access/Accounts"]
    assert res["assigned_team"] == "IT Support"


def test_sample_4_phishing_email_security(db):
    """Sample 4: phishing email -> Security category."""
    res = classify_and_route_ticket(
        title="Suspicious phishing email claiming urgent payroll update",
        description="Multiple employees received a suspicious email with link to fake login portal.",
    )
    assert res["category"] == "Security"
    assert res["assigned_team"] == "Security Team"


def test_sample_5_production_gateway_503_application_backend(db):
    """Sample 5: production gateway 503 -> Application/Backend, High or Critical priority."""
    res = classify_and_route_ticket(
        title="Production gateway 503 service unavailable error",
        description="API gateway returning 503 to customer requests on production cluster.",
    )
    assert res["category"] == "Application/Backend"
    assert res["priority"] in ["Critical", "High"]
    assert res["sla_target"] in ["4 hours", "24 hours"]


def test_skill_matching_prevents_network_agent_on_software_ticket(db):
    """
    Ensure Network agents (Meena) are NEVER assigned to Software tickets.
    If Sarah is on leave, it must escalate to manager, not pick Meena.
    """
    now_utc = datetime.utcnow()
    # Meena is in shift
    db.add(AgentShift(
        agent_id=10,
        agent_name="Meena",
        weekday=now_utc.weekday(),
        start_time="00:00",
        end_time="23:59",
        is_active=True,
    ))
    # Sarah is on approved leave
    db.add(AgentLeave(
        agent_id=20,
        agent_name="Sarah Agent",
        start_datetime=now_utc - timedelta(hours=2),
        end_datetime=now_utc + timedelta(hours=5),
        status="approved",
    ))
    db.commit()

    ticket = Ticket(
        id=505,
        title="Excel crashes when opening quarterly budget file",
        description="Excel has stopped working on large file",
        category="Software",
        assigned_team="IT Support",
    )
    db.add(ticket)
    db.commit()

    chosen, reason = assign_agent_for_ticket(ticket, "IT Support", db)
    # Must NOT be Meena because Meena lacks the Software skill
    assert chosen.name != "Meena"
    assert chosen.name == "John Manager"
    assert "Sarah Agent (on leave)" in reason
    assert ticket.assigned_agent_name == "John Manager"


def test_real_internal_project_distinction():
    """Ensure 'Internal Project' is strictly reserved for real internal developer projects."""
    real_internal = rule_based_classify(
        title="Internal project: architecture review of payment microservice dev branch",
        description="Dev sprint refactoring task for internal repo.",
    )
    assert real_internal["category"] == "Internal Project"

    software_ticket = rule_based_classify(
        title="Need IntelliJ IDEA Ultimate license installed",
        description="Please install and license IntelliJ on work laptop.",
    )
    assert software_ticket["category"] == "Software"
