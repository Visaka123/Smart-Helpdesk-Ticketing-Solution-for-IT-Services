import sys
import pandas as pd
import numpy as np
import lightgbm as lgb
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report, f1_score

def log(msg):
    print(msg)
    sys.stdout.flush()

DATA_PATH = "model_assets/raw/all_tickets_processed_improved_v3.csv"

# 1. Load data
log("Loading data...")
df = pd.read_csv(DATA_PATH).dropna(subset=["Document", "Topic_group"])
log(f"Total dataset rows: {len(df):,}")

# 2. Stratified 80/20 train/test split (random_state=42)
X_train_raw, X_test_raw, y_train_raw, y_test_raw = train_test_split(
    df["Document"].astype(str).tolist(),
    df["Topic_group"].tolist(),
    test_size=0.20,
    random_state=42,
    stratify=df["Topic_group"],
)

le = LabelEncoder()
y_train = le.fit_transform(y_train_raw)
y_test = le.transform(y_test_raw)

log(f"Train size: {len(X_train_raw):,}, Test size: {len(X_test_raw):,}")

# 3. TF-IDF vectorizer fit on TRAIN only
log("Fitting TF-IDF Vectorizer (max_features=10000, ngram_range=(1,2), sublinear_tf=True)...")
vec = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),
    sublinear_tf=True,
)
X_train = vec.fit_transform(X_train_raw)
X_test = vec.transform(X_test_raw)
log(f"X_train shape: {X_train.shape}, X_test shape: {X_test.shape}")

# Carve out 15% validation split from TRAIN ONLY for early stopping experiments
X_tr_raw, X_val_raw, y_tr_raw, y_val_raw = train_test_split(
    X_train_raw,
    y_train_raw,
    test_size=0.15,
    random_state=42,
    stratify=y_train_raw,
)
X_tr = vec.transform(X_tr_raw)
X_val = vec.transform(X_val_raw)
y_tr = le.transform(y_tr_raw)
y_val = le.transform(y_val_raw)

log(f"Sub-train: {X_tr.shape[0]:,}, Validation: {X_val.shape[0]:,}")

results = []

def evaluate_config(name, model_params, fit_mode="full_train"):
    log(f"\n--- Running: {name} ---")
    model = LGBMClassifier(**model_params)

    if fit_mode == "full_train":
        model.fit(X_train, y_train)
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        best_iter = getattr(model, "best_iteration_", model.n_estimators)
        if best_iter is None or best_iter == 0:
            best_iter = model.n_estimators
    elif fit_mode == "early_stopping":
        callbacks = [lgb.early_stopping(stopping_rounds=30, verbose=False)]
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            eval_metric="multi_logloss",
            callbacks=callbacks
        )
        best_iter = model.best_iteration_
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)

    tr_acc = accuracy_score(y_train, train_pred)
    te_acc = accuracy_score(y_test, test_pred)
    gap = tr_acc - te_acc
    te_f1 = f1_score(y_test, test_pred, average="weighted")
    rep = classification_report(y_test, test_pred, target_names=le.classes_, digits=4)

    res = {
        "Config": name,
        "train_acc": tr_acc,
        "test_acc": te_acc,
        "gap": gap,
        "test_weighted_f1": te_f1,
        "best_iter": best_iter,
        "report": rep,
        "params": model_params,
        "model": model
    }
    results.append(res)
    log(f"  Train Acc : {tr_acc*100:.2f}%")
    log(f"  Test Acc  : {te_acc*100:.2f}%")
    log(f"  Gap       : {gap*100:.2f}%")
    log(f"  WeightedF1: {te_f1:.4f}")
    log(f"  Best Iter : {best_iter}")
    return res

base_params = dict(
    n_estimators=500,
    learning_rate=0.1,
    num_leaves=63,
    class_weight="balanced",
    random_state=42,
    n_jobs=4,
    verbose=-1
)

# 1. Baseline
log("\n" + "="*70)
log("1. Baseline (n_est=500, lr=0.1, leaves=63, class_weight=balanced)")
log("="*70)
evaluate_config("1. Baseline (current)", base_params.copy())

# 2. Add max_depth=6-8 (cap tree depth)
log("\n" + "="*70)
log("2. Add max_depth=6-8")
log("="*70)
p = base_params.copy(); p["max_depth"] = 8
evaluate_config("2a. max_depth=8", p)

p = base_params.copy(); p["max_depth"] = 7
evaluate_config("2b. max_depth=7", p)

p = base_params.copy(); p["max_depth"] = 6
evaluate_config("2c. max_depth=6", p)

# 3. Increase min_child_samples (50-100)
log("\n" + "="*70)
log("3. Increase min_child_samples (50-100)")
log("="*70)
p = base_params.copy(); p["min_child_samples"] = 50
evaluate_config("3a. min_child_samples=50", p)

p = base_params.copy(); p["min_child_samples"] = 100
evaluate_config("3b. min_child_samples=100", p)

# 4. Add reg_alpha and reg_lambda (0.1 - 1.0)
log("\n" + "="*70)
log("4. Add reg_alpha and reg_lambda (0.1 - 1.0)")
log("="*70)
p = base_params.copy(); p["reg_alpha"] = 0.1; p["reg_lambda"] = 0.1
evaluate_config("4a. reg_alpha=0.1, reg_lambda=0.1", p)

p = base_params.copy(); p["reg_alpha"] = 1.0; p["reg_lambda"] = 1.0
evaluate_config("4b. reg_alpha=1.0, reg_lambda=1.0", p)

# 5. Reduce num_leaves from 63 to 31
log("\n" + "="*70)
log("5. Reduce num_leaves from 63 to 31")
log("="*70)
p = base_params.copy(); p["num_leaves"] = 31
evaluate_config("5. num_leaves=31", p)

# 6. Add subsample=0.8 and colsample_bytree=0.8
log("\n" + "="*70)
log("6. Add subsample=0.8, colsample_bytree=0.8")
log("="*70)
p = base_params.copy(); p["subsample"] = 0.8; p["colsample_bytree"] = 0.8; p["subsample_freq"] = 1
evaluate_config("6. subsample=0.8, colsample=0.8", p)

# 7. Add early_stopping_rounds=30
log("\n" + "="*70)
log("7. Early Stopping (30 rounds on val split)")
log("="*70)
p = base_params.copy()
evaluate_config("7. Early Stopping (30 rounds)", p, fit_mode="early_stopping")

# CUMULATIVE STACKING OF REGULARIZATIONS
log("\n" + "="*70)
log("CUMULATIVE COMBINED REGULARIZATIONS")
log("="*70)

cum = base_params.copy()
cum["num_leaves"] = 31
cum["max_depth"] = 7
cum["min_child_samples"] = 50
cum["reg_alpha"] = 0.5
cum["reg_lambda"] = 0.5
cum["subsample"] = 0.8
cum["colsample_bytree"] = 0.8
cum["subsample_freq"] = 1
evaluate_config("Cum-All: Full Regularization Stack", cum)

cum_es = cum.copy()
evaluate_config("Cum-All + Early Stopping (30 rounds)", cum_es, fit_mode="early_stopping")

# Stronger Regularization (for ~3-5% gap target)
strong_reg = dict(
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=20,
    max_depth=5,
    min_child_samples=80,
    reg_alpha=2.0,
    reg_lambda=2.0,
    subsample=0.8,
    colsample_bytree=0.8,
    subsample_freq=1,
    class_weight="balanced",
    random_state=42,
    n_jobs=4,
    verbose=-1
)
evaluate_config("StrongReg-1: depth=5, leaves=20, min_child=80, reg=2.0", strong_reg)
evaluate_config("StrongReg-1 + Early Stopping", strong_reg, fit_mode="early_stopping")

# Print Summary Table
summary_df = pd.DataFrame([
    {
        "Config Name": r["Config"],
        "train_acc": round(r['train_acc'] * 100, 2),
        "test_acc": round(r['test_acc'] * 100, 2),
        "gap": round(r['gap'] * 100, 2),
        "test_weighted_f1": round(r['test_weighted_f1'], 4),
        "best_iter": r["best_iter"]
    }
    for r in results
])

log("\n" + "="*80)
log("FINAL SUMMARY TABLE")
log("="*80)
log(summary_df.to_string(index=False))

summary_df.to_csv("experiment_results_summary.csv", index=False)
log("Saved summary to experiment_results_summary.csv")

# Save classification report of best model
best_res = min(results, key=lambda x: (x['gap'] if x['gap'] >= 0.02 and x['test_acc'] >= 0.85 else 1.0))
log("\n" + "="*80)
log(f"BEST CONFIG: {best_res['Config']}")
log("="*80)
log(f"Final Params: {best_res['params']}")
log(f"\nClassification Report:\n{best_res['report']}")

with open("best_model_details.txt", "w") as f:
    f.write(f"Best Config: {best_res['Config']}\n")
    f.write(f"Hyperparameters: {best_res['params']}\n")
    f.write(f"Train Acc: {best_res['train_acc']*100:.2f}%\n")
    f.write(f"Test Acc: {best_res['test_acc']*100:.2f}%\n")
    f.write(f"Gap: {best_res['gap']*100:.2f}%\n")
    f.write(f"Weighted F1: {best_res['test_weighted_f1']:.4f}\n")
    f.write(f"\nClassification Report:\n{best_res['report']}\n")
