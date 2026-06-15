import os
import random

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("MONGODB_URI"),
    reason="MONGODB_URI not set — needs MongoDB Atlas",
)


def _unique_phone() -> str:
    return f"999{random.randint(1000000, 9999999)}"


@pytest.mark.asyncio
async def test_create_and_find_patient():
    from database import Database

    phone = _unique_phone()
    db = Database()
    await db.ensure_indexes()
    try:
        pid = await db.create_patient("Test", "User", phone=phone)
        assert pid is not None

        found = await db.find_patient_by_phone(phone)
        assert found is not None
        assert found["first_name"] == "Test"
        assert found["last_name"] == "User"

        pid2 = await db.create_patient("Test", "Updated", phone=phone)
        assert pid2 == pid
        refound = await db.find_patient_by_phone(phone)
        assert refound["last_name"] == "Updated"
    finally:
        await db._patients.delete_one({"phone": phone})
        await db.close()


@pytest.mark.asyncio
async def test_create_patient_without_phone():
    from database import Database

    db = Database()
    pid = None
    try:
        pid = await db.create_patient("No", "Phone")
        assert pid is not None
        assert pid.startswith("PAT-")
        found = await db.find_patient_by_id(pid)
        assert found is not None
        assert found["first_name"] == "No"
        assert found["phone"] is None
    finally:
        if pid:
            await db._patients.delete_one({"patient_id": pid})
        await db.close()


@pytest.mark.asyncio
async def test_patient_memory_cycle():
    from database import Database

    phone = _unique_phone()
    db = Database()
    await db.ensure_indexes()
    try:
        pid = await db.create_patient("Memory", "Test", phone=phone)

        await db.remember_fact(pid, "allergy", "penicillin")
        val = await db.recall_fact(pid, "allergy")
        assert val == "penicillin"

        memories = await db.list_memories(pid)
        assert any(m["key"] == "allergy" and m["value"] == "penicillin" for m in memories)

        await db.remember_fact(pid, "allergy", "amoxicillin")
        val = await db.recall_fact(pid, "allergy")
        assert val == "amoxicillin"

        removed = await db.forget_fact(pid, "allergy")
        assert removed is True
        val = await db.recall_fact(pid, "allergy")
        assert val is None

        removed = await db.forget_fact(pid, "nonexistent")
        assert removed is False
    finally:
        await db._patients.delete_one({"phone": phone})
        await db.close()


@pytest.mark.asyncio
async def test_booking_crud():
    from datetime import datetime, timezone

    from database import Database

    phone = _unique_phone()
    db = Database()
    await db.ensure_indexes()
    try:
        pid = await db.create_patient("Booking", "Test", phone=phone)

        now = datetime.now(timezone.utc)
        await db.add_booking(
            patient_id=pid,
            cal_booking_uid="booking_001",
            event_type_slug="30min",
            start_time=now,
            attendee_name="Booking Test",
            attendee_email="b@test.com",
            attendee_timezone="Asia/Karachi",
        )

        bookings = await db.get_recent_bookings(pid, limit=5)
        assert len(bookings) == 1
        assert bookings[0]["cal_booking_uid"] == "booking_001"
        assert bookings[0]["status"] == "confirmed"

        await db.update_booking_status("booking_001", "cancelled")
        bookings = await db.get_recent_bookings(pid, limit=5)
        cancelled = [b for b in bookings if b["cal_booking_uid"] == "booking_001"]
        assert len(cancelled) == 1
        assert cancelled[0]["status"] == "cancelled"
    finally:
        await db._patients.delete_one({"phone": phone})
        await db.close()


@pytest.mark.asyncio
async def test_conversation_summary_save_and_read():
    from database import Database

    phone = _unique_phone()
    db = Database()
    await db.ensure_indexes()
    try:
        pid = await db.create_patient("Summary", "Test", phone=phone)

        await db.add_summary(pid, "Test summary one")
        summary = await db.get_recent_summary(pid)
        assert summary == "Test summary one"

        await db.add_summary(pid, "Test summary two")
        summary = await db.get_recent_summary(pid)
        assert summary == "Test summary two"
    finally:
        await db._patients.delete_one({"phone": phone})
        await db.close()
