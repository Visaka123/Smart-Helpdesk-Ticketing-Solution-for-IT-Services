import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.database.database import SessionLocal
from app.models import Ticket, TicketRequester, TicketComment, SLAEscalationLog, DuplicateFeedbackLog

print("=======================================================================")
print("  STEP 1: DATABASE CLEANUP & AUTO-INCREMENT RESET")
print("=======================================================================")

db_path = os.path.join(backend_dir, "smart_helpdesk.db")
print(f"Target SQLite Database: '{db_path}'")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

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
print("  STEP 2: SEEDING EXACTLY 13 UNIQUE ENTERPRISE TICKETS (#1 TO #13)")
print("=======================================================================")

seed_tickets = [
    {
        "id": 1,
        "title": "Production API returning 500 Internal Server Error on checkout",
        "description": "The payment gateway endpoint fails during cart checkout with a 500 status code after the v2.4 deployment. Customers are unable to complete transactions.",
        "category": "Internal Project",
        "priority": "Critical",
        "assigned_team": "Application Support",
        "sla_hours": 4,
        "requester_name": "Sarah Connor",
        "requester_dept": "Engineering"
    },
    {
        "id": 2,
        "title": "PostgreSQL read replica replication lag exceeding threshold",
        "description": "The analytics read replica has fallen 45 minutes behind the primary database instance. Database connection pool exhaustion observed on port 5432.",
        "category": "Internal Project",
        "priority": "High",
        "assigned_team": "Database Operations",
        "sla_hours": 24,
        "requester_name": "David Miller",
        "requester_dept": "Data Science"
    },
    {
        "id": 3,
        "title": "GitHub Actions CI/CD staging deployment pipeline failing",
        "description": "Docker build step timed out while pushing multi-arch images to AWS ECR. All staging deployments are blocked.",
        "category": "Internal Project",
        "priority": "High",
        "assigned_team": "DevOps & Cloud Infra",
        "sla_hours": 24,
        "requester_name": "Alex Rivera",
        "requester_dept": "DevOps"
    },
    {
        "id": 4,
        "title": "Internal CRM desktop client crashes on launch after v4.1 patch",
        "description": "The latest enterprise CRM update throws a fatal null pointer exception during initialization on Windows 11. Application fails to open.",
        "category": "Internal Project",
        "priority": "High",
        "assigned_team": "Application Support",
        "sla_hours": 24,
        "requester_name": "Emily Watson",
        "requester_dept": "Customer Success"
    },
    {
        "id": 5,
        "title": "SAP S/4HANA invoice synchronization sync failure",
        "description": "Automated billing batch job failed to sync invoices between Salesforce and SAP ERP module due to IDoc parsing error.",
        "category": "Internal Project",
        "priority": "High",
        "assigned_team": "SAP / ERP Team",
        "sla_hours": 24,
        "requester_name": "Robert Chen",
        "requester_dept": "Finance"
    },
    {
        "id": 6,
        "title": "Intermittent VPN gateway drops for remote engineering subnet",
        "description": "Engineers connecting to the corporate IPSec VPN gateway experience packet loss and repeated disconnection every 10 minutes.",
        "category": "Access",
        "priority": "High",
        "assigned_team": "Network & Security",
        "sla_hours": 24,
        "requester_name": "Marcus Vance",
        "requester_dept": "Infrastructure"
    },
    {
        "id": 7,
        "title": "Okta MFA push notification expired and account locked",
        "description": "Employee is locked out of single sign-on (SSO) portal after new phone migration. Needs Okta Verify MFA reset.",
        "category": "Access",
        "priority": "Medium",
        "assigned_team": "Identity & Access Management",
        "sla_hours": 48,
        "requester_name": "Jessica Taylor",
        "requester_dept": "Human Resources"
    },
    {
        "id": 8,
        "title": "Production S3 bucket storage quota alert triggered",
        "description": "The media asset storage volume has reached 95% capacity limit. Need quota increase for upcoming release.",
        "category": "Storage",
        "priority": "Medium",
        "assigned_team": "DevOps & Cloud Infra",
        "sla_hours": 48,
        "requester_name": "Michael Chang",
        "requester_dept": "Product"
    },
    {
        "id": 9,
        "title": "Procurement request for JetBrains All Products enterprise licenses",
        "description": "Requesting purchase approval for 5 annual JetBrains developer licenses for the incoming backend engineering team.",
        "category": "Purchase",
        "priority": "Low",
        "assigned_team": "Procurement",
        "sla_hours": 72,
        "requester_name": "Daniel Brooks",
        "requester_dept": "Engineering"
    },
    {
        "id": 10,
        "title": "Dell Thunderbolt 4 docking station dual-display flickering",
        "description": "Primary external 4K monitor goes black when connected via the Dell Type-C dock. Replaced HDMI/DisplayPort cables but hardware issue persists.",
        "category": "Hardware",
        "priority": "Low",
        "assigned_team": "Desktop Support",
        "sla_hours": 72,
        "requester_name": "Amanda Hayes",
        "requester_dept": "Design"
    },
    {
        "id": 11,
        "title": "Order service gRPC connection timeout to Inventory API",
        "description": "The order service microservice is experiencing gRPC connection timeouts (DEADLINE_EXCEEDED) when querying inventory availability.",
        "category": "Internal Project",
        "priority": "High",
        "assigned_team": "Application Support",
        "sla_hours": 24,
        "requester_name": "Alex Engineering",
        "requester_dept": "Backend Team"
    },
    {
        "id": 12,
        "title": "Liquibase schema migration deadlock on PostgreSQL transactions table",
        "description": "The latest automated DB migration locked the customer transaction table in production, blocking read/write queries and failing the release pipeline.",
        "category": "Internal Project",
        "priority": "Critical",
        "assigned_team": "Database Operations",
        "sla_hours": 4,
        "requester_name": "Sam DevOps",
        "requester_dept": "Data Platform"
    },
    {
        "id": 13,
        "title": "Production backend pod failing AWS IAM role authentication",
        "description": "The user authentication container throws an AccessDeniedException when fetching database connection secrets from AWS Secrets Manager. Workload IAM policy verification needed.",
        "category": "Internal Project",
        "priority": "Critical",
        "assigned_team": "DevOps & Cloud Infra",
        "sla_hours": 4,
        "requester_name": "DevOps Lead",
        "requester_dept": "Cloud Security"
    }
]

db = SessionLocal()

now_dt = datetime.now()

created_count = 0
for data in seed_tickets:
    sla_due = now_dt + timedelta(hours=data["sla_hours"])
    created_at_dt = now_dt - timedelta(minutes=10 * (14 - data["id"]))

    ticket = Ticket(
        id=data["id"],
        title=data["title"],
        description=data["description"],
        category=data["category"],
        priority=data["priority"],
        priority_confidence=0.98,
        status="open",
        assigned_team=data["assigned_team"],
        routing_confidence=0.98,
        top_alternative_teams=json.dumps([{"team": data["assigned_team"], "confidence": 0.98}]),
        is_low_confidence_routed=False,
        created_by=None,
        requester_name=data["requester_name"],
        requester_department=data["requester_dept"],
        created_at=created_at_dt,
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
print(f"  [SUCCESS] SEEDED EXACTLY {created_count} TICKETS (#1 TO #{created_count})!")
print("=======================================================================\n")
