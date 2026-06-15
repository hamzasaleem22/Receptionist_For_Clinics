import os

os.environ.setdefault("CAL_API_KEY", "dummy_test_key")
os.environ.setdefault("CAL_USERNAME", "test_user")

import pytest

from agent import Assistant, normalize_phone


class TestNormalizePhoneIntegration:
    def test_normalize_phone(self):
        assert normalize_phone("+923503070436") == "923503070436"
        assert normalize_phone("+92 (350) 307-0436") == "923503070436"
        assert normalize_phone(None) is None


@pytest.mark.skipif(
    not os.environ.get("LIVEKIT_API_KEY"),
    reason="LIVEKIT_API_KEY not set — needs LiveKit Cloud credentials",
)
@pytest.mark.asyncio
async def test_greeting_unknown_caller():
    from livekit.agents import AgentSession, inference

    async with (
        inference.LLM(model="openai/gpt-4o-mini") as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(user_input="Hello")

        await result.expect.next_event().is_message(role="assistant").judge(
            llm,
            intent="Introduces themselves as Jassey from Alfalha Hospital and offers assistance with appointments.",
        )

        result.expect.no_more_events()


@pytest.mark.skipif(
    not os.environ.get("LIVEKIT_API_KEY"),
    reason="LIVEKIT_API_KEY not set",
)
@pytest.mark.asyncio
async def test_greeting_returning_caller():
    from livekit.agents import AgentSession, inference, llm

    async with (
        inference.LLM(model="openai/gpt-4o-mini") as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        chat_ctx = llm.ChatContext()
        chat_ctx.add_message(
            role="assistant",
            content=(
                "Returning patient: Ahmed Hassan (ID: pat_001).\n\n"
                "Their recent bookings:\n"
                "- 30min on Monday June 15 at 09:00 AM (Status: confirmed)\n\n"
                "Summary of their last call:\n"
                "Patient called to check symptoms and book a follow-up.\n\n"
                "Remembered facts about this patient:\n"
                "- allergy: penicillin"
            ),
        )
        await session.start(Assistant(chat_ctx=chat_ctx, patient_id="pat_001"))

        result = await session.run(user_input="Hi")

        await result.expect.next_event().is_message(role="assistant").judge(
            llm_instance,
            intent="Greets the caller by name Ahmed and identifies themselves as Jassey from Alfalha Hospital.",
        )


@pytest.mark.skipif(
    not os.environ.get("LIVEKIT_API_KEY"),
    reason="LIVEKIT_API_KEY not set",
)
@pytest.mark.asyncio
async def test_multi_turn_booking_flow():
    from livekit.agents import AgentSession, inference

    async with (
        inference.LLM(model="openai/gpt-4o-mini") as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result1 = await session.run(user_input="I'd like to book an appointment")
        await result1.expect.next_event().is_message(role="assistant").judge(
            llm, intent="Asks what type of appointment the patient needs."
        )
