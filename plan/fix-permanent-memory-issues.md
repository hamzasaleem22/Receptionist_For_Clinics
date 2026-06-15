---
goal: Fix all 5 permanent memory issues (phone mismatch, duplicate crash, empty summaries, empty memories, missing updates)
version: 1.0
date_created: 2026-06-15
status: 'Completed'
tags: feature, bug, memory, telephony
---

# Fix All Permanent Memory Issues

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Fix the 5 issues identified from call logs: returning caller not recognized, `create_patient_record` crashes on duplicate, no summaries saved, no auto-memories, and missing update capability.

## 1. Requirements & Constraints

- **REQ-001**: Returning callers must be recognized by SIP phone number without asking
- **REQ-002**: `create_patient_record` must not crash on duplicate phone; return existing patient ID
- **REQ-003**: Conversation summaries must be persisted to MongoDB after each call
- **REQ-004**: Facts/memories should be auto-stored when bookings are made
- **REQ-005**: Patient `last_name` must be updatable when caller provides it
- **CON-001**: No vector search, no RAG — MongoDB only
- **CON-002**: Reuse existing `motor` dependency and env vars
- **PAT-001**: Normalize phone to just digits everywhere (strip `+`, spaces, dashes)

## 2. Implementation Steps

### Phase 1: Fix Phone Number Extraction from SIP

- GOAL-001: Replace `_get_caller_phone()` with correct LiveKit API

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Replace `room_io.linked_participant` + `sip.caller` with `ctx.wait_for_participant()` + `sip.phoneNumber` | ✅ | 2026-06-15 |
| TASK-002 | Add `phone`-based fallback from console mode when no SIP participant | ✅ | 2026-06-15 |
| TASK-003 | Normalize phone to digits only (strip `+`, spaces, dashes) | ✅ | 2026-06-15 |
| TASK-004 | Update `_get_caller_phone` to accept `ctx` instead of `JobContext` or pass participant directly | ✅ | 2026-06-15 |

### Phase 2: Fix `create_patient_record` to Handle Duplicates

- GOAL-002: Use upsert pattern instead of insert_one so duplicate phone returns existing patient

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Check existing phone before insert; update first_name/last_name if found | ✅ | 2026-06-15 |
| TASK-006 | Return existing `patient_id` when phone already exists (including DuplicateKeyError safety net) | ✅ | 2026-06-15 |
| TASK-007 | Update `memory_tools.create_patient_record` to handle both new and existing patient IDs | ✅ | 2026-06-15 |

### Phase 3: Fix Conversation Summary Persistence

- GOAL-003: Ensure summaries are generated and saved before session closes

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Replace LLM-based summary with simple structured summary from recent bookings | ✅ | 2026-06-15 |
| TASK-009 | Remove dependency on `self.session.chat_ctx` (cleared before on_exit fires) | ✅ | 2026-06-15 |
| TASK-010 | Always save a summary even when no bookings exist | ✅ | 2026-06-15 |

### Phase 4: Add Auto-Memory When Booking Created

- GOAL-004: Automatically store a memory fact when a booking is created

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Add `remember_fact` call inside `CalToolset.create_booking` after successful booking — stores `last_booked` fact | ✅ | 2026-06-15 |
| TASK-012 | Update LLM instructions to encourage memory storage for preferences | ✅ | 2026-06-15 |

### Phase 5: Add Patient Update Capability

- GOAL-005: Allow updating existing patient fields (last_name, etc.)

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | `update_patient` already existed in `Database` class | ✅ | 2026-06-15 |
| TASK-014 | `create_patient` now calls `update_patient` when phone matches existing record | ✅ | 2026-06-15 |

## 3. Alternatives

- **ALT-001**: Store phone in E.164 format in DB instead of normalized digits — rejected because speech-to-text gives local format (`03...`)
- **ALT-002**: Use separate `find_patient_by_phone` + `insert_one` in tool — rejected; upsert is atomic and handles race conditions
- **ALT-003**: Use `session.on("disconnect")` event — rejected; `ctx.add_shutdown_callback` already exists and runs reliably

## 4. Dependencies

- **DEP-001**: `livekit.agents` >= 1.5.0 (for `wait_for_participant`)
- **DEP-002**: `motor` >= 3.4 (already installed)

## 5. Files

- **FILE-001**: `src/agent.py` — `_get_caller_phone`, `preload_user_context`, `my_agent` entrypoint
- **FILE-002**: `src/database.py` — `create_patient` method
- **FILE-003**: `src/memory_tools.py` — `create_patient_record` tool
- **FILE-004**: `src/cal_tools.py` — `create_booking` method for auto-memory

## 6. Testing

- **TEST-001**: Phone normalization: `+923503070436` → `923503070436`
- **TEST-002**: Duplicate phone: calling `create_patient` twice returns same patient_id
- **TEST-003**: Summary: verify `conversation_summaries` array has entry after call ends
- **TEST-004**: Memory: verify `memories` array has "last_booked" entry after booking created

## 7. Risks & Assumptions

- **RISK-001**: `wait_for_participant` may block indefinitely if participant never joins — mitigated by timeout
- **ASSUMPTION-001**: SIP `sip.phoneNumber` is always in E.164 format
- **ASSUMPTION-002**: Console mode has no participant, so phone will be None
