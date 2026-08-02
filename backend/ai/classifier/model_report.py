"""
model_report.py
Generates an evaluator-ready report for the ticket routing model.
Outputs:
  - Console summary (accuracy, precision, recall, F1, per-class, confusion pairs)
  - model_assets/models/model_report.html  (full visual report)

Run from: smart-helpdesk/backend/
  python ai/classifier/model_report.py
"""

import os, pickle, textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from sentence_transformers import SentenceTransformer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, classification_report, confusion_matrix,
)
from sklearn.model_selection import train_test_split

SEED       = 42
TEST_SIZE  = 0.20
MAX_CLASS  = 2000
DATA_PATH  = "model_assets/processed/training_real.csv"
MODELS_DIR = "model_assets/models"

# ── Load artifacts ────────────────────────────────────────────
print("Loading artifacts...")
with open(os.path.join(MODELS_DIR, "router.pkl"), "rb") as f:
    model = pickle.load(f)
with open(os.path.join(MODELS_DIR, "label_encoder.pkl"), "rb") as f:
    le = pickle.load(f)
with open(os.path.join(MODELS_DIR, "embedder_name.txt")) as f:
    emb_name = f.read().strip()

# ── Rebuild test set (same seed/split as training) ────────────
print("Rebuilding test set...")
import random
random.seed(SEED); np.random.seed(SEED)

df = pd.read_csv(DATA_PATH)
df = df[["description", "assigned_team"]].dropna()
df["description"]   = df["description"].astype(str).str.strip()
df["assigned_team"] = df["assigned_team"].astype(str).str.strip()
df = df[df["description"].str.len() >= 40]
counts = df["assigned_team"].value_counts()
df = df[df["assigned_team"].isin(counts[counts >= 2].index)]

y     = le.transform(df["assigned_team"])
X_raw = df["description"].tolist()
_, X_test_raw, _, y_test = train_test_split(
    X_raw, y, test_size=TEST_SIZE, random_state=SEED, stratify=y
)

print(f"Embedding {len(X_test_raw):,} test samples with {emb_name}...")
embedder = SentenceTransformer(emb_name)
X_test   = embedder.encode(X_test_raw, batch_size=64, show_progress_bar=True, convert_to_numpy=True)

# ── Predict ───────────────────────────────────────────────────
y_pred       = model.predict(X_test)
y_test_names = le.inverse_transform(y_test)
y_pred_names = le.inverse_transform(y_pred)

# ── Metrics ───────────────────────────────────────────────────
acc  = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
rec  = recall_score(y_test, y_pred, average="weighted", zero_division=0)
f1   = f1_score(y_test, y_pred, average="weighted", zero_division=0)
report_dict = classification_report(y_test_names, y_pred_names, zero_division=0, output_dict=True)
report_str  = classification_report(y_test_names, y_pred_names, zero_division=0)

cm     = confusion_matrix(y_test_names, y_pred_names, labels=list(le.classes_))
labels = list(le.classes_)

# ── Console output ────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  MODEL REPORT — Ticket Routing Classifier")
print(f"{'='*55}")
print(f"  Algorithm   : LightGBM (n_estimators=300, lr=0.1, num_leaves=63)")
print(f"  Embedder    : {emb_name}")
print(f"  Classes     : {len(labels)}")
print(f"  Test samples: {len(y_test):,}")
print(f"{'='*55}")
print(f"  Accuracy    : {acc*100:.2f}%")
print(f"  Precision   : {prec*100:.2f}%  (weighted)")
print(f"  Recall      : {rec*100:.2f}%  (weighted)")
print(f"  F1-Score    : {f1*100:.2f}%  (weighted)")
print(f"{'='*55}")
print("\nPer-Class Report:")
print(report_str)

print("Top confused pairs:")
confused = sorted(
    [(cm[i, j], tc, pc)
     for i, tc in enumerate(labels)
     for j, pc in enumerate(labels) if i != j and cm[i, j] > 0],
    reverse=True,
)
for cnt, tc, pc in confused[:6]:
    print(f"  {tc:<30} -> {pc:<30} : {cnt}")

# ── Build HTML report ─────────────────────────────────────────
print("\nGenerating HTML report...")

# encode images as base64 so the HTML is self-contained
import base64

def img_b64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

cm_b64  = img_b64(os.path.join(MODELS_DIR, "router_confusion_matrix.png"))
f1_b64  = img_b64(os.path.join(MODELS_DIR, "per_class_f1.png"))

# per-class table rows
rows_html = ""
for cls in labels:
    m = report_dict.get(cls, {})
    p_  = m.get("precision", 0) * 100
    r_  = m.get("recall",    0) * 100
    f_  = m.get("f1-score",  0) * 100
    sup = int(m.get("support", 0))
    color = "#c8e6c9" if f_ >= 80 else "#fff9c4" if f_ >= 60 else "#ffcdd2"
    rows_html += f"""
      <tr style="background:{color}">
        <td>{cls}</td>
        <td>{p_:.1f}%</td>
        <td>{r_:.1f}%</td>
        <td>{f_:.1f}%</td>
        <td>{sup:,}</td>
      </tr>"""

# confusion matrix table
cm_header = "".join(f"<th>{l}</th>" for l in labels)
cm_rows   = ""
for i, true_cls in enumerate(labels):
    cm_rows += f"<tr><td><b>{true_cls}</b></td>"
    for j in range(len(labels)):
        val = cm[i, j]
        bg  = f"background:rgba(33,150,243,{min(val/max(cm.max(),1), 1):.2f})" if val > 0 else ""
        cm_rows += f"<td style='{bg}'>{val}</td>"
    cm_rows += "</tr>"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Model Report — Ticket Routing Classifier</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 1100px; margin: 40px auto; color: #222; }}
  h1   {{ color: #1565C0; }}
  h2   {{ color: #1976D2; border-bottom: 2px solid #1976D2; padding-bottom: 4px; margin-top: 40px; }}
  .badge {{ display:inline-block; padding:6px 14px; border-radius:20px; font-weight:bold;
            font-size:1.1em; margin:4px; }}
  .green  {{ background:#c8e6c9; color:#1b5e20; }}
  .orange {{ background:#fff9c4; color:#e65100; }}
  .red    {{ background:#ffcdd2; color:#b71c1c; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: center; }}
  th {{ background: #1976D2; color: white; }}
  tr:hover {{ filter: brightness(0.96); }}
  .meta td {{ text-align: left; }}
  img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 6px; margin-top: 12px; }}
  .summary-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin:20px 0; }}
  .card {{ background:#f5f5f5; border-radius:8px; padding:20px; text-align:center; }}
  .card .val {{ font-size:2em; font-weight:bold; color:#1565C0; }}
  .card .lbl {{ font-size:0.9em; color:#555; margin-top:4px; }}
  pre {{ background:#f5f5f5; padding:16px; border-radius:6px; font-size:0.85em; overflow-x:auto; }}
</style>
</head>
<body>

<h1>Model Report — Ticket Routing Classifier</h1>

<h2>1. Model Configuration</h2>
<table class="meta">
  <tr><td><b>Algorithm</b></td><td>LightGBM</td></tr>
  <tr><td><b>Hyperparameters</b></td><td>n_estimators=300, learning_rate=0.1, num_leaves=63, min_child_samples=20, class_weight=balanced</td></tr>
  <tr><td><b>Embedder</b></td><td>{emb_name}</td></tr>
  <tr><td><b>Embedding Dimension</b></td><td>384</td></tr>
  <tr><td><b>Number of Classes</b></td><td>{len(labels)}</td></tr>
  <tr><td><b>Training samples (balanced)</b></td><td>{len(labels) * MAX_CLASS:,} ({MAX_CLASS}/class cap)</td></tr>
  <tr><td><b>Test samples</b></td><td>{len(y_test):,} (20% stratified hold-out)</td></tr>
  <tr><td><b>Classes</b></td><td>{", ".join(labels)}</td></tr>
</table>

<h2>2. Overall Performance</h2>
<div class="summary-grid">
  <div class="card"><div class="val">{acc*100:.2f}%</div><div class="lbl">Accuracy</div></div>
  <div class="card"><div class="val">{prec*100:.2f}%</div><div class="lbl">Precision (weighted)</div></div>
  <div class="card"><div class="val">{rec*100:.2f}%</div><div class="lbl">Recall (weighted)</div></div>
  <div class="card"><div class="val">{f1*100:.2f}%</div><div class="lbl">F1-Score (weighted)</div></div>
</div>

<h2>3. Per-Class Metrics</h2>
<table>
  <tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1-Score</th><th>Support</th></tr>
  {rows_html}
</table>
<p style="font-size:0.85em">
  <span class="badge green">Green = F1 &ge; 80%</span>
  <span class="badge orange">Yellow = F1 60–79%</span>
  <span class="badge red">Red = F1 &lt; 60%</span>
</p>

<h2>4. Full Classification Report</h2>
<pre>{report_str}</pre>

<h2>5. Confusion Matrix</h2>
{"<img src='data:image/png;base64," + cm_b64 + "' alt='Confusion Matrix'>" if cm_b64 else "<p>Image not found.</p>"}

<h2>6. Confusion Matrix (Raw Counts)</h2>
<table>
  <tr><th>True \\ Predicted</th>{cm_header}</tr>
  {cm_rows}
</table>

<h2>7. Per-Class F1 Chart</h2>
{"<img src='data:image/png;base64," + f1_b64 + "' alt='Per-Class F1'>" if f1_b64 else "<p>Image not found.</p>"}

<h2>8. Top Misclassifications</h2>
<table>
  <tr><th>True Class</th><th>Predicted As</th><th>Count</th></tr>
  {"".join(f"<tr><td>{tc}</td><td>{pc}</td><td>{cnt}</td></tr>" for cnt, tc, pc in confused[:8])}
</table>

<h2>9. Dataset Summary</h2>
<table>
  <tr><th>Class</th><th>Total Samples</th><th>Share</th></tr>
  {"".join(f"<tr><td>{cls}</td><td>{counts.get(cls, 0):,}</td><td>{counts.get(cls,0)/len(df)*100:.1f}%</td></tr>" for cls in labels)}
</table>

<p style="margin-top:40px; color:#888; font-size:0.8em">
  Generated by model_report.py &mdash; Smart Help Desk Ticket Routing Classifier
</p>
</body>
</html>"""

out_path = os.path.join(MODELS_DIR, "model_report.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nReport saved -> {out_path}")
print("Open model_assets/models/model_report.html in any browser.")
