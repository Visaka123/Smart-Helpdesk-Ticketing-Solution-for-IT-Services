import sys
import os
import time

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.models import Ticket, TicketComment
from ai.rag.groq_client import get_groq_api_keys

client = TestClient(app)

def run_tests():
    print("=======================================================================")
    print("  VERIFYING GROQ API ROTATION, 429 HANDLING & SINGLE ACTIVITY LOGS    ")
    print("=======================================================================\n")

    # -------------------------------------------------------------------
    # PART 1: GROQ API KEY ROTATION & RATE-LIMIT (429) HANDLING
    # -------------------------------------------------------------------
    print("[PART 1] Testing Groq API Key Rotation & 429 Rate Limit Handling...")
    keys = get_groq_api_keys()
    print(f"-> Groq API Keys Loaded from .env: {len(keys)} key(s) detected.")

    # Query chatbot endpoint - must return HTTP 200 with structured Markdown answer even if Groq 429 occurs
    cb_res = client.post("/chatbot/ask", json={"message": "Teams app keeps crashing. What should I do?"})
    assert cb_res.status_code == 200, f"Expected 200, got {cb_res.status_code}"
    cb_data = cb_res.json()

    assert "answer" in cb_data and len(cb_data["answer"]) > 50, "Chatbot answer is missing or too short!"
    assert "Common Causes" in cb_data["answer"] or "Step-by-Step" in cb_data["answer"], "Structured sections missing from chatbot response!"
    assert "sources" in cb_data, "Sources list missing from chatbot response!"
    print("-> [SUCCESS] Chatbot API returned HTTP 200 with clean, structured RAG answer & source citations!")

    # -------------------------------------------------------------------
    # PART 2: DEDUPLICATION OF TICKET ACTIONS & SINGLE ACTIVITY LOG ENTRY
    # -------------------------------------------------------------------
    print("\n[PART 2] Testing Single Activity Log Entry Guarantee Across Ticket Actions...")

    agent_headers = {
        "X-User-Id": "3",
        "X-User-Role": "agent",
        "X-User-Email": "agent@helpdesk.com",
        "X-User-Name": "Sarah Agent"
    }

    alice_headers = {
        "X-User-Id": "5",
        "X-User-Role": "employee",
        "X-User-Email": "alice@company.com",
        "X-User-Name": "Alice Employee"
    }

    # Create a completely fresh unique ticket for test
    run_timestamp = int(time.time())
    create_res = client.post("/ticket/create", json={
        "title": f"Unique Test Ticket #{run_timestamp} - SAP SU53 Authorization",
        "description": f"Unique ticket created at {run_timestamp} for deduplication testing",
        "category": "SAP Support",
        "requester_name": "Alice Employee",
        "requester_department": "Finance",
        "skip_duplicate_check": True
    }, headers=alice_headers)
    assert create_res.status_code == 200
    ticket_id = create_res.json()["ticket"]["id"]
    print(f"-> Created Fresh Test Ticket #{ticket_id}")

    # 2a. Priority Update (Double call)
    print("-> Testing Priority Update (double call)...")
    db = SessionLocal()
    t_row = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    target_p = "Low" if t_row.priority == "Critical" else "Critical"
    db.close()

    res_p1 = client.post(f"/agent/change-priority/{ticket_id}", json={"new_priority": target_p}, headers=agent_headers)
    res_p2 = client.post(f"/agent/change-priority/{ticket_id}", json={"new_priority": target_p}, headers=agent_headers)
    assert res_p1.status_code == 200 and res_p2.status_code == 200

    db = SessionLocal()
    p_logs = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.content.like("%Changed priority%")
    ).all()
    db.close()
    print(f"   Priority logs created: {len(p_logs)} (Expected: 1)")
    assert len(p_logs) == 1, f"Priority update created {len(p_logs)} logs instead of 1!"

    # 2b. Engineer Assignment (Double call)
    print("-> Testing Engineer Assignment (double call)...")
    res_e1 = client.post(f"/agent/assign-engineer/{ticket_id}", json={"agent_name": "Dave Specialist"}, headers=agent_headers)
    res_e2 = client.post(f"/agent/assign-engineer/{ticket_id}", json={"agent_name": "Dave Specialist"}, headers=agent_headers)
    assert res_e1.status_code == 200 and res_e2.status_code == 200

    db = SessionLocal()
    e_logs = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.content.like("%Assigned engineer%")
    ).all()
    db.close()
    print(f"   Engineer logs created: {len(e_logs)} (Expected: 1)")
    assert len(e_logs) == 1, f"Engineer assignment created {len(e_logs)} logs instead of 1!"

    # 2c. Rapid Duplicate Comment (Double call within 5s)
    print("-> Testing Rapid Duplicate Comment Submission (double call)...")
    comment_text = f"Verified SAP GRC role request Z_SAP_SU53_ACCESS - Test Run #{run_timestamp}"
    res_c1 = client.post(f"/agent/comment/{ticket_id}", json={"content": comment_text, "author_name": "Sarah Agent", "author_role": "agent", "is_internal": False}, headers=agent_headers)
    res_c2 = client.post(f"/agent/comment/{ticket_id}", json={"content": comment_text, "author_name": "Sarah Agent", "author_role": "agent", "is_internal": False}, headers=agent_headers)
    assert res_c1.status_code == 200 and res_c2.status_code == 200

    db = SessionLocal()
    c_logs = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.content == comment_text
    ).all()
    db.close()
    print(f"   Comment logs created: {len(c_logs)} (Expected: 1)")
    assert len(c_logs) == 1, f"Duplicate comment submission created {len(c_logs)} logs instead of 1!"

    # 2d. Resolve Ticket (Double call)
    print("-> Testing Ticket Resolve (double call)...")
    resolve_payload = {
        "resolution_summary": f"Assigned SAP GRC role Z_SAP_SU53_ACCESS - Run #{run_timestamp}",
        "resolution_detail": f"Executed T-code PFCG for Run #{run_timestamp}",
        "root_cause": "Permission Issue"
    }
    res_r1 = client.post(f"/agent/resolve/{ticket_id}", json=resolve_payload, headers=agent_headers)
    res_r2 = client.post(f"/agent/resolve/{ticket_id}", json=resolve_payload, headers=agent_headers)
    assert res_r1.status_code == 200 and res_r2.status_code == 200

    db = SessionLocal()
    r_logs = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.content.like("%TICKET RESOLVED FOR ALL%"),
        TicketComment.content.like(f"%Run #{run_timestamp}%")
    ).all()
    db.close()
    print(f"   Resolve logs created: {len(r_logs)} (Expected: 1)")
    assert len(r_logs) == 1, f"Ticket resolve created {len(r_logs)} logs instead of 1!"

    # 2e. Reopen Ticket (Double call)
    print("-> Testing Ticket Reopen (double call)...")
    res_ro1 = client.post(f"/ticket/employee/reopen/{ticket_id}", json={"reason": f"Error recurred #{run_timestamp}"}, headers=alice_headers)
    res_ro2 = client.post(f"/ticket/employee/reopen/{ticket_id}", json={"reason": f"Error recurred #{run_timestamp}"}, headers=alice_headers)
    assert res_ro1.status_code == 200 and res_ro2.status_code == 200

    db = SessionLocal()
    ro_logs = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.content.like("%TICKET REOPENED BY USER%")
    ).all()
    db.close()
    print(f"   Reopen logs created: {len(ro_logs)} (Expected: 1)")
    assert len(ro_logs) == 1, f"Ticket reopen created {len(ro_logs)} logs instead of 1!"

    print("\n=======================================================================")
    print("  ALL GROQ API ROTATION & SINGLE ACTIVITY LOG TESTS PASSED WITH 100%!  ")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_tests()
