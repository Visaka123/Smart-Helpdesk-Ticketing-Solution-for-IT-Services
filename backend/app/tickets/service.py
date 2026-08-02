import pickle
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

router_model = pickle.load(
    open("model_assets/models/router.pkl", "rb")
)

priority_model = pickle.load(
    open("model_assets/models/priority.pkl", "rb")
)

import os
_le_path = "model_assets/models/label_encoder.pkl"
label_encoder = pickle.load(open(_le_path, "rb")) if os.path.exists(_le_path) else None

def predict_team(text):
    vector = embedder.encode([text])
    pred = router_model.predict(vector)[0]
    if label_encoder is not None:
        try:
            return label_encoder.inverse_transform([pred])[0]
        except Exception:
            return str(pred)
    return str(pred)

def predict_priority(text):
    vector = embedder.encode([text])
    return priority_model.predict(vector)[0]
