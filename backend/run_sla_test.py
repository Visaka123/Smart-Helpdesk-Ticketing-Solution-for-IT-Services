"""
run_sla_test.py
Run once to backdate an open ticket's SLA due date to the past,
then hit GET /ticket/all to trigger the audit and send the escalation email.

Run from: smart-helpdesk/backend/
  python run_sla_test.py
"""
from app.database.database import SessionLocal
from app.models import Ticket, Team
from datetime import datetime, timedelta

from app.models import Team
from app.auth.hashing import hash_password

db = SessionLocal()

# Try to find any existing open ticket first
ticket = db.query(Ticket).filter(
    Ticket.status.in_(["open", "in_progress"]),
    Ticket.is_sla_breached == False
).order_by(Ticket.id.desc()).first()

# None found — create one on the spot
if not ticket:
    print("No open ticket found. Creating a test ticket...")
    ticket = Ticket(
        title="VPN Certificate Error — SLA Test Ticket",
        description="Cannot connect to corporate VPN. Cisco AnyConnect shows server certificate verification failed. Need urgent access to internal systems.",
        category="Network",
        priority="High",
        status="open",
        assigned_team="Network Team",
        requester_name="Alice Employee",
        requester_department="Finance",
        created_at=datetime.now() - timedelta(hours=30),
        sla_due_at=datetime.now() + timedelta(hours=1),  # will be overridden below
        is_sla_breached=False,
        escalated_to_manager=False,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    print(f"  Created ticket #{ticket.id}")

print(f"Using ticket #{ticket.id}: '{ticket.title}'")
print(f"  Current SLA due: {ticket.sla_due_at}")

ticket.sla_due_at           = datetime.now() - timedelta(minutes=45)
ticket.is_sla_breached      = False
ticket.escalated_to_manager = False

db.commit()
db.close()

print(f"  Backdated SLA to 45 mins ago (overdue)")
print()
print("Now trigger the audit by visiting:")
print("  http://localhost:8000/ticket/all")
print()
print("Watch the backend terminal for:")
print("  [SLA ESCALATION] Ticket #X BREACHED!")
print("  [EMAIL SENT] Escalation email sent to visakavisaka2705@gmail.com")
