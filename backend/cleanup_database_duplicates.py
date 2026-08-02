import sqlite3
import os

db_path = "smart_helpdesk.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("[CLEANUP] Starting database schema migration and duplicate cleanup...")

    # 1. Add satisfaction_rating and satisfaction_feedback columns if missing
    cursor.execute("PRAGMA table_info(tickets)")
    existing_cols = [row[1] for row in cursor.fetchall()]

    if "satisfaction_rating" not in existing_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN satisfaction_rating INTEGER")
        print("[MIGRATION] Added satisfaction_rating column to tickets table.")

    if "satisfaction_feedback" not in existing_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN satisfaction_feedback TEXT")
        print("[MIGRATION] Added satisfaction_feedback column to tickets table.")

    # 2. Update created_by field for existing sample tickets to map to valid users
    cursor.execute("UPDATE tickets SET created_by = 5, requester_name = 'Alice Employee' WHERE id IN (1, 3)")
    cursor.execute("UPDATE tickets SET created_by = 6, requester_name = 'Bob Sales Employee' WHERE id IN (2, 4)")

    # 3. Clean up test duplicate tickets (e.g. tickets #5, #6, #7, #8, #9, etc. created during automated test runs)
    cursor.execute("SELECT id, title, description, requester_name FROM tickets ORDER BY id ASC")
    all_tickets = cursor.fetchall()

    seen_keys = {}
    duplicates_to_delete = []

    for t_id, title, desc, req_name in all_tickets:
        key = (title.strip().lower(), (desc or '').strip().lower())
        if key in seen_keys:
            duplicates_to_delete.append(t_id)
        else:
            seen_keys[key] = t_id

    print(f"[CLEANUP] Found {len(duplicates_to_delete)} duplicate ticket records: {duplicates_to_delete}")

    for dup_id in duplicates_to_delete:
        cursor.execute("DELETE FROM tickets WHERE id = ?", (dup_id,))
        cursor.execute("DELETE FROM ticket_requesters WHERE ticket_id = ?", (dup_id,))
        cursor.execute("DELETE FROM ticket_comments WHERE ticket_id = ?", (dup_id,))
        cursor.execute("DELETE FROM sla_escalation_logs WHERE ticket_id = ?", (dup_id,))

    conn.commit()
    conn.close()
    print("[CLEANUP] Database schema migration and duplicate removal completed successfully!")
