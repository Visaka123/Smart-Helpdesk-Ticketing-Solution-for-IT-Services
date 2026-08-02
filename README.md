# Smart Help Desk — AI-Powered Enterprise IT Support System

An enterprise-grade IT helpdesk system with AI-driven ticket routing, semantic duplicate detection, SLA monitoring with auto-escalation emails, RAG-powered chatbot, and role-based dashboards.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [ML Model Performance](#ml-model-performance)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [Role-Based Dashboards](#role-based-dashboards)
- [AI Features Deep Dive](#ai-features-deep-dive)
- [API Reference](#api-reference)
- [Testing Guide](#testing-guide)
- [Demo Credentials](#demo-credentials)

---

## Overview

Smart Help Desk is a full-stack AI-powered IT support portal built for enterprise environments. Employees raise support tickets which are automatically routed to the correct team using a trained ML classifier. The system prevents duplicate tickets using hybrid semantic + lexical similarity, monitors SLA deadlines and sends escalation emails to managers automatically, and provides an AI chatbot grounded in the company knowledge base.

---

## Key Features

### 1. AI-Powered Ticket Routing
- Automatically assigns every new ticket to the correct support team
- Uses `all-MiniLM-L6-v2` sentence embeddings + LightGBM classifier
- **81.77% weighted F1 score** on unseen test data across 6 teams
- Shows routing confidence % and top alternative teams
- Low-confidence tickets flagged for manual triage

### 2. Hybrid Semantic Duplicate Detection
- Prevents duplicate tickets before they are created
- Combines semantic embedding similarity (cosine) + lexical keyword overlap (Jaccard)
- **Open ticket match** → employee auto-linked to existing ticket, no new row created
- **Resolved ticket match** → verified solution surfaced instantly to employee
- Match rule: `(semantic >= 0.75 AND lexical >= 0.30) OR semantic >= 0.85`

### 3. SLA Monitoring & Auto-Escalation Email
- Every ticket gets an SLA deadline based on priority and team policy
- Background scheduler runs every 5 minutes automatically
- **AT RISK email** sent at 80% SLA elapsed
- **BREACH email** sent when SLA deadline passes
- HTML emails sent to manager via Gmail SMTP with full ticket details

### 4. RAG-Powered AI Chatbot
- Answers IT questions grounded in company knowledge base (PDFs)
- Uses FAISS vector index + Groq LLM (Llama 3)
- Cites source documents with similarity scores
- Suggests creating a ticket if no answer found

### 5. Priority Prediction
- Automatically predicts ticket priority (Critical / High / Medium / Low)
- Based on description text + requester department
- Feeds into SLA deadline calculation

### 6. Role-Based Dashboards
- **Employee** — submit tickets, track status, view resolutions, rate support
- **Support Agent** — full ticket management, resolve tickets, add comments
- **Manager** — analytics, SLA overview, team performance metrics

---

## ML Model Performance

| Metric | Score |
|---|---|
| Accuracy | 80.48% |
| Weighted F1 | **81.77%** |
| Weighted Precision | 82.1% |
| Weighted Recall | 80.5% |
| Training samples | 12,000 (2,000/class balanced) |
| Test samples | 5,389 (20% stratified hold-out) |

### Per-Class F1 Scores

| Team / Class | F1 Score |
|---|---|
| General Support | ~88% |
| Billing & Payments | ~82% |
| HR Support | ~79% |
| Returns & Exchanges | ~78% |
| Service & Maintenance | ~76% |
| Sales Support | ~72% |

### Model Configuration
- **Algorithm**: LightGBM (`n_estimators=300, learning_rate=0.1, num_leaves=63`)
- **Embedder**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- **Training data**: 26,942 real tickets from 4 datasets, 6 merged classes
- **Key insight**: Merging `IT Support + Product Support + Customer Service + General Inquiry` → `General Support` was the fix that jumped accuracy from 62% → 81.77%

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| API Framework | FastAPI |
| Database | SQLite (SQLAlchemy ORM) |
| ML Classifier | LightGBM + sentence-transformers |
| Embeddings | all-MiniLM-L6-v2 (shared singleton) |
| Vector Search | FAISS |
| LLM | Groq API (Llama 3) |
| Background Jobs | APScheduler |
| Email | Gmail SMTP (smtplib) |
| Auth | JWT (python-jose) |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| UI Library | Material UI v5 |
| State Management | Redux Toolkit |
| Routing | React Router DOM v6 |
| HTTP Client | Axios |
| Charts | Chart.js + react-chartjs-2 |
| Build Tool | Vite |

---

## Project Structure

```
smart-helpdesk/
├── backend/
│   ├── ai/
│   │   ├── classifier/
│   │   │   ├── build_dataset.py      # Dataset builder — merges 4 raw datasets, 6 classes
│   │   │   ├── train_router.py       # LightGBM training pipeline (v5, no GridSearch)
│   │   │   └── model_report.py       # Evaluator report — HTML + console metrics
│   │   ├── duplicate/
│   │   │   └── search.py             # FAISS-based semantic search
│   │   ├── priority/
│   │   │   └── train_priority.py     # Priority classifier training
│   │   └── rag/
│   │       ├── build_kb.py           # Knowledge base PDF indexer
│   │       ├── groq_client.py        # Groq LLM client
│   │       └── query_kb.py           # RAG query pipeline
│   ├── app/
│   │   ├── auth/                     # JWT auth, password hashing, RBAC
│   │   ├── tickets/                  # Ticket CRUD, ML routing, duplicate check
│   │   ├── sla/
│   │   │   └── service.py            # SLA audit + auto-escalation email
│   │   ├── duplicate/
│   │   │   └── service.py            # Hybrid semantic + lexical duplicate engine
│   │   ├── chatbot/                  # RAG chatbot service + routes
│   │   ├── agent/                    # Agent portal routes
│   │   ├── core/
│   │   │   └── embeddings.py         # Shared SentenceTransformer singleton
│   │   ├── database/
│   │   │   ├── database.py           # SQLAlchemy engine + session
│   │   │   └── seed_data.py          # Default users, teams, tickets, KB articles
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   └── main.py                   # FastAPI app + APScheduler startup
│   ├── model_assets/
│   │   ├── models/
│   │   │   ├── router.pkl            # Trained LightGBM classifier
│   │   │   ├── label_encoder.pkl     # Class label encoder
│   │   │   ├── priority.pkl          # Priority classifier
│   │   │   ├── kb.index              # FAISS knowledge base index
│   │   │   ├── model_report.html     # Evaluator-ready model report
│   │   │   ├── router_confusion_matrix.png
│   │   │   └── per_class_f1.png
│   │   ├── processed/
│   │   │   └── training_real.csv     # 26,942 cleaned training samples
│   │   └── knowlegde/                # Company KB PDFs (VPN, SAP, Security, etc.)
│   ├── .env                          # Environment variables
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── DashboardPage.tsx
    │   │   ├── CreateTicketPage.tsx   # Ticket form + duplicate detection modal
    │   │   ├── TicketsPage.tsx
    │   │   ├── AgentPortalPage.tsx
    │   │   ├── AnalyticsPage.tsx
    │   │   └── ChatbotPage.tsx
    │   ├── components/
    │   │   ├── layout/
    │   │   │   ├── AppLayout.tsx      # Role switcher, theme, sidebar
    │   │   │   ├── Header.tsx
    │   │   │   └── Sidebar.tsx
    │   │   └── ChatbotDrawer.tsx
    │   └── store/                     # Redux slices
    ├── package.json
    └── vite.config.ts
```

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- Git

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/smart-helpdesk.git
cd smart-helpdesk
```

### 2. Backend setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
pip install lightgbm sentence-transformers faiss-cpu apscheduler groq python-dotenv
```

### 3. Frontend setup
```bash
cd frontend
npm install
```

### 4. Seed the database
```bash
cd backend
python -c "from app.database.seed_data import init_db; init_db()"
```

---

## Environment Variables

Create `backend/.env`:

```env
# Database
DATABASE_URL=sqlite:///./smart_helpdesk.db

# Auth
JWT_SECRET=supersecretkey

# Groq LLM (for RAG chatbot)
GROQ_API_KEY=your_groq_api_key_here

# SLA Auto-Escalation Email (Gmail)
SMTP_SENDER_EMAIL=your_gmail@gmail.com
SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx
ESCALATION_MANAGER_EMAIL=manager@example.com
```

> **Gmail App Password setup:**
> 1. Enable 2-Step Verification at [myaccount.google.com/security](https://myaccount.google.com/security)
> 2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
> 3. Create an App Password → paste the 16-char code into `SMTP_APP_PASSWORD`

---

## Running the Application

### Start Backend
```bash
cd backend
uvicorn app.main:app --reload
```
API runs at: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### Start Frontend
```bash
cd frontend
npm run dev
```
App runs at: `http://localhost:5173`

---

## Role-Based Dashboards

The app has a **Switch Role** button in the header to cycle between views:

| Role | Access |
|---|---|
| **Employee** | Submit tickets, view own tickets, track status, rate resolution, AI chatbot |
| **Support Agent** | All tickets, resolve/update tickets, add internal notes, agent portal |
| **Manager** | Analytics dashboard, SLA overview, team performance, escalation logs |

---

## AI Features Deep Dive

### Ticket Routing Pipeline
```
Employee submits ticket description
        ↓
SentenceTransformer encodes text → 384-dim vector
        ↓
LightGBM classifier predicts team + confidence
        ↓
If confidence < 0.5 → flagged as Triage
        ↓
Ticket assigned to team, SLA deadline set
```

### Duplicate Detection Pipeline
```
Employee submits ticket
        ↓
Hybrid engine checks all existing tickets
        ↓
Semantic score (cosine similarity of embeddings)
  +
Lexical score (Jaccard similarity of keywords)
        ↓
Match rule: (sem >= 0.75 AND lex >= 0.30) OR sem >= 0.85
        ↓
Open match   → Hard block, link employee to existing ticket
Resolved match → Hard block, show verified solution
No match     → Create new ticket
```

### SLA Escalation Pipeline
```
APScheduler runs every 5 minutes (background, automatic)
        ↓
Checks all active tickets (open, in_progress, etc.)
        ↓
80% SLA elapsed → AT RISK email to manager
100% SLA elapsed → BREACHED email to manager
        ↓
Email contains: ticket ID, title, priority, team,
                requester, SLA deadline, overdue time
```

### RAG Chatbot Pipeline
```
Employee asks question
        ↓
Question embedded → FAISS search over KB PDFs
        ↓
Top-k relevant chunks retrieved
        ↓
Groq LLM (Llama 3) generates grounded answer
        ↓
Response includes source citations + similarity scores
```

---

## API Reference

### Tickets
| Method | Endpoint | Description |
|---|---|---|
| POST | `/ticket/create` | Create ticket (with duplicate check) |
| GET | `/ticket/all` | Get all tickets (role-filtered) |
| GET | `/ticket/my-tickets` | Get employee's own tickets |
| GET | `/ticket/stats` | Dashboard statistics |
| POST | `/ticket/route-ticket` | ML routing preview |
| POST | `/ticket/check-duplicate` | Manual duplicate check |
| GET | `/ticket/employee/{id}` | Employee ticket detail |
| POST | `/ticket/employee/comment/{id}` | Add comment |
| POST | `/ticket/employee/rate/{id}` | Submit satisfaction rating |
| POST | `/ticket/employee/reopen/{id}` | Reopen resolved ticket |

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login` | Login, returns JWT token |
| POST | `/auth/register` | Register new employee |

### Agent
| Method | Endpoint | Description |
|---|---|---|
| GET | `/agent/tickets` | All tickets for agent view |
| POST | `/agent/tickets/{id}/resolve` | Resolve ticket with notes |
| POST | `/agent/tickets/{id}/update-status` | Update ticket status |

### Chatbot
| Method | Endpoint | Description |
|---|---|---|
| POST | `/chatbot/query` | RAG chatbot query |

---

## Testing Guide

### Test Duplicate Detection

**Step 1** — Submit a ticket as Alice Employee (Employee role):
```
Name: Alice Employee
Title: Outlook keeps asking for password repeatedly
Description: My Outlook desktop client keeps prompting for my Microsoft account
             password every few minutes even after entering correct credentials.
```

**Step 2** — Resolve the ticket (switch to Support Agent role → Agent Portal)

**Step 3** — Submit similar ticket as Bob (change name field):
```
Name: Bob Sales Employee
Title: Outlook password prompt keeps appearing
Description: Outlook is constantly asking me to re-enter my password on my
             Windows laptop. Keeps popping up again after a few minutes.
```
→ **Expected**: Green modal — "This issue has already been resolved!"

### Test SLA Auto-Escalation Email

```bash
cd backend
python run_sla_test.py
```
This backdates a ticket's SLA to 45 minutes ago. The background scheduler fires the breach email within 5 minutes automatically.

### Generate Model Report
```bash
cd backend
python ai/classifier/model_report.py
```
Opens `model_assets/models/model_report.html` — full evaluator report with confusion matrix, per-class F1, and metrics.

---

## Demo Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@helpdesk.com | admin123 |
| Manager | manager@helpdesk.com | manager123 |
| Support Agent | agent@helpdesk.com | agent123 |
| Employee (Alice) | alice@company.com | user123 |
| Employee (Bob) | bob@company.com | user123 |

---

## SLA Policy Reference

| Priority | Response SLA | Resolution SLA |
|---|---|---|
| Critical | 2 hours | 6 hours |
| High | 8 hours | 24 hours |
| Medium | 16 hours | 48 hours |
| Low | 24 hours | 72 hours |

---

## Dataset & Training

The routing classifier was trained on 4 real-world helpdesk datasets:

| Dataset | Source | Used |
|---|---|---|
| tickets1 | IT Support tickets with Department labels | Yes |
| tickets2 | 493 unique descriptions × 2000 repeats | No — template noise |
| tickets3 | Multi-language tickets (English only) | Yes |
| tickets4 | Anonymized group names ("Group 70") | No — meaningless labels |

**Class merging insight**: `IT Support`, `Product Support`, `Customer Service`, and `General Inquiry` shared near-identical top-50 vocabulary. Merging them into `General Support` eliminated artificial ambiguity and was the key fix that improved F1 from 62% → 81.77%.

To retrain from scratch:
```bash
cd backend
python ai/classifier/build_dataset.py   # rebuild training_real.csv
python ai/classifier/train_router.py    # train LightGBM (~15 min)
python ai/classifier/model_report.py    # generate evaluation report
```

---

*Built with FastAPI · React · LightGBM · sentence-transformers · FAISS · Groq*
