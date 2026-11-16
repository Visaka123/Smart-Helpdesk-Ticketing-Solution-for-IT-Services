"""
backend/migrate_suggestion_feedback.py

Migration script to:
1. Add 'suggestions_tried' column to 'tickets' table if not present.
2. Create 'suggestion_feedback' table if not present.
"""
import sqlite3
import os
import sys

DB_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_helpdesk.db"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "smart_helpdesk.db"),
    r"D:\smart_help_desk\smart-helpdesk\backend\smart_helpdesk.db",
    r"D:\smart_help_desk\smart_helpdesk.db",
]

def run_migration():
    migrated_any = False
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if tickets table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tickets'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(tickets)")
                cols = [row[1] for row in cursor.fetchall()]
                if "suggestions_tried" not in cols:
                    print(f"Adding column 'suggestions_tried' to {db_path}...")
                    cursor.execute("ALTER TABLE tickets ADD COLUMN suggestions_tried TEXT")
                    migrated_any = True
                else:
                    print(f"Column 'suggestions_tried' already exists in {db_path}.")

            # Check / create suggestion_feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suggestion_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    query_text TEXT,
                    suggested_ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                    action VARCHAR(50) NOT NULL,
                    relevance FLOAT NOT NULL DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
            print(f"Verified schema for {db_path}")
            migrated_any = True
        except Exception as e:
            print(f"Migration error for {db_path}: {e}")

    if not migrated_any:
        print("No active databases found to migrate.")
    else:
        print("Migration complete!")

if __name__ == "__main__":
    run_migration()
