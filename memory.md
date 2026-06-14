# Receptionist Project — Memory

## Goal
Build and debug a voice receptionist agent for Alfalha Hospital using LiveKit Agents + Cal.com + MongoDB Atlas.

---

## Architecture

```
[Voice call] → LiveKit Cloud → Agent dispatched to room
                                    ↓
                     Voice conversation + MongoDB + Cal.com
```

---

## Current State — Fully Implemented

### Core Agent (`src/agent.py`)
- Warm receptionist "Jassey" with conversational speech (fillers, pauses, contractions)
- Tools: patient record creation, availability check, booking, cancellation, reschedule
- `on_enter()` → identifies caller by phone (from LinkedParticipant or console), loads recent bookings/summary
- `on_exit()` → saves conversation summary to MongoDB, updates booking status (rescheduled/cancelled)
- Console mode works via `try/except RuntimeError` on `room_io.linked_participant`
- Agent name in dispatch: **"Clinics Receptionist"**
- **System instructions rewritten (2026-06-14):** Follows LiveKit's recommended prompt structure (Identity → Output Rules → Goal → Speech Style → Conversation Flow → Tools → Format → Guardrails → User Context). Key additions:
  - **Guardrails section**: anti-hallucination rules (only speak facts from tools, never confirm uncompleted actions, ask for clarification when uncertain), scope boundaries (appointments only), privacy protection, honesty mandate
  - **Output rules**: TTS-optimized formatting — plain text, 1-3 sentences, no raw UIDs/IDs, conversational times, no exposing internals
  - **Read-back confirmation**: booking flow now requires reading details aloud before calling `create_booking`
  - **Voice realism**: phrase variation (rotate openers), self-correction (mid-sentence restarts), emotional baseline
  - **Dynamic date**: today's date is computed at runtime instead of hardcoded
  - **User context section**: explains injected context (patient ID, name, recent bookings, last summary)

### Cal.com Integration (`src/cal_tools.py`)
- **DB-aware constructor**: `CalToolset(db)` — receives MongoDB Database instance
- **`create_booking`** now accepts `patient_id` and saves booking to MongoDB after Cal.com success
- **Rate-limit retry**: unified `_request()` with exponential backoff (3 retries, ~1s→2s→4s + jitter) for 429 responses
- **Slot caching**: 30s TTL cache (`_slots_cache`) to avoid redundant API calls
- **`check_availability_bulk(slugs, date)`** — checks multiple event types in one call
- 5 event types: `30min` (General Consultation, 30m), `checkup` (Routine Checkup, 30m), `follow-up` (Follow-up, 15m), `secret` (Urgent, 15m), `new-patient` (New Patient Registration, 45m)
- All event types have `destinationCalendar` set to `hamziisalim0@gmail.com`
- Default schedule: Mon–Fri 07:00–12:00 Asia/Karachi

### MongoDB Integration (`src/database.py`)
- Async Motor client connected to MongoDB Atlas
- Collections: `patients`, `bookings`, `conversation_summaries`
- `ensure_indexes()` with `IndexOptionsConflict` retry logic
- Patients: create, find by phone/ID/name, update
- Bookings: create, find by phone, get recent, update status
- Summaries: create, get recent

### Data Models (`src/models.py`)
- `PatientData`: patient_id, first_name, last_name, phone, timestamps
- `BookingData`: patient_id, cal_booking_uid, event_type_slug, start_time, status, attendee info, timestamps
- `SummaryData`: patient_id, summary, booking_id, created_at

### Patient Tools (`src/patient_tools.py`)
- `create_patient_record(first_name, last_name, phone)` — stores new patient, returns patient ID

### Agent Instructions
- Prioritizes speed: ask type + date together, call ONE availability check, use `check_availability_bulk` when unsure
- Always pass `patient_id` to `create_booking`
- Clinic hours: Mon–Fri 7AM–12PM PKT
- Available appointment types listed in instructions

### Latency Fixes (2026-06-14)
- **Dynamic endpointing** (`min_delay=0.3`, `max_delay=2.0`) — replaces fixed 0.5s delay; adapts to conversation pause patterns
- **Preemptive TTS** — starts TTS synthesis before LLM finishes generating; overlaps compute with audio generation
- **`min_consecutive_speech_delay=0.3`** — natural breath gap between utterances without dead air
- **`BackgroundAudioPlayer`** with keyboard typing thinking sounds — fills silence during tool calls and LLM processing
- **Prewarmed VAD** via `setup_fnc` — loads Silero once at process startup, eliminates "inference is slower than realtime" warning
- **`QUAIL_VF_L` noise cancellation** — upgraded from `QUAIL_VF_S`; cleaner audio input improves turn detection confidence

---

## Running

```bash
./start.sh
```

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
| `CAL_API_KEY` | Cal.com API key (`cal_live_...`) |
| `CAL_USERNAME` | Cal.com username (`hamzii-salim-4xxmhu`) |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `COMPANY_NAME` | Clinic name for greeting |

---

## Git Branches
- **main** — base template
- **Database+Appointments-Done** — current branch with all DB + Cal.com features

---

## Files

| File | Purpose |
|------|---------|
| `src/agent.py` | Main voice agent (Assistant class, AgentServer) |
| `src/cal_tools.py` | Cal.com API tools (booking, availability, caching) |
| `src/database.py` | MongoDB async wrapper (Motor) |
| `src/models.py` | Dataclasses for Patient, Booking, Summary |
| `src/patient_tools.py` | create_patient_record tool |
| `start.sh` | Orchestrates agent process |
| `.env.local` | All credentials and config |
| `pyproject.toml` | Python dependencies |

---

## Testing
- Test booking created: `9LUZsNEp2yLQjxMhtwa6v8` (General Consultation, Mon June 15 7:30AM PKT)
- Patient test record: `PAT-826906` (Hamza Ali, +923359519916)
- Google Calendar verified: bookings appear on `hamziisalim0@gmail.com`
