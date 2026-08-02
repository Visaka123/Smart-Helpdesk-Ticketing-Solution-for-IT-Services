import sys
import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    print("=======================================================================")
    print("  VERIFYING AGENT WORKSPACE WORKFLOW & EMPLOYEE PORTAL SEPARATION     ")
    print("=======================================================================\n")

    # Headers for User #5 (Alice Employee - employee role)
    alice_headers = {
        "X-User-Id": "5",
        "X-User-Role": "employee",
        "X-User-Email": "alice@company.com",
        "X-User-Name": "Alice Employee"
    }

    # Headers for User #6 (Bob Sales Employee - employee role)
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
    # TEST 1: Agent Workspace Workflow (Open -> Controls -> Resolve)
    # -------------------------------------------------------------------
    print("[TEST 1] Testing Agent Workspace Workflow for Open Ticket #8...")

    # 1a. Fetch detail as agent
    res1 = client.get("/agent/detail/8", headers=agent_headers)
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}"
    detail1 = res1.json()
    print(f"-> Agent Detail Loaded: Ticket #{detail1['id']}, Status: '{detail1['status']}'")

    # 1b. Test changing priority and status inline
    res1_p = client.post("/agent/change-priority/8", json={"new_priority": "High"}, headers=agent_headers)
    assert res1_p.status_code == 200, f"Expected 200, got {res1_p.status_code}"
    print("-> Inline Priority Changed to 'High'.")

    res1_e = client.post("/agent/assign-engineer/8", json={"agent_name": "Dave Specialist"}, headers=agent_headers)
    assert res1_e.status_code == 200, f"Expected 200, got {res1_e.status_code}"
    print("-> Assigned Engineer 'Dave Specialist'.")

    # 1c. Post Public Reply from Agent
    res1_c = client.post("/agent/comment/8", json={
        "content": "Hi Alice, we have cleared the Cisco AnyConnect WFH VPN profile.",
        "author_name": "Dave Specialist",
        "author_role": "agent",
        "is_internal": False
    }, headers=agent_headers)
    assert res1_c.status_code == 200, f"Expected 200, got {res1_c.status_code}"
    print("-> Public Reply Posted by Support Specialist.")

    # 1d. Post Internal Note from Agent
    res1_in = client.post("/agent/comment/8", json={
        "content": "INTERNAL NOTE: Flushed RADIUS session table on gateway fw-01.",
        "author_name": "Dave Specialist",
        "author_role": "agent",
        "is_internal": True
    }, headers=agent_headers)
    assert res1_in.status_code == 200, f"Expected 200, got {res1_in.status_code}"
    print("-> Internal Note Posted by Support Specialist.")

    # 1e. Resolve Ticket #8
    res1_r = client.post("/agent/resolve/8", json={
        "resolution_summary": "Re-authenticated VPN client and cleared stale RADIUS session cache.",
        "resolution_detail": "Ran `vpn-gateway-cli flush-sessions --user=alice`. Verified connection uptime > 2 hours.",
        "root_cause": "Network Degradation"
    }, headers=agent_headers)
    assert res1_r.status_code == 200, f"Expected 200, got {res1_r.status_code}"
    print("-> Ticket #8 Resolved Successfully!")
    print("-> [SUCCESS] Agent Workspace Workflow Passed!\n")

    # -------------------------------------------------------------------
    # TEST 2: Employee Portal View, Support Reply Visibility & Strict Hiding
    # -------------------------------------------------------------------
    print("[TEST 2] Testing Employee Portal Detail View for Ticket #8...")

    res2 = client.get("/ticket/employee/8", headers=alice_headers)
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}"
    data2 = res2.json()

    print("-> Employee View Data Keys:", list(data2.keys()))
    print(f"-> Status: '{data2['status']}'")
    print(f"-> Resolution Summary: '{data2['resolution_summary']}'")

    # Verify public comment from support is visible in conversation
    public_comments = data2["comments"]
    print(f"-> Public Conversation Timeline Length: {len(public_comments)}")
    agent_public_comments = [c for c in public_comments if c["author_role"] == "agent"]
    assert len(agent_public_comments) > 0, "Public reply from agent was NOT found in employee conversation timeline!"
    print(f"-> Verified Agent Public Reply: '{agent_public_comments[0]['content']}'")

    # Verify 🔒 internal note is STRICTLY HIDDEN
    internal_comments = [c for c in public_comments if "INTERNAL NOTE" in c["content"]]
    assert len(internal_comments) == 0, "SECURITY BREACH: Internal note exposed to Employee!"

    # Verify forbidden fields are HIDDEN
    forbidden_fields = ["assigned_team", "predicted_team", "routing_confidence", "sla_badge", "sla_due_at", "resolution_detail", "root_cause", "linked_requesters"]
    for f_field in forbidden_fields:
        assert f_field not in data2, f"SECURITY BREACH: Internal field '{f_field}' was exposed to Employee view!"

    print("-> [SUCCESS] Support Replies Visible, Internal Notes & Tech Details Strictly Hidden!\n")

    # -------------------------------------------------------------------
    # TEST 3: RBAC Security Enforcement (HTTP 403 on Unauthorized Access)
    # -------------------------------------------------------------------
    print("[TEST 3] Testing RBAC Security Enforcement...")

    # Bob (User #6) tries accessing Alice's Ticket #8 -> 403
    res3_a = client.get("/ticket/employee/8", headers=bob_headers)
    print(f"-> Bob accessing Alice's Ticket #8: Status Code = {res3_a.status_code}")
    assert res3_a.status_code == 403, f"Expected HTTP 403 Forbidden, got {res3_a.status_code}"

    # Alice (User #5) tries accessing Agent Workspace /agent/detail/8 -> 403
    res3_b = client.get("/agent/detail/8", headers=alice_headers)
    print(f"-> Employee accessing Agent Workspace /agent/detail/8: Status Code = {res3_b.status_code}")
    assert res3_b.status_code == 403, f"Expected HTTP 403 Forbidden, got {res3_b.status_code}"

    print("-> [SUCCESS] RBAC Security & Ownership Validation Enforced (HTTP 403)!\n")

    # -------------------------------------------------------------------
    # TEST 4: Employee Actions (Rating & Reopen)
    # -------------------------------------------------------------------
    print("[TEST 4] Testing Satisfaction Rating & Reopen Actions...")

    # Rating
    res4_a = client.post("/ticket/employee/rate/8", json={"rating": 5, "feedback": "Resolved quickly, thanks!"}, headers=alice_headers)
    assert res4_a.status_code == 200, f"Expected 200, got {res4_a.status_code}"
    print("-> Satisfaction 5-Star Rating Submitted Successfully.")

    # Reopen
    res4_b = client.post("/ticket/employee/reopen/8", json={"reason": "VPN still drops when waking laptop from sleep"}, headers=alice_headers)
    assert res4_b.status_code == 200, f"Expected 200, got {res4_b.status_code}"
    print("-> Ticket Reopened Successfully.")

    # Check reopened status
    check_detail = client.get("/ticket/employee/8", headers=alice_headers).json()
    assert check_detail["status"] == "open", f"Expected status 'open', got '{check_detail['status']}'"
    print(f"-> Verified Reopened Status: '{check_detail['status']}'")

    print("\n=======================================================================")
    print("  ALL WORKSPACE & EMPLOYEE PORTAL TESTS PASSED WITH 100% CLEAN SUCCESS! ")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_tests()
