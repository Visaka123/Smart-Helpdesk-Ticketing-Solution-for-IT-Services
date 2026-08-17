import sqlite3, os, json, time
import numpy as np

print("=== CHECKING WHAT IS AVAILABLE IN THE PROJECT FOR RAG ===")

# Check DB knowledge_articles
db1 = "smart_helpdesk.db"
db2 = "smart-helpdesk/backend/smart_helpdesk.db"

for db_path in [db1, db2]:
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        print(f"\nDB: {db_path}")
        cur.execute("SELECT count(*) FROM knowledge_articles")
        print("Knowledge articles count:", cur.fetchone()[0])
        cur.execute("SELECT id, title, source_file, helpful_count, unhelpful_count FROM knowledge_articles")
        rows = cur.fetchall()
        for r in rows:
            print("  Article:", r)
        
        # Check tickets table
        cur.execute("SELECT count(*) FROM tickets")
        print("Total tickets in DB:", cur.fetchone()[0])
        
        # Check tickets columns
        cols = [c[1] for c in cur.execute("PRAGMA table_info(tickets)").fetchall()]
        print("Tickets columns:", cols)
        
        if 'resolved_at' in cols and 'created_at' in cols:
            cur.execute("SELECT count(*) FROM tickets WHERE status IN ('resolved', 'closed')")
            print("Resolved tickets count:", cur.fetchone()[0])
        conn.close()

# Check PDF files in model_assets/knowlegde
pdf_dir = "smart-helpdesk/backend/model_assets/knowlegde"
if os.path.exists(pdf_dir):
    pdfs = os.listdir(pdf_dir)
    print(f"\nPDF Catalog in {pdf_dir}: {len(pdfs)} documents:")
    for p in pdfs:
        size = os.path.getsize(os.path.join(pdf_dir, p))
        print(f"  - {p} ({size} bytes)")

# Test speed of embedding/retrieval query
try:
    from sentence_transformers import SentenceTransformer
    import faiss, pickle
    
    t0 = time.time()
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    t_embed_load = time.time() - t0
    print(f"\nEmbedder load time: {t_embed_load:.4f} sec")
    
    kb_idx_path = "smart-helpdesk/backend/model_assets/models/kb.index"
    kb_pkl_path = "smart-helpdesk/backend/model_assets/models/kb_docs.pkl"
    
    if os.path.exists(kb_idx_path) and os.path.exists(kb_pkl_path):
        index = faiss.read_index(kb_idx_path)
        docs = pickle.load(open(kb_pkl_path, "rb"))
        print(f"FAISS index total vectors: {index.ntotal}, Docs in pkl: {len(docs)}")
        
        # Benchmark retrieval latency across sample test queries
        sample_queries = [
            "VPN connection dropping error",
            "SAP login authentication failure",
            "Database connection pool exhausted",
            "Microsoft Teams keeps crashing on startup",
            "Password reset self service guide"
        ]
        
        latencies = []
        for q in sample_queries:
            t_start = time.time()
            vec = embedder.encode([q]).astype('float32')
            dists, ids = index.search(vec, 3)
            retrieved = [docs[i] for i in ids[0] if 0 <= i < len(docs)]
            t_elapsed = (time.time() - t_start) * 1000 # ms
            latencies.append(t_elapsed)
            print(f"Query: '{q}' -> Top 1 distance: {dists[0][0]:.4f}, Latency: {t_elapsed:.2f} ms")
        
        print(f"Average Retrieval Latency (FAISS vector search only): {np.mean(latencies):.2f} ms (Min: {np.min(latencies):.2f} ms, Max: {np.max(latencies):.2f} ms)")

except Exception as e:
    print(f"Error testing retrieval latency: {e}")
