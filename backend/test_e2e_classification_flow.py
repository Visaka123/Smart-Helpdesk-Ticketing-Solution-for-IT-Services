import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("\n=======================================================")
print("  TEST 1: /ticket/route-ticket (Live ML Preview)")
print("=======================================================")
route_req = {
    "title": "SAP Transaction SU53 Permission Error",
    "description": "User getting authorization denied error on SAP SU53 screen when accessing purchase orders.",
    "department": "Finance"
}
res1 = client.post("/ticket/route-ticket", json=route_req)
print(f"Status Code: {res1.status_code}")
print(f"Response Payload:\n{res1.json()}")
assert res1.status_code == 200
data1 = res1.json()
assert "predicted_team" in data1
assert "confidence" in data1
assert "suggested_category" in data1
assert "priority" in data1
print("[OK] Live ML preview route test passed!\n")

print("=======================================================")
print("  TEST 2: /ticket/create (Ticket Creation & ML DB Save)")
print("=======================================================")
create_req = {
    "title": "Network VPN disconnect issue in office",
    "description": "Cisco AnyConnect VPN disconnected repeatedly with certificate error when connected to corporate Wi-Fi.",
    "category": "General IT",
    "requester_name": "Test User",
    "requester_department": "Engineering",
    "skip_duplicate_check": True
}
res2 = client.post("/ticket/create", json=create_req)
print(f"Status Code: {res2.status_code}")
print(f"Response Payload:\n{res2.json()}")
assert res2.status_code == 200
data2 = res2.json()
assert data2["is_hard_blocked"] == False
ticket = data2["ticket"]
print(f"\nCreated Ticket ID        : #{ticket['id']}")
print(f"Predicted Support Team   : {ticket['predicted_team']}")
print(f"Routing Confidence       : {ticket['routing_confidence']}")
print(f"Ticket Category (Saved)  : {ticket['category']}")
print(f"Priority                 : {ticket['priority']}")
print(f"Priority Confidence      : {ticket['priority_confidence']}")
print(f"SLA Due At               : {ticket['sla_due_at']}")
print(f"SLA Hours Target         : {ticket['sla_hours']} hours")
print(f"Is Low Confidence Routed : {ticket['is_low_confidence_routed']}")
print("[OK] End-to-end ticket creation & database saving test passed!\n")
