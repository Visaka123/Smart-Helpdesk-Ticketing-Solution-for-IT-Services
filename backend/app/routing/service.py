import os
import pickle
import numpy as np
from app.core.embeddings import embed_text

MODELS_DIR = "model_assets/models"
ROUTER_PATH = os.path.join(MODELS_DIR, "router.pkl")
LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.pkl")

_router_cache = None
_label_encoder_cache = None

def get_router_model():
    global _router_cache
    if _router_cache is None and os.path.exists(ROUTER_PATH):
        try:
            with open(ROUTER_PATH, "rb") as f:
                _router_cache = pickle.load(f)
        except Exception as e:
            print(f"[WARN] Could not load router.pkl: {e}")
    return _router_cache

def get_label_encoder():
    global _label_encoder_cache
    if _label_encoder_cache is None and os.path.exists(LABEL_ENCODER_PATH):
        try:
            with open(LABEL_ENCODER_PATH, "rb") as f:
                _label_encoder_cache = pickle.load(f)
        except Exception as e:
            print(f"[WARN] Could not load label_encoder.pkl: {e}")
    return _label_encoder_cache

def predict_team_ml(text: str, confidence_threshold: float = 0.55):
    """
    ML-based team routing using shared embedding service with graceful degradation fallback.
    """
    router = get_router_model()
    le = get_label_encoder()

    if router is None or le is None:
        return {
            "predicted_team": "Unassigned/Triage",
            "confidence": None,
            "top_3_alternatives": [],
            "is_low_confidence": True,
            "reason": "Model artifacts not loaded",
        }

    try:
        vector = embed_text(text).reshape(1, -1)

        if hasattr(router, "predict_proba"):
            probs = router.predict_proba(vector)[0]
            top_indices = np.argsort(probs)[::-1][:3]

            classes = le.classes_
            top_3 = []
            for idx in top_indices:
                team_label = classes[idx]
                prob = float(probs[idx])
                top_3.append({"team": str(team_label), "confidence": round(prob, 4)})

            best_team = top_3[0]["team"]
            best_conf = top_3[0]["confidence"]

            if best_conf < confidence_threshold:
                return {
                    "predicted_team": "Unassigned/Triage",
                    "suggested_team": best_team,
                    "confidence": best_conf,
                    "top_3_alternatives": top_3,
                    "is_low_confidence": True,
                    "reason": f"Confidence {best_conf:.2f} below threshold {confidence_threshold:.2f}",
                }

            return {
                "predicted_team": best_team,
                "confidence": best_conf,
                "top_3_alternatives": top_3,
                "is_low_confidence": False,
            }
        else:
            pred_idx = router.predict(vector)[0]
            team_label = le.inverse_transform([pred_idx])[0]
            return {
                "predicted_team": str(team_label),
                "confidence": 0.85,
                "top_3_alternatives": [{"team": str(team_label), "confidence": 0.85}],
                "is_low_confidence": False,
            }
    except Exception as e:
        print(f"[ERROR] Graceful degradation in predict_team_ml: {e}")
        return {
            "predicted_team": "Unassigned/Triage",
            "confidence": None,
            "top_3_alternatives": [],
            "is_low_confidence": True,
            "reason": "Routing model error — safely degraded to triage queue",
        }
