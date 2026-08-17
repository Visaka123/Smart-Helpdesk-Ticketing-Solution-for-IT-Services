import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.database.database import SessionLocal, engine
from app.models import Ticket, TicketRequester, TicketComment, SLAEscalationLog, DuplicateFeedbackLog
from app.routing.service import predict_ticket_category, post_process_category, route_team_with_llm
from app.priority.service import predict_priority_enhanced
from app.sla.service import calculate_sla_due_at

print("=======================================================================")
print("  STEP 1: DATABASE CLEANUP & AUTO-INCREMENT RESET")
print("=======================================================================")

db_path = os.path.join(backend_dir, "smart_helpdesk.db")
print(f"Target SQLite Database: '{db_path}'")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Wipe all ticket-related tables
tables_to_clear = [
    "tickets", "ticket_requesters", "ticket_comments",
    "sla_escalation_logs", "duplicate_feedback_logs"
]

for table in tables_to_clear:
    try:
        cursor.execute(f"DELETE FROM {table};")
        print(f"  -> Cleared all rows from table '{table}'")
    except Exception as e:
        print(f"  -> Notice clearing '{table}': {e}")

try:
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('tickets', 'ticket_requesters', 'ticket_comments', 'sla_escalation_logs', 'duplicate_feedback_logs');")
    print("  -> Reset sqlite_sequence auto-increment counters to 1.")
except Exception as e:
    print(f"  -> Notice resetting sqlite_sequence: {e}")

conn.commit()
conn.close()

print("\n=======================================================================")
print("  STEP 2: SEEDING EXACTLY 10 CLEAN ENTERPRISE TICKETS")
print("=======================================================================")

seed_tickets = [
    {
        "title": "Production API returning 500 Internal Server Error on checkout",
        "description": "The payment gateway endpoint fails during cart checkout with a 500 status code after the v2.4 deployment. Customers are unable to complete transactions.",
        "expected_category": "Internal Project",
        "priority": "Critical",
        "expected_team": "Application Support",
        "requester_name": "Sarah Connor",
        "requester_dept": "Engineering"
    },
    {
        "title": "PostgreSQL read replica replication lag exceeding threshold",
        "description": "The analytics read replica has fallen 45 minutes behind the primary database instance. Database connection pool exhaustion observed on port 5432.",
        "expected_category": "Internal Project",
        "priority": "High",
        "expected_team": "Database Operations",
        "requester_name": "David Miller",
        "requester_dept": "Data Science"
    },
    {
        "title": "GitHub Actions CI/CD staging deployment pipeline failing",
        "description": "Docker build step timed out while pushing multi-arch images to AWS ECR. All staging deployments are blocked.",
        "expected_category": "Internal Project",
        "priority": "High",
        "expected_team": "DevOps & Cloud Infra",
        "requester_name": "Alex Rivera",
        "requester_dept": "DevOps"
    },
    {
        "title": "Internal CRM desktop client crashes on launch after v4.1 patch",
        "description": "The latest enterprise CRM update throws a fatal null pointer exception during initialization on Windows 11. Application fails to open.",
        "expected_category": "Internal Project",
        "priority": "High",
        "expected_team": "Application Support",
        "requester_name": "Emily Watson",
        "requester_dept": "Customer Success"
    },
    {
        "title": "SAP S/4HANA invoice synchronization sync failure",
        "description": "Automated billing batch job failed to sync invoices between Salesforce and SAP ERP module due to IDoc parsing error.",
        "expected_category": "Internal Project",
        "priority": "High",
        "expected_team": "SAP / ERP Team",
        "requester_name": "Robert Chen",
        "requester_dept": "Finance"
    },
    {
        "title": "Intermittent VPN gateway drops for remote engineering subnet",
        "description": "Engineers connecting to the corporate IPSec VPN gateway experience packet loss and repeated disconnection every 10 minutes.",
        "expected_category": "Access",
        "priority": "High",
        "expected_team": "Network & Security",
        "requester_name": "Marcus Vance",
        "requester_dept": "Infrastructure"
    },
    {
        "title": "Okta MFA push notification expired and account locked",
        "description": "Employee is locked out of single sign-on (SSO) portal after new phone migration. Needs Okta Verify MFA reset.",
        "expected_category": "Access",
        "priority": "Medium",
        "expected_team": "Identity & Access Management",
        "requester_name": "Jessica Taylor",
        "requester_dept": "Human Resources"
    },
    {
        "title": "Production S3 bucket storage quota alert triggered",
        "description": "The media asset storage volume has reached 95% capacity limit. Need quota increase for upcoming release.",
        "expected_category": "Storage",
        "priority": "Medium",
        "expected_team": "DevOps & Cloud Infra",
        "requester_name": "Michael Chang",
        "requester_dept": "Product"
    },
    {
        "title": "Procurement request for JetBrains All Products enterprise licenses",
        "description": "Requesting purchase approval for 5 annual JetBrains developer licenses for the incoming backend engineering team.",
        "expected_category": "Purchase",
        "priority": "Low",
        "expected_team": "Procurement",
        "requester_name": "Daniel Brooks",
        "requester_dept": "Engineering"
    },
    {
        "title": "Dell Thunderbolt 4 docking station dual-display flickering",
        "description": "Primary external 4K monitor goes black when connected via the Dell Type-C dock. Replaced HDMI/DisplayPort cables but hardware issue persists.",
        "expected_category": "Hardware",
        "priority": "Low",
        "expected_team": "Desktop Support",
        "requester_name": "Amanda Hayes",
        "requester_dept": "Design"
    }
]

db = SessionLocal()

created_count = 0
for idx, data in enumerate(seed_tickets, 1):
    combined_text = f"{data['title']} {data['description']}".strip()
    
    # 1. Predict category
    cat_res = predict_ticket_category(combined_text)
    raw_cat = cat_res.get("raw_category", cat_res["predicted_category"])
    post_res = post_process_category(raw_cat, combined_text)
    final_category = post_res["final_category"]
    
    if data.get("expected_category"):
        final_category = data["expected_category"]

    # 2. Route team with LLM
    assigned_team = route_team_with_llm(final_category, data["title"], data["description"])
    
    # 3. Calculate SLA (set to on track future target)
    priority = data["priority"]
    sla_due = calculate_sla_due_at(priority=priority, team_name=assigned_team, db=db)
    now_dt = datetime.now()

    ticket = Ticket(
        title=data["title"],
        description=data["description"],
        category=final_category,
        priority=priority,
        priority_confidence=0.95,
        status="open",
        assigned_team=assigned_team,
        routing_confidence=0.92,
        top_alternative_teams=json.dumps([{"team": assigned_team, "confidence": 0.92}]),
        is_low_confidence_routed=False,
        created_by=None,
        requester_name=data["requester_name"],
        requester_department=data["requester_dept"],
        created_at=now_dt - timedelta(minutes=10 * (10 - idx)),
        sla_due_at=sla_due,
        is_sla_breached=False,
        escalated_to_manager=False,
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    created_count += 1
    print(f"  [Ticket #{ticket.id}] Category: '{ticket.category}' | Priority: '{ticket.priority}' | Team: '{ticket.assigned_team}'")
    print(f"               Title: {ticket.title[:65]}...\n")

db.close()

print("=======================================================================")
print(f"  [SUCCESS] DATABASE RESET COMPLETE. SEEDED {created_count} CLEAN TICKETS!")
print("=======================================================================\n")
