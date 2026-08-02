from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_system_validation():
    print("\n=======================================================================")
    print("  EXECUTING SMART HELPDESK AI END-TO-END SYSTEM VALIDATION TEST         ")
    print("=======================================================================\n")

    # 1. Test Chatbot Ask Endpoint (No 500 Error, Grounded RAG + Citations)
    print("[TEST 1] Testing Chatbot RAG Query ('SAP SU53 permission error')...")
    res1 = client.post("/chatbot/ask", json={"message": "SAP SU53 permission error"})
    assert res1.status_code == 200, f"Expected 200 OK, got {res1.status_code}"
    body1 = res1.json()
    print(f"-> Chatbot Status   : {res1.status_code} OK")
    print(f"-> Answer Length   : {len(body1['answer'])} chars")
    print(f"-> Sources Count   : {len(body1['sources'])}")
    for s in body1['sources']:
        print(f"   • [{s['document_type']}] {s['title']} ({s['relevance_pct']}% match) -> Download: {s['download_url']}")
    assert len(body1['sources']) > 0, "TEST 1 FAILED: Expected source citations"

    # 2. Test Proactive Knowledge Recommendations
    print("\n[TEST 2] Testing Proactive Knowledge Recommendations API...")
    res2 = client.post("/chatbot/recommendations", json={
        "title": "VPN connection drop on Cisco AnyConnect",
        "description": "Cisco AnyConnect remote client disconnects with certificate posture error",
    })
    assert res2.status_code == 200, f"Expected 200 OK, got {res2.status_code}"
    body2 = res2.json()
    print(f"-> Recommendations Status: {res2.status_code} OK")
    print(f"-> Recommended Articles  : {len(body2['recommended_articles'])}")
    for a in body2['recommended_articles']:
        print(f"   • [{a['document_type']}] {a['title']} (Relevance: {a['relevance_pct']}%)")
    assert len(body2['recommended_articles']) > 0, "TEST 2 FAILED: Expected recommendations"

    # 3. Test SOP Document Download Endpoint
    print("\n[TEST 3] Testing Document Download Endpoint...")
    res3 = client.get("/docs/download/SOP-SAP-001_SU53_Authorization_Guide.pdf")
    assert res3.status_code == 200, f"Expected 200 OK, got {res3.status_code}"
    print(f"-> Download Status: {res3.status_code} OK | Content Type: {res3.headers.get('content-type')}")

    # 4. Test Ticket Detail & ITSM Audit Logs
    print("\n[TEST 4] Testing Agent Workspace Detail & ITSM Audit Logs...")
    res4 = client.get("/agent/detail/2")
    assert res4.status_code == 200, f"Expected 200 OK, got {res4.status_code}"
    body4 = res4.json()
    print(f"-> Ticket Workspace Status: {res4.status_code} OK")
    print(f"-> Title                  : '{body4['title']}'")
    print(f"-> Linked Requesters Count: {body4['requester_count']}")
    print(f"-> Audit Comments Count   : {len(body4['comments'])}")

    print("\n=======================================================================")
    print("  ALL SYSTEM VALIDATION TESTS PASSED 100% CLEANLY (ZERO HTTP 500)!     ")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_system_validation()
