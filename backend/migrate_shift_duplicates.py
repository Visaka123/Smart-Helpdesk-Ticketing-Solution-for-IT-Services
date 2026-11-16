import sqlite3
import os
import shutil
from pathlib import Path

def run_migration():
    db_path = str(Path(__file__).resolve().parent / "smart_helpdesk.db")
    if not os.path.exists(db_path):
        print(f"[MIGRATE] Database not found at {db_path}")
        return

    # Back up smart_helpdesk.db before running migration
    backup_path = db_path + ".bak"
    shutil.copy2(db_path, backup_path)
    print(f"[MIGRATE] Database backed up to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Delete duplicate shifts, keeping the MIN(id) for each (agent_id, weekday, start_time, end_time)
    cursor.execute("""
        DELETE FROM agent_shifts
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM agent_shifts
            GROUP BY agent_id, weekday, start_time, end_time
        )
    """)
    deleted_dupes = cursor.rowcount
    print(f"[MIGRATE] Deleted {deleted_dupes} duplicate shift rows.")

    # 2. Delete shifts belonging to manager-role users (admin, manager, team_lead)
    cursor.execute("""
        DELETE FROM agent_shifts
        WHERE agent_id IN (
            SELECT id FROM users
            WHERE role IN ('manager', 'admin', 'team_lead')
        )
    """)
    deleted_mgr_shifts = cursor.rowcount
    print(f"[MIGRATE] Deleted {deleted_mgr_shifts} shifts belonging to manager-role users.")

    # 3. Create unique index on (agent_id, weekday, start_time, end_time)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_shift_window
        ON agent_shifts (agent_id, weekday, start_time, end_time)
    """)
    print("[MIGRATE] Verified/created unique index uq_agent_shift_window on agent_shifts.")

    conn.commit()

    # Verify remaining shifts
    cursor.execute("SELECT id, agent_id, agent_name, weekday, start_time, end_time FROM agent_shifts")
    remaining = cursor.fetchall()
    print(f"[MIGRATE] Remaining shifts count: {len(remaining)}")
    for r in remaining:
        print(f"  Shift id={r[0]}: agent_id={r[1]} ({r[2]}), weekday={r[3]}, window={r[4]}-{r[5]}")

    conn.close()

if __name__ == "__main__":
    run_migration()
