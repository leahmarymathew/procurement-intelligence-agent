# Source-to-Pay Procurement Intelligence Agent

A multi-agent Source-to-Pay (S2P) automation system built on LangChain, LangGraph, FastAPI, React, and SQLite. Four specialist agents handle supplier scoring, approval routing, process discovery, and metrics reporting — coordinated by a LangGraph state machine.

**System version:** `procurement-agent-v1.0`

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   React Dashboard (Vite)                │
│  Dashboard · Supplier · Approval · Backlog · Pilot      │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (proxied /api → :8000)
┌────────────────────▼────────────────────────────────────┐
│                FastAPI Backend (:8000)                  │
│  /procurement  /metrics  /audit-log  /pilot             │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              LangGraph Orchestrator                     │
│                                                         │
│  intake → supplier_scoring → approval_routing → complete│
│         → process_discovery → complete                  │
│         → weekly_report    → complete                   │
│                                                         │
│  Every transition logged to /audit-log before execution │
└──┬─────────────┬──────────────┬───────────────┬─────────┘
   │             │              │               │
   ▼             ▼              ▼               ▼
Supplier     Approval      Process         Metrics &
Scoring      Routing       Discovery       Reporting
Agent        Agent         Agent           Agent
(RAG-based)  (policy-table)(log analysis)  (SQLite agg)
   │             │              │               │
   └─────────────┴──────────────┴───────────────┘
                     │                   │
              SQLite (local)       Slack (Block Kit)
              ChromaDB (RAG)
```

---

## Agents

| Agent | Trigger | Retrieval source | Output |
|---|---|---|---|
| **Supplier Scoring** | New/existing supplier on a PR | ChromaDB knowledge base (top-10 chunks) | 5-dimension score (1–10), composite, status |
| **Approval Routing** | Every purchase request | `policy_rules` SQLite table | Approval chain, SLA, escalation condition |
| **Process Discovery** | Scheduled / on-demand | `audit_log`, `approval_decisions`, feedback tables | Scored findings → `process_backlog` |
| **Metrics & Reporting** | After each action / weekly | `metrics_aggregate`, `process_backlog`, feedback | Dashboard data, Slack weekly report |

**Invariant:** No agent scores, routes, or writes to SQLite without a prior retrieval step. Enforced in `backend/agents/base.py`.

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+

### Install

```powershell
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

### Configure

```powershell
cp .env.example .env
# Edit .env — minimum required: OPENAI_API_KEY
# The system runs without a key; supplier scoring uses conservative fallback scores.
```

### Run

```powershell
# Start both backend and frontend
.\start.ps1

# Or backend only
.\start-backend.ps1

# Or frontend only (from frontend/)
npm run dev
```

| Service | URL |
|---|---|
| React dashboard | http://localhost:5173 |
| FastAPI + Swagger | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

---

## Key Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/procurement/request` | Submit a purchase request (triggers full pipeline) |
| `GET` | `/procurement/request/{id}` | Get request status + routing decision |
| `POST` | `/procurement/supplier/score` | Score a supplier against the knowledge base |
| `POST` | `/procurement/process-discovery` | Run process discovery on-demand |
| `POST` | `/procurement/weekly-report` | Generate and push weekly Slack report |
| `GET` | `/metrics` | Live dashboard metrics |
| `GET` | `/metrics/history` | 7-day rolling trend |
| `POST` | `/audit-log` | Ingest an agent action log |
| `GET` | `/audit-log` | Query audit trail |
| `GET` | `/pilot` | List all pilot teams |
| `GET` | `/pilot/{team}/summary` | Per-pilot metrics |
| `POST` | `/pilot/{team}/feedback` | Submit stakeholder feedback |

---

## Database

SQLite file: `procurement.db` (created on first run, gitignored).

Schema managed by `migrations/001_initial_schema.sql`, executed at startup. The `migration_log` table is always created first — any future schema changes must add a new migration file and insert a row into `migration_log` before creating or altering tables.

Key tables:

| Table | Purpose |
|---|---|
| `migration_log` | Schema change history (required before any DDL) |
| `policy_rules` | Approval routing policies — source of truth for the routing agent |
| `purchase_requests` | Inbound PRs |
| `approval_decisions` | Routing outputs keyed to requests |
| `supplier_scores` | Historical scores with source chunk citations |
| `process_backlog` | Process findings (score = impact weight × inverse-effort weight) |
| `audit_log` | Every agent action and state transition |
| `metrics_aggregate` | Daily rolled-up metrics consumed by the dashboard |
| `pilot_metrics` | Per-team, per-stage pilot tracking |
| `stakeholder_feedback` | Ratings and free-text feedback |
| `prompt_registry` | Versioned prompt records |

---

## Prompt Library

All prompts are versioned. No unversioned prompt may run in pilot or production.

| Prompt name | Agent |
|---|---|
| `supplier-score-v1.0` | Supplier Scoring Agent |
| `approval-route-v1.0` | Approval Routing Agent |
| `process-discovery-v1.0` | Process Discovery Agent |
| `metrics-report-v1.0` | Metrics & Reporting Agent |

Registered in `backend/prompts/library.py`. To update a prompt: add a new version (e.g. `supplier-score-v1.1`), document the change, and update the `PROMPT_VERSION` constant in the relevant agent file. Do not modify existing version entries.

---

## Slack Notifications

Five trigger events post structured Block Kit messages. Raw data is never posted.

| Event | Channel | Trigger condition |
|---|---|---|
| P1 escalation | `#procurement-alerts` | Approval chain has an escalation condition |
| Supplier flagged | `#supplier-intel` | Supplier scored `watch-list` or `disqualified` |
| Backlog alert | `#ops-process` | Process finding scored ≥ 7/9 |
| Weekly report | `#procurement-weekly` | Report generated (manual or scheduled) |
| Pilot milestone | `#pilot-ops` | Pilot stage advanced |

Configure `SLACK_BOT_TOKEN` in `.env`. Without a token, notifications are printed to stdout (mock mode).

---

## Knowledge Base

Markdown files in `data/knowledge_base/` are chunked by paragraph and embedded into ChromaDB on startup (skipped if already populated). Add new supplier records, compliance standards, or pricing data as `.md` files — restart the backend to re-index, or call `build_knowledge_base(force_rebuild=True)`.

Current knowledge base files:
- `supplier_performance.md` — 5 supplier performance reviews
- `compliance_standards.md` — certification requirements by category
- `pricing_benchmarks.md` — market benchmarks and scoring methodology

---

## Pilot Deployment

Two pilot teams are seeded on startup: `pilot-alpha` and `pilot-beta` (Stage 1, `v1.0`).

Each pilot tracks: active users, requests processed, routing accuracy, average scoring confidence, stakeholder satisfaction (1–5), open feedback items, and current prompt version.

Advancing a stage:
```
PATCH /pilot/{team}/advance
```

Blockers must be resolved and documented before a stage is promoted. Agent behavior changes validated during experimentation must increment the prompt version before promotion.

---

## Project Structure

```
procurement-intelligent-agent/
├── backend/
│   ├── main.py                  # FastAPI app + startup lifecycle
│   ├── config.py                # Settings (pydantic-settings + .env)
│   ├── database.py              # Async SQLAlchemy engine + migration runner
│   ├── models.py                # ORM models
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── agents/
│   │   ├── base.py              # Retrieval guard + audit log + LLM call
│   │   ├── supplier_scoring.py
│   │   ├── approval_routing.py
│   │   ├── process_discovery.py
│   │   ├── metrics_reporting.py
│   │   └── orchestrator.py      # LangGraph state machine
│   ├── prompts/library.py       # Versioned prompt registry
│   ├── rag/
│   │   ├── knowledge_base.py    # ChromaDB setup + document loading
│   │   └── retriever.py         # Top-k semantic retrieval
│   ├── notifications/slack.py   # Block Kit notification templates
│   └── routers/
│       ├── audit.py             # POST/GET /audit-log
│       ├── metrics.py           # GET /metrics
│       ├── procurement.py       # POST /procurement/request etc.
│       └── pilot.py             # Pilot CRUD + feedback
├── frontend/src/
│   ├── App.jsx                  # Tab navigation shell
│   ├── api.js                   # Typed API client
│   └── components/
│       ├── Dashboard.jsx        # Live metrics + audit summary + trend chart
│       ├── MetricsCards.jsx     # 8-metric KPI grid
│       ├── SupplierPanel.jsx    # Scoring form + dimension breakdown
│       ├── ApprovalPanel.jsx    # PR submission + routing result + lookup
│       ├── ProcessBacklog.jsx   # Ranked findings + pilot breakdown
│       └── PilotPanel.jsx       # Per-team metrics + feedback
├── migrations/001_initial_schema.sql
├── data/
│   ├── knowledge_base/          # Supplier/compliance/pricing documents
│   └── seed/                    # policy_rules.json, pilot_teams.json
├── requirements.txt
├── .env.example
└── start.ps1
```
