"""
backend/app/suggestions/service.py

Service for recommending previously resolved tickets with similar issues ("Fixes that worked before").
Matches only RESOLVED/CLOSED tickets with non-empty resolution notes.
Privacy-sanitizes summaries and provides deflection analytics.
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database.database import SessionLocal
from app.models.ticket import Ticket, SuggestionFeedback
from app.core.embeddings import embed_text
from app.duplicate.service import (
    has_specific_shared_term,
    cosine_similarity,
    compute_lexical_similarity,
    GENERIC_WORDS,
)

COMMON_PERSON_NAMES = [
    "sarah", "mike", "ravi", "priya", "arun", "meena", "kiran", "john manager",
    "john", "alice employee", "alice", "bob", "charlie", "deepak", "devon", "pooja"
]

def sanitize_resolution_summary(text: Optional[str]) -> str:
    """
    Strips sensitive PII and infrastructure details:
    - Emails
    - IP addresses (IPv4 & ports)
    - Passwords, tokens, api keys, secrets
    - Internal hostnames/domains (*.corp, *.local, *.internal, etc.)
    - Person names
    Truncates to at most 300 characters.
    """
    if not text:
        return ""

    sanitized = text

    # Strip emails
    sanitized = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[REDACTED_EMAIL]',
        sanitized
    )

    # Strip IP addresses (IPv4 with optional port)
    sanitized = re.sub(
        r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b',
        '[REDACTED_IP]',
        sanitized
    )

    # Strip credentials / passwords / tokens / keys
    sanitized = re.sub(
        r'(?i)\b(?:password|pwd|token|api[_-]?key|secret|bearer)\s*[:=]\s*\S+',
        '[REDACTED_KEY]',
        sanitized
    )

    # Strip internal hostnames and domain suffixes
    sanitized = re.sub(
        r'\b[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*\.(?:corp|local|internal|lan|company|domain|infra)\b',
        '[REDACTED_HOST]',
        sanitized,
        flags=re.IGNORECASE
    )
    sanitized = re.sub(
        r'\b[a-zA-Z0-9_-]+-(?:srv|db|app|web|host|vm|ap|dc|nas|san)\b',
        '[REDACTED_HOST]',
        sanitized,
        flags=re.IGNORECASE
    )

    # Strip agent/resolver name mentions
    sanitized = re.sub(
        r'(?i)\b(?:fixed by|resolved by|handled by|assigned to|agent)\s*[:=]?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b',
        '[REDACTED_NAME]',
        sanitized
    )
    for name in COMMON_PERSON_NAMES:
        pattern = r'\b' + re.escape(name) + r'\b'
        sanitized = re.sub(pattern, '[REDACTED_NAME]', sanitized, flags=re.IGNORECASE)

    # Clean redundant whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    # Truncate to 300 chars max
    if len(sanitized) > 300:
        sanitized = sanitized[:297].rstrip() + "..."

    return sanitized


def find_suggested_fixes(
    title: str,
    description: str,
    category: Optional[str] = None,
    db: Optional[Session] = None,
    min_relevance: float = 0.60,
    max_results: int = 3,
) -> List[Dict[str, Any]]:
    """
    Matches candidate resolved/closed tickets with non-empty resolution notes.
    Requirements:
    - Only tickets with non-empty resolution notes.
    - Relevance >= 60% AND at least one specific shared term (down-weighting generic words).
    - Prefer same category (+0.05 bonus).
    - Privacy: sanitized resolution summary truncated to 300 chars.
    - Returns top 3 results.
    """
    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    try:
        query_text = f"{title.strip()} {description.strip()}".strip()
        if not query_text:
            return []

        # 1. Fetch all resolved/closed tickets with non-empty resolution notes
        resolved_tickets = (
            db.query(Ticket)
            .filter(
                Ticket.status.in_(["resolved", "closed"]),
                (
                    (Ticket.resolution_summary != None) & (Ticket.resolution_summary != "")
                    | (Ticket.resolution_notes != None) & (Ticket.resolution_notes != "")
                    | (Ticket.resolution_detail != None) & (Ticket.resolution_detail != "")
                ),
            )
            .all()
        )

        if not resolved_tickets:
            return []

        query_vec = embed_text(query_text)
        candidates = []

        for ticket in resolved_tickets:
            raw_summary = (
                ticket.resolution_summary
                or ticket.resolution_notes
                or ticket.resolution_detail
                or ""
            ).strip()

            if not raw_summary:
                continue

            target_text = f"{ticket.title} {ticket.description or ''}".strip()

            # Specific shared technical term check (service name, error code, hostname, system, etc.)
            has_term, shared_terms = has_specific_shared_term(query_text, target_text)
            if not has_term:
                continue

            # Compute semantic embedding cosine similarity
            target_vec = embed_text(target_text)
            sem_sim = cosine_similarity(query_vec, target_vec)

            # Compute lexical similarity with technical boost
            lex_sim = compute_lexical_similarity(query_text, target_text)

            # Hybrid score
            relevance = (0.65 * sem_sim) + (0.35 * lex_sim)

            # Category preference boost (+0.05) if categories match
            if category and ticket.category and category.lower() == ticket.category.lower():
                relevance = min(1.0, relevance + 0.05)

            if relevance < min_relevance:
                continue

            sanitized_summary = sanitize_resolution_summary(raw_summary)

            candidates.append({
                "ticket_id": ticket.id,
                "title": ticket.title,
                "category": ticket.category or "General IT",
                "relevance": round(float(relevance), 2),
                "resolution_summary": sanitized_summary,
                "resolved_at": str(ticket.resolved_at or ticket.created_at),
                "resolved_by_team": ticket.assigned_team or "Support Team",
            })

        # Sort by relevance descending
        candidates.sort(key=lambda x: x["relevance"], reverse=True)
        return candidates[:max_results]
    finally:
        if close_db_on_exit:
            db.close()


def record_suggestion_feedback(
    suggestion_ticket_id: int,
    action: str,
    relevance: float = 0.0,
    user_id: Optional[int] = None,
    query_text: Optional[str] = "",
    db: Optional[Session] = None,
) -> SuggestionFeedback:
    """
    Stores suggestion feedback ("solved", "not_helpful", "still_need_help", "shown")
    in suggestion_feedback table.
    """
    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    try:
        feedback = SuggestionFeedback(
            user_id=user_id,
            query_text=(query_text or "")[:500],
            suggested_ticket_id=suggestion_ticket_id,
            action=action,
            relevance=float(relevance),
            created_at=datetime.utcnow(),
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback
    finally:
        if close_db_on_exit:
            db.close()


def get_deflection_analytics(db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Calculates deflection metrics:
    - suggestions_shown: total suggestion shown events
    - solved_count: count of 'solved' feedbacks
    - deflection_rate: solved / shown (0.0 if shown == 0)
    - top_5_helpful_tickets: top 5 tickets by 'solved' count
    """
    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    try:
        shown_count = (
            db.query(SuggestionFeedback)
            .filter(SuggestionFeedback.action.in_(["shown", "solved", "not_helpful", "still_need_help"]))
            .count()
        )

        solved_count = (
            db.query(SuggestionFeedback)
            .filter(SuggestionFeedback.action == "solved")
            .count()
        )

        deflection_rate = round(solved_count / max(shown_count, 1), 4) if shown_count > 0 else 0.0

        # Top 5 most helpful resolved tickets
        top_rows = (
            db.query(
                SuggestionFeedback.suggested_ticket_id,
                func.count(SuggestionFeedback.id).label("solved_total"),
            )
            .filter(SuggestionFeedback.action == "solved")
            .group_by(SuggestionFeedback.suggested_ticket_id)
            .order_by(desc("solved_total"))
            .limit(5)
            .all()
        )

        top_helpful_tickets = []
        for ticket_id, count_val in top_rows:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                top_helpful_tickets.append({
                    "ticket_id": ticket.id,
                    "title": ticket.title,
                    "category": ticket.category,
                    "solved_count": count_val,
                    "resolution_summary": sanitize_resolution_summary(
                        ticket.resolution_summary or ticket.resolution_notes or ""
                    ),
                })

        return {
            "suggestions_shown": shown_count,
            "solved_count": solved_count,
            "deflection_rate": deflection_rate,
            "top_helpful_tickets": top_helpful_tickets,
        }
    finally:
        if close_db_on_exit:
            db.close()
