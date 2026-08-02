import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer("all-MiniLM-L6-v2")

INDEX_PATH = "model_assets/models/tickets.index"

index = None
if os.path.exists(INDEX_PATH):
    index = faiss.read_index(INDEX_PATH)

def search_similar(text):
    if index is None:
        return []
    vec = embedder.encode([text]).astype(np.float32)
    distances, ids = index.search(vec, 5)
    return ids[0].tolist()
