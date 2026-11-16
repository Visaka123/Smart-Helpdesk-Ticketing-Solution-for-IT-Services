"""
migrate_hr_sync.py

Adds source, external_id, and last_synced_at columns to agent_leaves table if not already present.
Safe to re-run (idempotent).
"""
import sqlite3
import os
from pathlib import Path

def run_migration():
    # Find smart_helpdesk.db
    possible_paths = [
        Path(__file__).resolve().parent / "smart_helpdesk.db",
        Path("smart-helpdesk/backend/smart_helpdesk.db"),
        Path("smart_helpdesk.db"),
    ]

    target_db = None
    for p in possible_paths:
        if p.exists():
            target_db = p
            break

    if not target_db:
        print("[MIGRATE WARN] smart_helpdesk.db not found in standard paths.")
        return

    print(f"[MIGRATE] Running migration on {target_db}...")
    conn = sqlite3.connect(str(target_db))
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(agent_leaves)")
    existing_cols = [row[1] for row in cursor.fetchall()]

    if "source" not in existing_cols:
        cursor.execute("ALTER TABLE agent_leaves ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'manual'")
        print("[MIGRATE] Added 'source' column to agent_leaves.")
    else:
        print("[MIGRATE] Column 'source' already exists.")

    if "external_id" not in existing_cols:
        cursor.execute("ALTER TABLE agent_leaves ADD COLUMN external_id VARCHAR(100)")
        print("[MIGRATE] Added 'external_id' column to agent_leaves.")
    else:
        print("[MIGRATE] Column 'external_id' already exists.")

    if "last_synced_at" not in existing_cols:
        cursor.execute("ALTER TABLE agent_leaves ADD COLUMN last_synced_at DATETIME")
        print("[MIGRATE] Added 'last_synced_at' column to agent_leaves.")
    else:
        print("[MIGRATE] Column 'last_synced_at' already exists.")

    # Create index on external_id if possible
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_leaves_ext_id ON agent_leaves (external_id)")
    except Exception:
        pass

    conn.commit()
    conn.close()
    print("[MIGRATE] agent_leaves migration completed successfully!")

if __name__ == "__main__":
    run_migration()
