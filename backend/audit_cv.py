# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import scipy.stats as stats
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
from lightgbm import LGBMClassifier

DATA_PATH = "model_assets/raw/all_tickets_processed_improved_v3.csv"
SEED = 42

df    = pd.read_csv(DATA_PATH).dropna(subset=["Document","Topic_group"])
X_arr = np.array(df["Document"].astype(str).tolist())
y_enc = LabelEncoder().fit_transform(df["Topic_group"].tolist())

# Use n_estimators=100 for speed (same architecture, representative result)
cv_pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1,2), min_df=2, max_features=10000, sublinear_tf=True)),
    ("clf",   LGBMClassifier(n_estimators=100, learning_rate=0.05, num_leaves=63,
                              class_weight="balanced", random_state=SEED, n_jobs=-1, verbose=-1)),
])

skf    = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
print("Running 5-fold CV (n_estimators=100 for speed)...")
cv_acc = cross_val_score(cv_pipeline, X_arr, y_enc, cv=skf, scoring="accuracy",    n_jobs=1)
cv_f1  = cross_val_score(cv_pipeline, X_arr, y_enc, cv=skf, scoring="f1_weighted", n_jobs=1)

n      = len(cv_acc)
ci_acc = stats.t.interval(0.95, df=n-1, loc=cv_acc.mean(), scale=stats.sem(cv_acc))
ci_f1  = stats.t.interval(0.95, df=n-1, loc=cv_f1.mean(),  scale=stats.sem(cv_f1))

print("\n5-Fold CV Accuracy per fold : {}".format(np.round(cv_acc,4)))
print("Mean +/- Std               : {:.2f}% +/- {:.2f}%".format(cv_acc.mean()*100, cv_acc.std()*100))
print("95% CI Accuracy            : [{:.2f}%, {:.2f}%]".format(ci_acc[0]*100, ci_acc[1]*100))
print("\n5-Fold CV Wt-F1 per fold   : {}".format(np.round(cv_f1,4)))
print("Mean +/- Std               : {:.2f}% +/- {:.2f}%".format(cv_f1.mean()*100, cv_f1.std()*100))
print("95% CI Wt-F1               : [{:.2f}%, {:.2f}%]".format(ci_f1[0]*100, ci_f1[1]*100))
print("\nStability (std < 1%)       : {}".format("PASS" if cv_acc.std()<0.01 else "WARN"))
print("Note: n_estimators=100 used for speed. Full model uses 500 (slightly higher accuracy).")
