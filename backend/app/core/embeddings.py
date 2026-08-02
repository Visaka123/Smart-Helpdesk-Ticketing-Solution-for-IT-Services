import os
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

EMBEDDER_MODEL_NAME = "all-MiniLM-L6-v2"
_shared_embedder = None
_embedder_failed = False

def get_device():
    return "cuda" if torch.cuda.is_available() else "cpu"

def get_shared_embedder():
    """
    Singleton lazy loader for SentenceTransformer with explicit device assignment
    and meta tensor error handling.
    """
    global _shared_embedder, _embedder_failed

    if _embedder_failed:
        return None

    if _shared_embedder is None:
        try:
            device = get_device()
            print(f"[EMBEDDINGS] Initializing shared SentenceTransformer('{EMBEDDER_MODEL_NAME}') on device '{device}'...")
            
            # Instantiate with explicit device to prevent meta-tensor loading errors
            model = SentenceTransformer(EMBEDDER_MODEL_NAME, device=device)
            
            # Verify parameter tensor initialization
            try:
                for param in model.parameters():
                    if param.is_meta:
                        model.to_empty(device=device)
                        break
            except Exception:
                pass

            _shared_embedder = model
            print("[EMBEDDINGS] Shared SentenceTransformer model ready!")
        except Exception as e:
            print(f"[ERROR] Failed to load SentenceTransformer: {e}")
            _embedder_failed = True
            return None

    return _shared_embedder

def embed_text(text_input) -> np.ndarray:
    """
    Safely encode text or list of texts into embedding vectors.
    Returns 384-dimensional numpy array.
    Falls back gracefully to zero/hash vector on failure.
    """
    embedder = get_shared_embedder()

    is_single = isinstance(text_input, str)
    texts = [text_input] if is_single else text_input

    if embedder is not None:
        try:
            vectors = embedder.encode(texts, show_progress_bar=False)
            vectors_np = np.array(vectors, dtype=np.float32)
            return vectors_np[0] if is_single else vectors_np
        except Exception as e:
            print(f"[WARN] Error during sentence encoding: {e}")

    # Fallback pseudo-random deterministic vector from text hash
    print("[WARN] Using deterministic fallback vector generator.")
    fallback_vecs = []
    for txt in texts:
        seed = sum(ord(c) for c in str(txt)) % 100000
        np.random.seed(seed)
        vec = np.random.randn(384).astype(np.float32)
        vec /= (np.linalg.norm(vec) + 1e-9)
        fallback_vecs.append(vec)

    fallback_np = np.array(fallback_vecs, dtype=np.float32)
    return fallback_np[0] if is_single else fallback_np
