---
goal: Add permanent cross-call memory for the voice receptionist agent using pre-loaded user context + function-tool CRUD + session persistence (no vector search/RAG)
version: 1.0
date_created: 2026-06-15
owner: Receptionist Dev
status: Planned
tags: feature, memory, mongodb, receptionist
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan adds **permanent cross-call memory** to the Alfalha Hospital voice receptionist. When a returning caller phones again, the agent pre-loads their profile, past bookings, and conversation history from MongoDB into the ChatContext *before the session starts*. The LLM begins the call already knowing who they are and what happened last time — no RAG, no vector search, no embeddings.

## 1. Requirements & Constraints

- **REQ-001**: Caller must be identified by phone number (available from SIP participant attributes via `room_io.linked_participant`)
- **REQ-002**: On call start, pre-load patient profile + recent bookings + last conversation summary into ChatContext
- **REQ-003**: During call, provide function tools to remember/recall facts about the patient
- **REQ-004**: On call end, generate and persist a conversation summary to MongoDB
- **REQ-005**: Must NOT use vector search, embeddings, or RAG — only simple MongoDB queries
- **REQ-006**: Must reuse existing `motor` dependency and `MONGODB_URI` environment variable
- **REQ-007**: Must handle console mode fallback (no SIP caller ID) with a default user
- **REQ-008**: Updated bookings (rescheduled/cancelled) in current call must persist to MongoDB
- **CON-001**: No external embedding service (Voyage AI) — keep dependencies minimal
- **CON-002**: MongoDB Atlas already configured in `.env.local` — reuse existing cluster
- **PAT-001**: Follow the MongoDB starter repo's preload_user pattern: fetch → build ChatContext → pass to Agent constructor
- **PAT-002**: Follow LiveKit docs' chat context pattern: `chat_ctx.add_message(role="assistant", content=...)` for preloaded context

## 2. Implementation Steps

### Implementation Phase 1: Database Layer

- GOAL-001: Rebuild MongoDB async database module with patient, booking, conversation summary, and memory CRUD operations

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `src/database.py` with async MongoDB client (Motor), `ensure_indexes()`, `close()`, and CRUD operations for patients, bookings, conversation summaries, and memory slots | | |
| TASK-002 | Create `src/models.py` with dataclasses: `PatientData`, `BookingData`, `SummaryData`, `MemoryData` | | |
| TASK-003 | Wire database init into `agent.py` entrypoint with lazy singleton pattern | | |

**TASK-001 Details** — Create `src/database.py`:

```python
class Database:
    def __init__(self, uri: str | None = None, db_name: str = "receptionist")
    
    async def ensure_indexes(self) -> None
    async def close(self) -> None
    
    # Patients
    async def find_patient_by_phone(self, phone: str) -> PatientData | None
    async def find_patient_by_id(self, patient_id: str) -> PatientData | None
    async def create_patient(self, first_name, last_name, phone=None) -> str  # patient_id
    async def update_patient(self, patient_id, updates: dict) -> None
    
    # Bookings
    async def get_recent_bookings(self, patient_id, limit=3) -> list[BookingData]
    async def create_booking(self, patient_id, cal_booking_uid, event_type_slug, start_time, attendee_name, attendee_email, attendee_timezone) -> str
    async def update_booking_status(self, cal_booking_uid, status) -> None
    
    # Conversation Summaries
    async def create_summary(self, patient_id, summary, booking_id=None) -> str
    async def get_recent_summary(self, patient_id) -> str | None
    
    # Memory slots (key-value per patient, no vector search)
    async def remember(self, patient_id, key, value) -> None
    async def recall(self, patient_id, key) -> str | None
    async def list_memories(self, patient_id) -> list[dict]
    async def forget(self, patient_id, key) -> None
```

Indexes to create:
- `patients.phone` — unique sparse index for caller lookup
- `patients.patient_id` — unique sparse index
- `bookings.patient_id + created_at` — compound index for recent bookings query
- `bookings.cal_booking_uid` — unique sparse index
- `conversation_summaries.patient_id + created_at` — compound index
- `memories.patient_id + key` — unique compound index for upserts

**TASK-002 Details** — Create `src/models.py`:

```python
@dataclass
class PatientData:
    patient_id: str
    first_name: str
    last_name: str
    phone: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

@dataclass
class BookingData:
    patient_id: str
    cal_booking_uid: str
    event_type_slug: str
    start_time: datetime
    status: str = "confirmed"
    attendee_name: str = ""
    attendee_email: str = ""
    attendee_timezone: str = "UTC"
    created_at: datetime | None = None
    updated_at: datetime | None = None

@dataclass
class SummaryData:
    patient_id: str
    summary: str
    booking_id: str | None = None
    created_at: datetime | None = None

@dataclass
class MemoryData:
    patient_id: str
    key: str
    value: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

**TASK-003 Details**: In `agent.py`, instantiate `Database()` as module-level singleton (same pattern as `cal_tools`). Call `ensure_indexes()` once at startup in the entrypoint before the first session.

---

### Implementation Phase 2: Preload User Context

- GOAL-002: Identify caller by phone and pre-load profile + bookings + summary into ChatContext before session starts

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add caller phone extraction from SIP participant attributes in the entrypoint | | |
| TASK-005 | Create `preload_user_context(phone, db)` function that builds ChatContext | | |
| TASK-006 | Wire `preload_user_context` into the entrypoint and pass `chat_ctx` to `Assistant()` | | |
| TASK-007 | Modify `Assistant.__init__` to accept optional `chat_ctx` and `patient_id` | | |
| TASK-008 | Update `on_enter` to greet returning vs. new callers based on preloaded context | | |

**TASK-004 Details**: In the `@server.rtc_session` entrypoint, extract the caller's phone number:
```python
# SIP caller ID from telephony participant attributes
caller_phone = None
try:
    # LiveKit injects caller phone via linked participant in SIP rooms
    participant = room_io.linked_participant(ctx.room)
    if participant and participant.attributes:
        caller_phone = participant.attributes.get("sip.call_id", {}).get("from")
        # Or: participant.identity might contain the phone number
except Exception:
    pass  # Console mode or missing SIP metadata; fall back to asking
```
Fallback for console mode: `caller_phone = None` — the agent asks for name and phone naturally.

**TASK-005 Details** — `preload_user_context(phone, db)` function:
```python
async def preload_user_context(phone: str | None, db: Database) -> tuple[ChatContext, PatientData | None]:
    """Look up caller by phone, load profile + bookings + summary into ChatContext.
    
    Returns (chat_ctx, patient) where patient is None for first-time callers.
    """
    chat_ctx = ChatContext()
    
    if not phone:
        chat_ctx.add_message(
            role="assistant",
            content="No caller ID available. This caller is unknown — greet them as a new patient and ask for their name and phone number."
        )
        return chat_ctx, None
    
    patient = await db.find_patient_by_phone(phone)
    
    if not patient:
        chat_ctx.add_message(
            role="assistant",
            content="This phone number is not in our records. Greet the caller as a new patient and ask for their name to create a record."
        )
        return chat_ctx, None
    
    # Build context message for known patient
    context_parts = [
        f"Returning patient: {patient.first_name} {patient.last_name} (ID: {patient.patient_id})."
    ]
    
    # Add recent bookings
    bookings = await db.get_recent_bookings(patient.patient_id, limit=3)
    if bookings:
        booking_lines = []
        for b in bookings:
            time_str = b.start_time.strftime("%A %B %d at %I:%M %p")
            booking_lines.append(f"- {b.event_type_slug} on {time_str} (Status: {b.status}, UID: {b.cal_booking_uid})")
        context_parts.append("Their recent bookings:\n" + "\n".join(booking_lines))
    
    # Add last conversation summary
    summary = await db.get_recent_summary(patient.patient_id)
    if summary:
        context_parts.append(f"Summary of their last call:\n{summary}")
    
    # Add remembered facts
    memories = await db.list_memories(patient.patient_id)
    if memories:
        memory_lines = [f"- {m['key']}: {m['value']}" for m in memories]
        context_parts.append("Remembered facts about this patient:\n" + "\n".join(memory_lines))
    
    chat_ctx.add_message(
        role="assistant",
        content="\n\n".join(context_parts)
    )
    
    return chat_ctx, patient
```

**TASK-006 Details**: Wire into entrypoint:
```python
caller_phone = await _get_caller_phone(ctx)
initial_ctx, patient = await preload_user_context(caller_phone, db)

await session.start(
    room=ctx.room,
    agent=Assistant(
        chat_ctx=initial_ctx,
        patient_id=patient.patient_id if patient else None,
    ),
    ...
)
```

**TASK-007 Details**: `Assistant.__init__` changes:
```python
class Assistant(Agent):
    def __init__(self, chat_ctx: ChatContext | None = None, patient_id: str | None = None) -> None:
        self._patient_id = patient_id
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=f"""...
## User context
The following context about this caller has been pre-loaded from our records.
- Patient ID: {patient_id or 'New caller — not yet identified'}
...
"""
        )
```

**TASK-008 Details**: Update `on_enter`:
```python
async def on_enter(self) -> None:
    if self._patient_id:
        await self.session.generate_reply(
            instructions="Greet the returning patient warmly by name. Reference their last visit or booking if known. Ask how you can help today."
        )
    else:
        await self.session.generate_reply(
            instructions="Greet the caller warmly as a receptionist from Alfalha Hospital. Ask for their name and phone number to look them up or create a new record."
        )
```

---

### Implementation Phase 3: Memory Tools (Function-tool CRUD)

- GOAL-003: Add LLM-callable tools to remember, recall, and manage patient facts during the conversation

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `src/memory_tools.py` with `PatientToolset` class extending `llm.Toolset` | | |
| TASK-010 | Add `remember_fact`, `recall_fact`, `list_facts`, `forget_fact` function tools | | |
| TASK-011 | Wire `PatientToolset` into `Assistant.__init__` alongside other tools | | |

**TASK-009 Details** — `src/memory_tools.py`:
```python
class PatientToolset(llm.Toolset):
    def __init__(self, db: Database, patient_id: str | None = None) -> None:
        super().__init__(id="patient")
        self._db = db
        self._patient_id = patient_id
    
    def set_patient_id(self, patient_id: str) -> None:
        self._patient_id = patient_id
```

**TASK-010 Details** — Function tools:
```python
@llm.function_tool
async def create_patient_record(
    self,
    first_name: str,
    last_name: str,
    phone: Annotated[str | None, "Phone including country code, e.g. +923001234567"] = None,
) -> str:
    """Create a new patient record. Call this when a new patient provides their name.
    After creating, the patient_id is automatically remembered for the rest of the call."""
    ...

@llm.function_tool
async def remember_fact(
    self,
    key: Annotated[str, "Short label like 'preferred_time', 'allergy', 'insurance_provider'"],
    value: str,
) -> str:
    """Store a fact about this patient that you want to remember across calls.
    Use for preferences, allergies, insurance info, or any detail the patient volunteers."""
    ...

@llm.function_tool
async def recall_fact(
    self,
    key: str,
) -> str:
    """Retrieve a stored fact by its exact label. Returns 'No fact found' if not set."""
    ...

@llm.function_tool
async def list_facts(self) -> str:
    """List all stored facts about this patient, newest first."""
    ...

@llm.function_tool
async def forget_fact(self, key: str) -> str:
    """Delete a stored fact by its exact label."""
    ...
```

**TASK-011 Details**: In `Assistant.__init__`:
```python
self._patient_tools = PatientToolset(db, patient_id)
super().__init__(
    ...
    tools=[*end_call.tools, cal_tools, self._patient_tools],
)
```
When `create_patient_record` succeeds for a new caller, call `self._patient_tools.set_patient_id(new_id)` to link subsequent memory operations.

---

### Implementation Phase 4: Session Persistence

- GOAL-004: Save conversation summary and update booking statuses when the call ends

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Implement `on_exit` to generate a summary using the LLM and persist it to MongoDB | | |
| TASK-013 | Wire `on_session_end` callback to close the DB connection cleanly | | |
| TASK-014 | Update `CalToolset.create_booking` to persist booking to MongoDB after Cal.com success | | |

**TASK-012 Details** — `on_exit`:
```python
async def on_exit(self) -> None:
    if not self._patient_id:
        return
    try:
        # Generate a concise summary of the conversation
        await self.session.generate_reply(
            instructions=(
                "The call is ending. Summarize what happened in this call in 2-3 sentences: "
                "what the patient asked about, what was booked/rescheduled/cancelled, "
                "and any important facts or preferences they mentioned. "
                "This summary will be saved for next time they call."
            ),
        )
        # The summary is in chat_ctx — extract and save
        summary_text = self._extract_summary_from_context()
        if summary_text:
            await db.create_summary(self._patient_id, summary_text)
    except Exception:
        logger.exception("Failed to save conversation summary")
```

**TASK-013 Details**: Add `on_session_end` callback to close the MongoDB client:
```python
async def _on_session_end(ctx: JobContext) -> None:
    await db.close()
```

**TASK-014 Details**: In `CalToolset.__init__`, accept `db: Database`. In `create_booking`, after successful Cal.com API response:
```python
# After Cal.com booking succeeds
if self._db and patient_id:
    start = datetime.fromisoformat(booking.get("start", start_time).replace("Z", "+00:00"))
    await self._db.create_booking(
        patient_id=patient_id,
        cal_booking_uid=uid,
        event_type_slug=event_type_slug,
        start_time=start,
        attendee_name=attendee_name,
        attendee_email=resolved_email,
        attendee_timezone=attendee_timezone,
    )
```
Update `cal_tools.py` to accept patient_id from the tool call.

---

### Implementation Phase 5: Wire Everything Together

- GOAL-005: Integrate all components into a working entrypoint

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Update `agent.py` entrypoint to orchestrate: DB init → caller ID → preload → session start → background audio | | |
| TASK-016 | Update `pyproject.toml` if needed (motor already listed) | | |
| TASK-017 | Clean up stale `__pycache__` files from deleted modules | | |

**TASK-015 Details**: The final entrypoint flow:
```python
db = Database()
cal_tools = CalToolset(db)

async def _get_caller_phone(ctx: agents.JobContext) -> str | None:
    # Extract from SIP participant attributes
    ...

@server.rtc_session(agent_name="Clinics Receptionist", on_session_end=_on_session_end)
async def my_agent(ctx: agents.JobContext) -> None:
    await db.ensure_indexes()
    await cal_tools.sync_event_type_names()
    
    caller_phone = await _get_caller_phone(ctx)
    initial_ctx, patient = await preload_user_context(caller_phone, db)
    
    session = AgentSession(...)
    
    await session.start(
        room=ctx.room,
        agent=Assistant(
            chat_ctx=initial_ctx,
            patient_id=patient.patient_id if patient else None,
        ),
        room_options=...,
    )
    
    bg = BackgroundAudioPlayer(...)
    await bg.start(room=ctx.room, agent_session=session)
```

---

## 3. Alternatives

- **ALT-001 (RAG with `$vectorSearch`)**: Requires Voyage AI API key and MongoDB vector search index. More complex to set up and maintain. Overkill for simple fact recall. (Rejected as per user constraint)
- **ALT-002 (Agentic memory with `$rankFusion`)**: Requires MongoDB 8.0+ and Voyage AI embeddings. Adds an external embedding dependency. Not needed since we only do exact key-value lookups. (Rejected as per user constraint)
- **ALT-003 (Engram memory plugin)**: Third-party memory service. Adds another API key and dependency. Less control over data. (Rejected for simplicity)
- **ALT-004 (Sync all Cal.com bookings on every call via API)**: Avoids MongoDB entirely but means every call requires a full Cal.com API sync. Slower and rate-limit prone. (Rejected)

## 4. Dependencies

- **DEP-001**: `motor>=3.4` — already in `pyproject.toml`, no change needed
- **DEP-002**: MongoDB Atlas cluster — already configured in `.env.local` as `MONGODB_URI`
- **DEP-003**: No new packages required

## 5. Files

- **FILE-001**: `Receptionist/src/database.py` — New file. Async MongoDB CRUD operations
- **FILE-002**: `Receptionist/src/models.py` — New file. Patient/Booking/Summary/Memory dataclasses
- **FILE-003**: `Receptionist/src/memory_tools.py` — New file. PatientToolset with remember/recall tools
- **FILE-004**: `Receptionist/src/agent.py` — Modified. Add preloading, caller ID, chat_ctx, on_exit, entrypoint changes
- **FILE-005**: `Receptionist/src/cal_tools.py` — Modified. Accept db reference, persist bookings to MongoDB

## 6. Testing

- **TEST-001**: Console mode works with no SIP caller ID — agent asks for name and phone
- **TEST-002**: Returning caller with phone in DB gets greeted by name with booking context
- **TEST-003**: `remember_fact` / `recall_fact` persist across simulated sessions
- **TEST-004**: Booking created via Cal.com also appears in MongoDB `bookings` collection
- **TEST-005**: Conversation summary saved to MongoDB on call end
- **TEST-006**: Indexes created successfully on first run

## 7. Risks & Assumptions

- **RISK-001**: SIP caller phone extraction depends on LiveKit telephony attributes format. If the format differs, phone extraction may fail and fall back to asking the caller.
- **RISK-002**: Console mode (no SIP) cannot identify the caller — agent must ask. This is handled gracefully.
- **RISK-003**: LLM-generated conversation summaries may vary in quality. Consider setting a fixed max token limit for the summary.
- **ASSUMPTION-001**: MongoDB Atlas connection string in `.env.local` is valid and the cluster is accessible.
- **ASSUMPTION-002**: The `motor` package's async API is compatible with the LiveKit agents async event loop.

## 8. Related Specifications / Further Reading

- [LiveKit Docs: Chat Context — Initialize with user data](https://docs.livekit.io/agents/logic/chat-context/#initialize-with-user-data)
- [LiveKit Docs: External data and RAG — Initial context](https://docs.livekit.io/agents/logic/external-data/#initial-context)
- [LiveKit Docs: Pipeline nodes & hooks — on_user_turn_completed](https://docs.livekit.io/agents/logic/nodes.md)
- [MongoDB Starter Repo: Pre-loaded user context pattern](https://github.com/livekit-examples/mongodb-hacker-starter/blob/main/agent-py/src/agent.py)
- [LiveKit Docs: Function tools](https://docs.livekit.io/agents/logic/tools/definition/)
