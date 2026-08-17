import sqlite3
import os
import glob
import pickle
import json
import pandas as pd

print("=== 1. CHECKING DATABASES ===")
for db_path in ["smart-helpdesk/backend/smart_helpdesk.db", "smart_helpdesk.db"]:
    if os.path.exists(db_path):
        print(f"\nDatabase: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        print("Tables:", [t[0] for t in tables])
        for t in tables:
            tname = t[0]
            cnt = cursor.execute(f"SELECT count(*) FROM {tname}").fetchone()[0]
            print(f"  Table '{tname}': {cnt} rows")
            # Print columns
            cols = [col[1] for col in cursor.execute(f"PRAGMA table_info({tname})").fetchall()]
            print(f"    Columns: {cols}")
        conn.close()

print("\n=== 2. CHECKING KNOWLEDGE BASE ASSETS ===")
kb_pdf_dir = "smart-helpdesk/backend/model_assets/knowlegde"
if os.path.exists(kb_pdf_dir):
    pdfs = os.listdir(kb_pdf_dir)
    print(f"PDFs in {kb_pdf_dir}: {len(pdfs)} files -> {pdfs}")

kb_index = "smart-helpdesk/backend/model_assets/models/kb.index"
if os.path.exists(kb_index):
    print(f"FAISS index exists: {kb_index}, size: {os.path.getsize(kb_index)} bytes")

kb_docs_pkl = "smart-helpdesk/backend/model_assets/models/kb_docs.pkl"
if os.path.exists(kb_docs_pkl):
    with open(kb_docs_pkl, "rb") as f:
        docs = pickle.load(f)
    print(f"kb_docs.pkl exists: {len(docs)} documents loaded")
    for i, d in enumerate(docs[:5]):
        print(f"  Doc {i}: {d[:80]}...")

print("\n=== 3. CHECKING AUDIT / EXPERIMENT / EVALUATION SCRIPTS ===")
backend_dir = "smart-helpdesk/backend"
py_files = [f for f in os.listdir(backend_dir) if f.endswith(".py")]
print("Python scripts in backend:", py_files)
