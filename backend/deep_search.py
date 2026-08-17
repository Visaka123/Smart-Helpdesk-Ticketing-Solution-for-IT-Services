import os
import glob
import sqlite3
import pandas as pd
import json

root_dir = "D:/smart_help_desk"

print("--- ALL DB TABLES AND CONTENT ---")
for db_path in [os.path.join(root_dir, "smart_helpdesk.db"), os.path.join(root_dir, "smart-helpdesk", "backend", "smart_helpdesk.db")]:
    if os.path.exists(db_path):
        print(f"\nDB PATH: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        for t in tables:
            df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
            print(f"Table '{t}': {len(df)} rows")
            if t == 'knowledge_articles':
                print(df[['id', 'title', 'category', 'source_file', 'helpful_count', 'unhelpful_count']])
            if t == 'retraining_logs':
                print(df)
            if t == 'duplicate_feedback_logs':
                print(df)
        conn.close()

print("\n--- SEARCHING FOR EXPERIMENT LOGS OR EVALUATION METRICS IN BACKEND ---")
backend_path = os.path.join(root_dir, "smart-helpdesk", "backend")
for root, dirs, files in os.walk(backend_path):
    for f in files:
        if f.endswith(('.py', '.json', '.csv', '.md', '.txt', '.log')):
            filepath = os.path.join(root, f)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    for term in ['precision', 'recall', 'mrr', 'ndcg', 'hit rate', 'hit_rate', 'latency', 'ftr', 'first-time', 'first_time', 'resolution_time', 'knowledge', 'rag']:
                        if term in content.lower():
                            print(f"Match '{term}' in file: {filepath}")
            except Exception as e:
                pass
