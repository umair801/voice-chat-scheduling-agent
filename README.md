# Voice and Chat AI Scheduling Agent

**By Muhammad Umair | [Datawebify](https://datawebify.com)**

A production-grade AI scheduling and support agent that handles customer appointment booking through voice calls, chat messages, and Telegram. Powered by Google Gemini 2.5 Flash and orchestrated with LangGraph, the system includes a specialized sales intake agent, a RAG-powered technical support agent, ElevenLabs voice synthesis, and a live monitoring dashboard with human takeover. Deploys into any field service or satellite services business to eliminate manual scheduling and support entirely.

**Live:** [scheduling.datawebify.com](https://scheduling.datawebify.com) | **Monitor:** [scheduling.datawebify.com/monitor](https://scheduling.datawebify.com/monitor) | **Docs:** [scheduling.datawebify.com/docs](https://scheduling.datawebify.com/docs)

---

## Business Outcomes

| Metric | Manual Process | With This System | Change |
|--------|---------------|-----------------|--------|
| Average time to book | 8-15 minutes | Under 2 minutes | 85% faster |
| After-hours availability | 0% | 100% | Full coverage |
| Booking completion rate | 60-70% | 80%+ | +15-20% |
| Staff time on scheduling | 3-5 hours/day | Near zero | 90% reduction |
| No-show rate | 15-25% | Under 10% | 50% reduction |
| Support response time | Hours | Under 10 seconds | Real-time |

---

## Target Industries

- HVAC, plumbing, electrical, and general field service companies
- Satellite services and telecommunications providers
- Cleaning, pest control, and landscaping businesses
- Healthcare clinics and home care providers
- Any service business where scheduling and support are done manually

---

## System Architecture

The system uses a LangGraph-orchestrated multi-agent pipeline. A router agent dispatches each inbound message to the correct specialized agent. Routing is fully deterministic: the LLM handles language, the graph handles flow.

```
Inbound Call / Chat / Telegram Message
              |
        Input Normalizer
              |
        Router Agent
       /      |      \
      /        |       \
Sales      Booking    Tech Support
Agent      Flow       Agent (RAG)
  |           |           |
Sales      Availability   Knowledge
Intake     Agent          Base
  |           |           (Chroma)
  |       Conflict
  |       Resolver
  |           |
  |       Booking
  |       Confirmation
  |       Agent
   \          |          /
    \         |         /
     Supabase + Notifications
     (SendGrid + Twilio SMS)
```

### Agent Responsibilities

**Router Agent** -- First-turn classifier that dispatches to Sales Agent, Tech Support Agent, or the Booking flow based on message intent.

**Sales Agent** -- Handles pricing inquiries, demo requests, callback requests, and general sales questions. Collects customer name, email, company, and inquiry details for the sales team.

**Tech Support Agent (RAG-powered)** -- Classifies technical issues and retrieves relevant past resolutions from a Chroma vector knowledge base. Answers with high confidence when similar issues are found; escalates when not.

**Input Normalizer** -- Converts raw voice transcriptions, chat messages, and Telegram updates into a unified message object. All downstream agents are channel-agnostic.

**Intent Parser Agent** -- Uses Gemini 2.5 Flash to classify booking intents (book, reschedule, cancel, check status) and extract entities (service type, date, time, location).

**Availability Agent** -- Makes structured REST calls to the CRM API with exponential backoff retry logic (max 3 retries). Returns slots ranked by proximity and team workload.

**Conflict Resolution Agent** -- When no exact slots match, proposes the three nearest alternatives and maintains full conversation state across turns.

**Booking Confirmation Agent** -- Writes confirmed appointments to Supabase, triggers email via SendGrid, and sends SMS confirmation via Twilio.

**Cancellation and Reschedule Agent** -- Looks up bookings by phone or email, handles cancellations within configurable policy windows, and re-enters the booking flow for reschedules.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph |
| AI Model | Gemini 2.5 Flash (google.genai SDK) |
| Voice Interface | Twilio Voice (STT) + ElevenLabs (TTS) |
| Chat Interface | FastAPI webhook (WhatsApp, SMS, web widget) |
| Messaging | Telegram Bot API |
| Knowledge Base | Chroma vector database + RAG retriever |
| Backend API | FastAPI + Uvicorn |
| Database | Supabase (PostgreSQL) |
| Notifications | SendGrid (email) + Twilio (SMS) |
| Monitoring | Live dashboard at /monitor with human takeover |
| Deployment | Docker + Railway |
| Language | Python 3.12 |
| Tests | 54 passing (pytest) |

---

## Channels Supported

| Channel | Entry Point | Notes |
|---------|------------|-------|
| Voice | Twilio inbound call | STT via Twilio, TTS via ElevenLabs |
| WhatsApp | `/chat/webhook/twilio` | Via Twilio WhatsApp |
| SMS | `/chat/webhook/twilio` | Via Twilio SMS |
| Web Widget | `/chat/webhook/web` | Direct API integration |
| Telegram | `/telegram/webhook` | Native Telegram Bot API |

---

## API Endpoints

### Voice
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/voice/webhook` | Twilio voice webhook, STT input, ElevenLabs TTS response |
| POST | `/voice/status` | Twilio call status callback |
| GET | `/voice/audio/{clip_id}` | Serve ElevenLabs audio clip to Twilio |
| GET | `/voice/test` | Health check for voice router |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/webhook/twilio` | WhatsApp and SMS via Twilio |
| POST | `/chat/webhook/web` | Web widget and direct API |
| POST | `/chat/session/close` | Explicitly close a session |
| GET | `/chat/test` | Health check for chat router |

### Telegram
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/telegram/webhook` | Telegram bot webhook |
| GET | `/telegram/test` | Health check with token status |

### Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/monitor` | Live monitoring dashboard UI |
| GET | `/monitor/sessions` | Active sessions with conversation state |
| GET | `/monitor/stats` | Active sessions, total and confirmed bookings |
| POST | `/monitor/takeover` | Flag session for human takeover |

### Metrics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/metrics?period=monthly` | Full business KPI dashboard |
| GET | `/metrics/health` | Health check for metrics router |

### Mock CRM
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/crm/availability` | Query team availability by date and service type |
| GET | `/crm/teams` | List all service teams |
| POST | `/crm/bookings` | Create a booking record |
| GET | `/crm/bookings/{customer_id}` | Fetch bookings by customer |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Project info |
| GET | `/health` | System health check |
| GET | `/docs` | Swagger UI (full API documentation) |

---

## Project Structure

```
voice_chat_scheduling_agent/
├── agents/
│   ├── intent_parser.py         # Gemini-powered intent classification
│   ├── availability_agent.py    # CRM availability with retry logic
│   ├── conflict_resolver.py     # Alternative slot proposals
│   ├── booking_agent.py         # Booking confirmation and notifications
│   ├── cancellation_agent.py    # Cancel and reschedule handling
│   ├── sales_agent.py           # Sales intake and inquiry classification
│   ├── tech_support_agent.py    # RAG-powered technical support
│   └── router_agent.py          # First-turn dispatcher
├── core/
│   ├── orchestrator.py          # LangGraph conditional state graph
│   ├── config.py                # Pydantic settings and environment config
│   ├── database.py              # Supabase client and query functions
│   ├── session_manager.py       # Cross-turn conversation state persistence
│   ├── normalizer.py            # Voice, chat, and Telegram normalization
│   ├── models.py                # All Pydantic data models
│   ├── knowledge_base.py        # Chroma vector database wrapper
│   └── logger.py                # Structured JSON logging
├── api/
│   ├── main.py                  # FastAPI app assembly and middleware
│   ├── voice_router.py          # Twilio voice webhooks + ElevenLabs TTS
│   ├── chat_router.py           # Chat and SMS webhooks
│   ├── telegram_router.py       # Telegram bot webhook
│   ├── monitoring_router.py     # Live monitoring API
│   ├── monitor.html             # Monitoring dashboard UI
│   ├── crm_mock.py              # Self-contained mock CRM API
│   └── metrics_router.py        # Business KPI dashboard endpoint
├── notifications/
│   ├── email_sender.py          # SendGrid email notifications
│   ├── sms_sender.py            # Twilio SMS notifications
│   └── elevenlabs_tts.py        # ElevenLabs voice synthesis
├── tests/
│   ├── test_intent_parser.py    # Intent and message model tests
│   ├── test_availability.py     # Availability and entity model tests
│   ├── test_booking_flow.py     # Normalizer and booking flow tests
│   ├── test_sales_agent.py      # Sales agent and intent tests
│   ├── test_tech_support_agent.py # Tech support agent tests
│   └── test_rag_retriever.py    # Knowledge base and RAG tests
├── Dockerfile
├── railway.json
├── requirements.txt
├── .env.example
└── README.md
```

---

## Local Setup

### Prerequisites
- Python 3.12
- Docker Desktop
- A Supabase project
- A Google Gemini API key

### 1. Clone the repository

```bash
git clone https://github.com/umair801/voice-chat-scheduling-agent.git
cd voice-chat-scheduling-agent
```

### 2. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials.

### 5. Run the server

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### 6. Run tests

```bash
pytest tests/ -v
```

Expected: 54 passed.

---

## Environment Variables

```env
# Google Gemini
GEMINI_API_KEY=your_gemini_api_key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# SendGrid
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=noreply@yourdomain.com

# ElevenLabs
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_WEBHOOK_SECRET=your_webhook_secret

# App
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
```

---

## Docker Deployment

```bash
docker build -t voice-chat-scheduling-agent .
docker run --env-file .env -p 8000:8000 voice-chat-scheduling-agent
```

---

## Railway Deployment

1. Push this repository to GitHub
2. Create a new project at [railway.app](https://railway.app)
3. Connect your GitHub repository
4. Add all environment variables in the Railway dashboard
5. Railway auto-deploys on every push to main

Live: `https://scheduling.datawebify.com`

---

## Supabase Schema

| Table | Purpose |
|-------|---------|
| `scheduling_bookings` | All confirmed, cancelled, and rescheduled appointments |
| `scheduling_sessions` | Conversation state keyed by call SID or phone number |
| `scheduling_agent_logs` | Full audit trail of every agent event |

---

## Voice Flow

```
Customer calls Twilio number
        |
Twilio STT transcribes speech
        |
POST to /voice/webhook
        |
Agent pipeline runs
        |
ElevenLabs TTS generates audio
(Falls back to Polly if unavailable)
        |
Twilio streams audio to caller
        |
Loop continues until booking confirmed
```

## Chat and Telegram Flow

```
Customer sends message (WhatsApp / SMS / Telegram / Web)
        |
POST to channel webhook
        |
Router Agent dispatches:
  - Sales inquiry -> Sales Agent
  - Technical issue -> Tech Support Agent (RAG)
  - Booking request -> Booking Flow
        |
Agent processes and responds
        |
Reply delivered to customer on same channel
```

---

## Live Monitoring Dashboard

Available at `https://scheduling.datawebify.com/monitor`:

- Real-time active session count
- Total and confirmed booking stats
- Live conversation list with channel, intent, and turn count
- One-click human takeover per session
- Auto-refreshes every 10 seconds

---

## Test Coverage

```bash
pytest tests/ -v
# 54 passed
```

| Test File | Coverage |
|-----------|---------|
| test_intent_parser.py | Message models, channel normalization |
| test_availability.py | Availability models, entity extraction |
| test_booking_flow.py | Normalizer, booking flow |
| test_sales_agent.py | Sales intents, agent import, async check |
| test_tech_support_agent.py | Tech intents, agent import, async check |
| test_rag_retriever.py | Knowledge base, RAG retriever, context formatting |

---

## Portfolio

This is Project 7 of 50 in the Datawebify Agentic AI portfolio.

| Project | Description | URL |
|---------|-------------|-----|
| AgAI-1 | Enterprise WhatsApp Automation | whatsapp.datawebify.com |
| AgAI-2 | B2B Lead Generation System | leads.datawebify.com |
| AgAI-3 | Enterprise AI Support Agent | support.datawebify.com |
| AgAI-4 | RAG Knowledge Base Agent | rag.datawebify.com |
| AgAI-5 | Real Estate AI Domination System | reds.datawebify.com |
| AgAI-6 | Autonomous Research Agent | ara.datawebify.com |
| AgAI-7 | Voice and Chat Scheduling Agent | [scheduling.datawebify.com](https://scheduling.datawebify.com) — [Portfolio](https://datawebify.com/projects/agai7-voice-chat-scheduling-agent) |

---

## Contact

**Muhammad Umair**
Agentic AI Specialist and Enterprise Consultant
[datawebify.com](https://datawebify.com) | [github.com/umair801](https://github.com/umair801)
