import pandas as pd
import pickle

from sentence_transformers import (
    SentenceTransformer
)

from sklearn.ensemble import (
    RandomForestClassifier
)

df = pd.read_csv(
    "model_assets/processed/training.csv",
    low_memory=False
)

df = df[["description", "priority"]].dropna().head(50000)
df["description"] = df["description"].astype(str)
df["priority"] = df["priority"].astype(str)

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

X = embedder.encode(
    df["description"].tolist(),
    show_progress_bar=True
)

y = df["priority"]

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestClassifier()

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

print("\n=== Priority Model Evaluation ===")
print(f"Accuracy: {accuracy_score(y_test, y_pred) * 100:.2f}%")
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

pickle.dump(
    model,
    open(
        "model_assets/models/priority.pkl",
        "wb"
    )
)

print("Priority Model Ready")