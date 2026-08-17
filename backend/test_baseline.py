import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report, f1_score
from lightgbm import LGBMClassifier

DATA_PATH = "model_assets/raw/all_tickets_processed_improved_v3.csv"

df = pd.read_csv(DATA_PATH).dropna(subset=["Document", "Topic_group"])
print(f"Total rows: {len(df):,}")

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

vec = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),
    sublinear_tf=True,
)

X_train = vec.fit_transform(X_train_raw)
X_test = vec.transform(X_test_raw)

print(f"X_train shape: {X_train.shape}, X_test shape: {X_test.shape}")

model = LGBMClassifier(
    n_estimators=500,
    learning_rate=0.1,
    num_leaves=63,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
    verbose=-1
)

model.fit(X_train, y_train)

train_pred = model.predict(X_train)
test_pred = model.predict(X_test)

train_acc = accuracy_score(y_train, train_pred)
test_acc = accuracy_score(y_test, test_pred)
gap = train_acc - test_acc
test_f1 = f1_score(y_test, test_pred, average="weighted")

print(f"Train Acc: {train_acc*100:.2f}%")
print(f"Test Acc:  {test_acc*100:.2f}%")
print(f"Gap:       {gap*100:.2f}%")
print(f"Weighted F1: {test_f1:.4f}")
