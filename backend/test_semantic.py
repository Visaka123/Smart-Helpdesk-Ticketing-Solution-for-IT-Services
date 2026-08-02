"""
test_semantic.py
Proves the duplicate detection works on MEANING, not just keywords.
python test_semantic.py
"""
from app.core.embeddings import get_shared_embedder
from app.duplicate.service import cosine_similarity, compute_lexical_similarity

embedder = get_shared_embedder()

tests = [
    (
        "Same issue, same words (Alice vs Bob similar)",
        "Outlook keeps asking for password repeatedly. Microsoft account password prompt every few minutes on Windows 11.",
        "Outlook password prompt keeps appearing. Constantly asking to re-enter password on Windows laptop Office 365.",
    ),
    (
        "Same issue, COMPLETELY different words (true semantic test)",
        "Outlook keeps asking for password repeatedly. Microsoft account password prompt every few minutes on Windows 11.",
        "Email application wont stop requesting login credentials. Keeps popping up asking to authenticate again and again.",
    ),
    (
        "Different issue entirely (should NOT match)",
        "Outlook keeps asking for password repeatedly. Microsoft account password prompt every few minutes on Windows 11.",
        "The office printer is not connecting to the network. Cannot print any documents from my laptop.",
    ),
    (
        "VPN issue same meaning different words",
        "Cannot connect to corporate VPN from home. Cisco AnyConnect shows certificate verification failed.",
        "Remote access not working. Getting SSL error when trying to connect to company network through VPN client.",
    ),
]

THRESHOLD = 0.75
LEX_THRESHOLD = 0.30

print("=" * 65)
print("SEMANTIC DUPLICATE DETECTION — MEANING-BASED TEST")
print("=" * 65)

for label, text1, text2 in tests:
    v1 = embedder.encode([text1])[0]
    v2 = embedder.encode([text2])[0]
    sem = cosine_similarity(v1, v2)
    lex = compute_lexical_similarity(text1, text2)
    is_match = (sem >= THRESHOLD and lex >= LEX_THRESHOLD) or sem >= 0.85
    print(f"\n{label}")
    print(f"  Semantic score : {sem:.4f}  (need >= {THRESHOLD})")
    print(f"  Lexical score  : {lex:.4f}  (need >= {LEX_THRESHOLD})")
    print(f"  Result         : {'DUPLICATE DETECTED' if is_match else 'NOT a duplicate'}")

print("\n" + "=" * 65)
