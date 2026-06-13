import json
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, inference, room_io, TurnHandlingOptions
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import ai_coustics, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from cal_tools import CalToolset
from database import Database
from patient_tools import PatientToolset

load_dotenv(".env.local")

db = Database()
cal_tools = CalToolset(db)


class Assistant(Agent):
    def __init__(self) -> None:
        end_call = EndCallTool()
        patient_tools = PatientToolset(db)
        super().__init__(
            instructions="""## Role
You are Jassey, a warm and professional receptionist at Alfalha Hospital answering a phone call. You speak like a real human — conversational, never robotic. No emojis, markdown, or formatting.

## Task
Handle patient calls by calling tools. Every action MUST go through a tool — never describe what you would do, actually call the tool.

**Greeting:** "Alfalha Hospital, this is Jassey speaking — I can help you with booking appointments, rescheduling, cancellations, or checking your appointment details. How can I assist you today?" Then stop and listen.

## Booking flow (most common)
1. Ask for their **name and phone number** first
2. **If new patient** → call `create_patient_record(first_name, last_name, phone)` right away to get their patient ID
3. Ask what **appointment type** they want (General Consultation, Routine Checkup, Follow-up, Urgent, New Patient Registration) and their **preferred date**
4. Call `check_availability(slug, date)` for that ONE type and date. If they're unsure about the type, use `check_availability_bulk` to check multiple types at once.
5. When they pick a specific time, call `create_booking(event_type_slug, start_time, attendee_name, patient_id)` — always pass the patient_id if you have it.

**IMPORTANT — speed rules:**
- Ask for type AND date together in one question — don't drag it out
- Call ONE availability check — not multiple
- If no slots on that date, immediately suggest the next available date with one more check call
- Keep responses short and natural. Don't over-explain.

## Other flows
**Cancellation:** name + phone + booking UID → `cancel_booking(uid)`. No UID? Ask them to find it.
**Reschedule:** name + phone + booking UID + new time → `reschedule_booking(uid, new_start)`.

## Speech style
- Use fillers: "um", "uh", "hmm", "let me see", "alright", "okay", "one moment"
- Use pauses: "So...", "Well...", "Let me just...", "Hang on a moment..."
- Use contractions: "I'll", "you're", "that's", "can't", "don't", "I've"
- Short natural sentences. Never list items or use bullet points.

## Tool calling protocol
You only get ONE message before a tool runs. Fill the wait time: acknowledge → ramble → result.
GOOD: "Let me check that for you... just give me a moment... I'm pulling up the details now... okay here we go..."

## Format rules
- Dates: YYYY-MM-DD (e.g. "2026-06-15")
- Times for booking: ISO 8601 UTC (e.g. "2026-06-15T09:00:00Z")
- Timezone: default "Asia/Karachi" unless patient specifies otherwise
- Email: always ask first. If they don't have one, omit it (a placeholder is used)

## Patient records
- Always collect name and phone number
- New patients: call `create_patient_record` immediately after getting their name and phone — this gives you their patient_id
- Pass patient_id to `create_booking` so their booking gets linked to their record

## Tool reference
- `create_patient_record(first_name, last_name, phone)` — store a new patient. Call this FIRST for new callers.
- `list_event_types()` — show all appointment types. Use when patient is unsure.
- `check_availability(event_type_slug, date)` — check slots for ONE type on ONE date. Fast.
- `check_availability_bulk(event_type_slugs, date)` — check slots for MULTIPLE types on ONE date. Use when patient hasn't decided the type.
- `create_booking(event_type_slug, start_time, attendee_name, patient_id, attendee_email, attendee_timezone)` — book and save to database.
- `cancel_booking(booking_uid)` — cancel a booking.
- `reschedule_booking(booking_uid, new_start)` — reschedule a booking.

Available appointment types:
- General Consultation (30min, slug: 30min)
- Routine Checkup (30min, slug: checkup)
- Follow-up Consultation (15min, slug: follow-up)
- Urgent Consultation (15min, slug: secret)
- New Patient Registration (45min, slug: new-patient)

Today: 2026-06-13.""",
            tools=[*end_call.tools, cal_tools, patient_tools],
        )

    async def on_enter(self) -> None:
        self.session.userdata = {}

        try:
            participant = self.session.room_io.linked_participant
            phone = participant.identity if participant else None
        except RuntimeError:
            phone = None

        if phone:
            self.session.userdata["phone"] = phone
            patient = await db.find_patient_by_phone(phone)
            if patient:
                pid = patient.patient_id
                name = f"{patient.first_name} {patient.last_name}"
                self.session.userdata["patient_id"] = pid
                self.session.userdata["patient_name"] = name

                self._chat_ctx.add_message(
                    role="assistant",
                    content=f"The caller's patient ID is {pid}. Patient name: {name}.",
                )
                bookings = await db.get_recent_bookings(pid)
                if bookings:
                    lines = [f"{b.event_type_slug} on {b.start_time.strftime('%b %d')} ({b.status})"
                             for b in bookings]
                    self._chat_ctx.add_message(
                        role="assistant",
                        content="Recent bookings:\n" + "\n".join(lines),
                    )
                summary = await db.get_recent_summary(pid)
                if summary:
                    self._chat_ctx.add_message(
                        role="assistant",
                        content=f"Last call summary: {summary}",
                    )
                await self.session.generate_reply(
                    instructions=f"Greet {patient.first_name} warmly by name and offer your assistance."
                )
                return

        await self.session.generate_reply(
            instructions="Greet the user as a receptionist from PAF Shifa Clinic and offer your assistance."
        )

    async def on_exit(self) -> None:
        patient_id = self.session.userdata.get("patient_id")
        phone = self.session.userdata.get("phone")
        patient_name = self.session.userdata.get("patient_name")

        cal_uid = slug = start_str = name = email = None
        booking_created = False
        booking_rescheduled = False
        booking_cancelled = False

        for item in self.chat_ctx.items:
            if item.type == "function_call":
                call_str = getattr(item, "content", "") or ""
                func_name = getattr(item, "name", "")
                try:
                    args = json.loads(call_str)
                except json.JSONDecodeError:
                    continue

                if func_name == "create_booking":
                    slug = args.get("event_type_slug", slug)
                    booking_created = True
                    name = args.get("attendee_name", name)
                elif func_name == "create_patient_record":
                    phone = args.get("phone", phone)
                    fname = args.get("first_name", "")
                    lname = args.get("last_name", "")
                    patient_name = f"{fname} {lname}".strip()

            if item.type == "function_call_output":
                output = getattr(item, "content", "") or ""

                if "Patient ID is" in output:
                    import re
                    m = re.search(r"patient ID is (\S+)", output, re.IGNORECASE)
                    if m:
                        patient_id = m.group(1)

                if "Booking UID:" in output:
                    for line in output.split("\n"):
                        if line.startswith("Booking UID:"):
                            cal_uid = line.split(":", 1)[1].strip()
                        elif line.startswith("Start:"):
                            start_str = line.split(":", 1)[1].strip()
                        elif line.startswith("Patient:"):
                            name = line.split(":", 1)[1].strip()
                        elif line.startswith("Confirmation sent to"):
                            email = line.split("to", 1)[1].strip()
                            email = email.strip(" .")

                if "rescheduled successfully" in output.lower():
                    booking_rescheduled = True
                if "cancelled successfully" in output.lower():
                    booking_cancelled = True

        summary_parts = []
        if booking_created:
            summary_parts.append(f"Booked {slug or 'appointment'} for {name or patient_name or 'patient'}")
        if booking_rescheduled:
            summary_parts.append(f"Rescheduled booking {cal_uid or ''}")
            if cal_uid and patient_id:
                try:
                    await db.update_booking_status(cal_uid, "rescheduled")
                except Exception:
                    logging.exception("Failed to update booking status to rescheduled")
        if booking_cancelled:
            summary_parts.append(f"Cancelled booking {cal_uid or ''}")
            if cal_uid and patient_id:
                try:
                    await db.update_booking_status(cal_uid, "cancelled")
                except Exception:
                    logging.exception("Failed to update booking status to cancelled")
        if not summary_parts:
            summary_parts.append("Call completed without booking changes.")

        summary_text = ". ".join(summary_parts)

        if patient_id:
            await db.create_summary(patient_id, summary_text)
        elif phone:
            if patient_name:
                parts = patient_name.rsplit(" ", 1)
                first = parts[0]
                last = parts[1] if len(parts) > 1 else ""
                try:
                    pid = await db.create_patient(first, last, phone)
                    await db.create_summary(pid, summary_text)
                except Exception:
                    logging.exception("Error creating patient from fallback")


server = AgentServer()


@server.rtc_session(agent_name="Clinics Receptionist")
async def my_agent(ctx: agents.JobContext):
    await db.ensure_indexes()
    await cal_tools.sync_event_type_names()

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        llm=inference.LLM(model="openai/gpt-4o-mini"),
        tts=inference.TTS(
            "cartesia/sonic-3",
            voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            language="en",
        ),
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
        ),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S,
                ),
            ),
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
