from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, inference, room_io, TurnHandlingOptions
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import ai_coustics, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        end_call = EndCallTool()
        super().__init__(
            instructions="""You are a helpful receptionist AI assistant for Shifa Clinic.
            You greet callers warmly and assist them with booking appointments, answering questions,
            and directing them to the right department.
            Your responses are concise, to the point, and without any complex formatting or punctuation
            including emojis, asterisks, or other symbols.
            You are professional, friendly, and have a sense of humor.""",
            tools=end_call.tools,
        )

server = AgentServer()

@server.rtc_session(agent_name="receptionist")
async def my_agent(ctx: agents.JobContext):
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        llm=inference.LLM(model="openai/gpt-4o-mini"),
        tts=inference.TTS(
            model="cartesia/sonic-3",
            voice="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
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
