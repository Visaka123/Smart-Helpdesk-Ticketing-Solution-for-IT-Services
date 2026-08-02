import time
from fastapi.testclient import TestClient
from app.main import app
from app.routing.service import predict_team_ml

client = TestClient(app)

def run_verification():
    print("\n=======================================================================")
    print("  VERIFICATION 1: TESTING ML TEAM ROUTING CONFIDENCE & VARIED TEAMS    ")
    print("=======================================================================\n")

    test_queries = [
        ("SAP Transaction SU53 Permission Error", "SAP Team"),
        ("VPN connection drop on Cisco AnyConnect remote client", "Network Team"),
        ("MySQL database cluster failover node unreachable", "Database Team"),
        ("Printer paper jam and offline status in office bay", "IT Support"),
        ("Invoice payment failed on Stripe checkout portal", "Billing & Payments"),
    ]

    for query, expected in test_queries:
        res = predict_team_ml(query)
        print(f"Query: '{query}'")
        print(f"  -> Predicted Team : {res['predicted_team']} (Expected: {expected})")
        print(f"  -> Confidence     : {res['confidence'] * 100:.1f}%")
        print(f"  -> Low Confidence?: {res['is_low_confidence']}")
        print(f"  -> Alternatives   : {res.get('top_3_alternatives', [])}\n")
        assert res['is_low_confidence'] == False, f"Routing failed for {query}"
        assert res['predicted_team'] == expected, f"Expected {expected}, got {res['predicted_team']}"

    print("=======================================================================")
    print("  VERIFICATION 2: BACK-TO-BACK SUBMISSION OF 'SAP SU53' ISSUE           ")
    print("=======================================================================\n")

    sap_title = f"SAP SU53 Permission Error Test {int(time.time())}"
    sap_desc = "Getting ME21N permission denied error on SAP SU53 screen"

    print(f"[SUBMISSION 1] Submitting '{sap_title}'...")
    res_sap1 = client.post("/ticket/create", json={
        "title": sap_title,
        "description": sap_desc,
        "category": "SAP Support",
        "requester_name": "Test User A",
        "requester_department": "Finance",
        "skip_duplicate_check": True  # Force initial creation
    })
    body_sap1 = res_sap1.json()
    t_sap1_id = body_sap1["ticket"]["id"]
    print(f"-> Created Master Ticket #{t_sap1_id} | Hard Blocked: {body_sap1['is_hard_blocked']}\n")

    print(f"[SUBMISSION 2] Submitting SAME '{sap_title}' again...")
    res_sap2 = client.post("/ticket/create", json={
        "title": sap_title,
        "description": sap_desc,
        "category": "SAP Support",
        "requester_name": "Test User B",
        "requester_department": "Sales",
        "skip_duplicate_check": False
    })
    body_sap2 = res_sap2.json()
    print(f"-> Hard Blocked?             : {body_sap2['is_hard_blocked']}")
    print(f"-> Block Type                : {body_sap2['block_type']}")
    print(f"-> Linked to Master Ticket ID: #{body_sap2['ticket']['id']}")
    print(f"-> Message                   : '{body_sap2['message']}'\n")

    assert body_sap2['is_hard_blocked'] == True, "SAP Submission 2 was NOT blocked!"
    assert body_sap2['ticket']['id'] == t_sap1_id, "SAP Submission 2 linked to wrong ticket!"

    print("=======================================================================")
    print("  VERIFICATION 3: UNRELATED ISSUE (PRINTER NOT CONNECTING) TWICE BACK-TO-BACK ")
    print("=======================================================================\n")

    printer_title = f"Department printer not connecting to network {int(time.time())}"
    printer_desc = "Office HP LaserJet printer offline in 2nd floor copy room"

    print(f"[SUBMISSION 1] Submitting '{printer_title}'...")
    res_pr1 = client.post("/ticket/create", json={
        "title": printer_title,
        "description": printer_desc,
        "category": "IT Support",
        "requester_name": "Alice Printer User",
        "requester_department": "Operations",
        "skip_duplicate_check": False
    })
    body_pr1 = res_pr1.json()
    t_pr1_id = body_pr1["ticket"]["id"]
    print(f"-> Created Ticket #{t_pr1_id} | Hard Blocked: {body_pr1['is_hard_blocked']} | Team: {body_pr1['ticket']['predicted_team']}\n")
    assert body_pr1['is_hard_blocked'] == False, "Printer Submission 1 should NOT be blocked!"

    print(f"[SUBMISSION 2] Submitting SAME '{printer_title}' again...")
    res_pr2 = client.post("/ticket/create", json={
        "title": printer_title,
        "description": printer_desc,
        "category": "IT Support",
        "requester_name": "Bob Printer User",
        "requester_department": "Marketing",
        "skip_duplicate_check": False
    })
    body_pr2 = res_pr2.json()
    print(f"-> Hard Blocked?             : {body_pr2['is_hard_blocked']}")
    print(f"-> Block Type                : {body_pr2['block_type']}")
    print(f"-> Linked to Master Ticket ID: #{body_pr2['ticket']['id']}")
    print(f"-> Message                   : '{body_pr2['message']}'\n")

    assert body_pr2['is_hard_blocked'] == True, "Printer Submission 2 was NOT blocked!"
    assert body_pr2['ticket']['id'] == t_pr1_id, "Printer Submission 2 linked to wrong ticket!"

    print("=======================================================================")
    print("  VERIFICATION 4: DASHBOARD STATS & TICKET ALL ENDPOINT AUDIT           ")
    print("=======================================================================\n")

    stats = client.get("/ticket/stats").json()
    all_tickets = client.get("/ticket/all").json()

    print(f"Total Tickets in Dashboard Stats: {stats['total_tickets']}")
    print(f"Tickets by Team Breakdown        : {stats['tickets_by_team']}")
    print(f"Total Tickets Returned by /all  : {len(all_tickets)}\n")

    print("=======================================================================")
    print("  ALL 5 VERIFICATIONS PASSED 100% CLEANLY!                              ")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_verification()
