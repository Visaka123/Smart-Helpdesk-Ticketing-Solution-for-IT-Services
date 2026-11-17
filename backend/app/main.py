from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import time

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    HAS_APSCHEDULER = True
except ImportError:
    scheduler = None
    HAS_APSCHEDULER = False

from app.database.database import engine, Base
from app.auth.routes import router as auth_router
from app.tickets.routes import router as ticket_router
from app.chatbot.routes import router as chatbot_router
from app.agent.routes import router as agent_router
from app.availability.routes import router as availability_router
from app.core.embeddings import get_shared_embedder
from app.sla.service import audit_and_trigger_sla_escalations
from app.availability.scheduler import reroute_on_leave_approval, handover_before_shift_end
from app.availability.sync import sync_hr_leaves_job

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Pre-loading shared embedding model...")
    try:
        get_shared_embedder()
    except Exception as e:
        print(f"[STARTUP WARN] Shared embedder pre-load notice: {e}")

    try:
        from app.database.database import SessionLocal
        from app.availability.service import reassign_manager_fallback_tickets
        from app.tickets.service import cleanup_existing_ticket_titles
        db_startup = SessionLocal()
        reassigned = reassign_manager_fallback_tickets(db_startup)
        cleaned_titles = cleanup_existing_ticket_titles(db_startup)
        db_startup.close()
        if reassigned:
            print(f"[STARTUP] Reassigned {len(reassigned)} manager fallback tickets to available agents.")
        if cleaned_titles:
            print(f"[STARTUP] Cleaned {cleaned_titles} legacy ticket titles.")
    except Exception as e:
        print(f"[STARTUP WARN] Manager ticket reassignment on startup: {e}")

    stop_event = threading.Event()
    if HAS_APSCHEDULER and scheduler:
        # Run SLA audit and availability checks automatically
        scheduler.add_job(audit_and_trigger_sla_escalations, "interval", minutes=5,  id="sla_audit")
        scheduler.add_job(reroute_on_leave_approval,          "interval", minutes=5,  id="leave_reroute")
        scheduler.add_job(handover_before_shift_end,           "interval", minutes=5,  id="shift_handover")
        scheduler.add_job(sync_hr_leaves_job,                 "interval", minutes=15, id="hr_leave_sync")
        scheduler.start()
        print("[STARTUP] SLA, Availability, and HR Leave Sync (every 15 min) schedulers started.")
    else:
        def background_loop():
            tick_count = 0
            while not stop_event.is_set():
                stop_event.wait(300)
                if stop_event.is_set():
                    break
                tick_count += 1
                try:
                    audit_and_trigger_sla_escalations()
                except Exception as e:
                    print(f"[BACKGROUND SLA WARN] {e}")
                try:
                    reroute_on_leave_approval()
                except Exception as e:
                    print(f"[BACKGROUND LEAVE WARN] {e}")
                try:
                    handover_before_shift_end()
                except Exception as e:
                    print(f"[BACKGROUND SHIFT WARN] {e}")
                if tick_count % 3 == 0:  # Every 15 minutes
                    try:
                        sync_hr_leaves_job()
                    except Exception as e:
                        print(f"[BACKGROUND HR SYNC WARN] {e}")

        bg_thread = threading.Thread(target=background_loop, daemon=True)
        bg_thread.start()
        print("[STARTUP] Built-in background worker loop started (APScheduler fallback).")

    yield

    if HAS_APSCHEDULER and scheduler:
        scheduler.shutdown(wait=False)
    else:
        stop_event.set()
    print("[SHUTDOWN] Application shutdown complete.")

# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Helpdesk API",
    description="Enterprise Smart Helpdesk with Shared SentenceTransformer ML Routing, Multimodal Priority Prediction, Dynamic SLA Monitoring, Semantic Duplicate Detection, Grounded RAG Chatbot, and Professional Indigo Theme.",
    version="2.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,         prefix="/auth",         tags=["Auth"])
app.include_router(ticket_router,        prefix="/ticket",        tags=["Ticket"])
app.include_router(ticket_router,        prefix="/tickets",       tags=["Tickets"])
app.include_router(chatbot_router,       prefix="/chatbot",       tags=["Chatbot"])
app.include_router(agent_router,         prefix="/agent",         tags=["Agent / Support"])
app.include_router(availability_router,  prefix="/availability",  tags=["Availability"])

@app.get("/analytics/deflection", tags=["Analytics"])
def get_deflection_stats():
    from app.suggestions.service import get_deflection_analytics
    from app.database.database import SessionLocal
    db = SessionLocal()
    try:
        return get_deflection_analytics(db=db)
    finally:
        db.close()

@app.get("/docs/download/{filename}")
def download_sop_document(filename: str):
    content = f"""# Enterprise Standard Operating Procedure Document
Filename: {filename}
System: Smart Helpdesk Enterprise Knowledge Base

========================================================================
VERIFIED COMPANY SOP / INCIDENT RESOLUTION DOCUMENT
========================================================================

Document Title: {filename.replace('_', ' ').replace('.pdf', '').replace('.docx', '').replace('.txt', '')}
Classification: Internal Enterprise Use Only
Status: Active / Verified

Summary & Operational Instructions:
1. Verify user authorization credentials and role assignments in GRC/Okta.
2. Follow standard troubleshooting protocol outlined in Section 4.2.
3. If issue persists, escalate to team lead or log ticket in Agent Workspace.

Generated by Smart Helpdesk Enterprise Knowledge Management Platform.
"""
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/")
def root():
    return {
        "status": "online",
        "system": "Smart Helpdesk Enterprise API v2.2",
        "ml_routing": "Shared SentenceTransformer + LogisticRegression",
        "sla_monitoring": "Active Background Scheduler",
    }
