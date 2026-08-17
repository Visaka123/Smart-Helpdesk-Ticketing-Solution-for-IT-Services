import sqlite3
import pandas as pd

conn = sqlite3.connect("D:/smart_help_desk/smart-helpdesk/backend/smart_helpdesk.db")
df = pd.read_sql_query("SELECT * FROM tickets", conn)
print("=== ALL 10 TICKETS IN DB ===")
for idx, r in df.iterrows():
    print(f"\nTicket #{r['id']}: '{r['title']}' | Status: {r['status']}")
    print(f"  Created: {r['created_at']} | Resolved: {r['resolved_at']}")
    print(f"  Routing Conf: {r['routing_confidence']} | Sim Score: {r['similarity_score']}")
    print(f"  Res Summary: {r['resolution_summary']} | Res Detail: {r['resolution_detail']}")
    print(f"  Satisfaction Rating: {r['satisfaction_rating']} | Feedback: {r['satisfaction_feedback']}")

conn.close()
