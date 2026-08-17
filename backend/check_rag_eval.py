import os, glob

root = "D:/smart_help_desk"

print("Scanning all python files for RAG evaluation or vector search evaluation...")
found_rag_eval = False
for dirpath, dirnames, filenames in os.walk(root):
    for fname in filenames:
        if fname.endswith(".py"):
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if ("ndcg" in content.lower() or "mrr" in content.lower() or "precision@" in content.lower() or "recall@" in content.lower() or "hit_rate" in content.lower() or "hit rate" in content.lower()):
                        print(f"FOUND METRIC REFERENCE IN: {fpath}")
                        found_rag_eval = True
            except Exception as e:
                pass

if not found_rag_eval:
    print("NO RAG/Retrieval evaluation metrics (NDCG, MRR, Precision@K, Recall@K, Hit Rate@K) found in any script in the codebase.")
