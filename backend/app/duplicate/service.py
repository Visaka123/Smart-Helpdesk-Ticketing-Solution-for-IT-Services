import re
import numpy as np
from app.database.database import SessionLocal
from app.models import Ticket, TicketRequester, DuplicateFeedbackLog
from app.core.embeddings import embed_text

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

def detect_hybrid_duplicates(title: str, description: str, threshold: float = 0.75):
    """
    Hybrid Semantic + Lexical Duplicate Detection Engine.
    Requires BOTH semantic embedding similarity (>= threshold or 0.75) AND lexical/keyword overlap (>= 0.30)
    OR high semantic embedding similarity (>= 0.85).
    Differentiates between:
      1. Matched Open Ticket -> Hard block, link requester to existing ticket
      2. Matched Resolved Ticket -> Hard block, surface plain-language solution
    """
    try:
        db = SessionLocal()
        query_text = f"{title} {description}".strip()
        query_vec = embed_text(query_text)

        all_tickets = db.query(Ticket).all()

        open_matches = []
        resolved_matches = []

        eff_threshold = threshold if threshold is not None else 0.75

        for ticket in all_tickets:
            ticket_text = f"{ticket.title} {ticket.description}".strip()
            ticket_vec = embed_text(ticket_text)

            sem_score = cosine_similarity(query_vec, ticket_vec)
            lex_score = compute_lexical_similarity(query_text, ticket_text)

            # Hybrid Match Rule: BOTH semantic >= eff_threshold and lexical >= 0.30 OR sem >= 0.85
            is_match = (sem_score >= eff_threshold and lex_score >= 0.30) or (sem_score >= 0.85)

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
                    "hybrid_score": round(max(sem_score, lex_score), 4),
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

