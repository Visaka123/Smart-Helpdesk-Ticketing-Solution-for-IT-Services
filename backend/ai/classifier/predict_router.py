import pickle

from sentence_transformers import (
    SentenceTransformer
)

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

model = pickle.load(
    open(
        "model_assets/models/router.pkl",
        "rb"
    )
)

def predict_team(text):

    vector = embedder.encode(
        [text]
    )

    team = model.predict(
        vector
    )[0]

    return team