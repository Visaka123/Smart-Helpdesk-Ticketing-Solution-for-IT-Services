"""
train_router.py (v5 - fast, no GridSearch)
- 6 clean classes (merged overlapping ones)
- all-MiniLM-L6-v2 embeddings
- LightGBM (best from previous run, params hardcoded)
- No GridSearch, no CV loop — just train and evaluate
- Total runtime: ~15 minutes
"""

import os, gc, pickle, warnings, collections, random
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, classification_report, confusion_matrix, ConfusionMatrixDisplay,
)
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")

SEED      = 42
TEST_SIZE = 0.20
MAX_CLASS = 2000
EMB_MODEL = "all-MiniLM-L6-v2"
DATA_PATH = "model_assets/processed/training_real.csv"
MODELS_DIR= "model_assets/models"

os.makedirs(MODELS_DIR, exist_ok=True)
random.seed(SEED)
np.random.seed(SEED)

# ── STEP 1: Load ──────────────────────────────────────────────
print("STEP 1: Load data")
df = pd.read_csv(DATA_PATH)
df = df[["description","assigned_team"]].dropna()
df["description"]   = df["description"].astype(str).str.strip()
df["assigned_team"] = df["assigned_team"].astype(str).str.strip()
df = df[df["description"].str.len() >= 40]
counts = df["assigned_team"].value_counts()
df = df[df["assigned_team"].isin(counts[counts >= 2].index)]
print(f"Samples: {len(df):,}  Classes: {df['assigned_team'].nunique()}")
for cls, cnt in counts.items():
    print(f"  {cls:<30} {cnt:>6,}  ({cnt/len(df)*100:.1f}%)")

# ── STEP 2: Encode + Split ────────────────────────────────────
print("\nSTEP 2: Encode labels + split")
le = LabelEncoder()
y  = le.fit_transform(df["assigned_team"])
X_raw = df["description"].tolist()
X_train_raw, X_test_raw, y_train_raw, y_test = train_test_split(
    X_raw, y, test_size=TEST_SIZE, random_state=SEED, stratify=y
)
print(f"Train: {len(X_train_raw):,}  Test: {len(X_test_raw):,}")
print(f"Classes: {list(le.classes_)}")

# ── STEP 3: Balance train (cap 2000/class) ────────────────────
print(f"\nSTEP 3: Balance train (cap {MAX_CLASS}/class)")
from collections import defaultdict
ci = defaultdict(list)
for i, l in enumerate(y_train_raw):
    ci[l].append(i)
bi, bl = [], []
for l, idxs in ci.items():
    chosen = random.sample(idxs, MAX_CLASS) if len(idxs) >= MAX_CLASS \
             else idxs + random.choices(idxs, k=MAX_CLASS - len(idxs))
    bi.extend(chosen); bl.extend([l] * MAX_CLASS)
tmp = list(zip(bi, bl)); random.shuffle(tmp); bi, bl = zip(*tmp)
X_train_bal = [X_train_raw[i] for i in bi]
y_train     = np.array(bl)
print(f"Balanced train: {len(X_train_bal):,}")
for k, v in sorted(collections.Counter(le.inverse_transform(y_train)).items()):
    print(f"  {k:<30} {v:>5,}")

# ── STEP 4: Embed ─────────────────────────────────────────────
print(f"\nSTEP 4: Embed with {EMB_MODEL}")
embedder = SentenceTransformer(EMB_MODEL)
print(f"Encoding {len(X_train_bal):,} train samples...")
X_train = embedder.encode(X_train_bal, batch_size=64, show_progress_bar=True, convert_to_numpy=True)
print(f"Encoding {len(X_test_raw):,} test samples...")
X_test  = embedder.encode(X_test_raw,  batch_size=64, show_progress_bar=True, convert_to_numpy=True)
del embedder; gc.collect()
print(f"Train: {X_train.shape}  Test: {X_test.shape}")

# ── STEP 5: Train LightGBM (best params from previous run) ───
print("\nSTEP 5: Train LightGBM")
model = LGBMClassifier(
    n_estimators=300,
    learning_rate=0.1,
    num_leaves=63,
    min_child_samples=20,
    class_weight="balanced",
    random_state=SEED,
    verbose=-1,
    n_jobs=1,
)
model.fit(X_train, y_train)
print("Training done.")

# ── STEP 6: Evaluate ──────────────────────────────────────────
print("\nSTEP 6: Evaluate on unseen test set")
y_pred       = model.predict(X_test)
y_test_names = le.inverse_transform(y_test)
y_pred_names = le.inverse_transform(y_pred)

acc  = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
rec  = recall_score(y_test, y_pred, average="weighted", zero_division=0)
f1   = f1_score(y_test, y_pred, average="weighted", zero_division=0)

print(f"\n{'='*50}")
print(f"  Accuracy  : {acc*100:.2f}%")
print(f"  Precision : {prec*100:.2f}%")
print(f"  Recall    : {rec*100:.2f}%")
print(f"  F1-Score  : {f1*100:.2f}%")
print(f"{'='*50}")
print("\nPer-class Report:")
print(classification_report(y_test_names, y_pred_names, zero_division=0))

# Overfitting check
train_f1 = f1_score(y_train, model.predict(X_train), average="weighted", zero_division=0)
print(f"Train F1: {train_f1*100:.2f}%  Test F1: {f1*100:.2f}%  Gap: {(train_f1-f1)*100:.2f}%")

# Confusion pairs
print("\nTop confused pairs:")
cm = confusion_matrix(y_test_names, y_pred_names, labels=list(le.classes_))
confused = sorted(
    [(cm[i,j], tc, pc)
     for i, tc in enumerate(le.classes_)
     for j, pc in enumerate(le.classes_) if i != j and cm[i,j] > 0],
    reverse=True
)
for cnt, tc, pc in confused[:6]:
    print(f"  {tc:<30} -> {pc:<30} : {cnt}")

# ── STEP 7: Plots ─────────────────────────────────────────────
print("\nSTEP 7: Saving plots")
fig, ax = plt.subplots(figsize=(10, 8))
ConfusionMatrixDisplay.from_predictions(
    y_test_names, y_pred_names, ax=ax, xticks_rotation=45, colorbar=False
)
ax.set_title(f"{EMB_MODEL} + LightGBM\nAcc: {acc*100:.1f}%  F1: {f1*100:.1f}%")
plt.tight_layout()
plt.savefig(os.path.join(MODELS_DIR, "router_confusion_matrix.png"), dpi=150)

report_dict = classification_report(y_test_names, y_pred_names, zero_division=0, output_dict=True)
cls_list = list(le.classes_)
f1_vals  = [report_dict.get(c, {}).get("f1-score", 0)*100 for c in cls_list]
colors_c = ["#4CAF50" if v >= 80 else "#FF9800" if v >= 60 else "#F44336" for v in f1_vals]
fig2, ax2 = plt.subplots(figsize=(10, 4))
bars = ax2.bar(cls_list, f1_vals, color=colors_c)
ax2.axhline(80, color="green", linestyle="--", linewidth=1.2, label="80% target")
ax2.set_ylabel("F1-Score (%)")
ax2.set_title("Per-Class F1 on Test Set")
ax2.set_ylim(0, 105)
ax2.tick_params(axis="x", rotation=30)
ax2.legend()
for bar, v in zip(bars, f1_vals):
    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5,
             f"{v:.1f}%", ha="center", va="bottom", fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(MODELS_DIR, "per_class_f1.png"), dpi=150)
print("Plots saved.")

# ── STEP 8: Save artifacts ────────────────────────────────────
print("\nSTEP 8: Save artifacts")
with open(os.path.join(MODELS_DIR, "router.pkl"), "wb") as f:
    pickle.dump(model, f)
with open(os.path.join(MODELS_DIR, "label_encoder.pkl"), "wb") as f:
    pickle.dump(le, f)
with open(os.path.join(MODELS_DIR, "embedder_name.txt"), "w") as f:
    f.write(EMB_MODEL)
print(f"  router.pkl        -> LightGBM")
print(f"  label_encoder.pkl -> {list(le.classes_)}")
print(f"  embedder_name.txt -> {EMB_MODEL}")

if f1 >= 0.80:
    print(f"\nTARGET MET: F1 = {f1*100:.2f}% >= 80%")
else:
    print(f"\nF1 = {f1*100:.2f}% — see per-class report above for diagnosis.")
