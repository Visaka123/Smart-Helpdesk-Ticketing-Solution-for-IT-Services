import os
import pickle
import numpy as np
from app.core.embeddings import embed_text

MODELS_DIR = "model_assets/models"
PRIORITY_MODEL_PATH = os.path.join(MODELS_DIR, "priority.pkl")
LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "priority_label_encoder.pkl")

_priority_model_cache = None
_label_encoder_cache = None

def get_priority_model():
    global _priority_model_cache
    if _priority_model_cache is None and os.path.exists(PRIORITY_MODEL_PATH):
        try:
            with open(PRIORITY_MODEL_PATH, "rb") as f:
                _priority_model_cache = pickle.load(f)
        except Exception as e:
            print(f"[WARN] Could not load priority.pkl: {e}")
    return _priority_model_cache

def get_label_encoder():
    global _label_encoder_cache
    if _label_encoder_cache is None and os.path.exists(LABEL_ENCODER_PATH):
        try:
            with open(LABEL_ENCODER_PATH, "rb") as f:
                _label_encoder_cache = pickle.load(f)
        except Exception as e:
            print(f"[WARN] Could not load priority_label_encoder.pkl: {e}")
    return _label_encoder_cache

CRITICAL_KEYWORDS = ["outage", "down", "crash", "production", "data loss", "security breach", "malware", "ransomware", "emergency", "504 gateway"]
HIGH_KEYWORDS = ["urgent", "cannot work", "blocked", "vpn fail", "su53", "access denied", "payroll", "server error"]

def predict_priority_enhanced(description: str, department: str = "General", role: str = "employee") -> dict:
    """
    Predict priority considering text embeddings and requester department context,
    with built-in graceful degradation.
    """
    text_lower = description.lower()
    model = get_priority_model()

    try:
        vector = embed_text(description).reshape(1, -1)

        if model is not None:
            raw_pred = model.predict(vector)[0]
            le = get_label_encoder()
            if le is not None and isinstance(raw_pred, (int, np.integer)):
                base_pred = le.inverse_transform([raw_pred])[0]
            else:
                base_pred = raw_pred

            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(vector)[0]
                conf = float(np.max(probs))
            else:
                conf = 0.88
        else:
            base_pred = "Medium"
            conf = 0.70
    except Exception as e:
        print(f"[WARN] Graceful degradation in predict_priority_enhanced: {e}")
        base_pred = "Medium"
        conf = 0.65

    raw_ml_prediction = str(base_pred).capitalize()
    reasons = ["ML Text Classifier"]
    is_low_confidence = False
    CONFIDENCE_THRESHOLD = 0.45

    # Failure Mode 1 Fix: Confidence-Based Fallback Guardrail
    if conf < CONFIDENCE_THRESHOLD:
        is_low_confidence = True
        reasons.append(f"Low ML confidence ({round(conf * 100, 1)}% < 45.0% threshold); raw prediction '{raw_ml_prediction}' defaulted to Medium for triage review")
        predicted_priority = "Medium"
    else:
        predicted_priority = raw_ml_prediction

    if any(kw in text_lower for kw in CRITICAL_KEYWORDS):
        predicted_priority = "Critical"
        conf = min(0.98, conf + 0.15)
        reasons.append("Critical business impact keywords detected")
    elif any(kw in text_lower for kw in HIGH_KEYWORDS) and predicted_priority in ["Low", "Medium"]:
        predicted_priority = "High"
        conf = min(0.92, conf + 0.10)
        reasons.append("High urgency operational block detected")

    if department in ["Engineering", "Executive", "Finance"] and predicted_priority == "Medium":
        if any(kw in text_lower for kw in ["fail", "error", "unable", "cannot"]):
            predicted_priority = "High"
            reasons.append(f"Department '{department}' priority boost")

    return {
        "priority": predicted_priority,
        "confidence": round(conf, 4),
        "raw_ml_prediction": raw_ml_prediction,
        "is_low_confidence_priority": is_low_confidence,
        "needs_triage_review": is_low_confidence,
        "reasons": reasons,
    }
