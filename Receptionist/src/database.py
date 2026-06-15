from __future__ import annotations

import os
import random
import string
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from motor.motor_asyncio import AsyncIOMotorClient

DB_NAME = "voice_agent_clinic"
COLLECTION_NAME = "patients"
PATIENT_ID_PREFIX = "PAT-"
PATIENT_ID_DIGITS = 6


class Database:
    def __init__(self, uri: str | None = None) -> None:
        uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self._client = AsyncIOMotorClient(uri)
        self._db = self._client[DB_NAME]
        self._patients = self._db[COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        await self._patients.create_index("phone", unique=True, sparse=True)
        await self._patients.create_index("patient_id", unique=True, sparse=True)
        await self._patients.create_index(
            "bookings.cal_booking_uid",
            unique=True,
            partialFilterExpression={"bookings.cal_booking_uid": {"$exists": True}},
        )

    async def close(self) -> None:
        self._client.close()

    # ── Patient CRUD ──────────────────────────────────────────

    async def find_patient_by_phone(self, phone: str) -> dict | None:
        return await self._patients.find_one({"phone": phone})

    async def find_patient_by_id(self, patient_id: str) -> dict | None:
        return await self._patients.find_one({"patient_id": patient_id})

    async def create_patient(
        self, first_name: str, last_name: str, phone: str | None = None
    ) -> str:
        if phone:
            existing = await self.find_patient_by_phone(phone)
            if existing:
                await self.update_patient(existing["patient_id"], {
                    "first_name": first_name,
                    "last_name": last_name,
                })
                return existing["patient_id"]

        patient_id = await self._generate_patient_id()
        doc = {
            "patient_id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "bookings": [],
            "conversation_summaries": [],
            "memories": [],
        }
        try:
            await self._patients.insert_one(doc)
        except DuplicateKeyError:
            if phone:
                existing = await self.find_patient_by_phone(phone)
                if existing:
                    return existing["patient_id"]
            return await self.create_patient(first_name, last_name, phone)
        return patient_id

    async def update_patient(self, patient_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self._patients.update_one(
            {"patient_id": patient_id}, {"$set": updates}
        )

    async def _generate_patient_id(self) -> str:
        for _ in range(10):
            pid = PATIENT_ID_PREFIX + "".join(
                random.choices(string.digits, k=PATIENT_ID_DIGITS)
            )
            exists = await self._patients.find_one({"patient_id": pid})
            if not exists:
                return pid
        raise RuntimeError("Failed to generate unique patient ID")

    # ── Bookings (embedded array) ─────────────────────────────

    async def add_booking(
        self,
        patient_id: str,
        cal_booking_uid: str,
        event_type_slug: str,
        start_time: datetime,
        attendee_name: str,
        attendee_email: str,
        attendee_timezone: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        booking = {
            "cal_booking_uid": cal_booking_uid,
            "event_type_slug": event_type_slug,
            "start_time": start_time,
            "status": "confirmed",
            "attendee_name": attendee_name,
            "attendee_email": attendee_email,
            "attendee_timezone": attendee_timezone,
            "created_at": now,
            "updated_at": now,
        }
        await self._patients.update_one(
            {"patient_id": patient_id},
            {"$push": {"bookings": booking}, "$set": {"updated_at": now}},
        )

    async def get_recent_bookings(
        self, patient_id: str, limit: int = 3
    ) -> list[dict]:
        doc = await self._patients.find_one(
            {"patient_id": patient_id},
            projection={"bookings": 1, "_id": 0},
        )
        if not doc or not doc.get("bookings"):
            return []
        sorted_bookings = sorted(
            doc["bookings"],
            key=lambda b: b.get("created_at", datetime.min),
            reverse=True,
        )
        return sorted_bookings[:limit]

    async def update_booking_status(self, cal_booking_uid: str, status: str) -> None:
        now = datetime.now(timezone.utc)
        await self._patients.update_one(
            {"bookings.cal_booking_uid": cal_booking_uid},
            {
                "$set": {
                    "bookings.$.status": status,
                    "bookings.$.updated_at": now,
                    "updated_at": now,
                }
            },
        )

    # ── Conversation Summaries (embedded array) ───────────────

    async def add_summary(self, patient_id: str, summary: str) -> None:
        now = datetime.now(timezone.utc)
        await self._patients.update_one(
            {"patient_id": patient_id},
            {
                "$push": {
                    "conversation_summaries": {
                        "summary": summary,
                        "created_at": now,
                    }
                },
                "$set": {"updated_at": now},
            },
        )

    async def get_recent_summary(self, patient_id: str) -> str | None:
        doc = await self._patients.find_one(
            {"patient_id": patient_id},
            projection={"conversation_summaries": 1, "_id": 0},
        )
        if not doc or not doc.get("conversation_summaries"):
            return None
        sorted_summaries = sorted(
            doc["conversation_summaries"],
            key=lambda s: s.get("created_at", datetime.min),
            reverse=True,
        )
        return sorted_summaries[0]["summary"] if sorted_summaries else None

    # ── Memory Facts (embedded array, key-value) ──────────────

    async def remember_fact(self, patient_id: str, key: str, value: str) -> None:
        now = datetime.now(timezone.utc)
        await self._patients.update_one(
            {"patient_id": patient_id},
            {"$pull": {"memories": {"key": key}}},
        )
        await self._patients.update_one(
            {"patient_id": patient_id},
            {
                "$push": {
                    "memories": {
                        "key": key,
                        "value": value,
                        "created_at": now,
                        "updated_at": now,
                    }
                },
                "$set": {"updated_at": now},
            },
        )

    async def recall_fact(self, patient_id: str, key: str) -> str | None:
        doc = await self._patients.find_one(
            {"patient_id": patient_id, "memories.key": key},
            projection={"memories.$": 1, "_id": 0},
        )
        if doc and doc.get("memories"):
            return doc["memories"][0]["value"]
        return None

    async def list_memories(self, patient_id: str) -> list[dict]:
        doc = await self._patients.find_one(
            {"patient_id": patient_id},
            projection={"memories": 1, "_id": 0},
        )
        if not doc or not doc.get("memories"):
            return []
        return sorted(
            doc["memories"],
            key=lambda m: m.get("updated_at", datetime.min),
            reverse=True,
        )

    async def forget_fact(self, patient_id: str, key: str) -> bool:
        result = await self._patients.update_one(
            {"patient_id": patient_id},
            {"$pull": {"memories": {"key": key}}},
        )
        return result.modified_count > 0
