import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.database.database import SessionLocal
from app.models import Ticket, TicketRequester, TicketComment, User, SLAEscalationLog, Team
from app.routing.service import predict_team_ml, predict_ticket_category, post_process_category, route_team_with_llm, classify_and_route_ticket
from app.priority.service import predict_priority_enhanced
from app.sla.service import calculate_sla_due_at, audit_and_trigger_sla_escalations
from app.duplicate.service import detect_hybrid_duplicates, record_duplicate_feedback
from app.chatbot.service import RAG_chatbot_query
from app.auth.rbac import get_current_user_from_headers

router = APIRouter()

class TicketCreateRequest(BaseModel):
    title: str
    description: str
    category: Optional[str] = None
    requester_name: Optional[str] = "Alice Employee"
    requester_department: Optional[str] = "Finance"
    skip_duplicate_check: Optional[bool] = False

class RouteTicketRequest(BaseModel):
    title: Optional[str] = ""
    description: str
    department: Optional[str] = "General"

class DuplicateCheckRequest(BaseModel):
    title: str
    description: str

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

@router.post("/create")
def create_ticket(req: TicketCreateRequest, request: Request):
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
        created_at=now_dt,
        sla_due_at=sla_due,
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

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
def get_ticket_stats():
    db = SessionLocal()
    audit_and_trigger_sla_escalations()

    all_t = db.query(Ticket).all()
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
