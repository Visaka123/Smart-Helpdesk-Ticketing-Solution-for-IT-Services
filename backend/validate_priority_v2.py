import os
import pickle
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score, f1_score
from app.priority.service import predict_priority_enhanced

MODELS_DIR = "model_assets/models"
DATASET_PATH = "model_assets/processed/priority_training_real.csv"

def run_validation_v2():
    print("=======================================================================")
    print("       RE-VALIDATION OF FIXED PRIORITY MODEL (PRIORITY.PKL - V2)       ")
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
    # PART 1: 5-Fold Cross-Validation Re-Run
    # -------------------------------------------------------------------
    cv_scores = cross_val_score(clf, X_vec, y, cv=5, scoring='f1_macro')
    print("--- 1. NEW 5-FOLD CROSS-VALIDATION ---")
    print(f"F1 Macro Scores across 5 folds: {[round(s, 4) for s in cv_scores]}")
    print(f"New 5-fold CV F1 (macro): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    print(f"Prior 5-fold CV baseline: 0.7553 ± 0.0534\n")

    # -------------------------------------------------------------------
    # PART 2: New 25-Ticket Organic Stress Test (New Set)
    # -------------------------------------------------------------------
    stress_test_tickets_v2 = [
        # Category 1: Casual Phrasing & Typos
        {
            "id": 1,
            "text": "wifi is super spotty in the breakroom keeps logging off",
            "judgment": "medium",
            "rationale": "Wi-Fi instability in non-critical breakroom area (Medium)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 2,
            "text": "my wireless mouse battery died can i grab another from it stock",
            "judgment": "low",
            "rationale": "Routine peripheral supply request (Low)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 3,
            "text": "docking station not charging laptop unless i jiggle the cord hard",
            "judgment": "medium",
            "rationale": "Workstation connector wear; functional workaround exists (Medium)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 4,
            "text": "urgent! my excel sheet crashed and lost my last 10 mins of typing",
            "judgment": "medium",
            "rationale": "Single-app local crash, minor inconvenience (Medium)",
            "category": "Casual phrasing & typos"
        },
        {
            "id": 5,
            "text": "cant send attachment via outlook error popup 0x8004",
            "judgment": "medium",
            "rationale": "Outlook client attachment error for single user (Medium)",
            "category": "Casual phrasing & typos"
        },

        # Category 2: Mixed Signals
        {
            "id": 6,
            "text": "MUST FIX IMMEDIATELY: my wallpaper background reverted to corporate default",
            "judgment": "low",
            "rationale": "Cosmetic setting query despite screaming ALL-CAPS (Low)",
            "category": "Mixed signals"
        },
        {
            "id": 7,
            "text": "EMERGENCY CRITICAL HELP: I don't know how to request a second monitor",
            "judgment": "low",
            "rationale": "General inquiry despite false-alarm tone (Low)",
            "category": "Mixed signals"
        },
        {
            "id": 8,
            "text": "Small note, our internal identity authentication SSO system is down and nobody can log into work",
            "judgment": "critical",
            "rationale": "Company-wide SSO outage despite calm phrasing (Critical)",
            "category": "Mixed signals"
        },
        {
            "id": 9,
            "text": "FYI, ransomware note appearing on finance file server with encrypted extensions",
            "judgment": "critical",
            "rationale": "Severe malware infection despite casual 'FYI' tone (Critical)",
            "category": "Mixed signals"
        },
        {
            "id": 10,
            "text": "Urgent alert: water leaking onto server rack in main IT closet",
            "judgment": "critical",
            "rationale": "Immediate severe facility danger to hardware (Critical)",
            "category": "Mixed signals"
        },

        # Category 3: Ambiguous Boundary Cases
        {
            "id": 11,
            "text": "One developer unable to connect to staging DB cluster after credential update",
            "judgment": "high",
            "rationale": "Single developer work blocked on staging DB (High)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 12,
            "text": "Departmental shared drive returning permission denied error for marketing team",
            "judgment": "high",
            "rationale": "Department-wide read/write permission blocker (High)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 13,
            "text": "Software license activation count reached max limit for dev tool",
            "judgment": "medium",
            "rationale": "License seat cap reached; routine license add needed (Medium)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 14,
            "text": "Weekly executive report PDF generator running 20 minutes slower than usual",
            "judgment": "medium",
            "rationale": "Performance lag but report completes (Medium)",
            "category": "Ambiguous boundary"
        },
        {
            "id": 15,
            "text": "Laptop battery health under 60%, drains within 1 hour",
            "judgment": "medium",
            "rationale": "Degraded battery, functional on AC power (Medium)",
            "category": "Ambiguous boundary"
        },

        # Category 4: Non-Native English / Formal Phrasing (Failure Mode 2 Targets)
        {
            "id": 16,
            "text": "Respected sir, my laptop getting blue screen every one hour when doing work kindly resolve",
            "judgment": "high",
            "rationale": "Severe hourly blue screen crashes (Target Failure Mode 2 Fix -> High)",
            "category": "Non-native / Formal"
        },
        {
            "id": 17,
            "text": "Greetings support team, kindly do the needful as my SAP login is showing user locked error for my id",
            "judgment": "high",
            "rationale": "SAP lockout blocking work (High)",
            "category": "Non-native / Formal"
        },
        {
            "id": 18,
            "text": "Respected team, kindly be informed that our production database has been completely unreachable since this morning",
            "judgment": "critical",
            "rationale": "Formal phrasing paired with total production outage (Target Failure Mode 2 Fix -> Critical)",
            "category": "Non-native / Formal"
        },
        {
            "id": 19,
            "text": "Greetings, I am not getting email notifications in my mobile phone application since yesterday evening",
            "judgment": "medium",
            "rationale": "Mobile email notification sync issue (Medium)",
            "category": "Non-native / Formal"
        },
        {
            "id": 20,
            "text": "Good day, wanting to inquire regarding process for requesting secondary screen monitor",
            "judgment": "low",
            "rationale": "General monitor process inquiry (Low)",
            "category": "Non-native / Formal"
        },

        # Category 5: Underspecified / Terse Inputs (Failure Mode 1 Targets)
        {
            "id": 21,
            "text": "network problem",
            "judgment": "medium",
            "rationale": "Terse vague input (Target Failure Mode 1 Fix -> Medium)",
            "category": "Underspecified / Terse"
        },
        {
            "id": 22,
            "text": "system error popped up on my screen",
            "judgment": "medium",
            "rationale": "Terse vague error report (Target Failure Mode 1 Fix -> Medium)",
            "category": "Underspecified / Terse"
        },
        {
            "id": 23,
            "text": "it is not working",
            "judgment": "medium",
            "rationale": "Ultra-short vague statement (Target Failure Mode 1 Fix -> Medium)",
            "category": "Underspecified / Terse"
        },
        {
            "id": 24,
            "text": "computer issue",
            "judgment": "medium",
            "rationale": "Vague 2-word input (Medium)",
            "category": "Underspecified / Terse"
        },
        {
            "id": 25,
            "text": "help with laptop",
            "judgment": "medium",
            "rationale": "Vague help query (Medium)",
            "category": "Underspecified / Terse"
        },
    ]

    print("--- 2. NEW ORGANIC STRESS TEST (25 NEW TICKETS) ---")
    results = []
    agreements = 0

    for item in stress_test_tickets_v2:
        text = item["text"]
        target = item["judgment"].upper()

        # Call full predict_priority_enhanced() pipeline (includes confidence fallback & ML)
        res = predict_priority_enhanced(text)
        pred = res["priority"].upper()
        conf = res["confidence"]
        is_fallback = res.get("is_low_confidence_priority", False)

        is_agree = (pred == target)
        if is_agree:
            agreements += 1

        results.append({
            "ID": item["id"],
            "Category": item["category"],
            "Ticket Text": text,
            "My Judgment": target,
            "Model Pred": pred,
            "Confidence": f"{round(conf * 100, 1)}%",
            "Fallback": "YES" if is_fallback else "NO",
            "Match": "AGREE" if is_agree else "DISAGREE",
        })

    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))

    agree_pct = (agreements / len(stress_test_tickets_v2)) * 100.0
    print("\n=======================================================================")
    print(f"NEW STRESS TEST RESULT: {agreements} / {len(stress_test_tickets_v2)} Agreed ({agree_pct:.1f}% Agreement Rate)")
    print(f"Prior Organic Baseline: 16 / 25 Agreed (64.0% Agreement Rate)")
    print("=======================================================================\n")

    # -------------------------------------------------------------------
    # PART 3: Verify Confidence Fallback Execution
    # -------------------------------------------------------------------
    print("--- 3. VERIFYING CONFIDENCE-BASED FALLBACK GUARDRAIL ---")
    terse_test_text = "something unusual happened"
    fallback_res = predict_priority_enhanced(terse_test_text)
    print(f"Input: '{terse_test_text}'")
    print(f"Output Payload: {fallback_res}")
    assert fallback_res["is_low_confidence_priority"] == True, "Fallback flag should be True"
    assert fallback_res["priority"] == "Medium", "Priority should default to Medium"
    print("CONFIDENCE FALLBACK GUARDRAIL TEST PASSED!\n")

if __name__ == "__main__":
    run_validation_v2()
