# Issues Found — Permanent Memory Feature (All Fixed)

## Issue 1: Returning caller not recognized by phone

**Phone format mismatch between SIP and MongoDB.**

| Source | Phone value | Format |
|--------|-------------|--------|
| SIP (`sip.caller` attribute) | `+923035070436` | International (+92...) |
| DB (stored by `create_patient_record`) | `0303507042` | Local (03...) |

`_get_caller_phone()` returns `+923035070436` from SIP, but `find_patient_by_phone("+923035070436")` finds nothing since the patient was stored as `0303507042`. The returning caller is treated as a complete stranger every time.

## Issue 2: `create_patient_record` crashes on duplicate phone

When a returning caller gives their name and phone again, `create_patient_record` tries `insert_one`, which throws `pymongo.errors.DuplicateKeyError: E11000 duplicate key error` (phone has a unique index). The tool raises an unhandled exception, logged as `exception occurred while executing tool`. The agent says "Oops, there was a bit of a hiccup" but can't recover gracefully.

The same error retries (the LLM tries the tool again with the same args, seeing the same outcome). No fallback to `update_one` or `find_one_and_update` with upsert.

## Issue 3: `conversation_summaries` always empty

Three cascading reasons:

1. **`patient_id` is None when `on_exit` runs** — Since `preload_user_context` returned no match (Issue 1), `self._patient_id` was never set. The patient creation tool also crashed (Issue 2), so `self._patient_tools._patient_id` was never updated. The guard `if not pid or not self._db: return` at `agent.py:227` skips the entire summary generation.

2. **Caller disconnects before summary completes** — Log shows `session closed` at 01:56:07 and `process exiting` at 01:56:28. The LLM call for summary (`on_exit` line 242) needs to generate text via `openai/gpt-4o`, but the shutdown sequence closes things before the async work finishes.

3. **`chat_ctx` may be cleared** — By the time `on_exit` fires, `self.session.chat_ctx` may already be empty or `None`, so the function returns early at `agent.py:231`.

## Issue 4: `memories` array always empty

No code path automatically stores facts or memories after a booking is made. The LLM must be explicitly prompted to call `remember_fact` during the conversation, but nothing in the instructions or `on_exit` enforces it. The tool exists but is never exercised.

## Issue 5: Empty / duplicate `last_name`

The original patient record has `last_name: ""` (empty). When the caller said "my last name is Hamzah" (same as first name), the LLM tried to create a new record with `last_name: "Hamzah"`, but since the insert failed with duplicate phone, the original empty `last_name` was never updated. There is no `update_patient` flow for existing patients — only `create_patient_record` exists.

---

## Root Cause Chain

```
Phone format mismatch (SIP vs DB)
  → preload_user_context finds no patient
  → Agent treats returning caller as new
  → Agent calls create_patient_record
  → DuplicateKeyError on phone index
  → patient_id remains None
  → on_exit summary generation skipped
  → conversation_summaries and memories stay empty
```

---

## Fixes Applied

### Fix 1: `agent.py` — `_get_caller_phone()`
- **Before**: Used `room_io.linked_participant(ctx.room)` + `sip.caller` (non-existent attribute)
- **After**: Uses `ctx.wait_for_participant()` + `sip.phoneNumber` (LiveKit's standard SIP attribute)
- Phone is normalized to digits only via `re.sub(r'\D', '', phone)`
- 10-second timeout via `asyncio.wait_for` to prevent blocking in console mode
- Added `from livekit import rtc` and `import re`

### Fix 2: `database.py` — `create_patient()`
- **Before**: `insert_one` → `DuplicateKeyError` crash on existing phone
- **After**: Checks for existing phone first → if found, updates `first_name`/`last_name` via existing `update_patient()` and returns the existing `patient_id`. DuplicateKeyError safety net for race conditions.

### Fix 3: `agent.py` — `on_exit()`
- **Before**: Tried to read `self.session.chat_ctx` (cleared before on_exit fires), called `inference.LLM` for summary (could fail during shutdown)
- **After**: Reads the last booking from MongoDB via `get_recent_bookings()`, builds a simple structured summary. Always saves something (even "No bookings were made"). No dependency on session state.

### Fix 4: `cal_tools.py` — `create_booking()`
- **Before**: Only saved booking to MongoDB, no memory stored
- **After**: After successful booking + DB save, also calls `db.remember_fact("last_booked", "...")` with the event type and time

### Fix 5: `database.py` — `create_patient()` handles updates
- **Before**: No update path — `insert_one` failed on duplicate
- **After**: Calls `update_patient()` when existing phone found, merging new `first_name`/`last_name`

