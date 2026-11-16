import sqlite3
import os

db_path = "smart_helpdesk.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create ticket_requesters table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ticket_requesters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL REFERENCES tickets(id),
        user_id INTEGER REFERENCES users(id),
        requester_name TEXT NOT NULL,
        requester_department TEXT DEFAULT 'General',
        linked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        link_reason TEXT DEFAULT 'hard_blocked_auto_linked'
    )
    """)

    # B12: Add is_processed column to agent_leaves if missing
    cursor.execute("PRAGMA table_info(agent_leaves)")
    cols = [row[1] for row in cursor.fetchall()]
    if "is_processed" not in cols:
        cursor.execute(
            "ALTER TABLE agent_leaves ADD COLUMN is_processed INTEGER NOT NULL DEFAULT 0"
        )
        print("[MIGRATE] agent_leaves.is_processed column added.")
    else:
        print("[MIGRATE] agent_leaves.is_processed already exists — skipped.")

    # HR Sync columns for agent_leaves
    if "source" not in cols:
        cursor.execute("ALTER TABLE agent_leaves ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'manual'")
        print("[MIGRATE] agent_leaves.source column added.")
    if "external_id" not in cols:
        cursor.execute("ALTER TABLE agent_leaves ADD COLUMN external_id VARCHAR(100)")
        print("[MIGRATE] agent_leaves.external_id column added.")
    if "last_synced_at" not in cols:
        cursor.execute("ALTER TABLE agent_leaves ADD COLUMN last_synced_at DATETIME")
        print("[MIGRATE] agent_leaves.last_synced_at column added.")

    # B13: Add timezone column to users if missing
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    if "timezone" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC'")
        print("[MIGRATE] users.timezone column added.")
    else:
        print("[MIGRATE] users.timezone already exists — skipped.")

    # B14: Add max_open_tickets column to users if missing
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    if "max_open_tickets" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN max_open_tickets INTEGER DEFAULT 10")
        print("[MIGRATE] users.max_open_tickets column added.")
    else:
        print("[MIGRATE] users.max_open_tickets already exists — skipped.")

    conn.commit()
    conn.close()
    print("[MIGRATE] ticket_requesters table created/verified successfully!")
