import time, sys
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
from lightgbm import LGBMClassifier

def log(msg):
    print(msg, flush=True)

log("Loading data...")
df = pd.read_csv("model_assets/raw/all_tickets_processed_improved_v3.csv").dropna(subset=["Document", "Topic_group"])
log(f"Loaded {len(df):,} rows.")

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

log("Fitting TF-IDF...")
vec = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), sublinear_tf=True)
X_train = vec.fit_transform(X_train_raw)
X_test = vec.transform(X_test_raw)
log(f"TF-IDF done. Train shape: {X_train.shape}")

for nj in [1, 2, 4]:
    log(f"Testing n_jobs={nj}...")
    t0 = time.time()
    model = LGBMClassifier(
        n_estimators=100,
        learning_rate=0.1,
        num_leaves=63,
        class_weight="balanced",
        random_state=42,
        n_jobs=nj,
        verbose=-1
    )
    model.fit(X_train, y_train)
    dt = time.time() - t0
    tr_acc = accuracy_score(y_train, model.predict(X_train))
    te_acc = accuracy_score(y_test, model.predict(X_test))
    log(f"n_jobs={nj} | 100 trees | Time: {dt:.2f}s | Train Acc: {tr_acc*100:.2f}% | Test Acc: {te_acc*100:.2f}%")
