import os
import time
import pickle
import datetime
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report


from app.database.database import SessionLocal
from app.models import Ticket, RetrainingLog

MODELS_DIR = "model_assets/models"
CHECKPOINT_DIR = "model_assets/models/checkpoints"
BASE_DATASET = "model_assets/processed/training_real.csv"

def run_retraining(min_new_samples=1):
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    db = SessionLocal()
    # Fetch resolved tickets with confirmed teams
    resolved_tickets = db.query(Ticket).filter(
        Ticket.status.in_(["resolved", "closed"]),
        Ticket.assigned_team != "Unassigned/Triage"
    ).all()
    
    new_data = [{"description": t.description, "assigned_team": t.assigned_team} for t in resolved_tickets]
    db.close()

    print(f"[RETRAIN] Found {len(new_data)} resolved feedback tickets in database.")

    # Load base dataset
    if os.path.exists(BASE_DATASET):
        base_df = pd.read_csv(BASE_DATASET)
    else:
        base_df = pd.DataFrame(columns=["description", "assigned_team"])

    if new_data:
        feedback_df = pd.DataFrame(new_data)
        combined_df = pd.concat([base_df, feedback_df], ignore_index=True)
    else:
        combined_df = base_df

    combined_df = combined_df.dropna().drop_duplicates(subset=["description"])
    
    # Filter rare classes (< 2 instances)
    counts = combined_df["assigned_team"].value_counts()
    valid_teams = counts[counts >= 2].index
    combined_df = combined_df[combined_df["assigned_team"].isin(valid_teams)]

    if len(combined_df) < 10:
        print("[RETRAIN] Not enough data to train model.")
        return False

    print(f"[RETRAIN] Retraining on total {len(combined_df)} samples across {combined_df['assigned_team'].nunique()} teams.")

    # Encode labels
    le = LabelEncoder()
    y = le.fit_transform(combined_df["assigned_team"])
    X_raw = combined_df["description"].tolist()

    # Train / Test split
    X_train_raw, X_test_raw, y_train_raw, y_test = train_test_split(
        X_raw, y, test_size=0.2, random_state=42, stratify=y
    )

    # Oversample train set only using pure numpy
    unique_classes, counts = np.unique(y_train_raw, return_counts=True)
    max_count = np.max(counts)

    resampled_indices = []
    for cls in unique_classes:
        cls_indices = np.where(y_train_raw == cls)[0]
        chosen = np.random.choice(cls_indices, size=max_count, replace=True)
        resampled_indices.extend(chosen)

    np.random.seed(42)
    np.random.shuffle(resampled_indices)
    y_train = y_train_raw[resampled_indices]
    X_train_raw_balanced = [X_train_raw[i] for i in resampled_indices]


    # Sentence Transformer Embeddings
    embedder_name = "all-MiniLM-L6-v2"
    embedder = SentenceTransformer(embedder_name)
    X_train = embedder.encode(X_train_raw_balanced, show_progress_bar=False, batch_size=128)
    X_test = embedder.encode(X_test_raw, show_progress_bar=False, batch_size=128)

    # Fit Logistic Regression Classifier
    clf = LogisticRegression(max_iter=3000, C=1.0, random_state=42)
    clf.fit(X_train, y_train)

    # Evaluate
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred, average="weighted"))

    print(f"[RETRAIN SUCCESS] Accuracy: {acc*100:.2f}%, F1-Score: {f1*100:.2f}%")

    # Versioning & Checkpointing
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    version = f"router_v{timestamp}"

    # Save active model
    with open(os.path.join(MODELS_DIR, "router.pkl"), "wb") as f:
        pickle.dump(clf, f)
    with open(os.path.join(MODELS_DIR, "label_encoder.pkl"), "wb") as f:
        pickle.dump(le, f)
    with open(os.path.join(MODELS_DIR, "embedder_name.txt"), "w") as f:
        f.write(embedder_name)

    # Save versioned checkpoint
    checkpoint_path = os.path.join(CHECKPOINT_DIR, f"{version}.pkl")
    with open(checkpoint_path, "wb") as f:
        pickle.dump({"model": clf, "label_encoder": le, "version": version, "accuracy": acc, "f1_score": f1}, f)

    # Log to DB
    db = SessionLocal()
    log_entry = RetrainingLog(
        model_type="routing",
        version=version,
        samples_count=len(combined_df),
        accuracy=acc,
        f1_score=f1,
    )
    db.add(log_entry)
    db.commit()
    db.close()

    print(f"[RETRAIN LOGGED] Version {version} saved and registered in database.")
    return True

if __name__ == "__main__":
    run_retraining()