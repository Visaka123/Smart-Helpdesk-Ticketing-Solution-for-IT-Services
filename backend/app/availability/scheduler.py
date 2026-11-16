"""
app/availability/scheduler.py

Background jobs for availability-aware re-routing.
Plugs into the existing APScheduler in main.py.

Jobs:
  1. reroute_on_leave_approval()  — runs every 5 min
     When leave is approved, reassign that agent's unstarted tickets.
     is_processed flag prevents double-runs (B3).
  2. handover_before_shift_end()  — runs every 5 min
     30 min before shift ends, hand unstarted tickets to next available agent.
     Never touches in_progress tickets — only notifies team lead about those.
"""

from datetime import datetime, timedelta
from app.database.database import SessionLocal
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.user import User
from app.models.availability import AgentLeave, AgentShift, AssignmentLog
from app.availability.service import (
    assign_agent_for_ticket, _is_on_shift, _agent_local_now, _is_on_leave,
    UNSTARTED_STATUSES, HANDOVER_MINUTES
)


# ── Job 1: Reroute on leave approval ─────────────────────────

def reroute_on_leave_approval():
    """
    Phase 3: When approved leave becomes active (start time, approval, or sync),
    reassign ALL the agent's open and in-progress tickets via the same chain,
    excluding that agent. Never touch resolved/closed tickets.
    Add a handover comment "Reassigned from <agent> (on leave)".
    Idempotent, per-ticket commit, runs every 5 minutes and immediately on approval/sync.
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # Find agents who are currently on active approved leave
        active_leaves = db.query(AgentLeave).filter(
            AgentLeave.status == "approved",
            AgentLeave.start_datetime <= now,
            AgentLeave.end_datetime >= now,
        ).all()

        agent_ids_on_leave = set()
        for leave in active_leaves:
            agent = db.query(User).filter(User.id == leave.agent_id).first()
            if agent and _is_on_leave(agent, now, db):
                agent_ids_on_leave.add(agent.id)

        for agent_id in agent_ids_on_leave:
            agent = db.query(User).filter(User.id == agent_id).first()
            if not agent:
                continue

            # Reassign ALL open and in-progress tickets, never touch resolved/closed
            tickets = db.query(Ticket).filter(
                (Ticket.assigned_agent_id == agent.id) | (Ticket.assigned_agent_name == agent.name),
                Ticket.status.in_(["open", "in_progress"]),
            ).all()

            if not tickets:
                continue

            print(f"[REROUTE] Agent '{agent.name}' is on active leave. "
                  f"Reassigning {len(tickets)} open/in-progress tickets.")

            for ticket in tickets:
                try:
                    old_name = agent.name
                    new_agent, reason = assign_agent_for_ticket(
                        ticket, ticket.assigned_team, db,
                        override_by="Leave Scheduler",
                        exclude_agent_id=agent.id,
                        reason_prefix=f"Reassigned due to leave: Reassigned from {old_name} (on leave). ",
                    )

                    if new_agent:
                        ticket.assigned_agent_id = new_agent.id
                        ticket.assigned_agent_name = new_agent.name

                    # Handover comment: "Reassigned from <agent> (on leave)"
                    db.add(TicketComment(
                        ticket_id   = ticket.id,
                        author_name = "System / Availability Scheduler",
                        author_role = "agent",
                        content     = f"Reassigned from {old_name} (on leave)",
                        is_internal = True,
                    ))
                    db.commit()  # commit per ticket (idempotent, per-ticket commit)
                except Exception as e:
                    db.rollback()
                    print(f"[REROUTE ERROR] Ticket #{ticket.id}: {e}")

        for leave in active_leaves:
            leave.is_processed = True
        db.commit()

    except Exception as e:
        print(f"[REROUTE ERROR] reroute_on_leave_approval: {e}")
        db.rollback()
    finally:
        db.close()


# ── Job 2: Handover before shift end ─────────────────────────

def handover_before_shift_end():
    """
    30 minutes before an agent's shift ends, reassign their unstarted tickets.
    In-progress tickets are NOT touched — team lead is notified instead.
    B4: handles overnight shifts correctly by comparing times as minutes-since-midnight.
    """
    db = SessionLocal()
    try:
        now_utc = datetime.utcnow()
        handover_cutoff = now_utc + timedelta(minutes=HANDOVER_MINUTES)

        agents = db.query(User).filter(
            User.role.in_(["agent", "manager"])
        ).all()

        for agent in agents:
            local_now    = _agent_local_now(agent, now_utc)
            local_cutoff = _agent_local_now(agent, handover_cutoff)
            weekday      = local_now.weekday()

            # B4: convert HH:MM to minutes-since-midnight for safe cross-midnight comparison
            def to_mins(hhmm: str) -> int:
                h, m = hhmm.split(":")
                return int(h) * 60 + int(m)

            now_mins    = local_now.hour * 60 + local_now.minute
            cutoff_mins = local_cutoff.hour * 60 + local_cutoff.minute
            # If cutoff crossed midnight, add 1440 so arithmetic stays valid
            if cutoff_mins < now_mins:
                cutoff_mins += 1440

            shifts = db.query(AgentShift).filter(
                AgentShift.agent_id  == agent.id,
                AgentShift.is_active == True,
            ).all()

            for shift in shifts:
                s_mins = to_mins(shift.start_time)
                e_mins = to_mins(shift.end_time)

                # Overnight shift: end wraps past midnight
                if e_mins < s_mins:
                    e_mins += 1440

                # Agent is currently on shift
                on_shift_now = s_mins <= now_mins <= e_mins

                # Shift ends within the handover window
                # B4: compare in the same minute-space
                ends_soon = now_mins <= e_mins <= cutoff_mins

                # Weekday check: for overnight shifts the shift may have started yesterday
                shift_weekday_match = (
                    shift.weekday == weekday or
                    (e_mins >= 1440 and shift.weekday == (weekday - 1) % 7)
                )

                if on_shift_now and ends_soon and shift_weekday_match:
                    _do_handover(agent, shift, db, now_utc)

        db.commit()
    except Exception as e:
        print(f"[HANDOVER ERROR] handover_before_shift_end: {e}")
        db.rollback()
    finally:
        db.close()


def _do_handover(agent: User, shift, db, now_utc: datetime):
    """Reassign unstarted tickets; notify team lead about in-progress ones."""
    unstarted = db.query(Ticket).filter(
        Ticket.assigned_agent_name == agent.name,
        Ticket.status.in_(UNSTARTED_STATUSES),
    ).all()

    in_progress = db.query(Ticket).filter(
        Ticket.assigned_agent_name == agent.name,
        Ticket.status == "in_progress",
    ).all()

    print(f"[HANDOVER] Agent '{agent.name}' shift ends at {shift.end_time}. "
          f"Handing over {len(unstarted)} unstarted, "
          f"notifying about {len(in_progress)} in-progress tickets.")

    for ticket in unstarted:
        try:
            new_agent, reason = assign_agent_for_ticket(ticket, ticket.assigned_team, db)
            if new_agent:
                old_name = ticket.assigned_agent_name
                ticket.assigned_agent_name = new_agent.name
                db.add(TicketComment(
                    ticket_id   = ticket.id,
                    author_name = "System / Shift Handover",
                    author_role = "agent",
                    content     = (f"Shift handover: '{old_name}' shift ends at "
                                   f"{shift.end_time}. Reassigned to '{new_agent.name}'. "
                                   f"Reason: {reason}"),
                    is_internal = True,
                ))
            db.commit()  # B9: commit per ticket
        except Exception as e:
            db.rollback()
            print(f"[HANDOVER ERROR] Ticket #{ticket.id}: {e}")

    for ticket in in_progress:
        from app.models.sla import SLAEscalationLog
        db.add(SLAEscalationLog(
            ticket_id            = ticket.id,
            team_name            = ticket.assigned_team or "Unknown",
            manager_name         = "Team Lead",
            escalation_reason    = f"SHIFT_END_INPROGRESS: {agent.name} shift ends {shift.end_time}",
            time_overdue_minutes = 0.0,
        ))
        print(f"[HANDOVER NOTIFY] Ticket #{ticket.id} in-progress with "
              f"'{agent.name}' — team lead notified, not reassigned.")
