# -*- coding: utf-8 -*-
import sys, io, time, joblib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, classification_report
from lightgbm import LGBMClassifier

SEED = 42
t0 = time.time()

# ---------------------------------------------------------------
# 1. Load + split (same 80/20 split used during the search, so the
#    test set stays untouched / unbiased for the final evaluation)
# ---------------------------------------------------------------
df = pd.read_csv("model_assets/raw/all_tickets_processed_improved_v3.csv").dropna(subset=["Document", "Topic_group"])
X_all = df["Document"].astype(str).tolist()
y_all = df["Topic_group"].tolist()
print(f"[{time.time()-t0:.1f}s] Loaded {len(df)} rows, {df['Topic_group'].nunique()} classes", flush=True)

X_train_raw, X_test_raw, y_train_raw, y_test_raw = train_test_split(
    X_all, y_all, test_size=0.20, random_state=SEED, stratify=y_all)

# ---------------------------------------------------------------
# 2. TF-IDF (same settings used during the search)
# ---------------------------------------------------------------
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=5, max_features=3000, sublinear_tf=True)
X_train = vec.fit_transform(X_train_raw)
X_test  = vec.transform(X_test_raw)
print(f"[{time.time()-t0:.1f}s] TF-IDF done, shape={X_train.shape}", flush=True)

le = LabelEncoder()
y_train = le.fit_transform(y_train_raw)
y_test  = le.transform(y_test_raw)

# ---------------------------------------------------------------
# 3. Final model — the winning "BEST combined" config from the search,
#    trained on the FULL training set (no held-out val split needed
#    anymore, since early stopping already told us the right tree count)
# ---------------------------------------------------------------
BEST_PARAMS = dict(
    class_weight="balanced",
    random_state=SEED,
    n_jobs=-1,
    verbose=-1,
    max_bin=63,
    learning_rate=0.05,
    num_leaves=31,
    min_child_samples=50,
    reg_alpha=0.1,
    reg_lambda=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    subsample_freq=1,
    n_estimators=295,   # exact count from early stopping during the search — no early stopping needed here
)

tm = time.time()
model = LGBMClassifier(**BEST_PARAMS)
model.fit(X_train, y_train)
print(f"[{time.time()-t0:.1f}s] Final model trained in {time.time()-tm:.1f}s", flush=True)

# ---------------------------------------------------------------
# 4. Evaluate on the untouched test set
# ---------------------------------------------------------------
y_pred_train = model.predict(X_train)
y_pred_test  = model.predict(X_test)

tr = accuracy_score(y_train, y_pred_train)
te = accuracy_score(y_test, y_pred_test)
f1 = f1_score(y_test, y_pred_test, average="weighted")

print("\n" + "=" * 60)
print(f"Train acc: {tr*100:.2f}%   Test acc: {te*100:.2f}%   Gap: {(tr-te)*100:.2f}%   Wt-F1: {f1:.4f}")
print("=" * 60)
print(classification_report(le.inverse_transform(y_test), le.inverse_transform(y_pred_test), digits=4))

# ---------------------------------------------------------------
# 5. Save model + vectorizer + label encoder for inference later
# ---------------------------------------------------------------
joblib.dump(model, "model_assets/lgbm_ticket_classifier.joblib")
joblib.dump(vec,   "model_assets/tfidf_vectorizer.joblib")
joblib.dump(le,    "model_assets/label_encoder.joblib")
print(f"\n[{time.time()-t0:.1f}s] Saved model + vectorizer + label encoder to model_assets/", flush=True)
print(f"Total elapsed: {time.time()-t0:.1f}s")
