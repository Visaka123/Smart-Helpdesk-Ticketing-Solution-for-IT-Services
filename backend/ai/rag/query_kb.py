import faiss
import pickle

from sentence_transformers import (
    SentenceTransformer
)

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

index = faiss.read_index(
    "model_assets/models/kb.index"
)

documents = pickle.load(
    open(
        "model_assets/models/kb_docs.pkl",
        "rb"
    )
)

def retrieve_docs(query):

    vector = embedder.encode(
        [query]
    ).astype('float32')

    distances, ids = (
        index.search(
            vector,
            3
        )
    )

    results = []

    for idx in ids[0]:
        if idx >= 0 and idx < len(documents):
            results.append(
                documents[idx]
            )

    return results