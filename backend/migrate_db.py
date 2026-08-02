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

    conn.commit()
    conn.close()
    print("[MIGRATE] ticket_requesters table created/verified successfully!")
