from datetime import datetime, timedelta
from app.database.database import SessionLocal
from app.models import Ticket, Team, SLAEscalationLog, User

DEFAULT_SLA_HOURS = {
    "Critical": 6.0,
    "High": 24.0,
    "Medium": 48.0,
    "Low": 72.0,
}

ACTIVE_STATUSES = ["new", "open", "assigned", "in_progress", "waiting_for_user", "on_hold"]
FINAL_STATUSES = ["resolved", "closed", "cancelled"]

def calculate_sla_due_at(priority: str, team_name: str, db=None) -> datetime:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    resolve_hours = DEFAULT_SLA_HOURS.get(priority, 48.0)

    try:
        team = db.query(Team).filter(Team.name == team_name).first()
        if team:
            p_lower = priority.lower()
            if p_lower == "critical":
                resolve_hours = team.sla_resolve_hours_critical
            elif p_lower == "high":
                resolve_hours = team.sla_resolve_hours_high
            elif p_lower == "medium":
                resolve_hours = team.sla_resolve_hours_medium
            elif p_lower == "low":
                resolve_hours = team.sla_resolve_hours_low
    except Exception as e:
        print(f"[WARN] Error fetching team SLA policy: {e}")
    finally:
        if close_db:
            db.close()

    return datetime.now() + timedelta(hours=resolve_hours)

def audit_and_trigger_sla_escalations():
    """
    Background job to evaluate tickets for SLA warnings (80% time elapsed)
    and SLA breaches (100% time elapsed), notifying managers.
    STRICTLY IGNORES TICKETS IN FINAL STATES (resolved, closed, cancelled).
    """
    db = SessionLocal()
    now = datetime.now()

    # SLA evaluation runs ONLY on active tickets
    active_tickets = db.query(Ticket).filter(
        Ticket.status.in_(ACTIVE_STATUSES)
    ).all()

    escalations_triggered = 0

    for ticket in active_tickets:
        if not ticket.sla_due_at or not ticket.created_at:
            continue

        total_duration = (ticket.sla_due_at - ticket.created_at).total_seconds()
        if total_duration <= 0:
            total_duration = 3600 # default 1h safety

        elapsed = (now - ticket.created_at).total_seconds()
        elapsed_pct = elapsed / total_duration

        # 1. SLA Breach Check
        if now > ticket.sla_due_at:
            if not ticket.is_sla_breached:
                ticket.is_sla_breached = True
                ticket.escalated_to_manager = True
                ticket.escalated_at = now

                overdue_mins = (now - ticket.sla_due_at).total_seconds() / 60.0

                # Find team manager
                team = db.query(Team).filter(Team.name == ticket.assigned_team).first()
                mgr_id = team.manager_id if team else None
                mgr_name = team.manager_name if team else "Team Manager"

                log = SLAEscalationLog(
                    ticket_id=ticket.id,
                    team_name=ticket.assigned_team or "Unassigned",
                    manager_id=mgr_id,
                    manager_name=mgr_name,
                    agent_id=ticket.assigned_agent_id,
                    agent_name=ticket.assigned_agent_name,
                    escalation_reason="BREACHED_100%",
                    time_overdue_minutes=overdue_mins,
                )
                db.add(log)
                escalations_triggered += 1
                print(f"[SLA ESCALATION] Ticket #{ticket.id} ('{ticket.title}') BREACHED! Overdue by {overdue_mins:.1f} mins. Manager notified.")

        # 2. SLA At-Risk Warning Check (80% time elapsed)
        elif elapsed_pct >= 0.80 and not ticket.escalated_to_manager:
            ticket.escalated_to_manager = True
            ticket.escalated_at = now

            team = db.query(Team).filter(Team.name == ticket.assigned_team).first()
            mgr_id = team.manager_id if team else None
            mgr_name = team.manager_name if team else "Team Manager"

            log = SLAEscalationLog(
                ticket_id=ticket.id,
                team_name=ticket.assigned_team or "Unassigned",
                manager_id=mgr_id,
                manager_name=mgr_name,
                agent_id=ticket.assigned_agent_id,
                agent_name=ticket.assigned_agent_name,
                escalation_reason="AT_RISK_80%",
                time_overdue_minutes=0.0,
            )
            db.add(log)
            escalations_triggered += 1
            print(f"[SLA WARNING] Ticket #{ticket.id} ('{ticket.title}') IS AT RISK (80% SLA elapsed). Manager warned.")

    if escalations_triggered > 0:
        db.commit()

    db.close()
