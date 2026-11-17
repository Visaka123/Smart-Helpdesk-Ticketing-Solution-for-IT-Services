import os
import re
import pickle

_embedder = None
_router_model = None
_priority_model = None
_label_encoder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from app.core.embeddings import get_shared_embedder
            _embedder = get_shared_embedder()
        except Exception:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder

def _get_router_model():
    global _router_model
    if _router_model is None and os.path.exists("model_assets/models/router.pkl"):
        _router_model = pickle.load(open("model_assets/models/router.pkl", "rb"))
    return _router_model

def _get_priority_model():
    global _priority_model
    if _priority_model is None and os.path.exists("model_assets/models/priority.pkl"):
        _priority_model = pickle.load(open("model_assets/models/priority.pkl", "rb"))
    return _priority_model

def _get_label_encoder():
    global _label_encoder
    if _label_encoder is None:
        _le_path = "model_assets/models/label_encoder.pkl"
        if os.path.exists(_le_path):
            _label_encoder = pickle.load(open(_le_path, "rb"))
    return _label_encoder

def clean_ticket_title(title: str) -> str:
    """
    Trims whitespace and strips stray leading punctuation (colons, dashes, quotes, leading #N: prefixes).
    e.g. '#54: : CI pipeline failing...' -> 'CI pipeline failing...'
         ': CI pipeline failing...' -> 'CI pipeline failing...'
         '- Excel crash' -> 'Excel crash'
         '\"VPN down\"' -> 'VPN down'
    """
    if not title:
        return ""
    t = title.strip()
    while True:
        prev = t
        # Strip leading ticket number prefixes like #54: or #54 - or #54
        t = re.sub(r'^#\d+\s*[:\-–—]?\s*', '', t).strip()
        # Strip stray leading punctuation: colons, dashes, quotes, backticks
        t = re.sub(r'^[\s:\-–—"\'`]+', '', t).strip()
        # Strip trailing unmatched quotes
        if t.endswith('"') and not t.startswith('"'):
            t = t[:-1].strip()
        if t.endswith("'") and not t.startswith("'"):
            t = t[:-1].strip()
        if t == prev:
            break
    return t or title.strip()

def cleanup_existing_ticket_titles(db) -> int:
    """Cleans up stray leading punctuation and ticket number prefixes in existing DB rows."""
    from app.models.ticket import Ticket
    tickets = db.query(Ticket).all()
    count = 0
    for t in tickets:
        cleaned = clean_ticket_title(t.title)
        if cleaned != t.title:
            t.title = cleaned
            count += 1
    if count > 0:
        db.commit()
    return count

def predict_team(text):
    embedder = _get_embedder()
    router_model = _get_router_model()
    label_encoder = _get_label_encoder()
    vector = embedder.encode([text])
    pred = router_model.predict(vector)[0]
    if label_encoder is not None:
        try:
            return label_encoder.inverse_transform([pred])[0]
        except Exception:
            return str(pred)
    return str(pred)

def predict_priority(text):
    embedder = _get_embedder()
    priority_model = _get_priority_model()
    vector = embedder.encode([text])
    return priority_model.predict(vector)[0]

