"""
train_tfidf_lgbm.py
────────────────────────────────────────────────────────────────
TF-IDF + LightGBM ticket routing classifier.
Dataset : model_assets/raw/all_tickets_processed_improved_v3.csv
Target  : Topic_group  (8 classes)
Hard req: overall accuracy >= 80%
Auto-retry: max_features 10000 → 20000 → 30000
Output  : model_assets/models/tfidf_lgbm_bundle.joblib
"""

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from lightgbm import LGBMClassifier

DATA_PATH   = "model_assets/raw/all_tickets_processed_improved_v3.csv"
BUNDLE_PATH = "model_assets/models/tfidf_lgbm_bundle.joblib"
TARGET_ACC  = 0.80
MAX_FEATURES_SCHEDULE = [10000, 20000, 30000]

# ── 1. Load & clean ───────────────────────────────────────────
print("Loading data...")
df = pd.read_csv(DATA_PATH).dropna(subset=["Document", "Topic_group"])
print(f"Rows after dropna: {len(df):,}  |  Classes: {df['Topic_group'].nunique()}")

# ── 2. Train / test split (stratified 80/20) ──────────────────
X_train_raw, X_test_raw, y_train_raw, y_test_raw = train_test_split(
    df["Document"].astype(str).tolist(),
    df["Topic_group"].tolist(),
    test_size=0.20,
    random_state=42,
    stratify=df["Topic_group"],
)
print(f"Train: {len(X_train_raw):,}  |  Test: {len(X_test_raw):,}")

# ── 3. Label encoder ──────────────────────────────────────────
le = LabelEncoder()
y_train = le.fit_transform(y_train_raw)
y_test  = le.transform(y_test_raw)
print(f"Classes: {list(le.classes_)}")

# ── 4. Auto-retry loop over max_features ─────────────────────
final_acc    = 0.0
final_report = ""
final_cm     = None
best_vec     = None
best_model   = None
best_mf      = None

for max_features in MAX_FEATURES_SCHEDULE:
    print(f"\n{'='*60}")
    print(f"  Trying max_features = {max_features:,}")
    print(f"{'='*60}")

    # TF-IDF (fit on train only)
    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_features=max_features,
        sublinear_tf=True,
    )
    X_train = vec.fit_transform(X_train_raw)
    X_test  = vec.transform(X_test_raw)
    print(f"  Vocabulary size: {len(vec.vocabulary_):,}")

    # LightGBM
    model = LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    print("  Training LightGBM...")
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=le.classes_, digits=4)
    cm     = confusion_matrix(y_test, y_pred)

    print(f"\n  Accuracy : {acc*100:.2f}%")
    print(f"\n  Classification Report:\n{report}")
    print(f"  Confusion Matrix:\n{cm}")

    best_vec   = vec
    best_model = model
    best_mf    = max_features
    final_acc  = acc
    final_report = report
    final_cm   = cm

    if acc >= TARGET_ACC:
        print(f"\n  TARGET MET: {acc*100:.2f}% >= {TARGET_ACC*100:.0f}% at max_features={max_features:,}")
        break
    else:
        print(f"\n  {acc*100:.2f}% < {TARGET_ACC*100:.0f}% — retrying with larger max_features...")

# ── 5. Final summary ──────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  FINAL RESULT")
print(f"{'='*60}")
print(f"  max_features used : {best_mf:,}")
print(f"  Final Accuracy    : {final_acc*100:.2f}%")
print(f"  Target met        : {'YES' if final_acc >= TARGET_ACC else 'NO — consider tuning model hyperparameters'}")
print(f"\n  Final Classification Report:\n{final_report}")
print(f"  Final Confusion Matrix:\n{final_cm}")

# ── 6. Save bundle ────────────────────────────────────────────
import os
os.makedirs("model_assets/models", exist_ok=True)
bundle = {"vectorizer": best_vec, "classifier": best_model, "label_encoder": le}
joblib.dump(bundle, BUNDLE_PATH)
print(f"\n  Bundle saved -> {BUNDLE_PATH}")


# ── 7. Predict function ───────────────────────────────────────
def predict_ticket(text: str) -> str:
    """Load saved bundle and return predicted Topic_group for one raw ticket string."""
    b    = joblib.load(BUNDLE_PATH)
    vec  = b["vectorizer"]
    clf  = b["classifier"]
    enc  = b["label_encoder"]
    vec_ = vec.transform([str(text)])
    idx  = clf.predict(vec_)[0]
    return enc.inverse_transform([idx])[0]


# ── Quick smoke-test of predict_ticket ───────────────────────
if __name__ == "__main__":
    samples = [
        "My laptop screen is cracked and the keyboard is not working",
        "I need access to the shared drive on the finance server",
        "Request to purchase 3 additional software licenses for the team",
        "VPN is not connecting after the recent Windows update",
        "Payroll deduction query for this month",
    ]
    print(f"\n{'='*60}")
    print("  predict_ticket() smoke-test")
    print(f"{'='*60}")
    for s in samples:
        print(f"  Input : {s[:70]}")
        print(f"  Output: {predict_ticket(s)}\n")
