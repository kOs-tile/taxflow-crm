# TaxFlow CRM

> **Status — Portfolio/demo project.** TaxFlow demonstrates a vertical SaaS architecture for tax practices. It is **not tax, legal, compliance, or filing software**. Deadline logic is intentionally conservative and incomplete; production use requires authoritative current tax calendars and entity tax-classification data.


**Built for CPAs, not generic businesses.**

TaxFlow is an AI-powered practice management system designed specifically for US tax professionals and accounting firms. While generic CRMs treat every document like a "file" and every deadline like a calendar event, TaxFlow understands the difference between a W-2 and a K-1, knows that S-Corps file on March 15th, and can draft a client extension notice without you explaining what Form 4868 is.

---

## Why TaxFlow?

| Generic CRM | TaxFlow CRM |
|-------------|-------------|
| "Document attached" | W-2 · 1099-NEC · K-1 · Schedule C tracked per-client |
| Calendar reminder | April 15 · March 15 (S-Corp) · Quarterly estimates auto-generated |
| Email thread | Secure in-app messaging, separate from email |
| "AI chatbot" | Tax-aware assistant with full client context |
| One portal | Separate staff portal + client self-service portal |

---

## Features

### 1. Client Management
- Full client profiles: name, entity type, filing status, SSN last 4, EIN, state
- Entity types: Individual · LLC · S-Corp · C-Corp · Partnership · Sole Proprietor · Nonprofit
- Search, filter by preparer or entity type
- Per-client notes and assigned preparer

### 2. Document Tracker
Every document type the IRS cares about, tracked per client:

| Form | Description |
|------|-------------|
| W-2 | Wage and Tax Statement |
| 1099-NEC | Non-employee compensation |
| 1099-B | Proceeds from broker transactions |
| 1099-INT / DIV | Interest and dividend income |
| 1099-R | Retirement distributions |
| K-1 | Partnership / S-Corp / Trust share |
| 1098 | Mortgage interest |
| 1098-E | Student loan interest |
| Schedule C/E | Business / Rental income |
| Prior Year Return | Required for first-time clients |
| + more | Crypto, FBAR, Home Office, Vehicle Log... |

Status per document: **Awaiting → Received → Reviewed → N/A**

Completion percentage calculated automatically and displayed on dashboard.

### 3. Deadline Tracker
Auto-generated for tax classifications the demo can identify safely. LLC legal form alone is intentionally not auto-mapped because its federal tax classification can vary:

**Individual (1040)**
- April 15 — Federal return
- October 15 — Extension deadline
- Jan 15 / Apr 15 / Jun 15 / Sep 15 — Quarterly estimates

**S-Corp / Partnership (1120-S / 1065)**
- March 15 — Return due
- September 15 — Extension deadline
- January 31 — W-2 / 1099 employer filing

**C-Corp (1120)**
- April 15 — Return due
- October 15 — Extension deadline
- Quarterly estimated taxes

Visual timeline per client. At-risk detection for missed or overdue deadlines.

### 4. Secure Messaging
- In-app messaging between staff and each client (no email)
- **Server-Sent Events (SSE)** for real-time message notifications
- Separate client portal with its own login
- Unread badges on the Messages tab
- Staff inbox showing all client threads

### 5. AI Assistant

Powered by **OpenAI GPT-4o-mini** or **DeepSeek** (your choice).

The assistant uses a **minimized operational context**, not the full client record. By default the outbound LLM context contains an internal client reference plus filing/workflow status, document status, deadlines, and open tasks. Name/email require explicit `AI_CONTEXT_PRIVACY=identity`; SSN last4, EIN, phone, address, free-form notes, and portal credentials are never inserted into the LLM context.

**Example prompts:**
```
"What documents is Jennifer Walsh still missing?"
→ W-2 from Fidelity and 1099-B are still awaiting. Received_at timestamps
  show no activity in 2 weeks. Suggest sending a follow-up.

"Draft a reminder email for clients with missing W-2s"
→ Subject: Action Needed: Your W-2 for 2024 Tax Filing
  Dear [Client], We're preparing your 2024 tax return and still need
  your W-2 from [Employer]...

"Who are my at-risk clients this week?"
→ 3 clients have missed deadlines or documents below 30% complete:
  - Blue Ridge Partners LP (1065 due March 15, no K-1 yet)
  - Carlos Mendez (Q3 estimated underpayment)
  - Green Leaf Yoga Studio (Schedule C outstanding)

"What are the Q2 2025 estimated tax dates?"
→ Q2 2025 estimated tax payment is due June 16, 2025 (shifted from
  June 15 since it falls on a Sunday)...

"Generate an extension notice for Westlake Dentistry"
→ Dear Dr. Westlake, We are filing Form 7004 for Westlake Family
  Dentistry S-Corp to request an automatic 6-month extension...
```

### AI context boundary

TaxFlow treats the external model as a separate data boundary:

- default `AI_CONTEXT_PRIVACY=minimum`
- full name/email withheld by default
- explicit `identity` mode can add only name/email
- SSN last4, EIN, phone, address, notes, and portal credentials are excluded in all modes
- client-specific deadline reasoning must use stored application deadline records
- general/current deadline answers without an authoritative application record must recommend verification
- AI suggestions are drafts; they do not imply filing, payment, messaging, or another external action occurred

The chat response reports `context_privacy_mode` and `client_identity_sent` so the UI/audit layer can see which outbound context policy was active.

### 6. Dashboard
- Total clients · Docs received this week · Deadlines in 7 days · At-risk clients
- Upcoming deadline feed (color-coded by urgency)
- Recent activity stream (documents, messages, deadline changes)
- At-risk client list with document completion bars

### 7. Task System
- Per-client tasks with priority (Low / Medium / High / Urgent)
- Due dates and completion tracking
- Checkbox UI for quick completion

### 8. Client Portal
Separate login for clients (`/portal`):
- View their own document submission status
- See their upcoming tax deadlines
- Secure messaging with their accountant
- No access to other clients' data

---

## Screenshots (ASCII)

```
┌────────────────────────────────────────────────────────────────────────┐
│ TaxFlow           Dashboard                      Mon Jun 29, 2026      │
│ ─────────────────────────────────────────────────────────────────────  │
│ ■ Dashboard   │  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐ │
│   Clients     │  │ 47          │ │ 12          │ │ ⚠️ 3             │ │
│   Messages 2  │  │ Active      │ │ Deadlines   │ │ At-Risk Clients  │ │
│   Deadlines   │  │ Clients     │ │ in 7 days   │ │                  │ │
│   Documents   │  └─────────────┘ └─────────────┘ └──────────────────┘ │
│               │                                                         │
│ ■ AI Assistant│  ┌──── Upcoming Deadlines ────────────────────────┐    │
│               │  │ Jennifer Walsh     1040 Federal Return  3d 🔴  │    │
│   Sarah Chen  │  │ Westlake Dentistry  1120-S Extension   12d 🟡  │    │
│   Preparer    │  │ Blue Ridge Partners 1065 Return        28d 🟢  │    │
└───────────────┘  └────────────────────────────────────────────────┘    │
```

```
┌────────────────────────────────────────────────────────────────────────┐
│ TaxFlow      Jennifer & Robert Walsh            Individual · MFJ       │
│ ─────────────────────────────────────────────────────────────────────  │
│              │                                                          │
│ Document     │  ██████████░░░░░  67%                                   │
│ Checklist    │                                                          │
│              │  ✅ W-2                       Received                   │
│ [Initialize] │  ⏳ 1099-B                    Awaiting    [Change ▾]    │
│              │  ✅ 1099-INT                  Received                   │
│              │  ✅ 1098 (Mortgage)           Received                   │
│              │  ⏳ Charitable Donations      Awaiting    [Change ▾]    │
│              │                                                          │
│ Deadlines    │  ┌──── Messages ────────────────────────────────────┐   │
│ ────────────  │  │ Client: Hi, I just uploaded my W-2...           │   │
│ ● Apr 15 🔴  │  │ Staff:  Yes, please send the RSU vesting...     │   │
│   1040 due   │  │ Client: I'll dig those up...                     │   │
│ ● Oct 15     │  │                                                  │   │
│   Extension  │  │  Type a message...                        [Send] │   │
│              │  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────  │
```

---

## Tax Deadline Calendar (2025)

| Date | Deadline |
|------|----------|
| **Jan 15, 2025** | Q4 2024 estimated tax payment |
| **Jan 31, 2025** | W-2 and 1099-NEC employer filing |
| **Feb 18, 2025** | 1099-B, 1099-DIV consolidated statements |
| **Mar 17, 2025** | S-Corp (1120-S) and Partnership (1065) returns (Mar 15 falls on Saturday) |
| **Apr 15, 2025** | Individual 1040, C-Corp 1120, FBAR |
| **Apr 15, 2025** | Q1 2025 estimated tax payment |
| **Jun 16, 2025** | Q2 2025 estimated tax payment (Jun 15 falls on Sunday) |
| **Sep 15, 2025** | Q3 2025 estimated tax payment; S-Corp/Partnership extensions |
| **Oct 15, 2025** | Individual and C-Corp extension deadlines; FBAR extension |
| **Jan 15, 2026** | Q4 2025 estimated tax payment |

*The demo generator currently adjusts weekends only. It does not implement a complete federal/state holiday calendar; production use requires an authoritative tax-calendar source.*

---

## Quick Start

### Requirements
- Python 3.11+
- pip

### 1. Clone and install
```bash
git clone https://github.com/kOs-tile/taxflow-crm.git
cd taxflow-crm
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Set JWT_SECRET_KEY (32+ chars) and ADMIN_PASSWORD (12+ chars).
# Optionally set OPENAI_API_KEY or DEEPSEEK_API_KEY for the AI assistant.
```

### 3. Start the server
```bash
uvicorn backend.main:app --reload
```

### 4. Seed demo data
```bash
python -m scripts.seed
```

### 5. Open the app
- Staff CRM: http://localhost:8000/
- API Docs: http://localhost:8000/api/docs
- Client Portal: http://localhost:8000/portal

**Login:** use the `ADMIN_EMAIL` and `ADMIN_PASSWORD` values you configured in `.env`.

---

## Docker

```bash
docker-compose up
```

---

## Client Portal

The client portal (`/portal`) is completely separate from the staff CRM:

- Clients log in with their **email + portal password** (set by staff)
- They see **only their own data**: document status, deadlines, messages
- They can **message their accountant** directly (staff sees replies in Messages tab)
- JWT tokens are scoped: a client token cannot access the staff API

To set a client's portal password:
```
POST /api/clients/{id}/portal-password\nContent-Type: application/json\n\n{"password":"ClientSecret123"}
```

Or include `"portal_password": "..."` in the JSON body when creating the client. Passwords are never accepted in query strings.

---

## AI Assistant Capabilities

The AI assistant (`/assistant`) has two modes:

**Global mode** — general tax questions, firm-wide analysis:
- "Who are my at-risk clients?"
- "What's the FBAR filing deadline for 2025?"
- "Summarize what I should do today"

**Client context mode** — select a client to get personalized answers:
- Full client profile loaded into context
- Current document status and missing documents
- Upcoming and overdue deadlines
- Recent message history
- Open tasks

The system prompt includes comprehensive US tax knowledge and instructs the AI to:
- Draft professional client emails in the firm's voice
- Flag urgent situations clearly
- Never give definitive legal/tax advice without caveats
- Use form numbers and tax terminology correctly

---

## Architecture

```
taxflow-crm/
├── backend/
│   ├── config.py         # Pydantic Settings (env config)
│   ├── models.py         # Pydantic API models (400+ lines)
│   ├── db.py             # aiosqlite CRUD + SQL schema
│   ├── auth.py           # JWT auth, bcrypt, staff + portal login
│   ├── main.py           # FastAPI app, routing, static files
│   └── routes/
│       ├── clients.py    # Client CRUD + search + user management
│       ├── documents.py  # Document checklist + completion stats
│       ├── deadlines.py  # Deadline CRUD + auto-generation + calendar
│       ├── messages.py   # Messaging + SSE real-time stream
│       ├── assistant.py  # AI chat + context assembly
│       ├── dashboard.py  # Aggregated stats + activity feed
│       └── tasks.py      # Per-client task management
├── frontend/
│   ├── index.html        # Dashboard
│   ├── clients.html      # Client list + add modal
│   ├── client_detail.html# Full client view (all sections)
│   ├── messages.html     # Inbox / message threads
│   ├── assistant.html    # Full-page AI assistant
│   ├── portal.html       # Client portal (separate auth)
│   ├── login.html        # Staff login
│   ├── style.css         # Professional light theme (~1100 lines)
│   └── app.js            # All frontend JS: API client, SSE, UI
├── scripts/
│   ├── seed.py           # 10 realistic client records + history
│   └── demo.py           # CLI walkthrough
└── tests/
    ├── conftest.py       # Shared fixtures (in-memory SQLite)
    ├── test_clients.py   # CRUD + document completion tests
    ├── test_deadlines.py # Auto-generation + deadline logic
    ├── test_messages.py  # Thread + portal auth tests
    ├── test_assistant.py # Mocked AI + context assembly tests
    └── test_auth.py      # JWT auth flow tests
```

**Tech Stack:**
- **Backend:** FastAPI · Python 3.11 · aiosqlite (async SQLite)
- **Auth:** python-jose (JWT) · passlib/bcrypt
- **AI:** OpenAI SDK (compatible with OpenAI + DeepSeek)
- **Real-time:** sse-starlette (Server-Sent Events)
- **Frontend:** Vanilla JS + HTML + CSS (no build step)
- **Testing:** pytest-asyncio · httpx (async test client)

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use an **in-memory SQLite database** for complete isolation. No server required.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | required | Random hex string (generate with `openssl rand -hex 32`) |
| `OPENAI_API_KEY` | optional | OpenAI API key for AI assistant |
| `DEEPSEEK_API_KEY` | optional | DeepSeek API key (set `AI_PROVIDER=deepseek`) |
| `AI_PROVIDER` | `openai` | `openai` or `deepseek` |
| `AI_CONTEXT_PRIVACY` | `minimum` | `minimum` or explicit `identity` outbound LLM context |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model to use |
| `DATABASE_URL` | `taxflow.db` | SQLite file path |
| `ADMIN_EMAIL` | `admin@taxflow.app` | Default admin email |
| `ADMIN_PASSWORD` | required | Initial admin password (12+ chars; do not commit it) |
| `EMAIL_ENABLED` | `false` | Enable real SMTP (set SMTP_* vars) |

---

## API Reference

Interactive docs at `/api/docs` (Swagger UI) after starting the server.

Key endpoints:
```
POST   /api/auth/login              Staff login
POST   /api/auth/portal/login       Client portal login

GET    /api/dashboard               Full dashboard data
GET    /api/clients                 List / search clients
POST   /api/clients                 Create client
GET    /api/clients/{id}            Get client detail
GET    /api/clients/{id}/summary    Get AI context summary

GET    /api/documents/client/{id}   Get document checklist
POST   /api/documents/client/{id}/initialize   Initialize standard docs
PATCH  /api/documents/{doc_id}      Update document status

GET    /api/deadlines/upcoming      Upcoming deadlines (all clients)
POST   /api/deadlines/client/{id}/auto-generate   Generate standard deadlines
GET    /api/deadlines/calendar      US tax calendar reference

GET    /api/messages/threads        All client threads (inbox)
GET    /api/messages/client/{id}    Get thread
POST   /api/messages/client/{id}/send   Send message
GET    /api/messages/client/{id}/stream  SSE stream

POST   /api/assistant/chat          AI chat (with optional client context)
GET    /api/assistant/prompts       Suggested prompts

GET    /api/portal/messages         Client portal messages (client JWT)
POST   /api/portal/messages/send    Client portal send message
```

---

## About

Built by **Onur Kavi** as an AI engineering portfolio/demo project exploring a domain-specific Python/FastAPI application with AI integration.

This project demonstrates:
- Domain-specific AI applications (not generic chatbots)
- Clean async FastAPI architecture with real auth
- SSE for real-time features without WebSocket complexity
- Thoughtful UX design for professional users
- Comprehensive test coverage with mocked AI

---

*TaxFlow CRM is a portfolio project. It is not affiliated with any tax authority or financial institution.*
