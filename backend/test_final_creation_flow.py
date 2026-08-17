import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.models import Ticket

client = TestClient(app)

print("\n=======================================================================")
print("  EXECUTING FINAL END-TO-END TICKET CREATION & SYNCHRONIZATION TEST")
print("=======================================================================")

# 1. Create a realistic ticket
ticket_payload = {
    "title": "Monitor display flicker and USB docking station power failure",
    "description": "My secondary external monitor screen blinks randomly and the USB-C docking station loses power when connected.",
    "requester_name": "Sarah Connor",
    "requester_department": "Engineering",
    "skip_duplicate_check": True
}

# Fetch pre-creation stats
res_pre_stats = client.get("/ticket/stats")
pre_total = res_pre_stats.json().get("total_tickets", 0)

# Submit ticket creation
res_create = client.post("/ticket/create", json=ticket_payload)
assert res_create.status_code == 200
data = res_create.json()

assert not data["is_hard_blocked"], "Ticket creation was blocked unexpectedly"

created_ticket = data["ticket"]
ticket_id = created_ticket["id"]

print(f"\n[1] TICKET CREATED SUCCESSFULLY:")
print(f"    Ticket ID         : #{ticket_id}")
print(f"    Title             : {created_ticket['title']}")
print(f"    Predicted Category: {created_ticket['category']}")
print(f"    Assigned Team     : {created_ticket['assigned_team']}")
print(f"    Priority          : {created_ticket['priority']}")
print(f"    SLA Resolution    : {created_ticket['sla_hours']} hours (Due: {created_ticket['sla_due_at']})")

# 2. Verify Database Record
db = SessionLocal()
db_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

assert db_ticket is not None, f"Ticket #{ticket_id} not found in database!"
assert db_ticket.title == ticket_payload["title"]
assert db_ticket.category == "Hardware"

print(f"\n[2] DATABASE PERSISTENCE VERIFIED:")
print(f"    DB Ticket ID #{db_ticket.id} found in SQLite `smart_helpdesk.db`.")
print(f"    DB Category Column: {db_ticket.category}")
print(f"    DB Team Column    : {db_ticket.assigned_team}")

# 3. Verify Dashboard & Stats Synchronization
res_post_stats = client.get("/ticket/stats")
post_total = res_post_stats.json().get("total_tickets", 0)

assert post_total == pre_total + 1, f"Expected total tickets to be {pre_total + 1}, got {post_total}"

print(f"\n[3] DASHBOARD SYNCHRONIZATION VERIFIED:")
print(f"    Pre-creation total tickets : {pre_total}")
print(f"    Post-creation total tickets: {post_total} (Incremented by 1)")

# 4. Verify My Tickets API Synchronization
res_all = client.get("/ticket/all", headers={"X-User-Role": "employee", "X-User-Name": "Sarah Connor"})
user_tickets = res_all.json()
matching_ticket = next((t for t in user_tickets if t["id"] == ticket_id), None)

assert matching_ticket is not None, "Created ticket missing from My Tickets response!"

print(f"\n[4] MY TICKETS SYNCHRONIZATION VERIFIED:")
print(f"    Found Ticket #{matching_ticket['id']} ('{matching_ticket['title']}') in My Tickets queue.")
print(f"    Visible Category: {matching_ticket['category']}")
print(f"    Visible Priority: {matching_ticket['priority']}")

db.close()

print("\n=======================================================================")
print("[OK] ALL FINAL END-TO-END VERIFICATIONS PASSED CLEANLY!")
print("=======================================================================\n")
