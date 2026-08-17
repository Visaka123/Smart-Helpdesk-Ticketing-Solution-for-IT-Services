import sqlite3
import os
import pandas as pd

dbs = [
    "D:/smart_help_desk/smart_helpdesk.db",
    "D:/smart_help_desk/smart-helpdesk/backend/smart_helpdesk.db"
]

for db in dbs:
    if os.path.exists(db):
        print(f"\n==================== DB: {db} ====================")
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        print("Tables in DB:", tables)
        
        for t in tables:
            df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
            print(f"\n--- Table '{t}': {len(df)} rows ---")
            print("Columns:", list(df.columns))
            if 'status' in df.columns:
                print("Status counts:\n", df['status'].value_counts(dropna=False))
            if 'resolved_at' in df.columns:
                non_null = df[df['resolved_at'].notnull()]
                print(f"Non-null 'resolved_at': {len(non_null)} rows")
                if len(non_null) > 0:
                    print(non_null[['id', 'created_at', 'resolved_at']])
            if t == 'knowledge_articles' and 'helpful_count' in df.columns:
                print(df[['id', 'title', 'helpful_count', 'unhelpful_count']])
            if t == 'duplicate_feedback_logs':
                print(df.head(10))
        conn.close()
