from __future__ import annotations

import os
import random
import re
import string
from datetime import datetime, timezone

import pymongo.errors
from motor.motor_asyncio import AsyncIOMotorClient

from models import BookingData, PatientData, SummaryData

PATIENT_ID_LENGTH = 6


async def _generate_patient_id(db) -> str:
    for _ in range(10):
        pid = "PAT-" + "".join(random.choices(string.digits, k=PATIENT_ID_LENGTH))
        exists = await db.patients.find_one({"patient_id": pid})
        if not exists:
            return pid
    raise RuntimeError("Failed to generate unique patient ID")


class Database:
    def __init__(self, uri: str | None = None, db_name: str = "receptionist") -> None:
        uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self._client = AsyncIOMotorClient(uri)
        self._db = self._client[db_name]

    async def ensure_indexes(self) -> None:
        await self._db.patients.create_index("phone", unique=True, sparse=True)
        for attempt in range(2):
            try:
                await self._db.patients.create_index("patient_id", unique=True, sparse=True)
                break
            except pymongo.errors.OperationFailure as e:
                if "IndexOptionsConflict" in str(e) and attempt == 0:
                    await self._db.patients.drop_index("patient_id_1")
                    continue
                raise
        await self._db.bookings.create_index([("patient_id", 1), ("created_at", -1)])
        await self._db.bookings.create_index("cal_booking_uid", unique=True, sparse=True)
        await self._db.conversation_summaries.create_index(
            [("patient_id", 1), ("created_at", -1)]
        )

    async def close(self) -> None:
        self._client.close()

    # ── Patients ──────────────────────────────────────────────

    async def find_patient_by_phone(self, phone: str) -> PatientData | None:
        doc = await self._db.patients.find_one({"phone": phone})
        if not doc:
            return None
        doc.pop("_id", None)
        return PatientData(**doc)

    async def find_patient_by_id(self, patient_id: str) -> PatientData | None:
        doc = await self._db.patients.find_one({"patient_id": patient_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return PatientData(**doc)

    async def find_patient_by_name(self, full_name: str) -> list[PatientData]:
        parts = full_name.strip().split()
        if not parts:
            return []
        if len(parts) == 1:
            regex = re.compile(re.escape(parts[0]), re.IGNORECASE)
            cursor = self._db.patients.find(
                {"$or": [{"first_name": regex}, {"last_name": regex}]}
            ).limit(5)
        else:
            first = parts[0]
            last = parts[-1]
            regex_first = re.compile(re.escape(first), re.IGNORECASE)
            regex_last = re.compile(re.escape(last), re.IGNORECASE)
            cursor = self._db.patients.find(
                {"first_name": regex_first, "last_name": regex_last}
            ).limit(5)
        docs = await cursor.to_list(length=5)
        result = []
        for doc in docs:
            doc.pop("_id", None)
            result.append(PatientData(**doc))
        return result

    async def create_patient(
        self, first_name: str, last_name: str, phone: str | None = None
    ) -> str:
        patient_id = await _generate_patient_id(self._db)
        doc = {
            "patient_id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        if phone:
            doc["phone"] = phone
        result = await self._db.patients.insert_one(doc)
        return patient_id

    async def update_patient(self, patient_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self._db.patients.update_one(
            {"patient_id": patient_id}, {"$set": updates}
        )

    # ── Bookings ──────────────────────────────────────────────

    async def get_recent_bookings(
        self, patient_id: str, limit: int = 3
    ) -> list[BookingData]:
        cursor = (
            self._db.bookings.find({"patient_id": patient_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        result = []
        for doc in docs:
            doc.pop("_id", None)
            result.append(BookingData(**doc))
        return result

    async def create_booking(
        self,
        patient_id: str,
        cal_booking_uid: str,
        event_type_slug: str,
        start_time: datetime,
        attendee_name: str,
        attendee_email: str,
        attendee_timezone: str,
    ) -> str:
        doc = {
            "patient_id": patient_id,
            "cal_booking_uid": cal_booking_uid,
            "event_type_slug": event_type_slug,
            "start_time": start_time,
            "status": "confirmed",
            "attendee_name": attendee_name,
            "attendee_email": attendee_email,
            "attendee_timezone": attendee_timezone,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = await self._db.bookings.insert_one(doc)
        return str(result.inserted_id)

    async def find_bookings_by_phone(
        self, phone: str, limit: int = 10
    ) -> list[BookingData]:
        patient = await self.find_patient_by_phone(phone)
        if not patient:
            return []
        return await self.get_recent_bookings(patient.patient_id, limit=limit)

    async def update_booking_status(self, cal_booking_uid: str, status: str) -> None:
        await self._db.bookings.update_one(
            {"cal_booking_uid": cal_booking_uid},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )

    # ── Conversation Summaries ────────────────────────────────

    async def create_summary(
        self,
        patient_id: str,
        summary: str,
        booking_id: str | None = None,
    ) -> str:
        doc = {
            "patient_id": patient_id,
            "summary": summary,
            "created_at": datetime.now(timezone.utc),
        }
        if booking_id:
            doc["booking_id"] = booking_id
        result = await self._db.conversation_summaries.insert_one(doc)
        return str(result.inserted_id)

    async def get_recent_summary(self, patient_id: str) -> str | None:
        doc = await self._db.conversation_summaries.find_one(
            {"patient_id": patient_id},
            sort=[("created_at", -1)],
        )
        return doc["summary"] if doc else None
