import os
import faiss
import pickle

from sentence_transformers import (
    SentenceTransformer
)


from app.knowledge.parser import (
    load_pdf
)

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

documents = []
folder = "model_assets/knowlegde"


for file in os.listdir(folder):

    if file.endswith(".pdf"):

        docs = load_pdf(
            os.path.join(folder,file)
        )

        for d in docs:

            documents.append(
                d.page_content
            )

vectors = embedder.encode(
    documents
)

index = faiss.IndexFlatL2(
    vectors.shape[1]
)

index.add(vectors)

faiss.write_index(
    index,
    "model_assets/models/kb.index"
)

pickle.dump(
    documents,
    open(
        "model_assets/models/kb_docs.pkl",
        "wb"
    )
)

print("Knowledge Base Built")