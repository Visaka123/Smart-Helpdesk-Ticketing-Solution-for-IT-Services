import os
import pickle
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score, f1_score

MODELS_DIR = "model_assets/models"
DATASET_PATH = "model_assets/processed/priority_training_real.csv"

def run_validation():
    print("=======================================================================")
    print("       REAL VALIDATION OF RETRAINED PRIORITY MODEL (PRIORITY.PKL)      ")
    print("=======================================================================\n")

    # 1. Load dataset & model artifacts
    df = pd.read_csv(DATASET_PATH)
    with open(os.path.join(MODELS_DIR, "priority.pkl"), "rb") as f:
        clf = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "priority_label_encoder.pkl"), "rb") as f:
        le = pickle.load(f)

    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    X_raw = df["description"].tolist()
    y = le.transform(df["priority"])
    X_vec = embedder.encode(X_raw, show_progress_bar=False)

    # -------------------------------------------------------------------
    # PART 1: 5-Fold Cross-Validation
    # -------------------------------------------------------------------
    cv_scores = cross_val_score(clf, X_vec, y, cv=5, scoring='f1_macro')
    print("--- 1. 5-FOLD CROSS-VALIDATION ---")
    print(f"F1 Macro Scores across 5 folds: {[round(s, 4) for s in cv_scores]}")
    print(f"5-fold CV F1 (macro): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}\n")

    # -------------------------------------------------------------------
    # PART 2: Held-Out Test Set Confusion Matrix
    # -------------------------------------------------------------------
    X_train, X_test, y_train, y_test, desc_train, desc_test = train_test_split(
        X_vec, y, X_raw, test_size=0.20, random_state=42, stratify=y
    )
    # Fit test-split model to match exact held-out matrix
    split_clf = RandomForestClassifier(n_estimators=300, max_depth=None, random_state=42)
    split_clf.fit(X_train, y_train)
    y_pred = split_clf.predict(X_test)

    cm = confusion_matrix(y_test, y_pred)
    cm_df = pd.DataFrame(cm, index=le.classes_, columns=le.classes_)
    print("--- 2. CONFUSION MATRIX (Held-Out Test Set) ---")
    print("Rows: True Labels | Columns: Predicted Labels")
    print(cm_df)
    print("\nClassification Report (Held-Out Split):")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    # -------------------------------------------------------------------
    # PART 3: Organic Stress-Test with 25 Human-Like Tickets
    # -------------------------------------------------------------------
    stress_test_tickets = [
        # Casual phrasing & minor typos
        {
            "id": 1,
            "text": "vpn keeps dropping ugh so annoying every 5 mins it disconnects",
            "judgment": "high",
            "rationale": "Remote worker blocked by constant VPN drops (High operational impact, though casually phrased)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 2,
            "text": "heyy my second monitor screen is flickering a bit when plugged into dock",
            "judgment": "medium",
            "rationale": "Hardware nuisance; workstation functional via primary screen or workaround (Medium)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 3,
            "text": "pls help cant open pdf files on my laptop since morning update thx",
            "judgment": "medium",
            "rationale": "Software application issue for single user, non-critical app (Medium)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 4,
            "text": "keyboard spacebar sticky after coffee spill need new keyboard when u have time",
            "judgment": "low",
            "rationale": "Routine hardware replacement request, explicitly non-urgent (Low)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 5,
            "text": "hey support team, zoom audio is slightly echoing on my bluetooth headset",
            "judgment": "medium",
            "rationale": "Audio glitch, non-blocking peripheral issue (Medium)",
            "category": "Casual phrasing & typos"
        },

        # Mixed signals (Urgent tone for minor issue / Calm tone for severe outage)
        {
            "id": 6,
            "text": "URGENT ASAP EMERGENCY!!! need to change my profile picture on Slack for the company party",
            "judgment": "low",
            "rationale": "Cosmetic inquiry despite 'URGENT/ASAP' screaming text (Low)",
            "category": "Mixed signals"
        },
        {
            "id": 7,
            "text": "ASAP PLS NEED HELP RIGHT NOW i forgot where the wifi guest password link is on portal",
            "judgment": "low",
            "rationale": "Informational request with artificial urgency (Low)",
            "category": "Mixed signals"
        },
        {
            "id": 8,
            "text": "FYI, noticed the primary database master server node shut down silently and all customer checkouts are failing",
            "judgment": "critical",
            "rationale": "Full e-commerce checkout outage despite calm 'FYI' tone (Critical)",
            "category": "Mixed signals"
        },
        {
            "id": 9,
            "text": "Just letting you know, ransomware banner appeared on finance storage node and files are locking up",
            "judgment": "critical",
            "rationale": "Severe active malware breach despite matter-of-fact tone (Critical)",
            "category": "Mixed signals"
        },
        {
            "id": 10,
            "text": "CRITICAL EMERGENCY: printer in 2nd floor breakroom out of cyan ink",
            "judgment": "low",
            "rationale": "Routine supply request with false 'CRITICAL' flag (Low)",
            "category": "Mixed signals"
        },

        # Ambiguous boundary cases
        {
            "id": 11,
            "text": "Sales representative unable to open CRM lead page right before client demo call in 30 mins",
            "judgment": "high",
            "rationale": "Single user blocked from revenue-impacting demo (Boundary: High due to business impact)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 12,
            "text": "One engineer unable to pull Docker images from internal registry due to 403 forbidden error",
            "judgment": "high",
            "rationale": "Single developer work blocked by access error (Boundary: High)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 13,
            "text": "Team shared folder permissions reset after server migration, department has read-only access",
            "judgment": "high",
            "rationale": "Department-wide read-only limitation (Boundary: High)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 14,
            "text": "Internal wiki page for deployment guidelines returning 404 not found",
            "judgment": "medium",
            "rationale": "Documentation link broken; non-blocking nuisance (Boundary: Medium)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 15,
            "text": "Monthly analytics export job taking 45 minutes instead of usual 10 minutes",
            "judgment": "medium",
            "rationale": "Performance degradation but job completes (Boundary: Medium)",
            "category": "Ambiguous boundary"
        },

        # Non-native English phrasing
        {
            "id": 16,
            "text": "Respected sir, my laptop getting blue screen every one hour when doing work kindly resolve",
            "judgment": "high",
            "rationale": "Frequent crashing blocking work (High)",
            "category": "Non-native English"
        },
        {
            "id": 17,
            "text": "Greetings team, I am not getting email notifications in my mobile phone application since yesterday evening",
            "judgment": "medium",
            "rationale": "Mobile mail sync issue, web mail accessible (Medium)",
            "category": "Non-native English"
        },
        {
            "id": 18,
            "text": "Kindly do the needful, SAP login showing user locked error for my id",
            "judgment": "high",
            "rationale": "Account lockout blocking SAP work (High)",
            "category": "Non-native English"
        },
        {
            "id": 19,
            "text": "Please to assist, password reset link expired for internal portal",
            "judgment": "medium",
            "rationale": "Expired reset token, routine reset required (Medium)",
            "category": "Non-native English"
        },
        {
            "id": 20,
            "text": "Good day, wanting to inquire regarding process for requesting secondary screen monitor",
            "judgment": "low",
            "rationale": "General inquiry about monitor process (Low)",
            "category": "Non-native English"
        },

        # Vague & Underspecified Tickets
        {
            "id": 21,
            "text": "something is wrong with my laptop, not sure what",
            "judgment": "medium",
            "rationale": "Vague issue, needs triage (Default Medium)",
            "category": "Vague / Underspecified"
        },
        {
            "id": 22,
            "text": "system error popped up on my screen",
            "judgment": "medium",
            "rationale": "Underspecified error prompt (Default Medium)",
            "category": "Vague / Underspecified"
        },
        {
            "id": 23,
            "text": "it is not working",
            "judgment": "medium",
            "rationale": "Extremely vague report (Default Medium)",
            "category": "Vague / Underspecified"
        },
        {
            "id": 24,
            "text": "help me with my computer",
            "judgment": "low",
            "rationale": "Generic help request without error context (Low / Medium)",
            "category": "Vague / Underspecified"
        },
        {
            "id": 25,
            "text": "network problem",
            "judgment": "medium",
            "rationale": "Vague network issue statement (Default Medium)",
            "category": "Vague / Underspecified"
        },
    ]

    print("\n--- 3. ORGANIC STRESS TEST (25 HUMAN-LIKE TICKETS) ---")
    results = []
    agreements = 0

    for item in stress_test_tickets:
        text = item["text"]
        target = item["judgment"].lower()

        # Run vector embedding through priority model
        vec = embedder.encode(text).reshape(1, -1)
        raw_pred = clf.predict(vec)[0]
        if isinstance(raw_pred, (int, np.integer)):
            pred = le.inverse_transform([raw_pred])[0].lower()
        else:
            pred = str(raw_pred).lower()

        probs = clf.predict_proba(vec)[0] if hasattr(clf, "predict_proba") else [0.85]
        conf = float(np.max(probs))

        is_agree = (pred == target)
        if is_agree:
            agreements += 1

        results.append({
            "ID": item["id"],
            "Category": item["category"],
            "Ticket Text": text,
            "My Judgment": target.upper(),
            "Model Pred": pred.upper(),
            "Confidence": f"{round(conf * 100, 1)}%",
            "Match": "AGREE" if is_agree else "DISAGREE",
            "Rationale": item["rationale"]
        })

    results_df = pd.DataFrame(results)
    print(results_df[["ID", "Ticket Text", "My Judgment", "Model Pred", "Confidence", "Match"]].to_string(index=False))

    agree_pct = (agreements / len(stress_test_tickets)) * 100.0
    print("\n=======================================================================")
    print(f"STRESS TEST RESULT: {agreements} / {len(stress_test_tickets)} Agreed ({agree_pct:.1f}% Agreement Rate)")
    print("=======================================================================\n")

if __name__ == "__main__":
    run_validation()
