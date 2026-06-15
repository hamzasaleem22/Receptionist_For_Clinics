---
goal: Fix low TTS volume on phone calls for the Alfalha Hospital receptionist agent
version: 1.0
date_created: 2026-06-15
owner: AI Agent
status: 'Completed'
tags: bug, tts, volume, audio, cartesia
---

# Introduction

Fix the agent's TTS (Cartesia Sonic-3) volume being too low during mobile phone calls using two independent layers: (1) request higher volume from Cartesia API via `extra_kwargs`, and (2) post-process audio frames via `tts_node` override with numpy amplification.

## 1. Requirements & Constraints

- **REQ-001**: Agent must speak audibly on PSTN mobile calls (8-bit μ-law, 8kHz)
- **REQ-002**: Must not introduce clipping, distortion, or audio artifacts
- **REQ-003**: Must work with existing LiveKit Inference TTS (`cartesia/sonic-3`)
- **REQ-004**: Must not require separate Cartesia API key (LiveKit Inference only)
- **REQ-005**: Must not break console/text mode
- **REQ-006**: Must preserve all existing agent behavior (SSML, turn handling, etc.)
- **CON-001**: Only `livekit-agents` + `livekit-plugins-*` dependencies (no new packages)
- **CON-002**: Follow the exact `tts_node` override pattern from LiveKit docs
- **CON-003**: numpy already available in the environment (v2.3.5)

## 2. Implementation Steps

### Implementation Phase 1 — Cartesia Volume via extra_kwargs

- GOAL-001: Pass `volume=2.0` to Cartesia TTS through LiveKit Inference `extra_kwargs`

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add `extra_kwargs={"volume": 2.0}` to the `inference.TTS()` call in `src/agent.py` for Cartesia Sonic-3 | ✅ | 2026-06-15 |
| TASK-002 | Run `py_compile` syntax check on `src/agent.py` | ✅ | 2026-06-15 |

### Implementation Phase 2 — tts_node Override with numpy Amplification

- GOAL-002: Override `tts_node` in `Assistant` class to amplify audio frames by a configurable multiplier (1.5x)

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Add `import numpy as np` and `from livekit.agents import utils` to `src/agent.py` imports | ✅ | 2026-06-15 |
| TASK-004 | Add `self._volume: float = 1.5` attribute to `Assistant.__init__()` | ✅ | 2026-06-15 |
| TASK-005 | Implement `tts_node()` override in `Assistant` class (delegates to `Agent.default.tts_node`, wraps with `_adjust_volume_in_stream`) | ✅ | 2026-06-15 |
| TASK-006 | Implement `_adjust_volume_in_stream()` method using `AudioByteStream` with 100ms chunks | ✅ | 2026-06-15 |
| TASK-007 | Implement `_adjust_volume_in_frame()` method using numpy int16 → float32 → scale → int16 conversion | ✅ | 2026-06-15 |
| TASK-008 | Run `py_compile` syntax check on `src/agent.py` | ✅ | 2026-06-15 |

### Implementation Phase 3 — Verification

- GOAL-003: Verify the changes compile and run without errors

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Run `python3 -m py_compile src/agent.py` to confirm no syntax errors | ✅ | 2026-06-15 |
| TASK-010 | Verify no regressions in the `__init__` imports (numpy, utils.audio) | ✅ | 2026-06-15 |
| TASK-011 | Review that `Assistant.__init__()` signature is unchanged (accepts `chat_ctx`, `patient_id`, `db`) | ✅ | 2026-06-15 |

## 3. Alternatives

- **ALT-001** (Only Cartesia volume, no tts_node): Less reliable — Cartesia says volume is "guidance, not strict". Rejected in favor of dual-layer.
- **ALT-002** (Only tts_node, no Cartesia volume): Works but leaves potential gain on the table. Cartesia's native volume control may produce cleaner audio than post-hoc amplification.
- **ALT-003** (Switch to different TTS provider): Unnecessary — Cartesia Sonic-3 is the fastest TTS and the volume issue is fixable.
- **ALT-004** (SSML `<volume ratio="..."/>` tags in instructions): Unreliable — requires LLM to emit them every turn and Cartesia treats them as guidance only.

## 4. Dependencies

- **DEP-001**: `numpy` (already available, no install needed)
- **DEP-002**: `livekit.agents.utils.audio.AudioByteStream` (part of `livekit-agents>=0.14`)
- **DEP-003**: `livekit.rtc.AudioFrame` (part of `livekit-rtc`)

## 5. Files

- **FILE-001**: `src/agent.py` — Main agent file; add `extra_kwargs`, import numpy, implement `tts_node` override and volume amplification methods

## 6. Testing

- **TEST-001**: `py_compile` syntax check passes
- **TEST-002**: Console mode starts without import errors: `uv run python src/agent.py console --text`
- **TEST-003**: Visual inspection confirms `tts_node` override is called by the framework (log output if available)
- **TEST-004**: Volume amplification does not clip samples (all values within int16 range after processing)

## 7. Risks & Assumptions

- **RISK-001**: Over-amplification could cause clipping (distortion). Mitigated by cap at 1.5x multiplier and int16 bounds check in `_adjust_volume_in_frame`.
- **RISK-002**: `AudioByteStream` API may change across `livekit-agents` versions. Mitigated by pinning to the exact pattern from LiveKit docs.
- **ASSUMPTION-001**: The `tts_node` override pattern documented for `Agent` class works with `Assistant` which extends `Agent`.
- **ASSUMPTION-002**: LiveKit Inference `extra_kwargs` are forwarded to the Cartesia API correctly for `volume`.

## 8. Related Specifications / Further Reading

- https://docs.livekit.io/agents/multimodality/audio/customization/#adjusting-speech-volume
- https://docs.livekit.io/agents/models/tts/cartesia/#inference
- https://docs.cartesia.ai/build-with-cartesia/sonic-3/volume-speed-emotion
