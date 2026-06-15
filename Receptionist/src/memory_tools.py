from __future__ import annotations

from typing import Annotated

from livekit.agents import llm

from database import Database


class PatientToolset(llm.Toolset):
    def __init__(
        self,
        db: Database,
        patient_id: str | None = None,
        cal_tools: llm.Toolset | None = None,
    ) -> None:
        super().__init__(id="patient")
        self._db = db
        self._patient_id = patient_id
        self._cal_tools = cal_tools

    @llm.function_tool
    async def create_patient_record(
        self,
        first_name: Annotated[str, "First name of the patient"],
        last_name: Annotated[str, "Last name of the patient"],
        phone: Annotated[str | None, "Phone number in international format, e.g. +923001234567"] = None,
    ) -> str:
        """Create or find a patient record. Call this when a caller gives their name.

        Args:
            first_name: The patient's first name.
            last_name: The patient's last name.
            phone: The patient's phone number in international format.
        """
        patient_id = await self._db.create_patient(first_name, last_name, phone=phone)
        self._patient_id = patient_id
        if self._cal_tools and hasattr(self._cal_tools, "update_patient_id"):
            self._cal_tools.update_patient_id(patient_id)
        return f"Patient record ready for {first_name} {last_name} (ID: {patient_id})."

    @llm.function_tool
    async def remember_fact(
        self,
        key: Annotated[str, "A short label for the fact, e.g. 'preferred_time', 'allergy', 'insurance'"],
        value: Annotated[str, "The fact value, e.g. 'morning', 'penicillin', 'Blue Cross'"],
    ) -> str:
        """Remember a fact about the current patient. Overwrites any existing fact with the same key.

        Args:
            key: A label for the fact (e.g. 'preferred_time', 'allergy').
            value: The value of the fact.
        """
        if not self._patient_id:
            return "No patient record found. Create a patient record first using create_patient_record."
        await self._db.remember_fact(self._patient_id, key, value)
        return f"Got it, I've remembered that {key} is {value}."

    @llm.function_tool
    async def recall_fact(
        self,
        key: Annotated[str, "The label of the fact to recall, e.g. 'preferred_time'"],
    ) -> str:
        """Recall a specific fact about the current patient by its key.

        Args:
            key: The label of the fact to look up.
        """
        if not self._patient_id:
            return "No patient record found."
        value = await self._db.recall_fact(self._patient_id, key)
        if value is None:
            return f"I don't have any fact stored under '{key}'."
        return f"{key}: {value}"

    @llm.function_tool
    async def list_facts(self) -> str:
        """List all remembered facts about the current patient."""
        if not self._patient_id:
            return "No patient record found."
        memories = await self._db.list_memories(self._patient_id)
        if not memories:
            return "No facts stored for this patient."
        lines = [f"- {m['key']}: {m['value']}" for m in memories]
        return "Remembered facts:\n" + "\n".join(lines)

    @llm.function_tool
    async def forget_fact(
        self,
        key: Annotated[str, "The label of the fact to forget, e.g. 'preferred_time'"],
    ) -> str:
        """Forget a specific fact about the current patient.

        Args:
            key: The label of the fact to remove.
        """
        if not self._patient_id:
            return "No patient record found."
        removed = await self._db.forget_fact(self._patient_id, key)
        if removed:
            return f"OK, I've forgotten '{key}'."
        return f"I couldn't find a fact labeled '{key}' to forget."

    def set_patient_id(self, patient_id: str) -> None:
        self._patient_id = patient_id
