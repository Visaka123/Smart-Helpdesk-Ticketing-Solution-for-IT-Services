import json
import os
import re
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Request, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.database.database import SessionLocal
from app.models import Ticket, TicketRequester, TicketComment, User, SLAEscalationLog, Team, TicketAttachment
from app.routing.service import predict_team_ml, predict_ticket_category, post_process_category, route_team_with_llm, classify_and_route_ticket
from app.priority.service import predict_priority_enhanced
from app.sla.service import calculate_sla_due_at, audit_and_trigger_sla_escalations
from app.duplicate.service import detect_hybrid_duplicates, record_duplicate_feedback
from app.chatbot.service import RAG_chatbot_query
from app.auth.rbac import get_current_user_from_headers
from app.availability.service import assign_agent_for_ticket
from app.suggestions.service import (
    find_suggested_fixes,
    record_suggestion_feedback,
    get_deflection_analytics,
)
from app.tickets.service import clean_ticket_title

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "attachments")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_ATTACHMENT_SIZE = 15 * 1024 * 1024  # 15 MB
DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".msi", ".vbs", ".js", ".vbe",
    ".com", ".scr", ".pif", ".bin", ".cpl", ".gadget", ".hta", ".wsf"
}

def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    else:
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"

class TicketCreateRequest(BaseModel):
    title: str
    description: str
    category: Optional[str] = None
    requester_name: Optional[str] = "Alice Employee"
    requester_department: Optional[str] = "Finance"
    skip_duplicate_check: Optional[bool] = False
    is_demo: Optional[bool] = False
    suggestions_tried: Optional[Any] = None

class RouteTicketRequest(BaseModel):
    title: Optional[str] = ""
    description: str
    department: Optional[str] = "General"

class DuplicateCheckRequest(BaseModel):
    title: str
    description: str

class SuggestFixesRequest(BaseModel):
    title: str
    description: str
    category: Optional[str] = None

class SuggestionFeedbackRequest(BaseModel):
    suggestion_ticket_id: int
    action: str  # "solved" | "not_helpful" | "still_need_help"
    relevance: Optional[float] = 0.0
    query_text: Optional[str] = ""

class FollowTicketRequest(BaseModel):
    requester_name: Optional[str] = "Alice Employee"
    requester_department: Optional[str] = "Finance"
    similarity_score: Optional[float] = 0.0
    new_ticket_text: Optional[str] = ""

class DuplicateDecisionRequest(BaseModel):
    ticket_text: Optional[str] = ""
    matched_ticket_id: Optional[int] = None
    similarity_score: Optional[float] = 0.0
    decision: str  # "followed", "submitted_anyway", "dismissed"

class EmployeeCommentRequest(BaseModel):
    content: str

class EmployeeRatingRequest(BaseModel):
    rating: int  # 1 to 5
    feedback: Optional[str] = ""

class EmployeeReopenRequest(BaseModel):
    reason: Optional[str] = "Issue recurred"

@router.post("/route-ticket")
def route_ticket_endpoint(req: RouteTicketRequest):
    # Single-pass LLM Classification & Routing
    title = req.title or ""
    desc = req.description or ""
    llm_res = classify_and_route_ticket(title, desc)

    category = llm_res["category"]
    assigned_team = llm_res["assigned_team"]
    priority = llm_res["priority"]
    sla_target = llm_res["sla_target"]

    return {
        "predicted_category": category,
        "raw_category": category,
        "category_confidence": 0.95,
        "top_3_categories": [{"category": category, "confidence": 0.95}],
        "predicted_team": assigned_team,
        "suggested_team": assigned_team,
        "routing_confidence": 0.95,
        "is_low_confidence": False,
        "top_3_alternatives": [{"team": assigned_team, "confidence": 0.95}],
        "priority": priority,
        "sla_target": sla_target,
        "priority_confidence": 0.95,
        "priority_reasons": ["Single-pass LLM ITSM Dispatcher"],
    }

@router.post("/check-duplicate")
def check_duplicate_endpoint(req: DuplicateCheckRequest, request: Request):
    db = SessionLocal()
    try:
        dup_res = detect_hybrid_duplicates(req.title, req.description)

        def annotate_match(m):
            if not m or "ticket_id" not in m:
                return m
            t_obj = db.query(Ticket).filter(Ticket.id == m["ticket_id"]).first()
            if t_obj:
                m["is_own_ticket"] = is_ticket_owned_by_user(t_obj, request, db)
            else:
                m["is_own_ticket"] = False
            return m

        if dup_res.get("top_match"):
            annotate_match(dup_res["top_match"])
        for m in dup_res.get("open_matches", []):
            annotate_match(m)
        for m in dup_res.get("resolved_matches", []):
            annotate_match(m)
        for m in dup_res.get("matched_tickets", []):
            annotate_match(m)

        return dup_res
    finally:
        db.close()

@router.post("/{ticket_id}/follow")
@router.post("/follow/{ticket_id}")
def follow_ticket_endpoint(ticket_id: int, req: FollowTicketRequest, request: Request):
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        user = get_current_user_from_headers(request, db)
        user_id = user.id if user else None
        req_name = req.requester_name or (user.name if user else "Alice Employee")
        req_dept = req.requester_department or (user.department if user else "General")

        existing_link = db.query(TicketRequester).filter(
            TicketRequester.ticket_id == ticket_id,
            TicketRequester.requester_name == req_name
        ).first()

        if not existing_link:
            link = TicketRequester(
                ticket_id=ticket_id,
                user_id=user_id,
                requester_name=req_name,
                requester_department=req_dept,
                link_reason="followed_similar_incident"
            )
            db.add(link)
            db.commit()

        # Telemetry log
        record_duplicate_feedback(
            new_ticket_text=req.new_ticket_text or f"Followed Ticket #{ticket_id}",
            matched_ticket_id=ticket_id,
            similarity_score=float(req.similarity_score or 0.0),
            user_action="followed",
            db=db
        )

        requester_count = 1 + db.query(TicketRequester).filter(TicketRequester.ticket_id == ticket_id).count()

        return {
            "success": True,
            "message": f"You will get updates on #{ticket_id}",
            "ticket_id": ticket_id,
            "requester_count": requester_count
        }
    finally:
        db.close()

@router.post("/log-duplicate-decision")
def log_duplicate_decision_endpoint(req: DuplicateDecisionRequest):
    record_duplicate_feedback(
        new_ticket_text=req.ticket_text or "Decision logged",
        matched_ticket_id=req.matched_ticket_id,
        similarity_score=float(req.similarity_score or 0.0),
        user_action=req.decision
    )
    return {"success": True, "decision": req.decision}

@router.post("/suggest-fixes")
@router.post("/tickets/suggest-fixes")
def suggest_fixes_endpoint(req: SuggestFixesRequest):
    """
    Suggests previously resolved tickets with similar issues ("Fixes that worked before").
    Graceful degradation: on error, returns empty list without breaking the caller.
    """
    db = SessionLocal()
    try:
        results = find_suggested_fixes(
            title=req.title or "",
            description=req.description or "",
            category=req.category,
            db=db,
        )
        return results
    except Exception as e:
        print(f"[WARN] Error in suggest_fixes_endpoint: {e}")
        return []
    finally:
        db.close()

@router.post("/suggest-fixes/feedback")
@router.post("/tickets/suggest-fixes/feedback")
def suggestion_feedback_endpoint(req: SuggestionFeedbackRequest, request: Request):
    """
    Stores suggestion feedback ("solved", "not_helpful", "still_need_help").
    """
    db = SessionLocal()
    try:
        user = get_current_user_from_headers(request, db)
        user_id = user.id if user else None
        record_suggestion_feedback(
            suggestion_ticket_id=req.suggestion_ticket_id,
            action=req.action,
            relevance=req.relevance or 0.0,
            user_id=user_id,
            query_text=req.query_text or "",
            db=db,
        )
        return {"status": "ok", "action": req.action, "suggestion_ticket_id": req.suggestion_ticket_id}
    except Exception as e:
        print(f"[WARN] Error in suggestion_feedback_endpoint: {e}")
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()

@router.get("/analytics/deflection")
def deflection_analytics_endpoint():
    """
    Calculates deflection metrics: suggestions shown, solved count, deflection rate, top helpful tickets.
    """
    db = SessionLocal()
    try:
        metrics = get_deflection_analytics(db=db)
        return metrics
    except Exception as e:
        print(f"[WARN] Error in deflection_analytics_endpoint: {e}")
        return {
            "suggestions_shown": 0,
            "solved_count": 0,
            "deflection_rate": 0.0,
            "top_helpful_tickets": []
        }
    finally:
        db.close()

@router.post("/create")
def create_ticket(req: TicketCreateRequest, request: Request):
    req.title = clean_ticket_title(req.title)
    print(f"\n=======================================================")
    print(f"[TICKET CREATE ENDPOINT INVOCATION] Received Request:")
    print(f"  Title     : '{req.title}'")
    print(f"  Category  : '{req.category}'")
    print(f"  Requester : '{req.requester_name}' ({req.requester_department})")
    print(f"  SkipCheck : {req.skip_duplicate_check}")
    print(f"=======================================================")

    db = SessionLocal()

    user = get_current_user_from_headers(request, db)
    created_by_id = user.id if user else None
    req_name = req.requester_name or (user.name if user else "Alice Employee")
    req_dept = req.requester_department or (user.department if user else "General")

    # 0. RAPID RE-SUBMISSION & UPSERT DEDUPLICATION CHECK
    recent_dup = db.query(Ticket).filter(
        Ticket.title == req.title.strip(),
        Ticket.description == req.description.strip(),
        Ticket.status.in_(["open", "in_progress", "new"])
    ).order_by(Ticket.created_at.desc()).first()

    if recent_dup:
        print(f"[UPSERT DEDUPLICATION] Found existing matching open ticket #{recent_dup.id}. Returning existing ticket row.")
        res_dict = {
            "is_hard_blocked": False,
            "ticket": {
                "id": recent_dup.id,
                "title": recent_dup.title,
                "description": recent_dup.description,
                "category": recent_dup.category,
                "predicted_category": recent_dup.category,
                "status": recent_dup.status,
                "priority": recent_dup.priority,
                "priority_confidence": recent_dup.priority_confidence,
                "predicted_team": recent_dup.assigned_team,
                "assigned_team": recent_dup.assigned_team,
                "routing_confidence": recent_dup.routing_confidence,
                "is_low_confidence_routed": recent_dup.is_low_confidence_routed,
                "requester_name": recent_dup.requester_name,
                "requester_count": 1,
                "created_at": str(recent_dup.created_at),
                "sla_due_at": str(recent_dup.sla_due_at),
                "assigned_agent_name": recent_dup.assigned_agent_name,
                "assigned_agent_id": recent_dup.assigned_agent_id,
                "assignment_reason": f"Assigned to {recent_dup.assigned_agent_name}" if recent_dup.assigned_agent_name else "Queued for assignment",
            },
            "message": f"Ticket #{recent_dup.id} retrieved (deduplicated).",
        }
        db.close()
        return res_dict

    # 1. GLOBAL HARD BLOCK DUPLICATE CHECK
    if not req.skip_duplicate_check:
        dup_res = detect_hybrid_duplicates(req.title, req.description)

        # BRANCH A: Match = Open Ticket (HARD BLOCK: DO NOT CREATE A NEW TICKET ROW)
        if dup_res["has_open_match"]:
            match = dup_res["open_matches"][0]
            matched_id = match["ticket_id"]

            print(f"[DUPLICATE CHECK DECISION] -> HARD BLOCK DECISION: OPEN MATCH FOUND!")
            print(f"  New Request '{req.title}' matches existing OPEN Ticket #{matched_id} ('{match['title']}')")
            print(f"  Action: Auto-linking requester '{req_name}' to Ticket #{matched_id}. NO NEW TICKET ROW CREATED.\n")

            requester_link = TicketRequester(
                ticket_id=matched_id,
                user_id=created_by_id,
                requester_name=req_name,
                requester_department=req_dept,
                link_reason="hard_blocked_auto_linked",
            )
            db.add(requester_link)
            db.commit()

            total_linked = 1 + db.query(TicketRequester).filter(TicketRequester.ticket_id == matched_id).count()

            record_duplicate_feedback(
                new_ticket_text=f"{req.title} {req.description}",
                matched_ticket_id=matched_id,
                similarity_score=match["semantic_score"],
                user_action="hard_blocked_auto_linked",
                db=db,
            )

            res_dict = {
                "is_hard_blocked": True,
                "block_type": "open_ticket_linked",
                "ticket": {
                    "id": matched_id,
                    "title": match["title"],
                    "status": match["status"],
                    "assigned_team": match["assigned_team"],
                    "requester_count": total_linked,
                },
                "message": f"Already being worked on — Ticket #{matched_id}, Status: In Progress.",
            }
            db.close()
            return res_dict

        # BRANCH B: Match = Resolved Ticket (HARD BLOCK: DO NOT CREATE A NEW TICKET ROW)
        if dup_res["has_resolved_match"]:
            match = dup_res["resolved_matches"][0]
            matched_id = match["ticket_id"]

            print(f"[DUPLICATE CHECK DECISION] -> HARD BLOCK DECISION: RESOLVED MATCH FOUND!")
            print(f"  Action: Surfacing verified solution from Ticket #{matched_id} to '{req_name}'. NO NEW TICKET ROW CREATED.\n")

            record_duplicate_feedback(
                new_ticket_text=f"{req.title} {req.description}",
                matched_ticket_id=matched_id,
                similarity_score=match["semantic_score"],
                user_action="hard_blocked_resolved_solution",
                db=db,
            )

            res_dict = {
                "is_hard_blocked": True,
                "block_type": "resolved_solution_matched",
                "ticket": {
                    "id": matched_id,
                    "title": match["title"],
                    "status": "resolved",
                    "assigned_team": match["assigned_team"],
                    "resolution_summary": match["resolution_summary"],
                    "resolution_detail": match["resolution_detail"],
                },
                "message": f"This issue was already resolved — Ticket #{matched_id}.",
            }
            db.close()
            return res_dict

    # BRANCH C: No Match -> ALLOW DECISION: Proceed to ML 8-Class Category & Team Routing & Priority
    print(f"[DUPLICATE CHECK DECISION] -> ALLOW DECISION: No duplicate match. Proceeding to ML Classification.")

    # Single-pass LLM Classification & Routing
    llm_res = classify_and_route_ticket(req.title, req.description)
    final_category = llm_res["category"]
    assigned_team = llm_res["assigned_team"]
    priority = llm_res["priority"]
    sla_target = llm_res["sla_target"]
    category_confidence = llm_res.get("category_confidence", 0.95)

    if req.category and req.category.strip() and req.category != "string":
        final_category = req.category.strip()

    is_triage = False

    # 3. SLA Calculation
    sla_due = calculate_sla_due_at(priority=priority, team_name=assigned_team, db=db)
    now_dt = datetime.now()
    sla_hours = round((sla_due - now_dt).total_seconds() / 3600.0, 1)

    is_demo_ticket = bool(getattr(req, "is_demo", False) or "[demo]" in req.title.lower() or "[demo]" in req.description.lower())

    suggestions_tried_str = None
    if req.suggestions_tried:
        if isinstance(req.suggestions_tried, str):
            suggestions_tried_str = req.suggestions_tried
        else:
            try:
                suggestions_tried_str = json.dumps(req.suggestions_tried)
            except Exception:
                suggestions_tried_str = str(req.suggestions_tried)

    ticket = Ticket(
        title=req.title,
        description=req.description,
        category=final_category,
        priority=priority,
        priority_confidence=category_confidence,
        status="open",
        assigned_team=assigned_team,
        routing_confidence=category_confidence,
        top_alternative_teams=json.dumps([{"team": assigned_team, "confidence": category_confidence}]),
        is_low_confidence_routed=False,
        created_by=created_by_id,
        requester_name=req_name,
        requester_department=req_dept,
        suggestions_tried=suggestions_tried_str,
        created_at=now_dt,
        sla_due_at=sla_due,
        is_demo=is_demo_ticket,
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Record "still_need_help" feedback for suggestions tried
    if req.suggestions_tried:
        try:
            items = req.suggestions_tried
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception:
                    items = []
            if isinstance(items, list):
                for it in items:
                    s_id = it.get("ticket_id") if isinstance(it, dict) else (it if isinstance(it, int) else None)
                    if s_id:
                        record_suggestion_feedback(
                            suggestion_ticket_id=int(s_id),
                            action="still_need_help",
                            relevance=float(it.get("relevance", 0.0)) if isinstance(it, dict) else 0.0,
                            user_id=created_by_id,
                            query_text=f"{req.title} {req.description}",
                            db=db,
                        )
        except Exception as _fb_err:
            print(f"[WARN] Failed to record still_need_help feedback: {_fb_err}")

    # ── Availability-aware agent assignment (B6: graceful degradation) ────
    assignment_reason = None
    try:
        chosen_agent, assignment_reason = assign_agent_for_ticket(ticket, assigned_team, db)
        if chosen_agent:
            ticket.assigned_agent_name = chosen_agent.name
            ticket.assigned_agent_id   = chosen_agent.id
            ticket.status = "assigned"
    except Exception as _avail_err:
        import logging
        logging.getLogger(__name__).error(
            "[AVAILABILITY] assign_agent_for_ticket failed for ticket #%s: %s — "
            "falling back to original routing assignment.",
            ticket.id, _avail_err
        )
        # ticket retains the team assigned by LLM routing; agent stays unset
    db.commit()

    if is_triage:
        log = SLAEscalationLog(
            ticket_id=ticket.id,
            team_name="Unassigned/Triage",
            manager_name="System / Triage Owner",
            escalation_reason="LOW_CONFIDENCE_TRIAGE",
            time_overdue_minutes=0.0,
        )
        db.add(log)
        ticket.escalated_to_manager = True
        ticket.escalated_at = now_dt
        db.commit()

    res_dict = {
        "is_hard_blocked": False,
        "ticket": {
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "category": ticket.category,
            "predicted_category": ticket.category,
            "category_confidence": category_confidence,
            "status": ticket.status,
            "priority": ticket.priority,
            "priority_confidence": ticket.priority_confidence,
            "predicted_team": ticket.assigned_team,
            "assigned_team": ticket.assigned_team,
            "suggested_team": ticket.assigned_team,
            "routing_confidence": ticket.routing_confidence,
            "is_low_confidence_routed": ticket.is_low_confidence_routed,
            "top_3_alternatives": [{"category": ticket.category, "confidence": category_confidence}],
            "requester_name": ticket.requester_name,
            "requester_department": ticket.requester_department,
            "created_at": str(ticket.created_at),
            "sla_due_at": str(ticket.sla_due_at),
            "sla_hours": sla_hours,
            "is_demo": bool(ticket.is_demo),
            "suggestions_tried": ticket.suggestions_tried,
            "assigned_agent_name": ticket.assigned_agent_name,
            "assigned_agent_id": ticket.assigned_agent_id,
            "assignment_reason": assignment_reason or (f"Assigned to {ticket.assigned_agent_name}" if ticket.assigned_agent_name else "Queued for assignment"),
        },
        "message": "Ticket created successfully and classified by Single-Pass LLM Dispatcher.",
    }

    db.close()
    return res_dict

def is_ticket_owned_by_user(ticket: Ticket, request: Request, db) -> bool:
    """
    Checks if a ticket belongs to the user making the request.
    Extracts identity from JWT, X-User-Id, X-User-Email, or X-User-Name headers.
    """
    user = get_current_user_from_headers(request, db)
    req_name = request.headers.get("X-User-Name", "").strip()
    req_email = request.headers.get("X-User-Email", "").strip()

    u_ids = set()
    u_names = set()

    if user:
        if user.id:
            u_ids.add(user.id)
        if user.name:
            u_names.add(user.name.lower())
        if user.email:
            u_names.add(user.email.lower())

    hdr_id = request.headers.get("X-User-Id")
    if hdr_id:
        try:
            u_ids.add(int(hdr_id))
        except Exception:
            pass

    if req_name:
        u_names.add(req_name.lower())
    if req_email:
        u_names.add(req_email.lower())

    # Fallback to default demo employee if absolutely no identity header is passed
    if not u_ids and not u_names:
        u_names.add("alice employee")

    # 1. Match created_by user_id
    if ticket.created_by and ticket.created_by in u_ids:
        return True

    # 2. Match ticket.requester_name
    if ticket.requester_name and ticket.requester_name.lower() in u_names:
        return True

    # 3. Match TicketRequester linked rows
    linked_rows = db.query(TicketRequester).filter(TicketRequester.ticket_id == ticket.id).all()
    for r in linked_rows:
        if r.user_id and r.user_id in u_ids:
            return True
        if r.requester_name and r.requester_name.lower() in u_names:
            return True

    return False

ACTIVE_STATUSES = ["new", "open", "assigned", "in_progress", "waiting_for_user", "on_hold"]
FINAL_STATUSES = ["resolved", "closed", "cancelled"]

@router.get("/all")
def get_all_tickets(request: Request):
    db = SessionLocal()
    audit_and_trigger_sla_escalations()

    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "employee") if user else "employee")

    tickets = db.query(Ticket).order_by(Ticket.id.desc()).all()

    # Deduplicate tickets by ID
    seen_ids = set()
    unique_tickets = []
    for t in tickets:
        if t.id not in seen_ids:
            seen_ids.add(t.id)
            unique_tickets.append(t)

    now = datetime.now()
    results = []

    for t in unique_tickets:
        status_clean = (t.status or "open").lower()

        # If logged-in user is an Employee, ONLY include their own tickets
        if role == "employee":
            if not is_ticket_owned_by_user(t, request, db):
                continue

            results.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "category": t.category,
                "status": status_clean,
                "priority": t.priority or "Medium",
                "created_at": str(t.created_at) if t.created_at else None,
                "resolved_at": str(t.resolved_at) if t.resolved_at else None,
                "resolution_summary": t.resolution_summary or t.resolution_notes,
                "satisfaction_rating": t.satisfaction_rating,
                "is_demo": bool(t.is_demo),
            })
        else:
            # Agent / Manager Full View
            if status_clean in FINAL_STATUSES:
                sla_badge = "RESOLVED"
            elif t.is_sla_breached or (t.sla_due_at and now > t.sla_due_at and status_clean in ACTIVE_STATUSES):
                sla_badge = "BREACHED"
            elif t.escalated_to_manager or t.is_low_confidence_routed:
                sla_badge = "AT_RISK"
            else:
                sla_badge = "ON_TRACK"

            requesters = db.query(TicketRequester).filter(TicketRequester.ticket_id == t.id).all()
            requester_names = [t.requester_name] + [r.requester_name for r in requesters if r.requester_name != t.requester_name]

            results.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "category": t.category,
                "status": status_clean,
                "priority": t.priority or "Medium",
                "predicted_team": t.assigned_team or "Unassigned/Triage",
                "routing_confidence": t.routing_confidence,
                "requester_name": t.requester_name,
                "all_requester_names": list(set(requester_names)),
                "requester_count": len(set(requester_names)),
                "created_at": str(t.created_at) if t.created_at else None,
                "sla_due_at": str(t.sla_due_at) if t.sla_due_at else None,
                "sla_badge": sla_badge,
                "is_demo": bool(t.is_demo),
            })

    db.close()
    return results

@router.get("/my-tickets")
def get_my_tickets(request: Request):
    """
    Dedicated Employee endpoint to fetch tickets owned by logged-in employee.
    Deduplicated and strictly sanitized.
    """
    db = SessionLocal()
    tickets = db.query(Ticket).order_by(Ticket.id.desc()).all()

    seen_ids = set()
    results = []
    for t in tickets:
        if t.id not in seen_ids:
            if is_ticket_owned_by_user(t, request, db):
                seen_ids.add(t.id)
                results.append({
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "category": t.category,
                    "status": (t.status or "open").lower(),
                    "priority": t.priority or "Medium",
                    "created_at": str(t.created_at) if t.created_at else None,
                    "resolved_at": str(t.resolved_at) if t.resolved_at else None,
                    "resolution_summary": t.resolution_summary or t.resolution_notes,
                    "satisfaction_rating": t.satisfaction_rating,
                    "is_demo": bool(t.is_demo),
                })

    db.close()
    return results

@router.get("/employee/{ticket_id}")
def get_employee_ticket_detail(ticket_id: int, request: Request):
    """
    Employee Ticket Details API Endpoint.
    Validates ownership & RBAC. Returns 403 Forbidden for unauthorized access.
    Strictly excludes internal notes, technical details, audit logs, team assignments, and AI routing.
    """
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "employee") if user else "employee")

    # Security Validation (RBAC & Ownership)
    if role == "employee":
        if not is_ticket_owned_by_user(ticket, request, db):
            db.close()
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have permission to access this ticket."
            )

    # Fetch public comments ONLY (is_internal == False)
    comments = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.is_internal == False
    ).order_by(TicketComment.created_at.asc()).all()

    comment_list = [
        {
            "id": c.id,
            "author_name": c.author_name,
            "author_role": c.author_role,
            "content": c.content,
            "created_at": str(c.created_at),
        }
        for c in comments
    ]

    # Fetch public KB suggestions
    suggested_kb_articles = []
    try:
        rag_res = RAG_chatbot_query(f"{ticket.title} {ticket.description}", min_similarity_threshold=0.20)
        suggested_kb_articles = rag_res.get("sources", [])
    except Exception as e:
        print(f"[WARN] Error fetching public KB articles for employee view: {e}")

    # Fetch attachments
    attachments = db.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket_id).order_by(TicketAttachment.created_at.asc()).all()
    attachment_list = [
        {
            "id": a.id,
            "filename": a.original_filename,
            "file_size": a.file_size,
            "formatted_size": format_file_size(a.file_size),
            "content_type": a.content_type,
            "uploaded_by": a.uploaded_by,
            "uploaded_at": str(a.created_at),
            "download_url": f"/ticket/attachments/{a.id}/download",
        }
        for a in attachments
    ]

    # Return sanitized user-facing data (HIDE ALL INTERNAL FIELDS)
    data = {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority or "Medium",
        "status": (ticket.status or "open").lower(),
        "created_at": str(ticket.created_at),
        "resolved_at": str(ticket.resolved_at) if ticket.resolved_at else None,
        "resolution_summary": ticket.resolution_summary or ticket.resolution_notes,
        "satisfaction_rating": ticket.satisfaction_rating,
        "satisfaction_feedback": ticket.satisfaction_feedback,
        "comments": comment_list,
        "suggested_kb_articles": suggested_kb_articles,
        "attachments": attachment_list,
    }

    db.close()
    return data

@router.post("/employee/comment/{ticket_id}")
def add_employee_comment(ticket_id: int, req: EmployeeCommentRequest, request: Request):
    """
    Employee posts a public comment to ticket thread. Ownership validated (403 if unauthorized).
    """
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "employee") if user else "employee")

    if role == "employee":
        if not is_ticket_owned_by_user(ticket, request, db):
            db.close()
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have permission to comment on this ticket."
            )

    author = user.name if user else (ticket.requester_name or "Employee")

    recent_comment = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.content == req.content.strip(),
        TicketComment.author_role == "employee"
    ).order_by(TicketComment.id.desc()).first()

    if recent_comment:
        if not recent_comment.created_at or (datetime.now() - recent_comment.created_at).total_seconds() < 10.0:
            db.close()
            return {"message": "Comment posted successfully (deduplicated)."}

    comment = TicketComment(
        ticket_id=ticket_id,
        user_id=user.id if user else None,
        author_name=author,
        author_role="employee",
        content=req.content,
        is_internal=False,  # Public comment
        created_at=datetime.now(),
    )
    db.add(comment)
    db.commit()
    db.close()
    return {"message": "Comment posted successfully"}

@router.post("/employee/reopen/{ticket_id}")
def reopen_ticket_endpoint(ticket_id: int, req: EmployeeReopenRequest, request: Request):
    """
    Employee reopens a resolved/closed ticket. Ownership validated (403 if unauthorized).
    """
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "employee") if user else "employee")

    if role == "employee":
        if not is_ticket_owned_by_user(ticket, request, db):
            db.close()
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have permission to reopen this ticket."
            )

    if ticket.status == "open":
        db.close()
        return {"message": "Ticket is already open."}

    ticket.status = "open"
    ticket.resolved_at = None

    author = user.name if user else (ticket.requester_name or "Employee")
    comment = TicketComment(
        ticket_id=ticket_id,
        user_id=user.id if user else None,
        author_name=author,
        author_role="employee",
        content=f"TICKET REOPENED BY USER. Reason: {req.reason or 'Issue unresolved'}",
        is_internal=False,
    )
    db.add(comment)
    db.commit()
    db.close()
    return {"message": "Ticket reopened successfully"}

@router.post("/employee/rate/{ticket_id}")
def rate_ticket_endpoint(ticket_id: int, req: EmployeeRatingRequest, request: Request):
    """
    Employee submits satisfaction rating (1-5 stars) and feedback. Ownership validated (403 if unauthorized).
    """
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "employee") if user else "employee")

    if role == "employee":
        if not is_ticket_owned_by_user(ticket, request, db):
            db.close()
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have permission to rate this ticket."
            )

    ticket.satisfaction_rating = max(1, min(5, req.rating))
    ticket.satisfaction_feedback = req.feedback or ""
    db.commit()
    db.close()
    return {"message": "Satisfaction rating submitted successfully", "rating": req.rating}

@router.get("/stats")
def get_ticket_stats(include_demo: bool = True):
    db = SessionLocal()
    audit_and_trigger_sla_escalations()

    query = db.query(Ticket)
    if not include_demo:
        query = query.filter((Ticket.is_demo == False) | (Ticket.is_demo == None))
    all_t = query.all()
    total = len(all_t)
    now = datetime.now()

    by_status = {}
    by_priority = {}
    by_team = {}
    breached_count = 0
    at_risk_count = 0

    for t in all_t:
        s = (t.status or "open").lower()
        by_status[s] = by_status.get(s, 0) + 1

        p = (t.priority or "Medium").capitalize()
        by_priority[p] = by_priority.get(p, 0) + 1

        tm = t.assigned_team or "Unassigned/Triage"
        by_team[tm] = by_team.get(tm, 0) + 1

        if s in ACTIVE_STATUSES:
            if t.is_sla_breached or (t.sla_due_at and now > t.sla_due_at):
                breached_count += 1
            elif t.escalated_to_manager or t.is_low_confidence_routed:
                at_risk_count += 1

    active_tickets_count = sum(by_status.get(st, 0) for st in ACTIVE_STATUSES)
    closed_tickets_count = sum(by_status.get(st, 0) for st in FINAL_STATUSES)

    sla_compliance_pct = 100.0 if total == 0 else round(((total - breached_count) / max(1, total)) * 100.0, 1)

    db.close()
    return {
        "total_tickets": total,
        "open_tickets": active_tickets_count,
        "closed_tickets": closed_tickets_count,
        "high_priority": by_priority.get("High", 0) + by_priority.get("Critical", 0),
        "breached_tickets": breached_count,
        "at_risk_tickets": at_risk_count,
        "sla_compliance_pct": sla_compliance_pct,
        "tickets_by_status": by_status,
        "tickets_by_priority": by_priority,
        "tickets_by_team": by_team,
    }


# ── Document Attachment Endpoints ─────────────────────────────────────

@router.post("/{ticket_id}/attachments")
async def upload_ticket_attachments(
    ticket_id: int,
    request: Request,
    files: List[UploadFile] = File(...),
):
    """
    Upload and attach one or multiple documents to a ticket.
    Validates file sizes, extension sanitization, and stores files safely.
    """
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = get_current_user_from_headers(request, db)
    uploader_name = (
        request.headers.get("X-User-Name")
        or (user.name if user else None)
        or ticket.requester_name
        or "Employee"
    )
    uploader_role = (
        request.headers.get("X-User-Role")
        or (user.role if user else None)
        or "employee"
    )

    saved_attachments = []

    for file in files:
        if not file.filename:
            continue

        raw_filename = os.path.basename(file.filename)
        ext = os.path.splitext(raw_filename)[1].lower()

        if ext in DANGEROUS_EXTENSIONS:
            db.close()
            raise HTTPException(
                status_code=400,
                detail=f"File '{raw_filename}' has a forbidden extension ({ext}). Executables and script files are not allowed."
            )

        content = await file.read()
        file_size = len(content)

        if file_size > MAX_ATTACHMENT_SIZE:
            db.close()
            raise HTTPException(
                status_code=400,
                detail=f"File '{raw_filename}' ({format_file_size(file_size)}) exceeds the maximum allowed limit of 15MB."
            )

        clean_base = re.sub(r'[^a-zA-Z0-9_.-]', '_', raw_filename)
        stored_filename = f"{ticket_id}_{uuid.uuid4().hex[:8]}_{clean_base}"
        target_path = os.path.join(UPLOAD_DIR, stored_filename)

        with open(target_path, "wb") as f:
            f.write(content)

        att = TicketAttachment(
            ticket_id=ticket.id,
            filename=stored_filename,
            original_filename=raw_filename,
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
            file_path=stored_filename,
            uploaded_by=uploader_name,
        )
        db.add(att)
        saved_attachments.append(att)

        # Audit comment on ticket timeline
        comment = TicketComment(
            ticket_id=ticket.id,
            user_id=user.id if user else None,
            author_name=uploader_name,
            author_role=uploader_role,
            content=f"Attached document: {raw_filename} ({format_file_size(file_size)}).",
            is_internal=False,
        )
        db.add(comment)

    db.commit()

    for a in saved_attachments:
        db.refresh(a)

    res = [
        {
            "id": a.id,
            "ticket_id": a.ticket_id,
            "filename": a.original_filename,
            "file_size": a.file_size,
            "formatted_size": format_file_size(a.file_size),
            "content_type": a.content_type,
            "uploaded_by": a.uploaded_by,
            "uploaded_at": str(a.created_at),
            "download_url": f"/ticket/attachments/{a.id}/download",
        }
        for a in saved_attachments
    ]

    db.close()
    return {
        "message": f"Successfully attached {len(res)} document(s).",
        "attachments": res,
    }


@router.get("/{ticket_id}/attachments")
def get_ticket_attachments(ticket_id: int):
    """List all attachments associated with a given ticket."""
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    attachments = (
        db.query(TicketAttachment)
        .filter(TicketAttachment.ticket_id == ticket_id)
        .order_by(TicketAttachment.created_at.asc())
        .all()
    )

    res = [
        {
            "id": a.id,
            "ticket_id": a.ticket_id,
            "filename": a.original_filename,
            "file_size": a.file_size,
            "formatted_size": format_file_size(a.file_size),
            "content_type": a.content_type,
            "uploaded_by": a.uploaded_by,
            "uploaded_at": str(a.created_at),
            "download_url": f"/ticket/attachments/{a.id}/download",
        }
        for a in attachments
    ]
    db.close()
    return res


@router.get("/attachments/{attachment_id}/download")
def download_ticket_attachment(attachment_id: int):
    """Download an attached document by attachment ID."""
    db = SessionLocal()
    att = db.query(TicketAttachment).filter(TicketAttachment.id == attachment_id).first()
    if not att:
        db.close()
        raise HTTPException(status_code=404, detail="Attachment record not found")

    file_path = os.path.join(UPLOAD_DIR, att.file_path)
    if not os.path.exists(file_path):
        db.close()
        raise HTTPException(status_code=404, detail="Attachment file not found on server disk")

    db.close()
    return FileResponse(
        path=file_path,
        filename=att.original_filename,
        media_type=att.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{att.original_filename}"'},
    )


@router.delete("/attachments/{attachment_id}")
def delete_ticket_attachment(attachment_id: int, request: Request):
    """Delete an attachment from database and disk."""
    db = SessionLocal()
    att = db.query(TicketAttachment).filter(TicketAttachment.id == attachment_id).first()
    if not att:
        db.close()
        raise HTTPException(status_code=404, detail="Attachment not found")

    user = get_current_user_from_headers(request, db)
    actor_name = request.headers.get("X-User-Name") or (user.name if user else "User")

    file_path = os.path.join(UPLOAD_DIR, att.file_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"[WARN] Failed to delete file from disk: {e}")

    orig_name = att.original_filename
    t_id = att.ticket_id

    db.delete(att)

    comment = TicketComment(
        ticket_id=t_id,
        user_id=user.id if user else None,
        author_name=actor_name,
        author_role=user.role if user else "user",
        content=f"Removed attached document: {orig_name}.",
        is_internal=False,
    )
    db.add(comment)

    db.commit()
    db.close()
    return {"message": f"Attachment '{orig_name}' deleted successfully."}
