import sqlite3

conn = sqlite3.connect("smart_helpdesk.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(users)")
cols = [row[1] for row in cur.fetchall()]
print("Existing columns:", cols)

if "timezone" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC'")
    print("[MIGRATE] Added users.timezone")
else:
    print("[MIGRATE] users.timezone already exists — skipped")

if "max_open_tickets" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN max_open_tickets INTEGER DEFAULT 10")
    print("[MIGRATE] Added users.max_open_tickets")
else:
    print("[MIGRATE] users.max_open_tickets already exists — skipped")

conn.commit()
conn.close()
print("[MIGRATE] Done.")
