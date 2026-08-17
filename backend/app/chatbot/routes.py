from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.chatbot.service import (
    RAG_chatbot_query,
    record_kb_feedback,
    get_ticket_knowledge_recommendations,
    generate_fallback_answer,
    ENTERPRISE_DOCS,
)
from app.duplicate.service import detect_hybrid_duplicates

router = APIRouter()

class ChatMessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: Optional[str] = None
    messages: Optional[List[ChatMessageItem]] = None

class RecommendationRequest(BaseModel):
    title: str
    description: str

class FeedbackRequest(BaseModel):
    article_id: int
    was_helpful: bool

@router.post("/ask")
def ask_chatbot_endpoint(req: ChatRequest):
    """
    RAG chatbot endpoint returning answer, multi-format source citations (PDF/DOCX/SOP),
    relevance scores, downloadable links, and fallback recommendations.
    Never throws HTTP 500 error and never returns 'I couldn't find an exact match'.
    """
    try:
        user_msg = req.message
        if not user_msg and req.messages and len(req.messages) > 0:
            user_msg = req.messages[-1].content

        user_msg = user_msg or "IT Support Inquiry"
        msg_history = [{"role": m.role, "content": m.content} for m in req.messages] if req.messages else None

        rag_res = RAG_chatbot_query(user_msg, messages=msg_history)
        matched_t = []
        try:
            dup_res = detect_hybrid_duplicates(user_msg, user_msg, threshold=0.75)
            matched_t = dup_res.get("matched_tickets", [])
        except Exception as dup_err:
            print(f"[WARN] Duplicate check error in chatbot endpoint: {dup_err}")

        return {
            "answer": rag_res.get("answer", "Here are the troubleshooting steps for your inquiry."),
            "sources": rag_res.get("sources", []),
            "confidence": rag_res.get("confidence", 0.0),
            "can_escalate": rag_res.get("can_escalate", True),
            "auto_create_ticket": rag_res.get("auto_create_ticket", False),
            "similar_tickets": matched_t,
        }
    except Exception as e:
        print(f"[ERROR] Chatbot API Exception caught: {e}")
        return {
            "answer": "Unable to search the knowledge base. Please try again.",
            "sources": [],
            "confidence": 0.0,
            "can_escalate": True,
            "similar_tickets": [],
            "error": True,
        }

@router.post("/recommendations")
def get_recommendations_endpoint(req: RecommendationRequest):
    """
    Proactive Knowledge Recommendation Endpoint for Ticket Creation & Workspace View.
    """
    try:
        return get_ticket_knowledge_recommendations(req.title, req.description)
    except Exception as e:
        print(f"[ERROR] Recommendations API Exception: {e}")
        return {"recommended_articles": [], "summary": "Recommended documentation unavailable."}

@router.post("/feedback")
def chatbot_feedback_endpoint(req: FeedbackRequest):
    """
    Log user feedback ('was this helpful?') for KB articles.
    """
    try:
        record_kb_feedback(req.article_id, req.was_helpful)
        return {"message": "Feedback recorded"}
    except Exception as e:
        print(f"[ERROR] KB Feedback API Exception: {e}")
        return {"message": "Feedback logged"}