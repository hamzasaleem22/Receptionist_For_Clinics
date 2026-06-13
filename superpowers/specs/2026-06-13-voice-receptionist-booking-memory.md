# Voice Receptionist: Cal.com Booking & Returning Patient Memory

**Date:** 2026-06-13
**Status:** Draft
**Project:** Jessi Voice Agent (LiveKit Agents)

---

## Overview

Transform the current single-prompt voice receptionist agent into a persistent, memory-aware booking system. Patients call in via WhatsApp, get identified (by phone or patient ID), can book/reschedule/cancel appointments via Cal.com, and when they call again the agent remembers them and their booking history.

---

## Architecture

### Pattern: Supervisor Agent with Function Tools

A single `ReceptionistAgent` stays in control for the entire call. It uses `@function_tool()` methods to:

1. Identify the patient (phone number, patient ID lookup)
2. Check availability via Cal.com API
3. Create / reschedule / cancel bookings via Cal.com API
4. End the call gracefully

No multi-agent handoffs needed at this stage — the supervisor pattern keeps it simple. TaskGroups can be added later when multi-turn booking flows (date → time → confirm) become complex enough to warrant them.

### Flow

```
Incoming WhatsApp call
  → AcceptWhatsAppCall API creates room + dispatches agent
  → AgentSession starts with ReceptionistAgent
  → on_enter():
     1. Get caller's phone number from participant identity
     2. Look up patient in PostgreSQL
        - Found: load name + booking history into chat_ctx → greet by name
        - Not found: ask for name → create patient record
     3. Greet + offer options (book, reschedule, cancel, info)
  → LLM routes to appropriate tool
  → Tool calls Cal.com API
  → Agent confirms result to patient
  → Patient ends call → EndCallTool triggers cleanup
  → Store conversation summary in DB
```

---

## Component Design

### 1. Patient Database (PostgreSQL)

```sql
CREATE TABLE patients (
  id SERIAL PRIMARY KEY,
  phone TEXT,                           -- WhatsApp phone number
  patient_id TEXT UNIQUE,               -- Manual patient ID (fallback)
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bookings (
  id SERIAL PRIMARY KEY,
  patient_id INT REFERENCES patients(id),
  cal_booking_uid TEXT,                 -- Cal.com booking UID
  event_type_slug TEXT NOT NULL,        -- e.g. "checkup", "consultation"
  event_type_id INT,
  start_time TIMESTAMPTZ NOT NULL,
  status TEXT DEFAULT 'confirmed',      -- confirmed | rescheduled | cancelled
  attendee_name TEXT,
  attendee_email TEXT,
  attendee_timezone TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE conversation_summaries (
  id SERIAL PRIMARY KEY,
  patient_id INT REFERENCES patients(id),
  booking_id INT REFERENCES bookings(id),
  summary TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Patient Identification Strategy (ordered by priority):**
1. **WhatsApp phone number** — extracted from `participant_identity` or room metadata
2. **Patient ID** — if the patient was given a custom ID previously, they can recite it
3. **Name + phone fallback** — collect name, check if patient exists, create if not

### 2. Cal.com API Integration

| Tool | Cal.com API Endpoint | Method |
|---|---|---|
| `check_availability` | `GET /v2/slots?eventTypeId=X&start=...&end=...` | Public (no auth) |
| `create_booking` | `POST /v2/bookings` | Public (no auth) |
| `reschedule_booking` | `POST /v2/bookings/:uid/reschedule` | Requires auth |
| `cancel_booking` | `POST /v2/bookings/:uid/cancel` | Requires auth |
| `list_event_types` | `GET /v2/event-types` | Requires auth |

All tools use `utils.http_context.http_session()` for connection pooling.

**Cal.com authentication flow:**
- Public endpoints (availability check, create booking): no API key needed
- Mutating endpoints (reschedule, cancel): Pass `Authorization: Bearer <cal_api_key>` header
- API key stored in `.env.local` as `CAL_API_KEY`

### 3. Returning Patient Memory

**On session start (entrypoint):**
1. Extract phone number from `ctx.room.remote_participants` or participant attributes
2. Query PostgreSQL: `SELECT * FROM patients WHERE phone = :phone`
3. If found:
   - Load `first_name`, `last_name`
   - Load last 3 bookings with status
   - Load recent conversation summary
   - Inject into `ChatContext` as assistant messages
4. If not found:
   - Listen for name collection from the agent
   - Create patient record after name is gathered

**On session end:**
1. Generate a summary of what happened (booked/rescheduled/cancelled)
2. Store in `conversation_summaries` table
3. Update any booking records

### 4. Call End Rule

Two ways to end the call:

**A) Patient hangs up (WhatsApp disconnect):**
- WhatsApp sends `call terminate` webhook
- Webhook handler calls `DisconnectWhatsAppCall` with `USER_INITIATED`
- LiveKit detects disconnect → triggers `close` event on room
- `close_on_disconnect` (default) shuts down AgentSession
- `on_exit` hook stores conversation summary

**B) Agent ends call (EndCallTool):**
- LLM decides call is complete (booking confirmed, patient satisfied)
- Calls the prebuilt `EndCallTool`
- `EndCallTool` calls `session.shutdown()` → triggers cleanup
- In `on_exit` → store summary → cleanup room

```python
from livekit.agents.prebuilt.tools import EndCallTool

class ReceptionistAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="...",
            tools=[EndCallTool()],
        )
    
    async def on_exit(self):
        # Store conversation summary
        await store_summary(self.session.userdata)
```

---

## File Structure

```
Jessi/src/
├── agent.py              # Entrypoint + ReceptionistAgent
├── __init__.py
├── database.py           # PostgreSQL client + queries
├── cal_tools.py          # Cal.com API function tools
└── models.py             # Dataclasses (PatientData, BookingData)
```

---

## Dependencies (pyproject.toml additions)

```
livekit-agents[silero,turn-detector]~=1.5  (already present)
asyncpg                                    # async PostgreSQL driver
```

---

## LiveKit Docs References

| Concept | Doc Path |
|---|---|
| Function tools | `/agents/logic/tools/definition` |
| External data / initial context | `/agents/logic/external-data` |
| Supervisor pattern | `/agents/logic/supervisor-pattern` |
| WhatsApp Connector | `/telephony/connectors/whatsapp` |
| Chat context | `/agents/logic/chat-context` |
| Participant attributes | `/transport/data/state/participant-attributes` |
| Job lifecycle / metadata | `/agents/server/job` |
| Room metadata | `/transport/data/state/room-metadata` |
| Agent session | `/agents/logic/sessions` |
| EndCallTool | `/agents/prebuilt/tools/end-call-tool` |
| Agent handoffs | `/agents/logic/agents-handoffs` |

---

## Out of Scope (for this phase)

- SMS confirmations / reminders
- Knowledge base Q&A (hours, insurance, prep)
- Multi-agent handoffs (single supervisor is sufficient for now)
- TaskGroups for multi-turn collection (add when needed)
