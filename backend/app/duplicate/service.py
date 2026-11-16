import re
import numpy as np
from app.database.database import SessionLocal
from app.models import Ticket, TicketRequester, DuplicateFeedbackLog
from app.core.embeddings import embed_text
from ai.rag.groq_client import ask_llm

GENERIC_WORDS = {
    "quota", "error", "issue", "failed", "failing", "failure", "not working", "unable",
    "problem", "alert", "warning", "crash", "bug", "trouble", "broken", "request",
    "need", "support", "help", "slow", "down", "stopped", "intermittent"
}

COMMON_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "but", "by", "with", "from", "as", "into", "through", "during", "before", "after",
    "above", "below", "up", "down", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "can", "will", "just", "don", "should",
    "now", "getting", "my", "your", "our", "their", "his", "her", "its", "please",
    "thanks", "thank", "user", "employee", "team", "dear", "hi", "hello"
}

KNOWN_TECHNICAL_TERMS = {
    "file server", "branch office", "s3 bucket", "docking station",
    "s3", "vpn", "wifi", "wi-fi", "sap", "outlook", "excel", "exchange", "teams", "slack",
    "zoom", "fileserver", "nas", "san", "dns", "dhcp", "ldap", "okta", "iam", "sso",
    "printer", "firewall", "router", "switch", "gateway", "database", "postgres",
    "mysql", "oracle", "sql", "mongo", "mongodb", "redis", "jira", "git", "github",
    "gitlab", "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "intellij", "pycharm",
    "vscode", "erp", "crm", "salesforce", "workday", "payroll", "cisco", "fortinet",
    "anyconnect", "dock", "thunderbolt", "macbook", "windows", "linux", "ubuntu",
    "license", "certificate", "ssl", "tls", "token", "active directory", "backup",
    "disk", "storage", "subnet", "vlan", "port", "ip", "host", "hostname", "server"
}

def extract_technical_tokens(text: str) -> set:
    text_lower = text.lower()
    found = set()

    # Multi-word known technical phrases
    for phrase in ["file server", "branch office", "s3 bucket", "docking station", "active directory", "wi-fi"]:
        if phrase in text_lower:
            found.add(phrase)

    # Error code patterns (HTTP 500/503/404, hex 0x..., codes like SU53, ME21N, ERR-402)
    error_codes = re.findall(r'\b[1-5][0-9]{2}\b|\b0x[0-9a-fA-F]+\b|\b[a-zA-Z]{2,6}[-_]?[0-9]{2,5}\b', text_lower)
    for ec in error_codes:
        found.add(ec)

    # Hostnames / IPs / server names
    ips_hosts = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|[a-zA-Z0-9-]+\.(?:corp|local|internal|com|net|org|io|lan)\b|[a-zA-Z0-9]+-(?:srv|db|app|web|host|vm|ap|dc)\b', text_lower)
    for ih in ips_hosts:
        found.add(ih)

    clean = re.sub(r'[^\w\s]', ' ', text_lower)
    tokens = clean.split()
    for tok in tokens:
        if len(tok) < 3:
            continue
        if tok in COMMON_STOPWORDS or tok in GENERIC_WORDS:
            continue
        if tok in KNOWN_TECHNICAL_TERMS:
            found.add(tok)
            continue
        if any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok):
            found.add(tok)
            continue
        # Specific domain words (e.g. backup, server, workstation, subnet)
        found.add(tok)

    return found

def has_specific_shared_term(text1: str, text2: str) -> tuple:
    t1_tokens = extract_technical_tokens(text1)
    t2_tokens = extract_technical_tokens(text2)
    shared = t1_tokens.intersection(t2_tokens)
    shared = {s for s in shared if s not in GENERIC_WORDS and s not in COMMON_STOPWORDS}
    return (len(shared) > 0, shared)

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
    Down-weights generic words and boosts specific system terms.
    """
    t1_clean = re.sub(r'[^\w\s]', ' ', text1.lower())
    t2_clean = re.sub(r'[^\w\s]', ' ', text2.lower())

    tokens1 = set(t1_clean.split())
    tokens2 = set(t2_clean.split())

    # Filter out stopwords and generic words
    t1_filtered = tokens1 - COMMON_STOPWORDS - GENERIC_WORDS
    t2_filtered = tokens2 - COMMON_STOPWORDS - GENERIC_WORDS

    if not t1_filtered or not t2_filtered:
        return 0.0

    intersection = t1_filtered.intersection(t2_filtered)
    union = t1_filtered.union(t2_filtered)

    base_jaccard = len(intersection) / float(len(union))

    # Special boost for exact system codes & terms
    system_keywords = {"su53", "me21n", "vpn", "cisco", "sap", "outlook", "mysql", "504", "503", "403", "500", "okta", "s3", "fileserver"}
    matched_sys_keywords = intersection.intersection(system_keywords)

    if matched_sys_keywords:
        base_jaccard = min(1.0, base_jaccard + 0.35)

    return round(float(base_jaccard), 4)

def verify_borderline_duplicate_with_llm(existing_title: str, existing_desc: str, query_title: str, query_desc: str) -> bool:
    try:
        prompt = f"""Compare these two IT support tickets:
Ticket A (Existing Issue): '{existing_title}. {existing_desc}'
Ticket B (New Ticket): '{query_title}. {query_desc}'

Are Ticket A and Ticket B describing the EXACT SAME underlying IT problem or system failure?
Important Rules:
- If Ticket B is describing a DIFFERENT problem or root cause in the same feature area, answer NO.
- If Ticket B is describing the EXACT SAME purchasing/system failure phrased in non-technical user terms, answer YES.

Answer with ONLY 'YES' or 'NO'."""
        response = ask_llm(prompt).strip().upper()
        return response.startswith("YES")
    except Exception as e:
        return False

def detect_hybrid_duplicates(title: str, description: str, threshold: float = 0.75):
    """
    Duplicate Detection Engine with strict thresholding:
    - Modal Trigger: Relevance >= 0.75 AND same category or team AND at least one specific shared term.
    - Inline Hint: 0.50 <= Relevance < 0.75.
    - Silent: Relevance < 0.50.
    """
    try:
        from app.routing.service import classify_and_route_ticket
        query_meta = classify_and_route_ticket(title, description)
        query_category = query_meta.get("category", "")
        query_team = query_meta.get("assigned_team", "")
    except Exception:
        query_category = ""
        query_team = ""

    try:
        db = SessionLocal()
        query_text = f"{title} {description}".strip()
        query_vec = embed_text(query_text)

        all_tickets = db.query(Ticket).all()

        modal_matches = []
        inline_matches = []

        for ticket in all_tickets:
            ticket_text = f"{ticket.title} {ticket.description}".strip()
            ticket_vec = embed_text(ticket_text)

            sem_score = cosine_similarity(query_vec, ticket_vec)
            lex_score = compute_lexical_similarity(query_text, ticket_text)

            # Composite Score: 85% Semantic Cosine + 15% Lexical Jaccard
            composite_score = (sem_score * 0.85) + (lex_score * 0.15)

            # Check specific shared technical term
            has_term, matched_terms = has_specific_shared_term(query_text, ticket_text)

            # Check same category or team
            cand_cat = (ticket.category or "").strip().lower()
            cand_team = (ticket.assigned_team or "").strip().lower()
            q_cat = (query_category or "").strip().lower()
            q_team = (query_team or "").strip().lower()

            is_same_category_or_team = (
                bool(cand_cat and q_cat and (cand_cat == q_cat or cand_cat in q_cat or q_cat in cand_cat)) or
                bool(cand_team and q_team and (cand_team == q_team or cand_team in q_team or q_team in cand_team))
            )

            # Down-weight if no specific shared technical term
            if not has_term:
                effective_score = min(round(composite_score * 0.5, 4), 0.45)
            else:
                effective_score = round(composite_score, 4)

            # Threshold decisions:
            # 1. Modal: effective_score >= 0.75 AND same category/team AND has specific shared term
            # 2. Inline Hint: 0.50 <= effective_score < 0.75 (or score >= 0.75 without category/team match)
            should_show_modal = (effective_score >= 0.75) and is_same_category_or_team and has_term
            should_show_inline_hint = (0.50 <= effective_score < 0.75) or ((effective_score >= 0.75) and not should_show_modal)

            # Count total linked requesters
            requester_count = 1 + db.query(TicketRequester).filter(TicketRequester.ticket_id == ticket.id).count()

            match_info = {
                "ticket_id": ticket.id,
                "title": ticket.title,
                "description": ticket.description[:200] + "..." if len(ticket.description) > 200 else ticket.description,
                "category": ticket.category,
                "assigned_team": ticket.assigned_team or "Unassigned/Triage",
                "assigned_agent_name": ticket.assigned_agent_name,
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
                "relevance_score": round(effective_score, 4),
                "has_specific_term": has_term,
                "matched_terms": list(matched_terms),
                "is_same_category_or_team": is_same_category_or_team,
                "should_show_modal": should_show_modal,
                "should_show_inline_hint": should_show_inline_hint,
            }

            if should_show_modal:
                modal_matches.append(match_info)
            elif should_show_inline_hint:
                inline_matches.append(match_info)

        db.close()

        modal_matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        inline_matches.sort(key=lambda x: x["relevance_score"], reverse=True)

        open_modal_matches = [m for m in modal_matches if m["status"] in ["open", "in_progress", "pending"]]
        resolved_modal_matches = [m for m in modal_matches if m["status"] in ["resolved", "closed"]]

        has_modal_match = len(modal_matches) > 0
        has_open_match = len(open_modal_matches) > 0
        has_resolved_match = len(resolved_modal_matches) > 0

        top_match = None
        if has_modal_match:
            top_match = modal_matches[0]
        elif len(inline_matches) > 0:
            top_match = inline_matches[0]

        return {
            "has_duplicate": has_modal_match,
            "should_show_modal": has_modal_match,
            "should_show_inline_hint": (not has_modal_match) and (len(inline_matches) > 0),
            "top_match": top_match,
            "inline_match": inline_matches[0] if (not has_modal_match and len(inline_matches) > 0) else None,
            "has_open_match": has_open_match,
            "has_resolved_match": has_resolved_match,
            "open_matches": open_modal_matches,
            "resolved_matches": resolved_modal_matches,
            "matched_tickets": modal_matches if has_modal_match else inline_matches,
            "relevance_score": top_match["relevance_score"] if top_match else 0.0,
        }
    except Exception as e:
        print(f"[WARN] Error in detect_hybrid_duplicates: {e}")
        return {
            "has_duplicate": False,
            "should_show_modal": False,
            "should_show_inline_hint": False,
            "top_match": None,
            "inline_match": None,
            "has_open_match": False,
            "has_resolved_match": False,
            "open_matches": [],
            "resolved_matches": [],
            "matched_tickets": [],
            "relevance_score": 0.0,
        }

def record_duplicate_feedback(new_ticket_text: str, matched_ticket_id: int, similarity_score: float, user_action: str, db=None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        log_entry = DuplicateFeedbackLog(
            new_ticket_text=new_ticket_text,
            matched_ticket_id=matched_ticket_id,
            similarity_score=similarity_score,
            user_action=user_action,
        )
        db.add(log_entry)
        db.commit()
        return True
    except Exception as e:
        print(f"[WARN] Error recording duplicate feedback: {e}")
        return False
    finally:
        if close_db:
            db.close()

# Backward compatibility alias
detect_semantic_duplicates = detect_hybrid_duplicates
