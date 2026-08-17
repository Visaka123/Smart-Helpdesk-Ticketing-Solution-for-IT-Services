import re
import numpy as np
from app.database.database import SessionLocal
from app.models import Ticket, TicketRequester, DuplicateFeedbackLog
from app.core.embeddings import embed_text
from ai.rag.groq_client import ask_llm

def cosine_similarity(vec1, vec2):
    dot = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

def compute_lexical_similarity(text1: str, text2: str) -> float:
    """
    Computes lexical / keyword overlap score (Jaccard similarity on tokens & error codes).
    Gives extra weight to system terms and alphanumeric error codes (e.g. SU53, ME21N, 504, VPN).
    """
    t1_clean = re.sub(r'[^\w\s]', ' ', text1.lower())
    t2_clean = re.sub(r'[^\w\s]', ' ', text2.lower())

    tokens1 = set(t1_clean.split())
    tokens2 = set(t2_clean.split())

    # Stopwords filter
    stopwords = {"a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is", "are", "getting", "when", "with", "my", "your", "error", "issue", "problem"}
    t1_filtered = tokens1 - stopwords
    t2_filtered = tokens2 - stopwords

    if not t1_filtered or not t2_filtered:
        return 0.0

    intersection = t1_filtered.intersection(t2_filtered)
    union = t1_filtered.union(t2_filtered)

    base_jaccard = len(intersection) / float(len(union))

    # Special boost for exact system codes (e.g. su53, me21n, vpn, cisco, outlook, mysql)
    system_keywords = {"su53", "me21n", "vpn", "cisco", "sap", "outlook", "mysql", "504", "403", "500", "okta"}
    matched_sys_keywords = intersection.intersection(system_keywords)

    if matched_sys_keywords:
        base_jaccard = min(1.0, base_jaccard + 0.35)

    return round(float(base_jaccard), 4)

def verify_borderline_duplicate_with_llm(existing_title: str, existing_desc: str, query_title: str, query_desc: str) -> bool:
    """
    Lightweight LLM classification step for borderline paraphrased duplicates (semantic similarity in 0.28 to 0.48 range).
    Accurately distinguishes between:
      1. Same underlying failure in plain non-technical terms -> YES (Match)
      2. Different root cause in same feature area (e.g. slow page load vs 500 error, or promo code invalid vs checkout crash) -> NO (Reject)
    """
    try:
        prompt = f"""Compare these two IT support tickets:
Ticket A (Existing Issue): '{existing_title}. {existing_desc}'
Ticket B (New Ticket): '{query_title}. {query_desc}'

Are Ticket A and Ticket B describing the EXACT SAME underlying IT problem or system failure?
Important Rules:
- If Ticket B is describing a DIFFERENT problem or root cause in the same feature area (such as page loading slowly vs hard server error crash, or promo code invalid vs checkout crash), answer NO.
- If Ticket B is describing the EXACT SAME purchasing/system failure phrased in non-technical user terms, answer YES.

Answer with ONLY 'YES' or 'NO'."""
        response = ask_llm(prompt).strip().upper()
        return response.startswith("YES")
    except Exception as e:
        return False

def detect_hybrid_duplicates(title: str, description: str, threshold: float = 0.75):
    """
    Two-Stage Hybrid Duplicate Detection Engine.
    Stage 1: High-confidence Semantic Cosine (85% weight) + Lexical Jaccard (15% weight).
    Stage 2: Secondary LLM Classifier for borderline non-technical paraphrases (0.28 <= sem_score < 0.48).
    - Reworded/Paraphrased duplicates describing the same underlying issue are correctly matched.
    - Related-but-different issues in the same feature area (e.g. slow page load or promo code invalid vs 500 crash)
      are correctly identified as distinct and do NOT match.
    """
    try:
        db = SessionLocal()
        query_text = f"{title} {description}".strip()
        query_vec = embed_text(query_text)

        all_tickets = db.query(Ticket).all()

        open_matches = []
        resolved_matches = []

        for ticket in all_tickets:
            ticket_text = f"{ticket.title} {ticket.description}".strip()
            ticket_vec = embed_text(ticket_text)

            sem_score = cosine_similarity(query_vec, ticket_vec)
            lex_score = compute_lexical_similarity(query_text, ticket_text)

            # Semantic-Primary Composite Score: 85% Semantic Cosine + 15% Lexical Jaccard
            composite_score = (sem_score * 0.85) + (lex_score * 0.15)

            # Two-Stage Match Rule:
            # 1. High-Confidence Match: Semantic Cosine >= 0.48 OR Composite Score >= 0.45 OR Lexical Jaccard >= 0.50
            # 2. Borderline Paraphrase Verification (0.28 <= sem_score < 0.48): Call LLM Classifier
            is_match = False
            if (sem_score >= 0.48) or (composite_score >= 0.45) or (lex_score >= 0.50):
                is_match = True
            elif sem_score >= 0.28:
                is_match = verify_borderline_duplicate_with_llm(
                    existing_title=ticket.title,
                    existing_desc=ticket.description,
                    query_title=title,
                    query_desc=description
                )

            if is_match:
                # Count total linked requesters
                requester_count = 1 + db.query(TicketRequester).filter(TicketRequester.ticket_id == ticket.id).count()

                match_info = {
                    "ticket_id": ticket.id,
                    "title": ticket.title,
                    "description": ticket.description[:200] + "..." if len(ticket.description) > 200 else ticket.description,
                    "category": ticket.category,
                    "assigned_team": ticket.assigned_team or "Unassigned/Triage",
                    "status": ticket.status,
                    "requester_name": ticket.requester_name,
                    "requester_department": ticket.requester_department,
                    "requester_count": requester_count,
                    "resolution_summary": ticket.resolution_summary or ticket.resolution_notes or "Verified fix provided.",
                    "resolution_detail": ticket.resolution_detail or ticket.resolution_notes or "",
                    "root_cause": ticket.root_cause,
                    "semantic_score": round(sem_score, 4),
                    "lexical_score": round(lex_score, 4),
                    "hybrid_score": round(composite_score, 4),
                }

                if ticket.status in ["resolved", "closed"]:
                    resolved_matches.append(match_info)
                elif ticket.status in ["open", "in_progress", "pending"]:
                    open_matches.append(match_info)

        db.close()

        open_matches.sort(key=lambda x: x["semantic_score"], reverse=True)
        resolved_matches.sort(key=lambda x: x["semantic_score"], reverse=True)

        has_open_match = len(open_matches) > 0
        has_resolved_match = len(resolved_matches) > 0
        has_duplicate = has_open_match or has_resolved_match

        top_match = None
        if has_open_match and has_resolved_match:
            top_match = open_matches[0] if open_matches[0]["semantic_score"] >= resolved_matches[0]["semantic_score"] else resolved_matches[0]
        elif has_open_match:
            top_match = open_matches[0]
        elif has_resolved_match:
            top_match = resolved_matches[0]

        all_matches = open_matches + resolved_matches

        return {
            "has_duplicate": has_duplicate,
            "has_open_match": has_open_match,
            "has_resolved_match": has_resolved_match,
            "top_match": top_match,
            "open_matches": open_matches,
            "resolved_matches": resolved_matches,
            "matched_tickets": all_matches,
        }
    except Exception as e:
        print(f"[WARN] Error in detect_hybrid_duplicates: {e}")
        return {
            "has_duplicate": False,
            "has_open_match": False,
            "has_resolved_match": False,
            "top_match": None,
            "open_matches": [],
            "resolved_matches": [],
            "matched_tickets": [],
        }

    except Exception as e:
        print(f"[WARN] Error in detect_hybrid_duplicates: {e}")
        return {
            "has_duplicate": False,
            "has_open_match": False,
            "has_resolved_match": False,
            "top_match": None,
            "open_matches": [],
            "resolved_matches": [],
        }

def record_duplicate_feedback(new_ticket_text: str, matched_ticket_id: int, similarity_score: float, user_action: str):
    try:
        db = SessionLocal()
        log_entry = DuplicateFeedbackLog(
            new_ticket_text=new_ticket_text,
            matched_ticket_id=matched_ticket_id,
            similarity_score=similarity_score,
            user_action=user_action,
        )
        db.add(log_entry)
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"[WARN] Error recording duplicate feedback: {e}")
        return False

# Backward compatibility alias
detect_semantic_duplicates = detect_hybrid_duplicates

