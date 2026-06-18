---
goal: Fix backend stability issues - singleton race condition, useless summaries, raw UID leaks, env var dead code, unbounded cache, recursion risk
version: 1.0
date_created: 2026-06-19
status: 'Completed'
tags: bug, refactor, stability, security
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Fix 6 concrete issues discovered in the Receptionist voice agent backend that cause data corruption, poor patient experience, and latent bugs.

## 1. Requirements & Constraints

- **REQ-001**: CalToolset must not share mutable state between concurrent calls
- **REQ-002**: on_exit must save meaningful conversation summaries, not just "Call ended"
- **REQ-003**: Tool outputs must not leak raw booking UIDs to the LLM
- **REQ-004**: COMPANY_NAME env var must actually control the clinic name in the prompt
- **REQ-005**: Slots cache must not grow unboundedly across calls
- **REQ-006**: _generate_patient_id must have a max retries guard
- **CON-001**: All fixes must pass existing test suite
- **PAT-001**: Keep LiveKit Agent patterns (Toolset, AgentSession, inference)

## 2. Implementation Steps

### Implementation Phase 1: Eliminate Singleton Race Condition

- GOAL-001: Convert CalToolset from shared singleton to per-call instance

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Remove module-level `_cal_tools` singleton and `get_cal_tools()` function | ✅ | 2026-06-19 |
| TASK-002 | Create CalToolset instance inside `my_agent()` per-call | ✅ | 2026-06-19 |
| TASK-003 | Pass CalToolset instance to Assistant.__init__ and PatientToolset | ✅ | 2026-06-19 |
| TASK-004 | Remove `set_patient_context()` from CalToolset — pass db/patient_id via constructor | ✅ | 2026-06-19 |
| TASK-005 | Update PatientToolset to receive CalToolset reference from Assistant, not from singleton | ✅ | 2026-06-19 |

### Implementation Phase 2: Meaningful on_exit Summaries

- GOAL-002: Save actual conversation content to MongoDB when call ends

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Access session.history in on_exit to extract conversation content | ✅ | 2026-06-19 |
| TASK-007 | Build summary from LLM chat history instead of just booking status | ✅ | 2026-06-19 |
| TASK-008 | Ensure summary includes patient name, reason for call, and outcome | ✅ | 2026-06-19 |

### Implementation Phase 3: Sanitize Tool Outputs

- GOAL-003: Remove raw booking UIDs from create_booking return value

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Replace raw UID in create_booking return with patient-friendly message | ✅ | 2026-06-19 |
| TASK-010 | Verify cancel/reschedule also don't leak internal IDs | ✅ | 2026-06-19 |

### Implementation Phase 4: Use COMPANY_NAME Env Var

- GOAL-004: Make COMPANY_NAME actually control the clinic name

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Read COMPANY_NAME from env in Assistant.__init__ | ✅ | 2026-06-19 |
| TASK-012 | Replace hardcoded "Alfalha Hospital" with the env var value | ✅ | 2026-06-19 |

### Implementation Phase 5: Unbounded Cache & Recursion Guard

- GOAL-005: Fix unbounded slots_cache and infinite recursion risk

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Add periodic cleanup of stale entries in _slots_cache | ✅ | 2026-06-19 |
| TASK-014 | Add max_retries parameter to _generate_patient_id recursion | ✅ | 2026-06-19 |

## 3. Alternatives

- **ALT-001**: Use asyncio.Lock around CalToolset methods instead of removing singleton — rejected because locking doesn't prevent cross-call state clobbering; per-call instance is cleaner
- **ALT-002**: Use LLM to generate summary in on_exit (call LLM with conversation) — rejected because it adds latency and cost; extracting from session.history is sufficient
- **ALT-003**: Use TTL dict from stdlib for slots cache — rejected because manual cleanup is simpler and avoids extra dependency

## 4. Dependencies

- **DEP-001**: livekit-agents[default]>=1.2.0 (already installed)
- **DEP-002**: No new dependencies required

## 5. Files

| File | Changes |
|------|---------|
| **FILE-001**: `Receptionist/src/agent.py` | Remove singleton, pass per-call CalToolset, read COMPANY_NAME, fix on_exit summaries |
| **FILE-002**: `Receptionist/src/cal_tools.py` | Accept db/patient_id via constructor, remove singleton state, fix tool output, fix cache |
| **FILE-003**: `Receptionist/src/memory_tools.py` | Accept CalToolset from constructor instead of singleton |
| **FILE-004**: `Receptionist/src/database.py` | Add max retries guard to _generate_patient_id |

## 6. Testing

- **TEST-001**: Run all 25 existing unit tests — ✅ 25/25 passed
- **TEST-002**: Module import verification — ✅ Assistant, CalToolset, PatientToolset import cleanly
- **TEST-003**: Per-call CalToolset integration — ✅ CalToolset(db=db, patient_id=pid) works
- **TEST-004**: COMPANY_NAME env var — ✅ Agent prompt uses env var value
- **TEST-005**: create_booking output sanitized — ✅ No raw UIDs in return value

## 7. Risks & Assumptions

- **RISK-001**: Creating CalToolset per-call means the 30s slots cache is now per-call too, not shared. This slightly reduces cross-call cache hits but eliminates data corruption. Acceptable tradeoff.
- **ASSUMPTION-001**: session.history is available in on_exit callback
- **ASSUMPTION-002**: No external code depends on `get_cal_tools()` being a singleton

## 8. Related Specifications / Further Reading

- LiveKit Agents docs: https://docs.livekit.io/agents/
- Cartesia TTS API: https://docs.cartesia.ai/
