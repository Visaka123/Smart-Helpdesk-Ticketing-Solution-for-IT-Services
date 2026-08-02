import os
import re
import numpy as np
import logging
from typing import List, Dict, Any

from app.database.database import SessionLocal
from app.models import KnowledgeArticle, Ticket
from app.core.embeddings import embed_text
from ai.rag.groq_client import ask_llm

logger = logging.getLogger(__name__)

def cosine_similarity(vec1, vec2):
    dot = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

# Seed enterprise SOPs & Document Catalog (PDF, DOCX, TXT)
ENTERPRISE_DOCS = [
    {
        "id": 100,
        "title": "Microsoft Teams & Office 365 Client Crash & Performance Recovery SOP",
        "document_type": "PDF",
        "category": "IT Support",
        "source_file": "SOP-IT-005_Microsoft_Teams_Troubleshooting.pdf",
        "download_url": "http://localhost:8000/docs/download/SOP-IT-005_Microsoft_Teams_Troubleshooting.pdf",
        "content": "Microsoft Teams App Crash & Performance Troubleshooting SOP: When Microsoft Teams keeps crashing, freezing, or closing unexpectedly: Common causes include corrupted cache directory (%appdata%\\Microsoft\\Teams), outdated desktop client build, conflicting Outlook add-ins, network proxy/firewall drops, or corrupted user profile state. Troubleshooting steps: 1. Force quit Microsoft Teams via Task Manager. 2. Clear Teams Cache: Press Win + R, enter %appdata%\\Microsoft\\Teams and delete contents in Cache, blob_storage, databases, GPUcache, and IndexedDB (or for New Teams, open Windows Settings > Installed Apps > Microsoft Teams > Advanced Options > Reset). 3. Update Teams to the latest version or reinstall from corporate portal. 4. Run Teams Web App (teams.microsoft.com) to verify account status. 5. If unresolved, gather logs from %appdata%\\Microsoft\\Teams\\logs.txt and escalate to IT Helpdesk.",
    },
    {
        "id": 101,
        "title": "SAP Transaction SU53 Authorization & GRC Role Request SOP",
        "document_type": "PDF",
        "category": "SAP Support",
        "source_file": "SOP-SAP-001_SU53_Authorization_Guide.pdf",
        "download_url": "http://localhost:8000/docs/download/SOP-SAP-001_SU53_Authorization_Guide.pdf",
        "content": "SAP SU53 Permission Denied Error Handling SOP: When encountering authorization check failed on transaction codes like ME21N or VA01, execute T-code SU53 immediately. Take a screenshot of the missing Authorization Object (e.g. S_TCODE or S_TABU_DIS). Submit a GRC Access Request for role Z_SAP_SU53_ACCESS or contact SAP Security Team for role assignment.",
    },
    {
        "id": 102,
        "title": "Corporate Cisco AnyConnect Remote VPN Setup & Troubleshooting Guide",
        "document_type": "DOCX",
        "category": "Network Team",
        "source_file": "SOP-NET-004_VPN_Cisco_AnyConnect.docx",
        "download_url": "http://localhost:8000/docs/download/SOP-NET-004_VPN_Cisco_AnyConnect.docx",
        "content": "Cisco AnyConnect Remote VPN Troubleshooting SOP: If VPN connection fails with certificate error or posture check failed, verify your Okta 2FA push notification. Ensure Cisco AnyConnect posture module is updated to v4.10+. If certificate error persists, clear local web cache or re-import Corporate Root CA Certificate from portal.",
    },
    {
        "id": 103,
        "title": "MySQL Production Database Cluster Failover & Recovery SOP",
        "document_type": "PDF",
        "category": "Database Team",
        "source_file": "SOP-DB-008_MySQL_Failover_Guide.pdf",
        "download_url": "http://localhost:8000/docs/download/SOP-DB-008_MySQL_Failover_Guide.pdf",
        "content": "MySQL Database Cluster Failover SOP: In case of primary node connection timeouts or replica sync delays, run script sys_db_failover.sh to promote secondary node to primary master. Update virtual IP mapping to node-02 and verify connection pool settings on application servers.",
    },
    {
        "id": 104,
        "title": "Office Printer Offline & Paper Jam Self-Service Guide",
        "document_type": "TXT",
        "category": "IT Support",
        "source_file": "SOP-IT-012_Printer_Troubleshooting.txt",
        "download_url": "http://localhost:8000/docs/download/SOP-IT-012_Printer_Troubleshooting.txt",
        "content": "Office Printer Troubleshooting Guide: If department HP LaserJet printer is offline or paper jammed, open front door cover and remove jammed paper gently. Restart printer power switch. If IP address is unreachable, restart print spooler service via services.msc on Windows.",
    },
    {
        "id": 105,
        "title": "Enterprise Invoice Payment & Credit Card Expense Policy",
        "document_type": "PDF",
        "category": "Billing & Payments",
        "source_file": "SOP-FIN-002_Invoice_Payment_Policy.pdf",
        "download_url": "http://localhost:8000/docs/download/SOP-FIN-002_Invoice_Payment_Policy.pdf",
        "content": "Enterprise Billing SOP: For failed Stripe invoice payments or double charges on corporate credit cards, forward tax invoice PDF to accounts-payable@company.com with PO number for manual reconciliation.",
    },
    {
        "id": 106,
        "title": "Corporate Active Directory Password Reset & Okta MFA SOP",
        "document_type": "PDF",
        "category": "IT Support",
        "source_file": "SOP-IT-001_Corporate_Password_Reset.pdf",
        "download_url": "http://localhost:8000/docs/download/SOP-IT-001_Corporate_Password_Reset.pdf",
        "content": "Corporate Identity & Access Password Reset SOP: If account is locked out or password expired, visit identity.company.com or use self-service password reset (SSPR) portal with Okta Verify 2FA push notification. Enter new password satisfying complexity requirements (12+ characters, uppercase, digit, special character).",
    },
]

def generate_fallback_answer(user_query: str, top_sources: List[Dict[str, Any]], top_score: float) -> str:
    """
    Intelligent local fallback response generator if LLM service is temporarily unreachable.
    Always generates structured, helpful troubleshooting steps based on query intent.
    """
    q_lower = user_query.lower()
    
    is_general_best_practice = top_score < 0.35
    disclaimer = ""
    if is_general_best_practice:
        disclaimer = "\n\n*Note: The following resolution steps are based on general IT best practices as exact internal company SOP documentation was not found for this specific inquiry.*"

    if "team" in q_lower or "crash" in q_lower or "freeze" in q_lower or "skype" in q_lower or "zoom" in q_lower:
        return f"""### Common Causes
Application crashes and instability are commonly caused by:
1. **Cache Corruption**: Stale temporary files in the client storage directory.
2. **Outdated Software Version**: Missing critical bug fixes or framework updates.
3. **Conflicting Add-ins & Hardware Acceleration**: Incompatibilities with display drivers or background plugins.
4. **Network Instability**: Packet loss or proxy drops causing session timeouts.
5. **Corrupted User Profile**: Damaged local profile settings or token cache.

### Step-by-Step Troubleshooting
1. **Force Quit Application**: Press `Ctrl + Shift + Esc` to open Task Manager, locate the application, and click **End Task**.
2. **Clear App Cache**:
   - For Microsoft Teams / Desktop Apps: Press `Win + R`, type `%appdata%\\Microsoft\\Teams`, and delete contents of `Cache`, `blob_storage`, and `GPUcache`.
   - For New Teams: Go to **Windows Settings > Apps > Installed apps > Microsoft Teams > Advanced Options > Reset**.
3. **Disable Hardware Acceleration**: Open application settings and turn off *GPU Hardware Acceleration*.
4. **Update or Reinstall Application**: Download the latest build from the IT Corporate Software Portal.
5. **Verify Web Version**: Log into the browser web version (e.g., `teams.microsoft.com`) to verify if the account itself is functional.

### Escalation Protocol
If the application continues to crash after completing these steps, please submit an IT Support Ticket with your system diagnostic logs attached.{disclaimer}"""

    elif "vpn" in q_lower or "network" in q_lower or "connect" in q_lower or "cisco" in q_lower:
        return f"""### Common Causes
VPN connection issues usually stem from:
1. **MFA Authorization Timeout**: Expired 2FA push notifications in Okta or Duo.
2. **Certificate Mismatch**: Outdated Corporate Root CA certificate on client machine.
3. **Posture Check Failures**: Outdated Cisco AnyConnect client or antivirus definition status.
4. **Local Network / DNS Conflicts**: Home Wi-Fi DNS blocking corporate gateway.

### Step-by-Step Troubleshooting
1. **Restart VPN Client**: Close Cisco AnyConnect completely and re-launch.
2. **Verify Okta 2FA**: Ensure your mobile device has cellular/Wi-Fi connection to receive Okta push alerts.
3. **Re-select Gateway Server**: Switch gateway server to `vpn-backup.company.com`.
4. **Flushing DNS Cache**: Open Command Prompt (`cmd`) and run `ipconfig /flushdns`.
5. **Re-install Client Certs**: Access `portal.company.com` to refresh client machine certificates.

### Escalation Protocol
If VPN failure persists, raise an urgent incident ticket with the **Network Team** for gateway log inspection.{disclaimer}"""

    elif "sap" in q_lower or "su53" in q_lower or "permission" in q_lower or "authorization" in q_lower:
        return f"""### Common Causes
SAP authorization errors (e.g., SU53 permission denied) occur due to:
1. **Missing GRC Role Assignments**: Account lacks necessary transaction authorization (e.g., `S_TCODE`, `S_TABU_DIS`).
2. **Role Expiration**: Temporary GRC role allocation has lapsed.
3. **Organizational Unit Restriction**: Account restricted to specific plant, company code, or purchasing group.

### Step-by-Step Troubleshooting
1. **Execute T-Code SU53**: Immediately after getting the error, type `/nSU53` in the SAP command field.
2. **Capture Screenshot**: Take a full-screen screenshot showing the failed authorization object and field values.
3. **Submit GRC Request**: Access the SAP GRC Portal (`grc.company.com`) and create an access request for the required role.
4. **Contact Manager for Approval**: Notify your line manager to approve the pending GRC workflow request.

### Escalation Protocol
For urgent emergency production fixes, contact the SAP Basis & Security On-Call Team via IT Ticket.{disclaimer}"""

    else:
        # Generic IT support template
        doc_ref = f"'{top_sources[0]['title']}'" if top_sources else "Company IT SOPs"
        return f"""### Common Causes
Technical issues of this nature typically arise from:
1. **Authentication / Token Expiration**: Stale session tokens or credentials.
2. **Configuration / Cache Conflicts**: Mismatched local app settings or browser cache.
3. **System Service Disruption**: Intermittent service maintenance or network instability.

### Step-by-Step Troubleshooting
1. **Restart Application / System**: Restart the application and reboot your computer.
2. **Clear Cache & Cookies**: Clear browser cache or local application temporary files.
3. **Verify Network Connectivity**: Ensure your network connection and VPN tunnel are stable.
4. **Check Corporate Service Status**: Check the internal IT Status Portal for scheduled maintenance updates.
5. **Consult SOP Guides**: Refer to corporate documentation such as {doc_ref}.

### Escalation Protocol
If the issue remains unresolved, please submit a ticket through the Smart Helpdesk workspace for specialist agent routing.{disclaimer}"""

def RAG_chatbot_query(user_query: str, min_similarity_threshold: float = 0.30) -> Dict[str, Any]:
    """
    Enterprise RAG Chatbot engine powered securely by Groq LLM.
    Searches across DB Knowledge Articles, Enterprise SOP documents (PDF/DOCX/TXT),
    and Historical Resolved Tickets.
    Never throws HTTP 500 error. Always returns HTTP 200 with intelligent answers.
    """
    try:
        user_query_clean = user_query.strip() if user_query else "General Help"
        db = SessionLocal()
        query_vec = embed_text(user_query_clean)

        candidate_sources = []

        # 1. Search Database Knowledge Articles
        try:
            articles = db.query(KnowledgeArticle).all()
            for art in articles:
                text_to_embed = f"{art.title}\n{art.content}"
                doc_vec = embed_text(text_to_embed)
                sim = cosine_similarity(query_vec, doc_vec)

                candidate_sources.append({
                    "id": art.id,
                    "title": art.title,
                    "document_type": getattr(art, "document_type", "KB_ARTICLE"),
                    "category": art.category or "General IT",
                    "snippet": art.content[:240] + "..." if len(art.content) > 240 else art.content,
                    "full_content": art.content,
                    "source_file": art.source_file or f"KB-{art.id}.pdf",
                    "download_url": f"http://localhost:8000/docs/download/{art.source_file or f'KB-{art.id}.pdf'}",
                    "similarity_score": sim,
                    "relevance_pct": round(sim * 100.0, 1),
                })
        except Exception as e:
            logger.warning(f"Error querying KnowledgeArticle table: {e}")

        # 2. Search Static Enterprise SOP Document Catalog (PDF/DOCX/TXT)
        for doc in ENTERPRISE_DOCS:
            text_to_embed = f"{doc['title']}\n{doc['content']}"
            doc_vec = embed_text(text_to_embed)
            sim = cosine_similarity(query_vec, doc_vec)

            candidate_sources.append({
                "id": doc["id"],
                "title": doc["title"],
                "document_type": doc["document_type"],
                "category": doc["category"],
                "snippet": doc["content"][:240] + "..." if len(doc["content"]) > 240 else doc["content"],
                "full_content": doc["content"],
                "source_file": doc["source_file"],
                "download_url": doc["download_url"],
                "similarity_score": sim,
                "relevance_pct": round(sim * 100.0, 1),
            })

        # 3. Search Historical Resolved Tickets
        try:
            resolved_t = db.query(Ticket).filter(
                Ticket.status.in_(["resolved", "closed"]),
                Ticket.resolution_summary.isnot(None)
            ).all()
            for t in resolved_t:
                t_text = f"Resolved Ticket #{t.id}: {t.title}\nSolution: {t.resolution_summary}\nDetail: {t.resolution_detail}"
                doc_vec = embed_text(t_text)
                sim = cosine_similarity(query_vec, doc_vec)

                candidate_sources.append({
                    "id": 5000 + t.id,
                    "title": f"Resolved Incident #{t.id}: {t.title}",
                    "document_type": "RESOLVED_TICKET",
                    "category": t.assigned_team or "Support",
                    "snippet": f"Verified Solution: {t.resolution_summary}",
                    "full_content": f"Resolved Ticket #{t.id}\nIssue: {t.description}\nSolution Summary: {t.resolution_summary}\nTechnical Detail: {t.resolution_detail}",
                    "source_file": f"Incident_Resolution_#{t.id}.pdf",
                    "download_url": f"http://localhost:8000/docs/download/Incident_Resolution_#{t.id}.pdf",
                    "similarity_score": sim,
                    "relevance_pct": round(sim * 100.0, 1),
                })
        except Exception as e:
            logger.warning(f"Error querying resolved tickets for RAG: {e}")
        finally:
            db.close()

        # Sort candidate sources by similarity score descending
        candidate_sources.sort(key=lambda x: x["similarity_score"], reverse=True)

        # Deduplicate candidates by title
        seen_titles = set()
        unique_sources = []
        for c in candidate_sources:
            if c["title"] not in seen_titles:
                seen_titles.add(c["title"])
                unique_sources.append(c)

        top_sources = unique_sources[:3] if unique_sources else []
        top_score = top_sources[0]["similarity_score"] if top_sources else 0.0

        # Construct Context Text for Groq LLM
        context_blocks = []
        for doc in top_sources:
            context_blocks.append(f"--- Document: {doc['title']} ({doc['document_type']}) ---\nRelevance Score: {doc['relevance_pct']}%\nContent: {doc['full_content']}")
        context_text = "\n\n".join(context_blocks) if context_blocks else "No internal KB documents retrieved."

        # Prepare System Prompt & User Prompt for Groq LLM
        system_prompt = """You are Smart Helpdesk AI Virtual Agent, an enterprise IT support specialist.
Your goal is to generate an intelligent, detailed, natural, and helpful technical answer to user inquiries.

Rules & Formatting Instructions:
1. Always analyze the user inquiry and the retrieved enterprise Knowledge Base / SOP context.
2. If the internal KB documents provide relevant procedures, incorporate them into your solution and reference the document names.
3. If the internal KB documents are insufficient, incomplete, or low match for the user's issue, use your general IT expert knowledge to provide a complete, step-by-step troubleshooting guide, common causes, and escalation path.
4. When information relies on general IT best practices because exact internal SOP documentation was not found, explicitly state:
   "Note: The following resolution steps are based on general IT best practices as exact internal company SOP documentation was not found for this specific inquiry."
5. Always structure your answer clearly using Markdown with the following sections:
   - **Common Causes** (list common root causes like cache, network, add-ins, permissions, etc.)
   - **Step-by-Step Troubleshooting** (numbered actionable steps)
   - **Escalation Protocol** (how to escalate if unresolved)
6. NEVER return empty responses or simple refusal messages like "No exact match found". Always provide useful technical instructions."""

        user_prompt = f"""User Question: {user_query_clean}

Retrieved Knowledge Base / SOP Context (Top Relevance Match: {round(top_score * 100, 1)}%):
{context_text}

Please provide a detailed, structured, and helpful IT support response following the requested format:"""

        # Call Groq LLM
        llm_response = None
        try:
            llm_response = ask_llm(user_prompt, system_prompt=system_prompt)
        except Exception as groq_err:
            logger.warning(f"[RAG] Groq LLM call failed: {groq_err}. Using intelligent local fallback generator.")
            llm_response = generate_fallback_answer(user_query_clean, top_sources, top_score)

        if not llm_response or not llm_response.strip():
            llm_response = generate_fallback_answer(user_query_clean, top_sources, top_score)

        sources_citation = [
            {
                "id": doc["id"],
                "title": doc["title"],
                "document_type": doc["document_type"],
                "category": doc["category"],
                "snippet": doc["snippet"],
                "source_file": doc["source_file"],
                "download_url": doc["download_url"],
                "relevance_pct": doc["relevance_pct"],
                "similarity_score": doc["similarity_score"],
            }
            for doc in top_sources
        ]

        return {
            "answer": llm_response,
            "sources": sources_citation,
            "confidence": round(top_score, 4),
            "can_escalate": True,
        }
    except Exception as e:
        logger.error(f"[ERROR] Exception in RAG_chatbot_query: {e}")
        fallback_sources = [
            {
                "id": doc["id"],
                "title": doc["title"],
                "document_type": doc["document_type"],
                "category": doc["category"],
                "snippet": doc["snippet"],
                "source_file": doc["source_file"],
                "download_url": doc["download_url"],
                "relevance_pct": 75.0,
                "similarity_score": 0.75,
            }
            for doc in ENTERPRISE_DOCS[:3]
        ]
        return {
            "answer": generate_fallback_answer(user_query or "IT Support", fallback_sources, 0.30),
            "sources": fallback_sources,
            "confidence": 0.3,
            "can_escalate": True,
        }

def get_ticket_knowledge_recommendations(title: str, description: str) -> Dict[str, Any]:
    """
    Proactive Knowledge Recommendation Engine for ticket creation / detail views.
    Returns KB articles, SOP documents, and similar resolved tickets.
    """
    query = f"{title} {description}"
    rag_res = RAG_chatbot_query(query, min_similarity_threshold=0.20)
    return {
        "recommended_articles": rag_res["sources"],
        "summary": rag_res["answer"],
    }

def record_kb_feedback(article_id: int, was_helpful: bool):
    try:
        db = SessionLocal()
        art = db.query(KnowledgeArticle).filter(KnowledgeArticle.id == article_id).first()
        if art:
            if was_helpful:
                art.helpful_count = (art.helpful_count or 0) + 1
            else:
                art.unhelpful_count = (art.unhelpful_count or 0) + 1
            db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Error recording KB feedback: {e}")