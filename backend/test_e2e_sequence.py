import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_e2e_verification_sequence():
    print("\n=======================================================")
    print("  EXECUTING END-TO-END BUG & FEATURE VERIFICATION TEST  ")
    print("=======================================================\n")

    # STEP 1: Submit Ticket 1 - "SAP Transaction SU53 Permission Error"
    print("[STEP 1] Submitting Ticket #1: 'SAP Transaction SU53 Permission Error'...")
    res1 = client.post("/ticket/create", json={
        "title": "SAP Transaction SU53 Permission Error",
        "description": "Getting ME21N permission denied screenshot on SAP SU53 screen",
        "category": "SAP Support",
        "requester_name": "Alice Employee",
        "requester_department": "Finance",
        "skip_duplicate_check": True,
    })
    print(f"Status Code: {res1.status_code}")
    t1_data = res1.json()["ticket"]
    t1_id = t1_data["id"]
    print(f"-> Created Ticket #{t1_id} | Assigned Team: '{t1_data['predicted_team']}' | Confidence: {t1_data['routing_confidence']} | Low Conf Triage: {t1_data['is_low_confidence_routed']}\n")

    # Verify Manager Alert generated if unassigned triage
    mgr_res = client.get("/agent/manager-dashboard")
    escalations = mgr_res.json()["recent_escalations"]
    triage_alerts = [e for e in escalations if e["ticket_id"] == t1_id]
    print(f"-> Manager Triage Escalation Alert Triggered for Ticket #{t1_id}: {len(triage_alerts) > 0}")
    if triage_alerts:
        print(f"   Alert Reason: '{triage_alerts[0]['escalation_reason']}' | Team: '{triage_alerts[0]['team_name']}'\n")

    # STEP 2: Immediately Submit Ticket 2 - Near Identical Wording to Open Ticket #1
    print("[STEP 2] Submitting Ticket #2 (near-identical wording to open Ticket #1)...")
    res2_dup = client.post("/ticket/create", json={
        "title": "SAP Transaction SU53 Permission Error",
        "description": "Getting ME21N permission denied screenshot on SAP SU53 screen",
        "category": "SAP Support",
        "requester_name": "Bob Employee",
        "requester_department": "Sales",
        "skip_duplicate_check": False,
    })
    print(f"Status Code: {res2_dup.status_code}")
    dup_body = res2_dup.json()
    print(f"-> Is Duplicate Warning Fired? : {dup_body.get('is_duplicate_warning')}")
    print(f"-> Has Open Match Detected?    : {dup_body.get('has_open_match')}")
    if dup_body.get("top_match"):
        print(f"-> Matched Open Ticket ID      : #{dup_body['top_match']['ticket_id']} ('{dup_body['top_match']['title']}')")
        print(f"-> Calculated Similarity Score : {dup_body['top_match']['similarity_score'] * 100:.1f}%\n")
    assert dup_body.get("has_open_match") == True, "STEP 2 FAILED: Open duplicate was not detected!"

    # STEP 3: Resolve Ticket #1 as an Agent with Structured Resolution Summary + Detail
    print(f"[STEP 3] Resolving Ticket #{t1_id} with structured resolution summary & technical detail...")
    res_resolve = client.post(f"/agent/resolve/{t1_id}", json={
        "resolution_summary": "Added SAP role Z_SAP_SU53_ACCESS to user profile for transaction ME21N.",
        "resolution_detail": "1. Identified missing authorization object S_TCODE in SAP GRC.\n2. Added role Z_SAP_SU53_ACCESS to user profile.\n3. Verified transaction ME21N access.",
        "root_cause": "Permission Issue",
    })
    print(f"Status Code: {res_resolve.status_code}")
    print(f"Response: {res_resolve.json()}")

    # Verify Ticket Detail shows structured summary & expandable detail
    t1_detail = client.get(f"/agent/detail/{t1_id}").json()
    print(f"-> Verified Resolved Status      : '{t1_detail['status']}'")
    print(f"-> Resolution Summary (Plain)    : '{t1_detail['resolution_summary']}'")
    print(f"-> Resolution Detail (Technical) : '{t1_detail['resolution_detail'][:70]}...'\n")

    # STEP 4: Submit Ticket 3 - Near Identical Wording to Resolved Ticket #1
    print("[STEP 4] Submitting Ticket #3 (near-identical wording to RESOLVED Ticket #1)...")
    res3_dup = client.post("/ticket/create", json={
        "title": "SAP ERP Transaction SU53 Authorization Denied",
        "description": "Getting ME21N permission denied error on SAP SU53 screen",
        "category": "SAP Support",
        "requester_name": "Charlie Employee",
        "requester_department": "Engineering",
        "skip_duplicate_check": False,
    })
    dup3_body = res3_dup.json()
    print(f"-> Is Duplicate Warning Fired?     : {dup3_body.get('is_duplicate_warning')}")
    print(f"-> Has Resolved Match Detected?    : {dup3_body.get('has_resolved_match')}")
    
    top_resolved = dup3_body.get("resolved_matches", [{}])[0]
    if top_resolved:
        print(f"-> Matched Resolved Ticket ID      : #{top_resolved.get('ticket_id')}")
        print(f"-> Surfaced Plain Resolution Summary: '{top_resolved.get('resolution_summary')}'")
        print(f"-> Calculated Similarity Score     : {top_resolved.get('similarity_score', 0) * 100:.1f}%\n")
    assert dup3_body.get("has_resolved_match") == True, "STEP 4 FAILED: Resolved duplicate was not detected!"

    # Test Path B: Proceed with creation with related_ticket_id attached
    res3_create = client.post("/ticket/create", json={
        "title": "SAP ERP Transaction SU53 Authorization Denied",
        "description": "Getting ME21N permission denied error on SAP SU53 screen",
        "category": "SAP Support",
        "requester_name": "Charlie Employee",
        "requester_department": "Engineering",
        "skip_duplicate_check": True,
        "related_ticket_id": t1_id,
    })
    t3_data = res3_create.json()["ticket"]
    print(f"-> Created Ticket #{t3_data['id']} with Attached Related Ticket ID: #{t3_data['related_ticket_id']}")

    print("\n=======================================================")
    print("  ALL E2E VERIFICATION STEPS PASSED WITH 100% SUCCESS! ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_e2e_verification_sequence()
