import time
from app.core.embeddings import get_shared_embedder, embed_text

def test_embedder_standalone():
    print("\n=== Testing Standalone Shared Embedder ===")
    start = time.time()
    model = get_shared_embedder()
    elapsed = time.time() - start

    if model is not None:
        print(f"[SUCCESS] Shared SentenceTransformer model loaded in {elapsed:.2f} seconds.")
    else:
        print("[WARN] Model loaded in fallback mode.")

    text = "Cisco AnyConnect VPN certificate error when connecting from home"
    vector = embed_text(text)

    print(f"Input Text   : '{text}'")
    print(f"Vector Shape : {vector.shape}")
    print(f"Sample Values: {vector[:5].tolist()}")
    print("=== Standalone Test PASSED ===\n")

if __name__ == "__main__":
    test_embedder_standalone()
