"""
backfill_unassigned.py

Phase 2 Backfill Script:
1. Moves ticket #26 and any ticket in 'Unassigned-Urgent' or without an agent to a valid skilled owner.
2. Reassigns any ticket currently owned by an on-leave agent to a valid owner.
3. Records human-readable AssignmentLog rows for every re-routed ticket.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add app to path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database.database import SessionLocal
from app.models.ticket import Ticket
from app.models.user import User
from app.models.availability import AgentLeave
from app.availability.service import assign_agent_for_ticket, _is_on_leave


def run_backfill():
    db = SessionLocal()
    try:
        now_utc = datetime.utcnow()
        print("[BACKFILL] Starting backfill of unassigned / on-leave tickets...")

        # 1. Backfill Ticket #26 specifically and any unassigned tickets
        unassigned_tickets = db.query(Ticket).filter(
            (Ticket.id == 26) |
            (Ticket.assigned_team == "Unassigned-Urgent") |
            (Ticket.assigned_agent_name == None)
        ).all()

        print(f"[BACKFILL] Found {len(unassigned_tickets)} unassigned / orphaned tickets.")
        for t in unassigned_tickets:
            # Determine appropriate team
            if not t.assigned_team or t.assigned_team in ["Unassigned-Urgent", "Unassigned/Triage"]:
                # Default to IT Support or Network Team based on title/category
                title_lower = (t.title or "").lower()
                if any(w in title_lower for w in ["license", "software", "intellij", "laptop", "email", "access"]):
                    t.assigned_team = "IT Support"
                elif any(w in title_lower for w in ["network", "router", "switch", "vpn", "firewall", "wifi"]):
                    t.assigned_team = "Network Team"
                else:
                    t.assigned_team = "IT Support"

            chosen, reason = assign_agent_for_ticket(t, t.assigned_team, db, override_by="Phase 2 Backfill")
            print(f"[BACKFILL] Ticket #{t.id} ('{t.title}') assigned to '{t.assigned_agent_name}' in '{t.assigned_team}'. Reason: {reason}")

        # 2. Reassign any ticket owned by an agent currently on approved leave
        agents_on_leave = [
            a for a in db.query(User).filter(User.role == "agent").all()
            if _is_on_leave(a, now_utc, db)
        ]
        leave_agent_names = [a.name for a in agents_on_leave]
        if leave_agent_names:
            print(f"[BACKFILL] Agents currently on leave: {leave_agent_names}")
            leave_tickets = db.query(Ticket).filter(
                Ticket.assigned_agent_name.in_(leave_agent_names),
                Ticket.status.in_(["open", "new", "assigned", "in_progress"])
            ).all()
            print(f"[BACKFILL] Found {len(leave_tickets)} tickets currently held by on-leave agents.")
            for lt in leave_tickets:
                chosen, reason = assign_agent_for_ticket(lt, lt.assigned_team, db, override_by="Phase 2 Leave Backfill")
                print(f"[BACKFILL] Reassigned ticket #{lt.id} from on-leave agent to '{lt.assigned_agent_name}'. Reason: {reason}")
        else:
            print("[BACKFILL] No agents currently on leave holding open tickets.")

        db.commit()
        print("[BACKFILL] Backfill completed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    run_backfill()
