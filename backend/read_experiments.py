import os

backend_path = "D:/smart_help_desk/smart-helpdesk/backend"

for fname in ['run_experiments.py', 'full_audit.py', 'audit_full.py', 'test_semantic.py', 'verify_all_requirements.py']:
    fpath = os.path.join(backend_path, fname)
    if os.path.exists(fpath):
        print(f"\n==================== {fname} ====================")
        with open(fpath, 'r', encoding='utf-8') as f:
            print(f.read())
