import faiss
import numpy as np
import pandas as pd

from sentence_transformers import (
    SentenceTransformer
)

df = pd.read_csv(
    "model_assets/processed/training.csv"
)

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

vectors = embedder.encode(
    df["description"]
    .tolist()
)

index = faiss.IndexFlatL2(
    vectors.shape[1]
)

index.add(
    np.array(vectors)
)

faiss.write_index(
    index,
    "model_assets/models/tickets.index"
)

print("FAISS Index Built")