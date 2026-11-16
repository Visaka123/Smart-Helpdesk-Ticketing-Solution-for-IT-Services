"""
app/availability/sync.py

Synchronization engine between external HR LeaveProvider and local agent_leaves.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.availability import AgentLeave
from app.availability.providers import LeaveProvider, MockHRProvider
from app.database.database import SessionLocal

logger = logging.getLogger(__name__)

# In-memory record of the last sync timestamp
_GLOBAL_LAST_SYNC_TIME: Optional[datetime] = None


def _parse_datetime(val: Any, is_end: bool = False) -> datetime:
    """Safely parse various datetime/date string formats."""
    if isinstance(val, datetime):
        return val
    s = str(val).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d" and is_end:
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Unrecognized datetime format: {val}")


def sync_leaves(provider: LeaveProvider, db: Session) -> Dict[str, Any]:
    """
    Synchronizes leaves from a LeaveProvider into agent_leaves:
      1. Matches users by email.
      2. Upserts by external_id (idempotent, no duplicates).
      3. Marks leaves cancelled if removed from source.
      4. Ignores pending leaves.
      5. Skips bad records without halting the batch.
      6. Stores only dates, never a leave reason.
      7. Triggers reroute_on_leave_approval for newly approved leaves.
    """
    global _GLOBAL_LAST_SYNC_TIME

    records = provider.fetch_approved_leave()
    now = datetime.utcnow()

    synced_count = 0
    cancelled_count = 0
    skipped_count = 0
    errors = []
    valid_external_ids = set()
    newly_approved_count = 0

    for rec in records:
        try:
            if not isinstance(rec, dict):
                skipped_count += 1
                errors.append("Record is not a dict")
                continue

            external_id = str(rec.get("external_id") or "").strip()
            if not external_id:
                skipped_count += 1
                errors.append("Missing external_id")
                continue

            # Requirement: ignore pending leave
            status = str(rec.get("status") or "").strip().lower()
            if status != "approved":
                skipped_count += 1
                continue

            user_email = str(rec.get("user_email") or "").strip().lower()
            if not user_email:
                skipped_count += 1
                errors.append(f"Record {external_id} missing user_email")
                continue

            # Match user by email
            agent = db.query(User).filter(func.lower(User.email) == user_email).first()
            if not agent:
                skipped_count += 1
                errors.append(f"No user found for email: {user_email}")
                continue

            # Parse dates
            start_dt = _parse_datetime(rec.get("start"), is_end=False)
            end_dt = _parse_datetime(rec.get("end"), is_end=True)
            if end_dt < start_dt:
                skipped_count += 1
                errors.append(f"Invalid range for {external_id}: end ({end_dt}) < start ({start_dt})")
                continue

            leave_type = "half_day" if rec.get("half_day") else "annual"

            # Upsert by external_id
            existing = db.query(AgentLeave).filter(AgentLeave.external_id == external_id).first()
            if existing:
                was_approved = (existing.status == "approved")
                existing.agent_id       = agent.id
                existing.agent_name     = agent.name
                existing.start_datetime = start_dt
                existing.end_datetime   = end_dt
                existing.leave_type     = leave_type
                existing.status         = "approved"
                existing.source         = "hr_sync"
                existing.notes          = None  # Store only dates, never a leave reason
                existing.last_synced_at = now
                if not was_approved:
                    existing.is_processed = False
                    newly_approved_count += 1
                synced_count += 1
            else:
                new_leave = AgentLeave(
                    agent_id       = agent.id,
                    agent_name     = agent.name,
                    start_datetime = start_dt,
                    end_datetime   = end_dt,
                    leave_type     = leave_type,
                    status         = "approved",
                    source         = "hr_sync",
                    external_id    = external_id,
                    notes          = None,  # Store only dates, never a leave reason
                    approved_by    = "HR System",
                    is_processed   = False,
                    last_synced_at = now,
                )
                db.add(new_leave)
                synced_count += 1
                newly_approved_count += 1

            valid_external_ids.add(external_id)

        except Exception as e:
            # Skip bad records without stopping the batch
            skipped_count += 1
            errors.append(f"Error processing record {rec.get('external_id', 'unknown')}: {e}")
            logger.warning(f"[HR SYNC SKIP] Bad record: {e}")

    # Requirement: mark leave cancelled if it is removed from the source
    existing_hr_leaves = db.query(AgentLeave).filter(
        AgentLeave.source == "hr_sync",
        AgentLeave.status == "approved"
    ).all()

    for leave in existing_hr_leaves:
        if leave.external_id not in valid_external_ids:
            leave.status = "cancelled"
            leave.last_synced_at = now
            cancelled_count += 1

    db.commit()
    _GLOBAL_LAST_SYNC_TIME = now

    # Requirement: trigger existing reroute for newly approved leave
    if newly_approved_count > 0:
        try:
            from app.availability.scheduler import reroute_on_leave_approval
            reroute_on_leave_approval()
        except Exception as re_err:
            logger.error(f"[HR SYNC REROUTE ERROR] {re_err}")

    return {
        "success": True,
        "synced": synced_count,
        "cancelled": cancelled_count,
        "skipped": skipped_count,
        "errors": errors,
        "last_synced_at": now.isoformat(),
    }


def get_sync_status(db: Session) -> Dict[str, Any]:
    """
    Returns current sync status, last sync timestamp, and staleness (>60 mins).
    """
    global _GLOBAL_LAST_SYNC_TIME

    # Check database for most recent sync if memory is not set
    last_dt = _GLOBAL_LAST_SYNC_TIME
    if not last_dt:
        max_synced = db.query(func.max(AgentLeave.last_synced_at)).filter(
            AgentLeave.source == "hr_sync"
        ).scalar()
        if max_synced:
            last_dt = max_synced
            _GLOBAL_LAST_SYNC_TIME = last_dt

    now = datetime.utcnow()
    minutes_since = None
    stale = True

    if last_dt:
        minutes_since = max(0, int((now - last_dt).total_seconds() / 60))
        stale = minutes_since > 60

    return {
        "sync_enabled": True,
        "last_synced_at": last_dt.isoformat() if last_dt else None,
        "minutes_since_sync": minutes_since,
        "stale": stale,
    }


def sync_hr_leaves_job():
    """
    Background scheduler job called every 15 minutes.
    """
    db = SessionLocal()
    try:
        provider = MockHRProvider()
        res = sync_leaves(provider, db)
        print(f"[HR SYNC JOB] Completed: {res.get('synced')} synced, {res.get('cancelled')} cancelled.")
    except Exception as e:
        print(f"[HR SYNC JOB ERROR] {e}")
    finally:
        db.close()
