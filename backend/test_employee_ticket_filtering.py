import sys
import os

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    print("=======================================================================")
    print("  VERIFYING STRICT EMPLOYEE TICKET LIST FILTERING & ACCESS GUARANTEE  ")
    print("=======================================================================\n")

    # Headers for Alice Employee (User #5)
    alice_headers = {
        "X-User-Id": "5",
        "X-User-Role": "employee",
        "X-User-Email": "alice@company.com",
        "X-User-Name": "Alice Employee"
    }

    # Headers for Bob Sales Employee (User #6)
    bob_headers = {
        "X-User-Id": "6",
        "X-User-Role": "employee",
        "X-User-Email": "bob@company.com",
        "X-User-Name": "Bob Sales Employee"
    }

    # Headers for Support Agent (agent role)
    agent_headers = {
        "X-User-Id": "3",
        "X-User-Role": "agent",
        "X-User-Email": "agent@helpdesk.com",
        "X-User-Name": "Sarah Agent"
    }

    # -------------------------------------------------------------------
    # TEST 1: Alice's Ticket List & Detail Access
    # -------------------------------------------------------------------
    print("[TEST 1] Checking 'My Tickets' list for Alice Employee (User #5)...")
    res1_all = client.get("/ticket/all", headers=alice_headers)
    assert res1_all.status_code == 200, f"Expected 200, got {res1_all.status_code}"
    alice_tickets_all = res1_all.json()

    res1_my = client.get("/ticket/my-tickets", headers=alice_headers)
    assert res1_my.status_code == 200, f"Expected 200, got {res1_my.status_code}"
    alice_tickets_my = res1_my.json()

    print(f"-> Alice GET /ticket/all returned {len(alice_tickets_all)} ticket(s).")
    print(f"-> Alice GET /ticket/my-tickets returned {len(alice_tickets_my)} ticket(s).")

    # Verify EVERY ticket listed opens without 403 Access Denied
    for t in alice_tickets_all:
        tid = t["id"]
        detail_res = client.get(f"/ticket/employee/{tid}", headers=alice_headers)
        assert detail_res.status_code == 200, f"ERROR: Ticket #{tid} in Alice's list returned HTTP {detail_res.status_code} Access Denied!"
    print("-> [SUCCESS] 100% of tickets in Alice's list open successfully with ZERO 403 Access Denied errors!")

    # -------------------------------------------------------------------
    # TEST 2: Bob's Ticket List & Detail Access
    # -------------------------------------------------------------------
    print("\n[TEST 2] Checking 'My Tickets' list for Bob Sales Employee (User #6)...")
    res2_all = client.get("/ticket/all", headers=bob_headers)
    assert res2_all.status_code == 200, f"Expected 200, got {res2_all.status_code}"
    bob_tickets_all = res2_all.json()

    res2_my = client.get("/ticket/my-tickets", headers=bob_headers)
    assert res2_my.status_code == 200, f"Expected 200, got {res2_my.status_code}"
    bob_tickets_my = res2_my.json()

    print(f"-> Bob GET /ticket/all returned {len(bob_tickets_all)} ticket(s).")
    print(f"-> Bob GET /ticket/my-tickets returned {len(bob_tickets_my)} ticket(s).")

    # Verify EVERY ticket listed opens without 403 Access Denied
    for t in bob_tickets_all:
        tid = t["id"]
        detail_res = client.get(f"/ticket/employee/{tid}", headers=bob_headers)
        assert detail_res.status_code == 200, f"ERROR: Ticket #{tid} in Bob's list returned HTTP {detail_res.status_code} Access Denied!"
    print("-> [SUCCESS] 100% of tickets in Bob's list open successfully with ZERO 403 Access Denied errors!")

    # Verify Bob and Alice do not see each other's tickets
    alice_tids = set(t["id"] for t in alice_tickets_all)
    bob_tids = set(t["id"] for t in bob_tickets_all)
    overlap = alice_tids.intersection(bob_tids)
    print(f"-> Ticket ID Overlap between Alice and Bob: {list(overlap)}")
    assert len(overlap) == 0, f"SECURITY ERROR: Tickets {overlap} are visible to both Alice and Bob!"
    print("-> [SUCCESS] Zero ticket overlap between employees!")

    # -------------------------------------------------------------------
    # TEST 3: Support Agent / Admin View
    # -------------------------------------------------------------------
    print("\n[TEST 3] Checking Support Agent View...")
    res3 = client.get("/ticket/all", headers=agent_headers)
    assert res3.status_code == 200, f"Expected 200, got {res3.status_code}"
    agent_tickets = res3.json()

    print(f"-> Support Agent GET /ticket/all returned {len(agent_tickets)} ticket(s) (Full system view).")
    assert len(agent_tickets) >= len(alice_tickets_all) + len(bob_tickets_all), "Agent view should see all tickets in the system!"

    for t in agent_tickets:
        tid = t["id"]
        agent_detail = client.get(f"/agent/detail/{tid}", headers=agent_headers)
        assert agent_detail.status_code == 200, f"Support Agent should be able to view Ticket #{tid}!"
    print("-> [SUCCESS] Support Agent can view and open all system tickets!")

    print("\n=======================================================================")
    print("  ALL EMPLOYEE FILTERING TESTS PASSED WITH 100% CLEAN SUCCESS!         ")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_tests()
