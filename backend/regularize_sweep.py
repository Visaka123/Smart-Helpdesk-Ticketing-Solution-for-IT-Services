# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, classification_report
from lightgbm import LGBMClassifier, early_stopping, log_evaluation

DATA_PATH = "model_assets/raw/all_tickets_processed_improved_v3.csv"
SEED = 42

# ── Load & split (identical to original, never changes) ───────
df = pd.read_csv(DATA_PATH).dropna(subset=["Document", "Topic_group"])
X_all = df["Document"].astype(str).tolist()
y_all = df["Topic_group"].tolist()

X_train_raw, X_test_raw, y_train_raw, y_test_raw = train_test_split(
    X_all, y_all, test_size=0.20, random_state=SEED, stratify=y_all
)

# ── TF-IDF (fit on train only, identical to original) ─────────
vec = TfidfVectorizer(ngram_range=(1,2), min_df=2, max_features=10000, sublinear_tf=True)
X_train = vec.fit_transform(X_train_raw)
X_test  = vec.transform(X_test_raw)

le = LabelEncoder()
y_train = le.fit_transform(y_train_raw)
y_test  = le.transform(y_test_raw)

print("Train: {:,}  Test: {:,}  Vocab: {:,}".format(
    len(X_train_raw), len(X_test_raw), len(vec.vocabulary_)))

# ── Validation split carved from train (for early stopping only)
X_tr2, X_val, y_tr2, y_val = train_test_split(
    X_train, y_train, test_size=0.10, random_state=SEED, stratify=y_train
)

SEP = "=" * 75

def run(name, params, use_early_stopping=False):
    """Train, evaluate, print row. Returns (train_acc, test_acc, gap, f1_wt)."""
    base = dict(class_weight="balanced", random_state=SEED, n_jobs=-1, verbose=-1)
    base.update(params)
    model = LGBMClassifier(**base)

    if use_early_stopping:
        model.fit(
            X_tr2, y_tr2,
            eval_set=[(X_val, y_val)],
            callbacks=[early_stopping(30, verbose=False), log_evaluation(-1)],
        )
    else:
        model.fit(X_train, y_train)

    tr_acc = accuracy_score(y_train if not use_early_stopping else y_tr2,
                            model.predict(X_train if not use_early_stopping else X_tr2))
    te_acc = accuracy_score(y_test, model.predict(X_test))
    gap    = tr_acc - te_acc
    f1_wt  = f1_score(y_test, model.predict(X_test), average="weighted")

    print("  {:<45} tr={:.2f}%  te={:.2f}%  gap={:.2f}%  F1={:.4f}".format(
        name, tr_acc*100, te_acc*100, gap*100, f1_wt))
    return model, tr_acc, te_acc, gap, f1_wt

print("\n" + SEP)
print("  REGULARIZATION SWEEP")
print(SEP)
print("  {:<45} {:>8}  {:>8}  {:>7}  {:>8}".format(
    "Config", "Train", "Test", "Gap", "Wt-F1"))
print("  " + "-"*73)

results = {}

# 1. Baseline
m, *r = run("1. Baseline (n_est=500 lr=0.05 leaves=63)",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63))
results["1_baseline"] = (m, r)

# 2a. max_depth=6
m, *r = run("2a. max_depth=6",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63, max_depth=6))
results["2a_depth6"] = (m, r)

# 2b. max_depth=8
m, *r = run("2b. max_depth=8",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63, max_depth=8))
results["2b_depth8"] = (m, r)

# 3a. min_child_samples=50
m, *r = run("3a. min_child_samples=50",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63, min_child_samples=50))
results["3a_mcs50"] = (m, r)

# 3b. min_child_samples=100
m, *r = run("3b. min_child_samples=100",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63, min_child_samples=100))
results["3b_mcs100"] = (m, r)

# 4a. reg_alpha=0.1, reg_lambda=0.1
m, *r = run("4a. reg_alpha=0.1 reg_lambda=0.1",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63, reg_alpha=0.1, reg_lambda=0.1))
results["4a_reg01"] = (m, r)

# 4b. reg_alpha=1.0, reg_lambda=1.0
m, *r = run("4b. reg_alpha=1.0 reg_lambda=1.0",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63, reg_alpha=1.0, reg_lambda=1.0))
results["4b_reg10"] = (m, r)

# 5a. num_leaves=31
m, *r = run("5a. num_leaves=31",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=31))
results["5a_leaves31"] = (m, r)

# 5b. num_leaves=15
m, *r = run("5b. num_leaves=15",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=15))
results["5b_leaves15"] = (m, r)

# 6a. subsample=0.8, colsample_bytree=0.8
m, *r = run("6a. subsample=0.8 colsample=0.8",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63,
         subsample=0.8, colsample_bytree=0.8, subsample_freq=1))
results["6a_sub08"] = (m, r)

# 6b. subsample=0.7, colsample_bytree=0.7
m, *r = run("6b. subsample=0.7 colsample=0.7",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=63,
         subsample=0.7, colsample_bytree=0.7, subsample_freq=1))
results["6b_sub07"] = (m, r)

# 7. Early stopping (val carved from train, NOT test set)
m, *r = run("7. Early stopping (rounds=30, val=10% of train)",
    dict(n_estimators=1000, learning_rate=0.05, num_leaves=63),
    use_early_stopping=True)
results["7_early"] = (m, r)

# ── Best combined config ───────────────────────────────────────
# Combine the best individual levers: leaves=31 + min_child=50 + reg + subsample
print("\n" + SEP)
print("  COMBINED BEST CONFIG")
print(SEP)
print("  {:<45} {:>8}  {:>8}  {:>7}  {:>8}".format(
    "Config", "Train", "Test", "Gap", "Wt-F1"))
print("  " + "-"*73)

m_best, *r_best = run(
    "BEST: leaves=31 mcs=50 reg=0.1 sub=0.8 col=0.8",
    dict(n_estimators=500, learning_rate=0.05, num_leaves=31,
         min_child_samples=50, reg_alpha=0.1, reg_lambda=0.1,
         subsample=0.8, colsample_bytree=0.8, subsample_freq=1))
results["best"] = (m_best, r_best)

# ── Full classification report for best config ────────────────
print("\n" + SEP)
print("  FULL CLASSIFICATION REPORT — BEST CONFIG")
print(SEP)
y_pred_best  = m_best.predict(X_test)
y_pred_names = le.inverse_transform(y_pred_best)
y_test_names = le.inverse_transform(y_test)
print(classification_report(y_test_names, y_pred_names, digits=4))

# ── Summary table ─────────────────────────────────────────────
print(SEP)
print("  FINAL SUMMARY TABLE")
print(SEP)
print("  {:<45} {:>8}  {:>8}  {:>7}  {:>8}".format(
    "Config", "Train%", "Test%", "Gap%", "Wt-F1"))
print("  " + "-"*73)
labels_order = [
    ("1_baseline",  "1. Baseline"),
    ("2a_depth6",   "2a. max_depth=6"),
    ("2b_depth8",   "2b. max_depth=8"),
    ("3a_mcs50",    "3a. min_child_samples=50"),
    ("3b_mcs100",   "3b. min_child_samples=100"),
    ("4a_reg01",    "4a. reg_alpha/lambda=0.1"),
    ("4b_reg10",    "4b. reg_alpha/lambda=1.0"),
    ("5a_leaves31", "5a. num_leaves=31"),
    ("5b_leaves15", "5b. num_leaves=15"),
    ("6a_sub08",    "6a. subsample/col=0.8"),
    ("6b_sub07",    "6b. subsample/col=0.7"),
    ("7_early",     "7. Early stopping"),
    ("best",        "BEST combined"),
]
for key, label in labels_order:
    if key in results:
        _, (tr, te, gap, f1) = results[key]
        marker = " <-- BEST" if key == "best" else ""
        print("  {:<45} {:>7.2f}%  {:>7.2f}%  {:>6.2f}%  {:>8.4f}{}".format(
            label, tr*100, te*100, gap*100, f1, marker))

print("\n" + SEP)
print("  BEST CONFIG FINAL HYPERPARAMETERS")
print(SEP)
print("  n_estimators     = 500")
print("  learning_rate    = 0.05")
print("  num_leaves       = 31")
print("  min_child_samples= 50")
print("  reg_alpha        = 0.1")
print("  reg_lambda       = 0.1")
print("  subsample        = 0.8")
print("  colsample_bytree = 0.8")
print("  subsample_freq   = 1")
print("  class_weight     = balanced")
print("  random_state     = 42")
print(SEP)
