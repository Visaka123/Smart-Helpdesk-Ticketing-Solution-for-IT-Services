import sys
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    print("\n==========================================")
    print("  VERIFYING ALL FOUR ENDPOINTS FOR CLEAN SUCCESS")
    print("==========================================\n")

    # Endpoint 1: POST /ticket/route-ticket
    print("[1/4] Testing POST /ticket/route-ticket...")
    res1 = client.post("/ticket/route-ticket", json={"description": "Cisco AnyConnect VPN certificate error when connecting from home"})
    print(f"Status: {res1.status_code}")
    print(f"Response: {res1.json()}\n")
    assert res1.status_code == 200, "Endpoint 1 failed"

    # Endpoint 2: POST /ticket/create
    print("[2/4] Testing POST /ticket/create...")
    res2 = client.post("/ticket/create", json={
        "title": "SAP Transaction SU53 Permission Error",
        "description": "Getting ME21N permission denied screenshot on SAP SU53 screen",
        "category": "SAP Support",
        "requester_name": "Alice Employee",
        "requester_department": "Finance",
        "skip_duplicate_check": True
    })
    print(f"Status: {res2.status_code}")
    print(f"Response: {res2.json()}\n")
    assert res2.status_code == 200, "Endpoint 2 failed"

    # Endpoint 3: GET /agent/detail/{id}
    ticket_id = res2.json()["ticket"]["id"]
    print(f"[3/4] Testing GET /agent/detail/{ticket_id}...")
    res3 = client.get(f"/agent/detail/{ticket_id}")
    print(f"Status: {res3.status_code}")
    detail = res3.json()
    print(f"Ticket #{detail['id']} - Title: '{detail['title']}' | Priority: {detail['priority']} | Team: {detail['assigned_team']}")
    print(f"Similar Tickets Count: {len(detail['similar_tickets'])} | Suggested KB Count: {len(detail['suggested_kb_articles'])}\n")
    assert res3.status_code == 200, "Endpoint 3 failed"

    # Endpoint 4: POST /chatbot/ask
    print("[4/4] Testing POST /chatbot/ask...")
    res4 = client.post("/chatbot/ask", json={"message": "How do I reset my corporate password when locked out?"})
    print(f"Status: {res4.status_code}")
    bot_res = res4.json()
    print(f"Answer Sample: {bot_res['answer'][:120]}...")
    print(f"Sources Returned: {len(bot_res['sources'])}\n")
    assert res4.status_code == 200, "Endpoint 4 failed"

    print("==========================================")
    print("  ALL FOUR ENDPOINTS PASSED WITH 100% CLEAN SUCCESS!")
    print("==========================================\n")

if __name__ == "__main__":
    run_tests()
