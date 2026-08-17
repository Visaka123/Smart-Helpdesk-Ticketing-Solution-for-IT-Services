# Smart Help Desk — AI-Powered Enterprise IT Support System

Smart Help Desk is a full-stack, enterprise-grade IT Service Management (ITSM) system powered by Machine Learning and Retrieval-Augmented Generation (RAG). It provides automated ticket classification and team routing, multi-stage hybrid semantic duplicate detection, dynamic SLA tracking with automated email escalations, a grounded AI virtual assistant, and role-based interactive workspaces for employees, support agents, and managers.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [Role-Based Workspaces & Dashboards](#role-based-workspaces--dashboards)
- [AI & ML Technical Details](#ai--ml-technical-details)
- [API Reference](#api-reference)
- [Testing Guide](#testing-guide)
- [Demo Credentials](#demo-credentials)
- [Model Training & Evaluation](#model-training--evaluation)
- [Future Enhancements](#future-enhancements)

---

## Overview

Modern enterprise IT departments process thousands of support tickets, facing challenges such as misrouted requests, duplicate incident reports, SLA breaches, and repetitive end-user inquiries.

**Smart Help Desk** addresses these challenges by integrating:

1. **Automated ML Classification** — Uses text embeddings (`all-MiniLM-L6-v2`) and a LightGBM classifier to route incoming tickets to specialized support teams with confidence scoring.
2. **Hybrid Duplicate Prevention** — Combines semantic cosine similarity, lexical keyword matching, and LLM paraphrase evaluation to detect duplicate incidents org-wide before creation.
3. **Cross-Employee Privacy & Access Control** — Ensures org-wide incident tracking without exposing sensitive details or creating "Access Denied" navigation dead ends.
4. **Dynamic SLA Engine & Auto-Escalation** — Calculates resolution deadlines based on ticket priority and automatically fires HTML escalation emails to managers upon SLA risk or breach.
5. **RAG Virtual Assistant** — An interactive AI chatbot grounded in enterprise Knowledge Base PDFs and SOP documents, featuring citation verification and document downloads.

---

## Key Features

### 1. AI-Powered Ticket Classification & Routing
- Automatically classifies ticket titles and descriptions to assign appropriate support teams.
- Employs `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional embeddings) and a LightGBM classifier.
- Displays routing confidence percentages and top alternative team suggestions.
- Automatically flags low-confidence tickets (< 55% confidence threshold) for manual triage queue review.

### 2. Multi-Stage Hybrid Duplicate Detection
- Runs real-time similarity checks against active and resolved tickets during ticket creation.
- **Composite Scoring** — Combines Semantic Cosine Similarity (85% weight) and Lexical Jaccard Keyword Similarity (15% weight).
- **Secondary LLM Verification** — Evaluates borderline paraphrase matches (`0.28 ≤ semantic_score < 0.48`) to catch reworded, non-technical duplicates.
- **Resolved Ticket Match** — Instantly surfaces verified solution summaries and resolution steps directly in the interstitial dialog.
- **Open Ticket Match (Own Ticket)** — Offers a *"View my existing ticket"* action that opens the employee's ticket detail modal (`/tickets?open={id}`).
- **Open Ticket Match (Cross-Employee Ticket)** — Displays a privacy-safe incident summary with an informational alert and a *"Got it, already tracked"* dismiss button, preventing unauthorized access dead ends.

### 3. Dynamic SLA Engine & Automated Email Escalations
- Calculates SLA resolution targets dynamically based on priority levels (`Critical`, `High`, `Medium`, `Low`).
- Background job scheduler (`APScheduler`) audits all active ticket SLA deadlines every 5 minutes.
- Triggers automated Gmail SMTP emails with HTML formatting to escalation managers:
  - **AT_RISK Notification** — sent when SLA time elapsed reaches 80%.
  - **BREACHED Notification** — sent when the SLA deadline passes.

### 4. RAG-Powered Knowledge Assistant (Chatbot)
- Grounded conversational AI interface built with `SentenceTransformer` embeddings and the Groq LLM API (Llama 3).
- Indexes enterprise SOP documentation and PDFs.
- Provides downloadable SOP guides, source citations, relevance scores, and similar-ticket recommendations.
- Implements security guardrails to flag high-risk credential queries and sanitize web content.

### 5. Multi-Role Workspaces & Interactive Dashboards
- **Employee Portal** — Raise tickets with real-time pre-check, view personal ticket status, access interactive ticket detail modals, post replies, rate resolution satisfaction (1–5 stars), and reopen resolved tickets.
- **Support Agent Workspace** — Dedicated ticket queue, inline team re-assignment, priority/status updates, engineer assignment, public/internal notes, resolution with root-cause logging, and requester splitting.
- **Manager Command Center** — Real-time SLA compliance percentages, team volume breakdown, breach count tracking, and manager escalation logs.
- **Analytics View** — Visual charts for category distribution, priority breakdown, SLA compliance, and team ticket volume.

---

## System Architecture

```
                               ┌────────────────────────────────────────┐
                               │           React 18 + MUI v5            │
                               │           Frontend Portal              │
                               └───────────────────┬────────────────────┘
                                                    │ HTTP / REST
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FastAPI Backend App                                         │
│                                                                                                     │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  ┌────────────────────────────────┐   │
│  │   Auth Router (/auth)   │  │   Ticket Router (/ticket)│  │   Chatbot Router (/chatbot)    │   │
│  │   - JWT Auth & Hash     │  │   - CRUD & Pre-Check     │  │   - RAG Grounded Inquiry       │   │
│  └─────────────────────────┘  └──────────────────────────┘  └────────────────────────────────┘   │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  ┌────────────────────────────────┐   │
│  │   Agent Router (/agent) │  │   SLA Scheduler Service  │  │   Hybrid Duplicate Engine      │   │
│  │   - Queue & Resolution  │  │   - 5-Min APScheduler    │  │   - Cosine + Jaccard + LLM     │   │
│  └─────────────────────────┘  └──────────────────────────┘  └────────────────────────────────┘   │
└──────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              ▼                             ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│     SQLAlchemy ORM      │   │  SentenceTransformers   │   │        Groq LLM         │
│   (SQLite / MySQL DB)   │   │    (all-MiniLM-L6-v2)   │   │   (Llama 3 API Client)  │
└─────────────────────────┘   └─────────────────────────┘   └─────────────────────────┘
```

---

## Technology Stack

### Backend

| Layer | Technology |
|---|---|
| **Framework** | FastAPI (Python 3.10+) |
| **Server** | Uvicorn |
| **Database & ORM** | SQLAlchemy, SQLite (default), PyMySQL / PostgreSQL support |
| **Machine Learning** | LightGBM, scikit-learn, Joblib |
| **NLP & Embeddings** | `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dimensional) |
| **Vector Search & RAG** | FAISS, Groq LLM API (Llama 3) |
| **Background Scheduler** | APScheduler |
| **Email Escalations** | Python `smtplib` (Gmail SMTP) |
| **Authentication** | JWT (`python-jose`), Passlib (`bcrypt`), RBAC headers |

### Frontend

| Layer | Technology |
|---|---|
| **Framework** | React 18, TypeScript |
| **Build Tool** | Vite 5 |
| **UI Library** | Material-UI (MUI v5), Emotion |
| **State Management** | Redux Toolkit |
| **Routing** | React Router DOM v6 |
| **HTTP Client** | Axios |
| **Data Visualization** | Chart.js, `react-chartjs-2` |

> **Note:** FAISS is listed as part of the vector search stack. Confirm during review whether it is actively used for indexed search or whether current similarity checks are computed directly (pairwise) without a FAISS index — update this table if the latter.

---

## Project Structure

```
smart-helpdesk/
├── backend/
│   ├── ai/
│   │   ├── classifier/             # Model dataset builder, router training & evaluator report
│   │   ├── duplicate/              # FAISS vector indexing & semantic search
│   │   ├── priority/               # Priority model trainer
│   │   └── rag/                    # Knowledge Base indexing, Groq client & RAG pipeline
│   ├── app/
│   │   ├── agent/                  # Agent workspace routes (queue, detail, resolve, split)
│   │   ├── analytics/              # Analytics aggregation helpers
│   │   ├── auth/                   # JWT auth, hashing & RBAC header middleware
│   │   ├── chatbot/                # RAG chatbot routes & fallback guardrails
│   │   ├── core/                   # Shared SentenceTransformer singleton loader
│   │   ├── database/               # SQLAlchemy setup & database seeder
│   │   ├── duplicate/              # Hybrid duplicate detection engine
│   │   ├── models/                 # SQLAlchemy ORM models (Ticket, User, Team, etc.)
│   │   ├── priority/                # Priority inference service
│   │   ├── routing/                # ML team classification predictor service
│   │   ├── sla/                    # SLA calculation & email escalation service
│   │   ├── tickets/                # Ticket CRUD & pre-check endpoints
│   │   └── main.py                 # FastAPI application entry point & APScheduler startup
│   ├── model_assets/
│   │   ├── models/                 # Trained LightGBM router, priority model & FAISS index
│   │   └── processed/              # Processed training dataset
│   ├── requirements.txt            # Python dependencies
│   └── .env                        # Environment configuration
└── frontend/
    ├── src/
    │   ├── api/                    # Axios API client setup
    │   ├── components/
    │   │   ├── layout/             # AppLayout, Header, Sidebar
    │   │   ├── ui/                 # SemanticBadges, ITSMTimeline, KnowledgePanel
    │   │   ├── ChatbotDrawer.tsx   # Slide-out virtual assistant drawer
    │   │   └── EmployeeTicketDetailsModal.tsx  # Employee ticket detail modal
    │   ├── pages/
    │   │   ├── DashboardPage.tsx   # Overview dashboard & KPI cards
    │   │   ├── CreateTicketPage.tsx# Ticket submission form & duplicate interstitials
    │   │   ├── TicketsPage.tsx     # Ticket management list page
    │   │   ├── AgentPortalPage.tsx # Support Agent workspace
    │   │   ├── AnalyticsPage.tsx   # Analytics & chart visualizations
    │   │   └── ChatbotPage.tsx     # Dedicated RAG Virtual Assistant page
    │   ├── store/                  # Redux store slices
    │   ├── App.tsx                 # Route configuration
    │   └── main.tsx                # Frontend entry point
    ├── package.json
    ├── vite.config.ts
    └── index.html
```

---

## Setup & Installation

### Prerequisites
- **Python**: version 3.10 or higher
- **Node.js**: version 18 or higher (with `npm`)
- **Git**

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/smart-helpdesk.git
cd smart-helpdesk
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux / macOS
# source venv/bin/activate

pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
```

### 4. Initialize Database
Initialize SQLite database tables and seed default users, teams, and sample data:
```bash
cd ../backend
python -c "from app.database.seed_data import init_db; init_db()"
```

---

## Environment Variables

Create a `.env` file inside `backend/`:

```env
# Database (SQLite default)
DATABASE_URL=sqlite:///./smart_helpdesk.db

# Authentication
JWT_SECRET=your_jwt_secret_key_here

# Groq LLM API (for RAG Chatbot)
GROQ_API_KEY=your_groq_api_key_here

# SLA Auto-Escalation Email (Gmail SMTP)
SMTP_SENDER_EMAIL=your_email@gmail.com
SMTP_APP_PASSWORD=your_gmail_app_password
ESCALATION_MANAGER_EMAIL=manager_email@gmail.com
```

> Replace all placeholder values with your actual service credentials. Never commit a populated `.env` file to version control.

---

## Running the Application

### Start Backend API
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
- API Endpoint: `http://localhost:8000`
- Interactive Swagger Documentation: `http://localhost:8000/docs`

### Start Frontend Application
```bash
cd frontend
npm run dev
```
- Frontend Web App: `http://localhost:5173`

---

## Role-Based Workspaces & Dashboards

Use the **Switch Role** control in the header to switch between roles:

| Role | Access Level | Capabilities |
|---|---|---|
| **Employee** | Self-Service | Raise tickets, view personal tickets, track status, view resolution details, rate satisfaction (1–5 stars), reopen tickets, interact with RAG chatbot |
| **Support Agent** | Agent Workspace | View ticket queue, filter by team/status/SLA, reassign teams, adjust priority/status, post public replies & internal notes, resolve tickets with root-cause analysis, split requesters |
| **Manager** | Command Center | View overall SLA compliance metrics, team performance breakdowns, SLA breach counts, and manager escalation audit logs |
| **Admin** | Administration | System administration and access control oversight |

---

## AI & ML Technical Details

### 1. Ticket Classification & Routing Model
- **Input**: ticket title and description text.
- **Embedding**: encoded into a 384-dimensional vector using `all-MiniLM-L6-v2`.
- **Classifier**: LightGBM classifier predicting the target support team.
- **Confidence Triage**: outputs a probability confidence score; classifications below 55% are routed to `Unassigned/Triage`.

### 2. Hybrid Duplicate Detection Engine
- **Stage 1 (Hybrid Score):**

  ```
  Composite Score = (0.85 × Semantic Cosine) + (0.15 × Lexical Jaccard)
  ```

  High-confidence match triggered if `Semantic ≥ 0.48`, `Composite ≥ 0.45`, or `Lexical ≥ 0.50`.

- **Stage 2 (LLM Verification):** for borderline scores (`0.28 ≤ Semantic < 0.48`), the Groq LLM evaluates paraphrase similarity to confirm or reject duplicate status.
- **Privacy Safety:** checks ticket ownership (`is_own_ticket`). Owned tickets allow direct modal viewing (`/tickets?open={id}`), while cross-employee matches present a summary with a dismissal option to preserve privacy.

### 3. SLA Escalation Logic
- **Priority SLAs:**
  - `Critical` — 2h response / 6h resolution
  - `High` — 8h response / 24h resolution
  - `Medium` — 16h response / 48h resolution
  - `Low` — 24h response / 72h resolution
- **Audit Execution:** `APScheduler` scans active tickets every 5 minutes. Sends formatted HTML email alerts when the SLA threshold passes 80% (`AT_RISK`) or 100% (`BREACHED`).

---

## API Reference

### Auth (`/auth`)
- `POST /auth/register` — register a new employee account.
- `POST /auth/login` — authenticate a user and receive a JWT token.

### Ticket (`/ticket`)
- `POST /ticket/create` — submit a new ticket with optional duplicate pre-check override.
- `POST /ticket/check-duplicate` — perform a real-time pre-submission duplicate check.
- `POST /ticket/route-ticket` — preview ML classification and team routing.
- `GET /ticket/all` — list tickets filtered by caller role.
- `GET /ticket/stats` — retrieve general ticket dashboard metrics.
- `GET /ticket/employee/{id}` — fetch detailed ticket information for the employee owner.
- `POST /ticket/employee/comment/{id}` — post a public reply to a ticket thread.
- `POST /ticket/employee/rate/{id}` — submit a satisfaction rating (1–5 stars).
- `POST /ticket/employee/reopen/{id}` — reopen a resolved ticket.

### Chatbot (`/chatbot`)
- `POST /chatbot/ask` — query the RAG Knowledge Base virtual assistant.
- `POST /chatbot/recommendations` — fetch proactive documentation recommendations.
- `POST /chatbot/feedback` — submit feedback on KB article usefulness.

### Agent Workspace (`/agent`)
- `GET /agent/queue` — fetch agent queue tickets with SLA indicators.
- `GET /agent/detail/{id}` — fetch detailed ticket data for support agents.
- `POST /agent/assign-team/{id}` — reassign a ticket to another support team.
- `POST /agent/change-priority/{id}` — update ticket priority level.
- `POST /agent/change-status/{id}` — update ticket status.
- `POST /agent/assign-engineer/{id}` — assign a support specialist to a ticket.
- `POST /agent/resolve/{id}` — resolve a ticket with resolution summary and root cause.
- `POST /agent/split-requester/{id}` — un-link a co-requester into a new standalone ticket.
- `POST /agent/comment/{id}` — post a public reply or internal agent note.
- `GET /agent/agent-stats` — fetch operational agent statistics.
- `GET /agent/manager-dashboard` — fetch manager escalation metrics and team performance.

---

## Testing Guide

The repository includes test scripts in `backend/` to validate API routes, authentication, duplicate detection, and SLA escalation logic:

```bash
cd backend

# Test employee portal endpoints and duplicate detection
python test_employee_portal_and_dedup.py

# Test hard-block duplicate prevention logic
python test_hard_block_sequence.py

# Test full end-to-end API sequence
python test_e2e_sequence.py

# Test dashboard stats and SLA states
python test_dashboard_sla_final_state.py

# Test SLA auto-escalation trigger manually
python run_sla_test.py
```

> Verify each script exists and runs cleanly before publishing this section — a testing guide referencing missing or broken scripts undermines trust in the rest of the documentation.

---

## Demo Credentials

The seeded database (`init_db()`) contains pre-configured accounts for testing:

| Role | Email | Password |
|---|---|---|
| **Admin** | `admin@helpdesk.com` | `admin123` |
| **Manager** | `manager@helpdesk.com` | `manager123` |
| **Support Agent** | `agent@helpdesk.com` | `agent123` |
| **Network Agent** | `mike.agent@helpdesk.com` | `agent123` |
| **Employee (Finance)** | `alice@company.com` | `user123` |
| **Employee (Sales)** | `bob@company.com` | `user123` |

> These are demo/seed credentials for local development only — do not reuse these passwords in any deployed or production environment.

---

## Model Training & Evaluation

To re-train the router model or generate evaluation reports:

```bash
cd backend

# Rebuild processed dataset
python ai/classifier/build_dataset.py

# Train LightGBM classification model
python ai/classifier/train_router.py

# Generate evaluation report (HTML report saved to model_assets/models/model_report.html)
python ai/classifier/model_report.py
```

---

## Future Enhancements

- **SSO Integration** — add OAuth2 / SAML single sign-on support (Okta, Azure AD, Google Workspace).
- **Multi-Tenant Support** — extend the database schema to isolate ticket queues across separate enterprise organizations.
- **WebSocket Live Updates** — real-time notifications for live comment threads and agent assignment changes.
- **Mobile Application** — a native mobile app built with React Native for support agents on call.
- **Containerization** — add Dockerfiles and `docker-compose.yml` service configurations for containerized deployment.