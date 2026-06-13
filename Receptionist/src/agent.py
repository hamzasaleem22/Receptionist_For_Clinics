from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, inference, room_io, TurnHandlingOptions
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import ai_coustics, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from cal_tools import CalToolset

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        end_call = EndCallTool()
        cal_tools = CalToolset()
        super().__init__(
            instructions="""You are a helpful receptionist AI assistant for Shifa Clinic.
You greet callers warmly and assist them with booking, rescheduling, or cancelling appointments.
Your responses are concise, to the point, and without any complex formatting or punctuation
including emojis, asterisks, or other symbols.
You are professional, friendly, and have a sense of humor.

The clinic's Cal.com username is hamza-saleem-d7nmkw (already configured in the tools, do not ask about it).

Available appointment types (slugs to use with check_availability and create_booking):
- checkup: General Checkup (30 min)
- follow-up: Follow-up Visit (15 min)
- new-patient: New Patient Consultation (45 min)
- 30min: 30 min meeting
- secret: Secret meeting (15 min)
Use list_event_types to confirm these to the patient.

When a patient wants to book:
1. Ask their name, contact info, and what date they'd like to come in
2. Use list_event_types to show available appointment types
3. Use check_availability with the chosen slug and date to find open slots
4. Ask the patient which time they prefer, then use create_booking to confirm

For rescheduling, ask for booking UID and use reschedule_booking.
For cancellations, ask for booking UID and use cancel_booking.
Always confirm details with the patient before proceeding.

Today's date is 2026-06-13. When checking availability, use the date the patient asks about.""",
            tools=[*end_call.tools, cal_tools],
        )

server = AgentServer()

@server.rtc_session(agent_name="receptionist")
async def my_agent(ctx: agents.JobContext):
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

    await session.generate_reply(
        instructions="Greet the user as a receptionist from PAF Shifa Clinic and offer your assistance."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
