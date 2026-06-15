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
          Caller identified by SIP phone (sip.phoneNumber)
          Memory tools: remember/recall/list/forget facts
          Bookings auto-persisted to MongoDB after Cal.com
          Auto-memory (last_booked) stored on booking
          Structured summary saved on call end
```

---

## Current State — Fully Implemented & Fixed

### Core Agent (`src/agent.py`)
- **Identity**: "Jassey", warm conversational receptionist
- **Caller ID**: Uses `ctx.wait_for_participant()` + `sip.phoneNumber` (LiveKit standard SIP attribute). Phone normalized to digits only. 10s timeout for console fallback.
- **Phone auto-captured**: Agent never asks caller for phone number — it's extracted automatically from SIP attributes
- **Preloaded context**: `preload_user_context(phone, db)` fetches patient profile + recent bookings + last conversation summary + memories; injects into `ChatContext` before session starts
- **Two greeting paths**: returning caller (known phone) greeted by name; unknown caller greeted generically
- **Patient Memory Tools** section in instructions (create_patient_record, remember_fact, recall_fact, list_facts, forget_fact)
- **`on_enter()`** branches on `patient_id` for returning-vs-new greeting
- **`on_exit()`** reads recent booking from DB and saves structured summary via `db.add_summary()` — no dependency on `session.chat_ctx` (which is cleared before on_exit fires)
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
- **Duplicate-safe create_patient**: checks existing phone first → updates name → returns existing patient_id. DuplicateKeyError safety net for race conditions
- All operations use `$push`, `$pull`, positional `$` on embedded arrays

### Cal.com Integration (`src/cal_tools.py`)
- 5 event types with retry + caching
- **DB-aware**: `set_patient_context(db, patient_id)` and `update_patient_id(pid)` methods
- `create_booking` persists to MongoDB + auto-stores `last_booked` fact in memories
- `reschedule_booking` / `cancel_booking` update booking status in MongoDB

### Patient Memory Tools (`src/memory_tools.py`)
- `PatientToolset` with 5 `@llm.function_tool` methods:
  - `create_patient_record(first_name, last_name, phone)` — creates or finds patient, syncs `patient_id` to CalToolset
  - `remember_fact(key, value)` — upserts key-value fact in embedded `memories[]`
  - `recall_fact(key)` — retrieves a specific fact
  - `list_facts()` — lists all stored facts
  - `forget_fact(key)` — removes a fact

### Data Models (`src/models.py`)
- `PatientData` dataclass matching single-document schema

### Agent Instructions
- Full LiveKit-recommended prompt structure with guardrails, SSML, returning-vs-new greeting rules
- Agent never asks for phone number (auto-captured from SIP)
- Patient Memory Tools section listing all 5 tools
- Dynamic `{_today}` date

---

## Issues Resolved (2026-06-15)

See `issue.md` and `plan/fix-permanent-memory-issues.md` for full details.

| # | Issue | Fix |
|---|-------|-----|
| 1 | Returning caller not recognized | Changed `sip.caller` → `sip.phoneNumber`, use `wait_for_participant()`, normalize phone to digits |
| 2 | `create_patient_record` crashes on duplicate | Check existing phone first → update name → return existing ID |
| 3 | `conversation_summaries` always empty | `on_exit` reads recent bookings from DB instead of cleared session chat_ctx |
| 4 | `memories` always empty | Auto-store `last_booked` fact in `create_booking()` |
| 5 | Empty `last_name` | `create_patient()` updates existing patient fields when phone matches |

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
- **Memory-Successful** — feature/permanent-memory
- **Memory-Issue-Resolved** — latest: 5 memory bugs fixed

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
| `issue.md` | Issue analysis — 5 problems found |
| `plan/fix-permanent-memory-issues.md` | Fix plan + checklist |
| `plan/feature-permanent-memory-1.md` | Original implementation plan |
| `.env.local` | All credentials |
| `pyproject.toml` | Python dependencies |

---

## Testing
- All 14 CRUD operations verified against live MongoDB Atlas
- Console mode (`--text`) — agent starts, connects to LiveKit Inference, session initializes
- Production mode — agent registers with LiveKit Cloud (India West region)
- Phone normalization: `+923503070436` → `923503070436`
- Duplicate-safe patient creation verified
- Auto-memory `last_booked` stored on booking create
- Summary saves reliably on call end (no dependency on session state)
