import os

backend_dir = "smart-helpdesk/backend"
scripts_to_check = [
    'run_experiments.py', 'test_semantic.py', 'audit_full.py', 
    'data_audit.py', 'full_audit.py', 'test_duplicate_logs_and_groq.py', 
    'verify_all_requirements.py', 'test_e2e_sequence.py', 'test_baseline.py'
]

for s in scripts_to_check:
    path = os.path.join(backend_dir, s)
    if os.path.exists(path):
        print(f"================ {s} ================")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            # print summary or relevant parts
            lines = content.splitlines()
            print(f"Total lines: {len(lines)}")
            for line in lines:
                if any(k in line.lower() for k in ["rag", "retriev", "relevance", "precision", "recall", "mrr", "ndcg", "hit", "latency", "ftr", "resolution", "kb", "article"]):
                    print("  ", line[:120])
