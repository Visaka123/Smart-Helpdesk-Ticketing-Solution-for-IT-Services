import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_hard_block_e2e_sequence():
    print("\n=======================================================================")
    print("  EXECUTING HARD BLOCK DUPLICATE & LINKED REQUESTERS VERIFICATION TEST  ")
    print("=======================================================================\n")

    unique_suffix = f"Run{int(time.time())}"
    title1 = f"Cluster Database Failover {unique_suffix}"
    title2 = f"Cluster Database Failover {unique_suffix}"
    title3 = f"Cluster Database Failover {unique_suffix}"
    title4 = f"Cluster Database Failover {unique_suffix}"

    desc = f"MySQL primary node unreachable in datacenter region {unique_suffix}"

    # Step 1: User A submits issue -> 1 master ticket created in agent queue
    print(f"[STEP 1] User A (Alice) submits initial Master Ticket '{title1}'...")
    res_a = client.post("/ticket/create", json={
        "title": title1,
        "description": desc,
        "category": "Database",
        "requester_name": "Alice (User A)",
        "requester_department": "Engineering",
        "skip_duplicate_check": True,
    })
    body_a = res_a.json()
    t1_id = body_a["ticket"]["id"]
    print(f"-> Created Master Ticket #{t1_id} | Hard Blocked: {body_a['is_hard_blocked']}")

    queue1 = client.get("/agent/queue").json()
    sap_tickets1 = [t for t in queue1 if unique_suffix in t["title"]]
    print(f"-> Agent Queue Total Tickets for '{unique_suffix}' Issue: {len(sap_tickets1)} (Ticket #{t1_id})\n")
    assert len(sap_tickets1) == 1, "STEP 1 FAILED: Expected exactly 1 ticket in queue"

    # Step 2: User B submits matching issue -> NO NEW TICKET CREATED, B linked to Ticket #1
    print(f"[STEP 2] User B (Bob) submits matching issue '{title2}'...")
    res_b = client.post("/ticket/create", json={
        "title": title2,
        "description": desc,
        "category": "Database",
        "requester_name": "Bob (User B)",
        "requester_department": "Sales",
        "skip_duplicate_check": False,
    })
    body_b = res_b.json()
    print(f"-> Hard Blocked?             : {body_b['is_hard_blocked']}")
    print(f"-> Block Type                : {body_b['block_type']}")
    print(f"-> Linked to Master Ticket ID: #{body_b['ticket']['id']}")
    print(f"-> User Message              : '{body_b['message']}'")
    assert body_b["is_hard_blocked"] == True, "STEP 2 FAILED: User B was not hard blocked!"
    assert body_b["ticket"]["id"] == t1_id, f"STEP 2 FAILED: User B linked to #{body_b['ticket']['id']} instead of #{t1_id}"

    queue2 = client.get("/agent/queue").json()
    sap_tickets2 = [t for t in queue2 if unique_suffix in t["title"]]
    print(f"-> Agent Queue Total Tickets for '{unique_suffix}' Issue: {len(sap_tickets2)} (STILL EXACTLY 1 TICKET IN QUEUE!)")
    print(f"-> Linked Requesters Count on Ticket #{t1_id}: {sap_tickets2[0]['requester_count']} ({', '.join(sap_tickets2[0]['all_requester_names'])})\n")
    assert len(sap_tickets2) == 1, "STEP 2 FAILED: Duplicate ticket was created in agent queue!"

    # Step 3: User C submits matching issue -> NO NEW TICKET CREATED, 3 linked users
    print(f"[STEP 3] User C (Charlie) submits matching issue '{title3}'...")
    res_c = client.post("/ticket/create", json={
        "title": title3,
        "description": desc,
        "category": "Database",
        "requester_name": "Charlie (User C)",
        "requester_department": "Finance",
        "skip_duplicate_check": False,
    })
    body_c = res_c.json()
    print(f"-> Hard Blocked?             : {body_c['is_hard_blocked']}")
    print(f"-> Linked to Master Ticket ID: #{body_c['ticket']['id']}")
    assert body_c["is_hard_blocked"] == True, "STEP 3 FAILED: User C was not hard blocked!"

    detail_c = client.get(f"/agent/detail/{t1_id}").json()
    queue3 = client.get("/agent/queue").json()
    sap_tickets3 = [t for t in queue3 if unique_suffix in t["title"]]
    print(f"-> Agent Queue Total Tickets for '{unique_suffix}' Issue: STILL EXACTLY 1 TICKET IN QUEUE!")
    print(f"-> Linked Requesters Count on Ticket #{t1_id}: {detail_c['requester_count']} ({', '.join([r['name'] for r in detail_c['linked_requesters']])})\n")
    assert len(sap_tickets3) == 1, "STEP 3 FAILED: Duplicate ticket was created in agent queue!"

    # Step 4: Agent resolves Ticket #1 with summary + detail -> Resolves for A, B, C simultaneously
    print(f"[STEP 4] Support Agent resolves Ticket #{t1_id} with single close action...")
    res_resolve = client.post(f"/agent/resolve/{t1_id}", json={
        "resolution_summary": "Promoted secondary database node to primary master and restored sync.",
        "resolution_detail": "1. Executed failover script `sys_db_failover.sh`.\n2. Re-routed virtual IP to node-02.",
        "root_cause": "Hardware Defect",
    })
    resolve_body = res_resolve.json()
    print(f"-> Single Resolve Action Response: {resolve_body}")

    detail_resolved = client.get(f"/agent/detail/{t1_id}").json()
    print(f"-> Ticket #{t1_id} Status for ALL Linked Users: '{detail_resolved['status']}'")
    print(f"-> Surfaced Resolution Summary: '{detail_resolved['resolution_summary']}'\n")

    # Step 5: User D submits matching issue after resolution -> NO NEW TICKET CREATED, hard blocked!
    print(f"[STEP 5] User D (David) submits matching issue after resolution...")
    res_d = client.post("/ticket/create", json={
        "title": title4,
        "description": desc,
        "category": "Database",
        "requester_name": "David (User D)",
        "requester_department": "Human Resources",
        "skip_duplicate_check": False,
    })
    body_d = res_d.json()
    print(f"-> Hard Blocked?                  : {body_d['is_hard_blocked']}")
    print(f"-> Block Type                     : {body_d['block_type']}")
    print(f"-> Message                        : '{body_d['message']}'")
    assert body_d["is_hard_blocked"] == True, "STEP 5 FAILED: User D was not hard blocked!"

    queue_final = client.get("/agent/queue").json()
    open_sap_tickets = [t for t in queue_final if unique_suffix in t["title"] and t["status"] in ["open", "in_progress"]]
    print(f"-> Final Open Tickets in Agent Queue for '{unique_suffix}' Issue: {len(open_sap_tickets)}\n")
    assert len(open_sap_tickets) == 0, "STEP 5 FAILED: Open ticket remained in queue!"

    print("=======================================================================")
    print("  HARD BLOCK & LINKED REQUESTERS VERIFICATION TEST PASSED 100%!        ")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_hard_block_e2e_sequence()
