"""
data_audit.py
─────────────
Full data understanding audit before modeling.
Covers: shape, dtypes, class distribution, missing values,
duplicates, text quality, master.csv vs training_real.csv comparison,
vocabulary overlap between classes, and cleaning signal check.
"""

import re
import os
import pandas as pd
import numpy as np
from collections import Counter

pd.set_option("display.max_colwidth", 120)
pd.set_option("display.width", 200)

PROCESSED = "model_assets/processed"
RAW       = "model_assets/raw"

# ═══════════════════════════════════════════════════════════════
# STEP 1 — LOAD training_real.csv
# ═══════════════════════════════════════════════════════════════
print("=" * 65)
print("  STEP 1: LOAD training_real.csv")
print("=" * 65)

df = pd.read_csv(os.path.join(PROCESSED, "training_real.csv"))
print(f"\nShape   : {df.shape}")
print(f"Dtypes  :\n{df.dtypes}")
print(f"\nFirst 5 rows:\n{df.head()}")
print(f"\nMissing values:\n{df.isnull().sum()}")
print(f"\nDuplicate rows (exact): {df.duplicated().sum()}")
print(f"Duplicate descriptions : {df.duplicated(subset=['description']).sum()}")

# ═══════════════════════════════════════════════════════════════
# STEP 2 — CLASS DISTRIBUTION
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  STEP 2: CLASS DISTRIBUTION")
print("=" * 65)

dist = df["assigned_team"].value_counts()
total = len(df)
print(f"\n{'Class':<35} {'Count':>7}  {'%':>6}")
print("-" * 52)
for cls, cnt in dist.items():
    print(f"{cls:<35} {cnt:>7}  {cnt/total*100:>5.1f}%")

majority = dist.max()
minority = dist.min()
imbalance_ratio = majority / minority
print(f"\nImbalance ratio (majority/minority): {imbalance_ratio:.1f}x")
print(f"Majority class : {dist.idxmax()} ({majority})")
print(f"Minority class : {dist.idxmin()} ({minority})")

# ═══════════════════════════════════════════════════════════════
# STEP 3 — TEXT QUALITY ANALYSIS
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  STEP 3: TEXT QUALITY ANALYSIS")
print("=" * 65)

df["text_len"]   = df["description"].str.len()
df["word_count"] = df["description"].str.split().str.len()

print("\nText length stats per class:")
stats = df.groupby("assigned_team")["text_len"].agg(["mean", "min", "max", "std"])
stats.columns = ["mean_len", "min_len", "max_len", "std_len"]
print(stats.round(1).to_string())

print("\nWord count stats per class:")
wstats = df.groupby("assigned_team")["word_count"].agg(["mean", "min", "max"])
wstats.columns = ["mean_words", "min_words", "max_words"]
print(wstats.round(1).to_string())

# Check for very short descriptions that slipped through
short = df[df["text_len"] < 30]
print(f"\nDescriptions < 30 chars: {len(short)}")
if len(short) > 0:
    print(short[["description", "assigned_team"]].head(5).to_string())

# Check for boilerplate that should have been cleaned
boilerplate_patterns = [
    r"dear customer support",
    r"i hope this message",
    r"user reported.*further investigation",
]
print("\nBoilerplate check (should be 0 after cleaning):")
for pat in boilerplate_patterns:
    count = df["description"].str.contains(pat, case=False, regex=True).sum()
    status = "✓ CLEAN" if count == 0 else f"✗ {count} rows still contain this"
    print(f"  '{pat[:50]}' → {status}")

# ═══════════════════════════════════════════════════════════════
# STEP 4 — VOCABULARY OVERLAP BETWEEN CLASSES
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  STEP 4: VOCABULARY OVERLAP (top words per class)")
print("=" * 65)

STOPWORDS = {
    "the","a","an","is","it","in","on","at","to","for","of","and",
    "or","but","with","this","that","are","was","were","be","been",
    "have","has","had","do","does","did","will","would","could",
    "should","may","might","i","we","you","he","she","they","our",
    "your","my","their","its","not","no","so","as","by","from",
    "am","us","me","him","her","them","which","who","what","when",
    "where","how","all","any","some","more","also","can","just",
    "been","being","about","up","out","if","into","than","then",
    "there","these","those","such","after","before","during","while",
}

class_vocab = {}
for cls in df["assigned_team"].unique():
    texts = df[df["assigned_team"] == cls]["description"].str.lower()
    words = []
    for t in texts:
        words.extend(re.findall(r"\b[a-z]{3,}\b", t))
    freq = Counter(words)
    top = [(w, c) for w, c in freq.most_common(30) if w not in STOPWORDS][:10]
    class_vocab[cls] = set(w for w, _ in top)
    print(f"\n  {cls}:")
    print(f"    Top words: {', '.join(w for w, _ in top)}")

# Overlap matrix
print("\nVocabulary overlap between classes (Jaccard similarity):")
classes = list(class_vocab.keys())
print(f"{'':>30}", end="")
for c in classes:
    print(f"  {c[:12]:>12}", end="")
print()
for c1 in classes:
    print(f"{c1:>30}", end="")
    for c2 in classes:
        if c1 == c2:
            print(f"  {'---':>12}", end="")
        else:
            inter = len(class_vocab[c1] & class_vocab[c2])
            union = len(class_vocab[c1] | class_vocab[c2])
            jac = inter / union if union > 0 else 0
            print(f"  {jac:.2f}{'':>8}", end="")
    print()

# ═══════════════════════════════════════════════════════════════
# STEP 5 — COMPARE training_real.csv vs master.csv
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  STEP 5: COMPARE training_real.csv vs master.csv")
print("=" * 65)

master_path = os.path.join(PROCESSED, "master.csv")
if os.path.exists(master_path):
    master = pd.read_csv(master_path, low_memory=False)
    master.columns = master.columns.str.lower().str.strip()
    print(f"\nmaster.csv shape  : {master.shape}")
    print(f"training_real.csv : {df.shape}")
    print(f"\nmaster.csv columns: {list(master.columns)}")

    # Check if description column exists in master
    desc_col = None
    for c in ["description", "body", "short_description"]:
        if c in master.columns:
            desc_col = c
            break

    if desc_col:
        master_descs = set(master[desc_col].dropna().astype(str).str.strip())
        train_descs  = set(df["description"].astype(str).str.strip())
        # Note: train descriptions are cleaned so exact match won't work
        # Check approximate coverage
        print(f"\nmaster.csv unique descriptions : {len(master_descs)}")
        print(f"training_real.csv descriptions : {len(train_descs)}")
        print(f"\nNote: training_real descriptions are cleaned (salutations removed)")
        print(f"      so exact match with master is not expected.")
        print(f"      What matters: no test-set rows leaked into train.")
    else:
        print(f"\nNo description column found in master.csv")
        print(f"master.csv columns: {list(master.columns[:10])}")
else:
    print("\nmaster.csv not found — skipping comparison")

# ═══════════════════════════════════════════════════════════════
# STEP 6 — SAMPLE DESCRIPTIONS PER CLASS
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  STEP 6: SAMPLE DESCRIPTIONS PER CLASS (after cleaning)")
print("=" * 65)

for cls in df["assigned_team"].unique():
    print(f"\n--- {cls} ---")
    samples = df[df["assigned_team"] == cls]["description"].head(2).tolist()
    for s in samples:
        print(f"  {repr(s[:200])}")

# ═══════════════════════════════════════════════════════════════
# STEP 7 — NEAR-DUPLICATE DETECTION
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  STEP 7: NEAR-DUPLICATE DETECTION")
print("=" * 65)

df["prefix_60"] = df["description"].str.lower().str[:60]
near_dups = df[df.duplicated(subset=["prefix_60"], keep=False)]
print(f"\nRows sharing same first 60 chars: {len(near_dups)}")
if len(near_dups) > 0:
    sample = near_dups.groupby("prefix_60").filter(lambda x: len(x) > 1).head(6)
    print(sample[["description", "assigned_team"]].to_string())

# ═══════════════════════════════════════════════════════════════
# STEP 8 — FINAL AUDIT SUMMARY
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  STEP 8: AUDIT SUMMARY")
print("=" * 65)
print(f"\n  Total samples       : {len(df)}")
print(f"  Classes             : {df['assigned_team'].nunique()}")
print(f"  Missing values      : {df[['description','assigned_team']].isnull().sum().sum()}")
print(f"  Exact duplicates    : {df.duplicated(subset=['description']).sum()}")
print(f"  Near-duplicates     : {len(near_dups)}")
print(f"  Imbalance ratio     : {imbalance_ratio:.1f}x")
print(f"  Avg description len : {df['text_len'].mean():.0f} chars")
print(f"  Min description len : {df['text_len'].min()} chars")
print()
