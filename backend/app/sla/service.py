import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from dotenv import load_dotenv
from app.database.database import SessionLocal
from app.models import Ticket, Team, SLAEscalationLog, User

load_dotenv()

MANAGER_EMAIL   = os.getenv("ESCALATION_MANAGER_EMAIL", "visakavisaka2705@gmail.com")
SMTP_SENDER     = os.getenv("SMTP_SENDER_EMAIL", "")
SMTP_PASSWORD   = os.getenv("SMTP_APP_PASSWORD", "")
SMTP_HOST       = "smtp.gmail.com"
SMTP_PORT       = 587

def _send_escalation_email(subject: str, html_body: str):
    """Send escalation email via Gmail SMTP. Silently skips if credentials not configured."""
    print(f"[EMAIL DEBUG] SMTP_SENDER='{SMTP_SENDER}' PASSWORD_SET={'yes' if SMTP_PASSWORD else 'NO'}")
    if not SMTP_SENDER or not SMTP_PASSWORD:
        print(f"[EMAIL SKIP] SMTP credentials not set. Subject: {subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_SENDER
        msg["To"]      = MANAGER_EMAIL
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_SENDER, SMTP_PASSWORD)
            server.sendmail(SMTP_SENDER, MANAGER_EMAIL, msg.as_string())
        print(f"[EMAIL SENT] Escalation email sent to {MANAGER_EMAIL}: {subject}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send escalation email: {e}")

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

                _send_escalation_email(
                    subject=f"[SLA BREACHED] Ticket #{ticket.id} — {ticket.title}",
                    html_body=f"""
                    <h2 style="color:#dc2626">SLA Breach Alert</h2>
                    <p>A ticket has <strong>breached its SLA deadline</strong> and requires immediate attention.</p>
                    <table style="border-collapse:collapse;width:100%">
                      <tr><td style="padding:6px;font-weight:bold">Ticket ID</td><td style="padding:6px">#{ticket.id}</td></tr>
                      <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Title</td><td style="padding:6px">{ticket.title}</td></tr>
                      <tr><td style="padding:6px;font-weight:bold">Priority</td><td style="padding:6px">{ticket.priority}</td></tr>
                      <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Assigned Team</td><td style="padding:6px">{ticket.assigned_team or 'Unassigned'}</td></tr>
                      <tr><td style="padding:6px;font-weight:bold">Requester</td><td style="padding:6px">{ticket.requester_name or 'Unknown'}</td></tr>
                      <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">SLA Due At</td><td style="padding:6px">{ticket.sla_due_at}</td></tr>
                      <tr><td style="padding:6px;font-weight:bold">Overdue By</td><td style="padding:6px;color:#dc2626"><strong>{overdue_mins:.1f} minutes</strong></td></tr>
                      <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Manager</td><td style="padding:6px">{mgr_name}</td></tr>
                    </table>
                    <p style="margin-top:16px;color:#6b7280;font-size:12px">Smart Help Desk — Auto Escalation System</p>
                    """
                )

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

            remaining_mins = (ticket.sla_due_at - now).total_seconds() / 60.0
            _send_escalation_email(
                subject=f"[SLA AT RISK] Ticket #{ticket.id} — {ticket.title}",
                html_body=f"""
                <h2 style="color:#d97706">SLA At-Risk Warning</h2>
                <p>A ticket has consumed <strong>80% of its SLA window</strong> and is at risk of breaching.</p>
                <table style="border-collapse:collapse;width:100%">
                  <tr><td style="padding:6px;font-weight:bold">Ticket ID</td><td style="padding:6px">#{ticket.id}</td></tr>
                  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Title</td><td style="padding:6px">{ticket.title}</td></tr>
                  <tr><td style="padding:6px;font-weight:bold">Priority</td><td style="padding:6px">{ticket.priority}</td></tr>
                  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Assigned Team</td><td style="padding:6px">{ticket.assigned_team or 'Unassigned'}</td></tr>
                  <tr><td style="padding:6px;font-weight:bold">Requester</td><td style="padding:6px">{ticket.requester_name or 'Unknown'}</td></tr>
                  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">SLA Due At</td><td style="padding:6px">{ticket.sla_due_at}</td></tr>
                  <tr><td style="padding:6px;font-weight:bold">Time Remaining</td><td style="padding:6px;color:#d97706"><strong>{remaining_mins:.1f} minutes</strong></td></tr>
                  <tr style="background:#f9fafb"><td style="padding:6px;font-weight:bold">Manager</td><td style="padding:6px">{mgr_name}</td></tr>
                </table>
                <p style="margin-top:16px;color:#6b7280;font-size:12px">Smart Help Desk — Auto Escalation System</p>
                """
            )

    if escalations_triggered > 0:
        db.commit()

    db.close()
