import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from typing import Optional, List

from app.database.database import SessionLocal
from app.models import Ticket, TicketRequester, TicketComment, SLAEscalationLog, Team, User, DuplicateFeedbackLog
from app.models.availability import AgentLeave
from app.availability.service import _is_on_leave, _is_on_shift, _open_ticket_count
from app.auth.rbac import get_current_user_from_headers
from app.duplicate.service import detect_hybrid_duplicates
from app.chatbot.service import RAG_chatbot_query
from app.sla.service import audit_and_trigger_sla_escalations
from app.routing.service import predict_team_ml
from app.priority.service import predict_priority_enhanced
from app.sla.service import calculate_sla_due_at
from app.availability.routes import view_as_agent, ViewAsRequest

router = APIRouter()

def _get_audit_actor(request: Request, db, default_role="agent") -> tuple:
    """
    Returns (actor_name, actor_role, audit_context).
    If request is impersonating an agent via X-View-As-Agent:
      actor_name = real_manager.name (or "John Manager")
      actor_role = "manager"
      audit_context = f"viewing as {view_as_name}"
    """
    if not request:
        return "Support Agent", default_role, ""

    view_as_name = request.headers.get("X-View-As-Agent")
    if view_as_name:
        caller = get_current_user_from_headers(request, db, bypass_view_as=True)
        caller_role = request.headers.get("X-Real-User-Role") or (caller.role if caller else "") or request.headers.get("X-User-Role", "")
        if caller_role not in {"manager", "admin", "team_lead"}:
            raise HTTPException(status_code=403, detail="Forbidden: Impersonation only allowed for managers")

        import os
        demo_mode_env = os.environ.get("DEMO_MODE", "true").lower() == "true"
        if not demo_mode_env:
            raise HTTPException(status_code=403, detail="Forbidden: Impersonation only allowed when DEMO_MODE is on")

        target = db.query(User).filter(
            (User.name == view_as_name) | (User.name.like(f"%{view_as_name}%"))
        ).first()
        if not target or target.role != "agent":
            raise HTTPException(status_code=403, detail="Forbidden: Can only impersonate support agents")

        real_name = getattr(caller, "name", None) or request.headers.get("X-Real-User-Name") or "John Manager"
        return real_name, "manager", f"viewing as {target.name}"

    caller = get_current_user_from_headers(request, db)
    if caller:
        return caller.name, caller.role, ""
    return "Support Agent", default_role, ""

@router.post("/view-as")
def agent_view_as(req: ViewAsRequest, request: Request):
    return view_as_agent(req, request)

class ResolveTicketRequest(BaseModel):
    resolution_summary: str
    resolution_detail: Optional[str] = ""
    root_cause: str

class AddCommentRequest(BaseModel):
    content: str
    author_name: str = "Support Agent"
    author_role: str = "agent"
    is_internal: bool = False

class InlineAssignRequest(BaseModel):
    new_team: str

class SplitRequesterRequest(BaseModel):
    requester_name: str
    reason: Optional[str] = "Distinct issue un-merged by agent"

class ChangePriorityRequest(BaseModel):
    new_priority: str

class ChangeStatusRequest(BaseModel):
    new_status: str

class AssignEngineerRequest(BaseModel):
    agent_name: str

@router.get("/queue")
def get_agent_queue(
    request: Request,
    team: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    sla_status: Optional[str] = None,
):
    db = SessionLocal()
    audit_and_trigger_sla_escalations()

    caller = get_current_user_from_headers(request, db)
    # If caller is an agent who is on leave, queue is completely empty
    if caller and caller.role == "agent" and _is_on_leave(caller, datetime.utcnow(), db):
        db.close()
        return []

    query = db.query(Ticket)
    # Agent view: show only that agent's own tickets
    if caller and caller.role == "agent":
        query = query.filter(Ticket.assigned_agent_name == caller.name)

    if team and team != "All":
        query = query.filter(Ticket.assigned_team == team)
    if priority and priority != "All":
        query = query.filter(Ticket.priority == priority)
    if status and status != "All":
        query = query.filter(Ticket.status == status)

    tickets = query.order_by(Ticket.created_at.desc()).all()
    teams = [tm.name for tm in db.query(Team).all()]

    now = datetime.now()
    results = []

    ACTIVE_STATUSES = ["new", "open", "assigned", "in_progress", "waiting_for_user", "on_hold"]
    FINAL_STATUSES = ["resolved", "closed", "cancelled"]

    for t in tickets:
        status_clean = (t.status or "open").lower()
        sla_badge = "ON_TRACK"
        overdue_minutes = 0.0

        if status_clean in FINAL_STATUSES:
            sla_badge = "RESOLVED"
        elif t.is_sla_breached or (t.sla_due_at and now > t.sla_due_at and status_clean in ACTIVE_STATUSES):
            sla_badge = "BREACHED"
            overdue_minutes = (now - t.sla_due_at).total_seconds() / 60.0 if t.sla_due_at else 0
        elif t.escalated_to_manager or t.is_low_confidence_routed:
            sla_badge = "AT_RISK"


        # Linked requesters
        req_rows = db.query(TicketRequester).filter(TicketRequester.ticket_id == t.id).all()
        all_req_names = list(set([t.requester_name] + [r.requester_name for r in req_rows if r.requester_name]))

        results.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "category": t.category,
            "priority": t.priority or "Medium",
            "status": t.status or "open",
            "assigned_team": t.assigned_team or "Unassigned/Triage",
            "assigned_agent_name": t.assigned_agent_name or "Unassigned",
            "routing_confidence": t.routing_confidence,
            "is_low_confidence_routed": t.is_low_confidence_routed,
            "requester_name": t.requester_name or "User",
            "requester_department": t.requester_department or "General",
            "all_requester_names": all_req_names,
            "requester_count": len(all_req_names),
            "created_at": str(t.created_at) if t.created_at else None,
            "sla_due_at": str(t.sla_due_at) if t.sla_due_at else None,
            "sla_badge": sla_badge,
            "overdue_minutes": round(overdue_minutes, 1),
            "available_teams": teams,
        })

    db.close()
    return results

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from app.auth.rbac import get_current_user_from_headers

@router.get("/detail/{ticket_id}")
def get_ticket_detail(ticket_id: int, request: Request):
    db = SessionLocal()
    user = get_current_user_from_headers(request, db)
    role = request.headers.get("X-User-Role", getattr(user, "role", "agent") if user else "agent")

    # Enforce strict separation: Employees cannot access Agent Workspace details
    if role == "employee":
        db.close()
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Employees are not authorized to view internal Agent Workspace ticket details."
        )

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).order_by(TicketComment.created_at.asc()).all()
    req_rows = db.query(TicketRequester).filter(TicketRequester.ticket_id == ticket_id).all()

    linked_requesters_list = [
        {
            "name": r.requester_name,
            "department": r.requester_department,
            "linked_at": str(r.linked_at),
            "is_primary": False,
        }
        for r in req_rows
    ]
    if ticket.requester_name:
        linked_requesters_list.insert(0, {
            "name": ticket.requester_name,
            "department": ticket.requester_department or "General",
            "linked_at": str(ticket.created_at),
            "is_primary": True,
        })

    # Triage explanation if low confidence
    triage_explanation = None
    if ticket.is_low_confidence_routed or ticket.assigned_team == "Unassigned/Triage":
        conf_str = f"{round(ticket.routing_confidence * 100)}%" if ticket.routing_confidence else "Unknown"
        triage_explanation = f"Routing confidence was {conf_str} (below 55% threshold). Please assign team manually."

    now = datetime.now()
    sla_badge = "ON_TRACK"
    if ticket.is_sla_breached or (ticket.sla_due_at and now > ticket.sla_due_at and ticket.status in ["open", "in_progress"]):
        sla_badge = "BREACHED"

    comment_list = [
        {
            "id": c.id,
            "author_name": c.author_name,
            "author_role": c.author_role,
            "content": c.content,
            "is_internal": c.is_internal,
            "created_at": str(c.created_at),
        }
        for c in comments
    ]

    # Retrieve similar tickets and recommended KB articles
    similar_tickets = []
    suggested_kb_articles = []
    try:
        dup_res = detect_hybrid_duplicates(ticket.title, ticket.description, threshold=0.60)
        similar_tickets = dup_res.get("matched_tickets", [])
    except Exception as e:
        print(f"[WARN] Error fetching similar tickets in detail endpoint: {e}")

    try:
        rag_res = RAG_chatbot_query(f"{ticket.title} {ticket.description}", min_similarity_threshold=0.20)
        suggested_kb_articles = rag_res.get("sources", [])
    except Exception as e:
        print(f"[WARN] Error fetching suggested KB articles in detail endpoint: {e}")

    data = {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "assigned_team": ticket.assigned_team,
        "assigned_agent_name": ticket.assigned_agent_name,
        "routing_confidence": ticket.routing_confidence,
        "is_low_confidence_routed": ticket.is_low_confidence_routed,
        "triage_explanation": triage_explanation,
        "requester_name": ticket.requester_name,
        "requester_department": ticket.requester_department,
        "linked_requesters": linked_requesters_list,
        "requester_count": len(linked_requesters_list),
        "resolution_summary": ticket.resolution_summary or ticket.resolution_notes,
        "resolution_detail": ticket.resolution_detail,
        "root_cause": ticket.root_cause,
        "resolved_at": str(ticket.resolved_at) if ticket.resolved_at else None,
        "created_at": str(ticket.created_at),
        "sla_due_at": str(ticket.sla_due_at),
        "sla_badge": sla_badge,
        "comments": comment_list,
        "similar_tickets": similar_tickets,
        "suggested_kb_articles": suggested_kb_articles,
    }

    db.close()
    return data

@router.post("/assign-team/{ticket_id}")
def assign_team_inline(ticket_id: int, req: InlineAssignRequest, request: Request = None):
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_team = ticket.assigned_team
    if old_team == req.new_team:
        db.close()
        return {"message": f"Team is already '{req.new_team}'"}

    actor_name, actor_role, audit_ctx = _get_audit_actor(request, db, default_role="agent")
    comment_author = f"{actor_name} ({audit_ctx})" if audit_ctx else "System / Queue Triage"
    comment_content = f"Assigned team from '{old_team}' to '{req.new_team}'."
    if audit_ctx:
        comment_content += f"\n[Audit: {actor_name}, context: {audit_ctx}]"

    ticket.assigned_team = req.new_team
    ticket.is_low_confidence_routed = False

    comment = TicketComment(
        ticket_id=ticket_id,
        author_name=comment_author,
        author_role=actor_role,
        content=comment_content,
        is_internal=True,
    )
    db.add(comment)
    db.commit()
    db.close()
    return {"message": f"Ticket #{ticket_id} assigned to '{req.new_team}'"}

@router.post("/change-priority/{ticket_id}")
def change_priority_endpoint(ticket_id: int, req: ChangePriorityRequest, request: Request = None):
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_p = ticket.priority
    if old_p == req.new_priority:
        db.close()
        return {"message": f"Priority is already '{req.new_priority}'"}

    actor_name, actor_role, audit_ctx = _get_audit_actor(request, db, default_role="agent")
    comment_author = f"{actor_name} ({audit_ctx})" if audit_ctx else (actor_name or "Support Agent")
    comment_content = f"Changed priority from '{old_p}' to '{req.new_priority}'."
    if audit_ctx:
        comment_content += f"\n[Audit: {actor_name}, context: {audit_ctx}]"

    ticket.priority = req.new_priority
    comment = TicketComment(
        ticket_id=ticket_id,
        author_name=comment_author,
        author_role=actor_role,
        content=comment_content,
        is_internal=True,
    )
    db.add(comment)
    db.commit()
    db.close()
    return {"message": f"Priority changed to {req.new_priority}"}

@router.post("/change-status/{ticket_id}")
def change_status_endpoint(ticket_id: int, req: ChangeStatusRequest, request: Request = None):
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_s = ticket.status
    if old_s == req.new_status:
        db.close()
        return {"message": f"Status is already '{req.new_status}'"}

    actor_name, actor_role, audit_ctx = _get_audit_actor(request, db, default_role="agent")
    comment_author = f"{actor_name} ({audit_ctx})" if audit_ctx else (actor_name or "Support Agent")
    comment_content = f"Changed status from '{old_s}' to '{req.new_status}'."
    if audit_ctx:
        comment_content += f"\n[Audit: {actor_name}, context: {audit_ctx}]"

    ticket.status = req.new_status
    if req.new_status in ["resolved", "closed"] and not ticket.resolved_at:
        ticket.resolved_at = datetime.now()

    comment = TicketComment(
        ticket_id=ticket_id,
        author_name=comment_author,
        author_role=actor_role,
        content=comment_content,
        is_internal=False,
    )
    db.add(comment)
    db.commit()
    db.close()
    return {"message": f"Status changed to {req.new_status}"}

@router.post("/assign-engineer/{ticket_id}")
def assign_engineer_endpoint(ticket_id: int, req: AssignEngineerRequest, request: Request = None):
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    target_user = db.query(User).filter(User.name == req.agent_name).first()
    if target_user and _is_on_leave(target_user, datetime.utcnow(), db):
        db.close()
        raise HTTPException(status_code=400, detail=f"Cannot assign: Agent '{req.agent_name}' is currently on leave.")

    old_engineer = ticket.assigned_agent_name
    if old_engineer == req.agent_name:
        db.close()
        return {"message": f"Engineer '{req.agent_name}' is already assigned."}

    actor_name, actor_role, audit_ctx = _get_audit_actor(request, db, default_role="agent")
    comment_author = f"{actor_name} ({audit_ctx})" if audit_ctx else (actor_name or "Support Agent")
    comment_content = f"Assigned engineer '{req.agent_name}' to Ticket #{ticket_id}."
    if audit_ctx:
        comment_content += f"\n[Audit: {actor_name}, context: {audit_ctx}]"

    ticket.assigned_agent_name = req.agent_name
    comment = TicketComment(
        ticket_id=ticket_id,
        author_name=comment_author,
        author_role=actor_role,
        content=comment_content,
        is_internal=True,
    )
    db.add(comment)
    db.commit()
    db.close()
    return {"message": f"Engineer '{req.agent_name}' assigned."}

@router.post("/resolve/{ticket_id}")
def resolve_ticket(ticket_id: int, req: ResolveTicketRequest, request: Request = None):
    """
    Single close action resolves Ticket #X for ALL linked requesters at once.
    """
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status == "resolved":
        db.close()
        return {
            "message": f"Ticket #{ticket_id} is already resolved.",
            "ticket_id": ticket_id,
            "resolved_requesters": [ticket.requester_name],
        }

    actor_name, actor_role, audit_ctx = _get_audit_actor(request, db, default_role="agent")
    comment_author = f"{actor_name} ({audit_ctx})" if audit_ctx else (actor_name or "Support Agent")

    ticket.status = "resolved"
    ticket.resolution_summary = req.resolution_summary
    ticket.resolution_detail = req.resolution_detail or req.resolution_summary
    ticket.resolution_notes = req.resolution_summary
    ticket.root_cause = req.root_cause
    ticket.resolved_at = datetime.now()

    # Query all linked requesters
    req_rows = db.query(TicketRequester).filter(TicketRequester.ticket_id == ticket_id).all()
    all_names = list(set([ticket.requester_name] + [r.requester_name for r in req_rows if r.requester_name]))

    comment_content = f"TICKET RESOLVED FOR ALL {len(all_names)} LINKED REQUESTERS ({', '.join(all_names)}).\nResolution Summary: {req.resolution_summary}\nRoot Cause: {req.root_cause}"
    if audit_ctx:
        comment_content += f"\n[Audit: {actor_name}, context: {audit_ctx}]"

    comment = TicketComment(
        ticket_id=ticket_id,
        author_name=comment_author,
        author_role=actor_role,
        content=comment_content,
        is_internal=False,
    )
    db.add(comment)
    db.commit()
    db.close()

    print(f"[SINGLE RESOLVE ACTION] Ticket #{ticket_id} marked RESOLVED by {comment_author} for all {len(all_names)} linked requesters: {', '.join(all_names)}!")

    return {
        "message": f"Ticket #{ticket_id} resolved for all {len(all_names)} linked requesters",
        "ticket_id": ticket_id,
        "resolved_requesters": all_names,
    }

@router.post("/split-requester/{ticket_id}")
def split_requester(ticket_id: int, req: SplitRequesterRequest):
    """
    Agent Action: Un-link a requester from Ticket #X and create a standalone new Ticket #Y for them.
    """
    db = SessionLocal()
    master_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not master_ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Master ticket not found")

    # Find the link record
    link = db.query(TicketRequester).filter(
        TicketRequester.ticket_id == ticket_id,
        TicketRequester.requester_name == req.requester_name
    ).first()

    if link:
        dept = link.requester_department or "General"
        db.delete(link)
    else:
        dept = master_ticket.requester_department or "General"

    # Create new standalone ticket for un-linked requester
    routing_res = predict_team_ml(master_ticket.description)
    team = routing_res["predicted_team"]

    new_ticket = Ticket(
        title=f"[Split Issue] {master_ticket.title}",
        description=f"{master_ticket.description}\n\n[Agent Split Note]: Un-linked from Ticket #{ticket_id} by support agent. Reason: {req.reason}",
        category=master_ticket.category,
        priority=master_ticket.priority,
        status="open",
        assigned_team=team,
        requester_name=req.requester_name,
        requester_department=dept,
        created_at=datetime.now(),
        sla_due_at=master_ticket.sla_due_at,
    )

    db.add(new_ticket)

    comment = TicketComment(
        ticket_id=ticket_id,
        author_name="Support Agent",
        author_role="agent",
        content=f"AGENT ACTION: Un-linked requester '{req.requester_name}' from Ticket #{ticket_id} into standalone new Ticket #{new_ticket.id}. Reason: {req.reason}",
        is_internal=True,
    )
    db.add(comment)
    db.commit()
    db.refresh(new_ticket)
    new_id = new_ticket.id
    db.close()

    print(f"[AGENT SPLIT ACTION] Requester '{req.requester_name}' un-linked from Ticket #{ticket_id} -> New Ticket #{new_id} created!")

    return {
        "message": f"Un-linked '{req.requester_name}' into new standalone Ticket #{new_id}",
        "new_ticket_id": new_id,
        "master_ticket_id": ticket_id,
    }

@router.post("/comment/{ticket_id}")
def add_ticket_comment(ticket_id: int, req: AddCommentRequest, request: Request = None):
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        db.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    actor_name, actor_role, audit_ctx = _get_audit_actor(request, db, default_role=req.author_role)
    author_name = f"{actor_name} ({audit_ctx})" if audit_ctx else req.author_name
    author_role = actor_role if audit_ctx else req.author_role
    content = req.content
    if audit_ctx:
        content += f"\n[Audit: {actor_name}, context: {audit_ctx}]"

    recent_comment = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id,
        TicketComment.content == content.strip(),
        TicketComment.author_role == author_role
    ).order_by(TicketComment.id.desc()).first()

    if recent_comment:
        if not recent_comment.created_at or (datetime.now() - recent_comment.created_at).total_seconds() < 10.0:
            db.close()
            return {"message": "Comment already added (deduplicated)."}

    comment = TicketComment(
        ticket_id=ticket_id,
        author_name=author_name,
        author_role=author_role,
        content=content,
        is_internal=req.is_internal,
        created_at=datetime.now(),
    )
    db.add(comment)
    db.commit()
    db.close()
    return {"message": "Comment added"}

@router.get("/canned-responses")
def get_canned_responses():
    return [
        {"id": 1, "title": "VPN Re-authentication Guide", "content": "Hi there,\n\nPlease flush DNS: run 'ipconfig /flushdns' and re-enter Okta credentials."},
        {"id": 2, "title": "SAP SU53 Role Escalation", "content": "Hello,\n\nForwarded your SAP SU53 screenshot to SAP Security for T-code role assignment."},
        {"id": 3, "title": "Password Lockout Self-Service", "content": "Hi,\n\nYour account lockout has been cleared at https://identity.company.com/reset."},
    ]

@router.get("/agent-stats")
def get_agent_stats():
    db = SessionLocal()
    all_t = db.query(Ticket).all()
    closed_t = [t for t in all_t if t.status in ["resolved", "closed"]]
    breached_t = [t for t in all_t if t.is_sla_breached]

    total = len(all_t)
    resolved_count = len(closed_t)
    breached_count = len(breached_t)
    sla_comp = 100.0 if total == 0 else round(((total - breached_count) / total) * 100.0, 1)

    db.close()
    return {
        "tickets_resolved": resolved_count,
        "total_assigned": total,
        "sla_compliance_pct": sla_comp,
        "avg_resolution_hours": 3.4,
        "breached_count": breached_count,
    }

@router.get("/manager-dashboard")
def get_manager_dashboard():
    db = SessionLocal()
    teams = db.query(Team).all()
    escalations = db.query(SLAEscalationLog).order_by(SLAEscalationLog.created_at.desc()).limit(20).all()
    tickets = db.query(Ticket).all()

    total_tickets = len(tickets)
    total_breached = len([t for t in tickets if t.is_sla_breached])
    total_at_risk = len([t for t in tickets if t.escalated_to_manager and not t.is_sla_breached])
    overall_compliance = round(((total_tickets - total_breached) / max(1, total_tickets)) * 100.0, 1)

    team_stats = []
    for tm in teams:
        team_t = [t for t in tickets if t.assigned_team == tm.name]
        t_count = len(team_t)
        t_breached = len([t for t in team_t if t.is_sla_breached])
        comp = 100.0 if t_count == 0 else round(((t_count - t_breached) / max(1, t_count)) * 100.0, 1)
        team_stats.append({
            "team_name": tm.name,
            "manager_name": tm.manager_name or "Manager",
            "total_tickets": t_count,
            "breached_tickets": t_breached,
            "compliance_pct": comp,
        })

    escalation_list = [
        {
            "id": e.id,
            "ticket_id": e.ticket_id,
            "team_name": e.team_name,
            "manager_name": e.manager_name,
            "agent_name": e.agent_name,
            "escalation_reason": e.escalation_reason,
            "time_overdue_minutes": round(e.time_overdue_minutes, 1),
            "created_at": str(e.created_at),
        }
        for e in escalations
    ]

    db.close()
    return {
        "overall_sla_compliance": overall_compliance,
        "total_tickets": total_tickets,
        "at_risk_tickets": total_at_risk,
        "breached_tickets": total_breached,
        "team_performance": team_stats,
        "recent_escalations": escalation_list,
    }


@router.get("/my-status")
def get_my_status(request: Request):
    db = SessionLocal()
    try:
        user = get_current_user_from_headers(request, db)
        if not user:
            return {
                "status": "off_shift",
                "is_on_leave": False,
                "leave_until": None,
                "return_date": None,
                "open_tickets": 0,
                "ticket_cap": 10,
                "shift_status": "Off Shift",
                "next_shift": "Next shift starts 09:00 IST",
            }
        from app.availability.service import get_agent_status
        utc_now = datetime.utcnow()
        agent_status = get_agent_status(user, utc_now, db)

        leave_until = None
        if agent_status.leave_rec:
            leave_until = agent_status.leave_rec.end_datetime.strftime("%b %d, %Y")

        shift_status_label = "On Leave" if agent_status.status == "on_leave" else (
            "In Shift" if agent_status.status in ("available", "at_capacity") else "Off Shift"
        )

        return {
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "status": agent_status.status,
            "is_on_leave": agent_status.status == "on_leave",
            "leave_until": leave_until,
            "return_date": agent_status.return_date,
            "open_tickets": agent_status.open_count,
            "ticket_cap": agent_status.cap,
            "shift_status": shift_status_label,
            "next_shift": agent_status.next_shift,
            "on_call": agent_status.on_call,
        }
    finally:
        db.close()
