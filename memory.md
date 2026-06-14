# Receptionist Project — Memory

## Goal
Build and deploy a voice receptionist agent for Alfalha Hospital using LiveKit Agents + Cal.com + MongoDB Atlas with permanent cross-call memory.

---

## Architecture

```
[Phone call] → LiveKit Cloud → Agent dispatched to room
                                    ↓
                Voice conversation + MongoDB + Cal.com
                                    ↓
          Caller identified by phone (SIP) → preload context
          Memory tools: remember/recall/list/forget facts
          Bookings auto-persisted to MongoDB after Cal.com
          LLM summary saved on call end
```

---

## Current State — Fully Implemented

### Core Agent (`src/agent.py`)
- **Identity**: "Jassey", warm conversational receptionist
- **Caller ID**: Extracts `sip.caller` from participant attributes; gracefully falls back to unknown caller in console mode
- **Preloaded context**: `preload_user_context(phone, db)` fetches patient profile + recent bookings + last conversation summary + memories; injects into `ChatContext` before session starts
- **Two greeting paths**: returning caller (known phone) greeted by name; unknown caller greeted generically
- **Patient Memory Tools** section in instructions (create_patient_record, remember_fact, recall_fact, list_facts, forget_fact)
- **`on_enter()`** branches on `patient_id` for returning-vs-new greeting
- **`on_exit()`** generates 2-3 sentence LLM summary of the conversation and persists via `db.add_summary()`
- **Cleanup**: `ctx.add_shutdown_callback()` closes MongoDB connection on shutdown
- Agent name in dispatch: **"Clinics Receptionist"**

### MongoDB Integration (`src/database.py`)
- **Single database**: `voice_agent_clinic`
- **Single collection**: `patients` — one document per patient with embedded sub-arrays:
  - `bookings[]` — `{cal_booking_uid, event_type_slug, start_time, status, attendee_name, attendee_email, attendee_timezone, created_at, updated_at}`
  - `conversation_summaries[]` — `{summary, created_at}`
  - `memories[]` — `{key, value, created_at, updated_at}`
- **Indexes**: `phone` (unique, sparse), `patient_id` (unique, sparse), `bookings.cal_booking_uid` (unique, partial filter)
- **CRUD**: find/create/update patient, add/get/update bookings, add/get summaries, remember/recall/list/forget facts
- All operations use `$push`, `$pull`, positional `$` on embedded arrays — no joins

### Cal.com Integration (`src/cal_tools.py`)
- 5 event types with retry + caching
- **DB-aware**: `set_patient_context(db, patient_id)` and `update_patient_id(pid)` methods
- `create_booking` persists to MongoDB after Cal.com success
- `reschedule_booking` / `cancel_booking` update booking status in MongoDB

### Patient Memory Tools (`src/memory_tools.py`)
- `PatientToolset` with 5 `@llm.function_tool` methods:
  - `create_patient_record(first_name, last_name, phone)` — creates patient, syncs `patient_id` to CalToolset
  - `remember_fact(key, value)` — upserts key-value fact in embedded `memories[]`
  - `recall_fact(key)` — retrieves a specific fact
  - `list_facts()` — lists all stored facts
  - `forget_fact(key)` — removes a fact

### Data Models (`src/models.py`)
- `PatientData` dataclass matching single-document schema

### Agent Instructions
- Full LiveKit-recommended prompt structure with guardrails, SSML, returning-vs-new greeting rules
- Patient Memory Tools section listing all 5 tools
- Dynamic `{_today}` date

---

## Deploying

### Start modes
| Mode | Command |
|------|---------|
| Production | `./start.sh` or `uv run python src/agent.py start` |
| Dev (auto-reload) | `uv run python src/agent.py dev` |
| Console (local test) | `uv run python src/agent.py console --text` |

### LiveKit Cloud deployment
1. Install LiveKit CLI: `lk --version`
2. From project dir: `lk app env -w` (loads secrets)
3. `lk agent create` (registers + deploys agent)
4. In LiveKit dashboard → Telephony → Dispatch Rules → add rule targeting **"Clinics Receptionist"**

### Dependencies
- `livekit-agents`, `livekit-api`, `livekit-plugins-silero`, `livekit-plugins-ai-coustics`, `livekit-plugins-turn-detector`
- `python-dotenv`, `httpx`, `motor`

---

## Environment Variables (`.env.local`)

| Variable | Purpose |
|----------|---------|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `CAL_API_KEY` | Cal.com API key |
| `CAL_USERNAME` | Cal.com username |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `COMPANY_NAME` | Clinic name for greeting |

---

## Git Branches
- **Database+Appointments-Done** — current (feature/permanent-memory built on top)

---

## Files

| File | Purpose |
|------|---------|
| `src/agent.py` | Main voice agent (Assistant, AgentServer, preload_user_context, caller ID) |
| `src/cal_tools.py` | Cal.com API tools (booking, availability, caching, DB persistence) |
| `src/database.py` | MongoDB async wrapper — single collection with embedded arrays |
| `src/memory_tools.py` | PatientToolset (create_patient_record, remember/recall/list/forget facts) |
| `src/models.py` | PatientData dataclass |
| `start.sh` | Production launch script |
| `plan.md` | Implementation plan (v2 — single-collection schema) |
| `.env.local` | All credentials |
| `pyproject.toml` | Python dependencies |

---

## Testing
- All 14 CRUD operations verified against live MongoDB Atlas
- Console mode (`--text`) — agent starts, connects to LiveKit Inference, session initializes
- Production mode — agent registers with LiveKit Cloud (India West region)
- Test patient: Ahmed Hassan (+923001112233) used for DB verification
