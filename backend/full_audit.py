"""
full_audit.py
─────────────
Complete data audit from master.csv and all raw datasets.
"""
import os, re
import pandas as pd
import numpy as np
from collections import Counter

pd.set_option("display.max_colwidth", 100)
pd.set_option("display.width", 200)

PROCESSED = "model_assets/processed"
RAW       = "model_assets/raw"

# ── 1. master.csv overview ────────────────────────────────────
print("=" * 65)
print("  master.csv OVERVIEW")
print("=" * 65)
master = pd.read_csv(os.path.join(PROCESSED, "master.csv"), low_memory=False)
master.columns = master.columns.str.lower().str.strip()
print(f"Shape   : {master.shape}")
print(f"Columns : {list(master.columns)}")

# ── 2. Identify real label columns ───────────────────────────
print("\n" + "=" * 65)
print("  REAL LABEL COLUMNS IN master.csv")
print("=" * 65)
label_candidates = ["department","assigned_team","queue","assignment_group","category"]
for col in label_candidates:
    if col in master.columns:
        non_null = master[col].dropna()
        print(f"\n  [{col}]  non-null={len(non_null)}")
        print(f"  Top values:\n{non_null.value_counts().head(10).to_string()}")

# ── 3. Text columns ───────────────────────────────────────────
print("\n" + "=" * 65)
print("  TEXT COLUMNS IN master.csv")
print("=" * 65)
text_candidates = ["body","description","subject","body.1"]
for col in text_candidates:
    if col in master.columns:
        non_null = master[col].dropna()
        print(f"\n  [{col}]  non-null={len(non_null)}")
        sample = non_null.iloc[0] if len(non_null) > 0 else ""
        print(f"  Sample: {repr(str(sample)[:200])}")

# ── 4. Per-source dataset analysis ───────────────────────────
print("\n" + "=" * 65)
print("  PER-SOURCE DATASET ANALYSIS")
print("=" * 65)

# tickets1
p1 = os.path.join(RAW, "tickets1.csv/IT Support Ticket Data.csv")
if os.path.exists(p1):
    d1 = pd.read_csv(p1)
    print(f"\n[tickets1] shape={d1.shape}")
    print(f"  columns: {list(d1.columns)}")
    print(f"  Department:\n{d1['Department'].value_counts().to_string()}")
    print(f"  Body sample: {repr(str(d1['Body'].iloc[0])[:200])}")
    print(f"  Unique bodies: {d1['Body'].nunique()} / {len(d1)}")

# tickets2
p2 = os.path.join(RAW, "tickets2.csv/helpdesk_tickets.csv")
if os.path.exists(p2):
    d2 = pd.read_csv(p2)
    print(f"\n[tickets2] shape={d2.shape}")
    print(f"  columns: {list(d2.columns)}")
    print(f"  Assigned_Team:\n{d2['Assigned_Team'].value_counts().to_string()}")
    print(f"  Unique descriptions: {d2['Description'].nunique()} / {len(d2)}")
    print(f"  Description sample: {repr(str(d2['Description'].iloc[0])[:200])}")

# tickets3 files
t3_files = [
    "tickets3.csv/aa_dataset-tickets-multi-lang-5-2-50-version.csv",
    "tickets3.csv/dataset-tickets-multi-lang3-4k.csv",
    "tickets3.csv/dataset-tickets-multi-lang-4-20k.csv",
]
for fname in t3_files:
    fp = os.path.join(RAW, fname)
    if os.path.exists(fp):
        d3 = pd.read_csv(fp, low_memory=False)
        en = d3[d3.get("language","en") == "en"] if "language" in d3.columns else d3
        print(f"\n[{fname}] shape={d3.shape}, English={len(en)}")
        print(f"  queue:\n{en['queue'].value_counts().to_string()}")
        print(f"  Unique bodies (EN): {en['body'].nunique()}")
        print(f"  Body sample: {repr(str(en['body'].iloc[0])[:200])}")

# tickets4
p4 = os.path.join(RAW, "tickets4.csv/incident_event_log.csv")
if os.path.exists(p4):
    d4 = pd.read_csv(p4, low_memory=False)
    print(f"\n[tickets4] shape={d4.shape}")
    print(f"  assignment_group top:\n{d4['assignment_group'].value_counts().head(10).to_string()}")
    desc_cols = [c for c in d4.columns if "desc" in c.lower() or "short" in c.lower()]
    print(f"  Description-like cols: {desc_cols}")

# ── 5. training_real.csv current state ───────────────────────
print("\n" + "=" * 65)
print("  training_real.csv CURRENT STATE")
print("=" * 65)
tr = pd.read_csv(os.path.join(PROCESSED, "training_real.csv"))
print(f"Shape   : {tr.shape}")
print(f"Classes : {tr['assigned_team'].value_counts().to_string()}")
print(f"\nSample rows:")
print(tr.head(5).to_string())
print(f"\nConclusion: This file has {len(tr)} rows — it is the OLD keyword-generated")
print(f"dataset, NOT the large real dataset. It needs to be rebuilt from master.csv.")
