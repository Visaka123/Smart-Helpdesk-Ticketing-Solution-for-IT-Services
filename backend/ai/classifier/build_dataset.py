"""
build_dataset.py  (v4 — merge overlapping classes)
────────────────────────────────────────────────────
KEY FINDING from vocabulary analysis:
  IT Support, Product Support, Customer Service share identical
  top-50 vocabulary. Discriminative words:
    IT Support       : 2 unique words (devices, persists)
    Product Support  : 1 unique word  (address)
    Customer Service : 2 unique words (integrating, seeking)

  These 3 classes are SEMANTICALLY INDISTINGUISHABLE in this dataset.
  Keeping them separate is the root cause of 62% accuracy.

FIX: Merge all 3 into "General Support".
  This gives 6 clean classes with distinct vocabulary:
    Billing & Payments   -> billing, payment, charges, invoice, subscription
    Returns & Exchanges  -> return, product, outdated, measures
    Sales Support        -> sales, pricing, solutions, insights
    Service & Maintenance-> outage, disruption, maintenance, critical
    HR Support           -> employee, training, resources
    General Support      -> everything else (IT/Product/Customer)
"""

import os, re
import contractions
import pandas as pd

RAW = "model_assets/raw"
OUT = "model_assets/processed/training_real.csv"

LABEL_MAP = {
    # Merge the 3 indistinguishable classes
    "Technical Support":                "General Support",
    "It Support":                       "General Support",
    "IT Support":                       "General Support",
    "Customer Service":                 "General Support",
    "General Inquiry":                  "General Support",
    "Product Support":                  "General Support",
    # Keep distinct classes
    "Billing And Payments":             "Billing & Payments",
    "Billing and Payments":             "Billing & Payments",
    "Returns And Exchanges":            "Returns & Exchanges",
    "Returns and Exchanges":            "Returns & Exchanges",
    "Service Outages And Maintenance":  "Service & Maintenance",
    "Service Outages and Maintenance":  "Service & Maintenance",
    "Sales And Pre-Sales":              "Sales Support",
    "Sales and Pre-Sales":              "Sales Support",
    "Human Resources":                  "HR Support",
}

_SALUTATION = re.compile(
    r"dear\s+(customer\s+support(\s+team)?|support\s+team|it\s+(services\s+)?support\s+team"
    r"|team|sir|madam|helpdesk)[,.\s]*", re.IGNORECASE,
)
_HOPE_LINE  = re.compile(r"i hope this (message|email|letter) (reaches|finds) you[^.]*\.\s*", re.IGNORECASE)
_URL        = re.compile(r"https?://\S+|www\.\S+")
_EMAIL      = re.compile(r"\S+@\S+\.\S+")
_WHITESPACE = re.compile(r"\s+")

def clean_text(text):
    text = str(text)
    try:
        text = contractions.fix(text)
    except Exception:
        pass
    text = _SALUTATION.sub(" ", text)
    text = _HOPE_LINE.sub(" ", text)
    text = _URL.sub(" ", text)
    text = _EMAIL.sub(" ", text)
    text = text.encode("ascii", errors="ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9\s.,!?'\-]", " ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text

frames = []

# tickets1
p1 = os.path.join(RAW, "tickets1.csv/IT Support Ticket Data.csv")
if os.path.exists(p1):
    d = pd.read_csv(p1)[["Body","Department"]].rename(columns={"Body":"description","Department":"assigned_team"})
    frames.append(d)
    print(f"[tickets1] {len(d):,} rows")

# tickets3 (English only)
for fname in [
    "tickets3.csv/aa_dataset-tickets-multi-lang-5-2-50-version.csv",
    "tickets3.csv/dataset-tickets-german_normalized.csv",
    "tickets3.csv/dataset-tickets-german_normalized_50_5_2.csv",
    "tickets3.csv/dataset-tickets-multi-lang3-4k.csv",
    "tickets3.csv/dataset-tickets-multi-lang-4-20k.csv",
]:
    fp = os.path.join(RAW, fname)
    if not os.path.exists(fp): continue
    d = pd.read_csv(fp, low_memory=False)
    if "language" in d.columns:
        d = d[d["language"] == "en"]
    if len(d) == 0: continue
    d = d[["body","queue"]].rename(columns={"body":"description","queue":"assigned_team"})
    frames.append(d)
    print(f"[{fname}] {len(d):,} English rows")

df = pd.concat(frames, ignore_index=True)
print(f"\nCombined: {len(df):,}")

df["description"]   = df["description"].astype(str).str.strip()
df["assigned_team"] = df["assigned_team"].astype(str).str.strip()
df = df[~df["description"].isin(["","nan","None"])]
df = df[~df["assigned_team"].isin(["","nan","None"])]

# Map labels
df["assigned_team"] = df["assigned_team"].map(lambda x: LABEL_MAP.get(x, LABEL_MAP.get(x.title(), x)))

# Clean text
print("Cleaning text...")
df["description"] = df["description"].apply(clean_text)
df = df[df["description"].str.len() >= 40]

# Dedup on cleaned text
before = len(df)
df = df.drop_duplicates(subset=["description"])
print(f"Removed {before-len(df):,} duplicates")

# Remove rare classes
counts = df["assigned_team"].value_counts()
df = df[df["assigned_team"].isin(counts[counts >= 50].index)]

print(f"\nFINAL: {len(df):,} rows, {df['assigned_team'].nunique()} classes")
print(f"\nClass distribution:")
for cls, cnt in df["assigned_team"].value_counts().items():
    print(f"  {cls:<30} {cnt:>6,}  ({cnt/len(df)*100:.1f}%)")

imbalance = df["assigned_team"].value_counts().max() / df["assigned_team"].value_counts().min()
print(f"\nImbalance ratio: {imbalance:.1f}x")

os.makedirs("model_assets/processed", exist_ok=True)
df[["description","assigned_team"]].to_csv(OUT, index=False)
print(f"\nSaved to {OUT}")
