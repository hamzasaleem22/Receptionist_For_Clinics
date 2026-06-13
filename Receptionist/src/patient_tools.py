from typing import Annotated

from livekit.agents import llm

from database import Database


class PatientToolset(llm.Toolset):
    def __init__(self, db: Database) -> None:
        super().__init__(id="patient")
        self._db = db

    @llm.function_tool
    async def create_patient_record(
        self,
        first_name: str,
        last_name: str,
        phone: Annotated[str | None, "Phone number including country code, e.g. +923001234567"] = None,
    ) -> str:
        """Create a new patient record in the database. Use this when a new patient provides their name and phone.

        Args:
            first_name: The patient's first name.
            last_name: The patient's last name.
            phone: The patient's phone number (optional).
        """
        patient_id = await self._db.create_patient(first_name, last_name, phone)
        return f"Patient record created. Their patient ID is {patient_id}. Name: {first_name} {last_name}."
