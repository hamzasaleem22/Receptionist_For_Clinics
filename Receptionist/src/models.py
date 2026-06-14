from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PatientData:
    patient_id: str
    first_name: str
    last_name: str
    phone: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    bookings: list = field(default_factory=list)
    conversation_summaries: list = field(default_factory=list)
    memories: list = field(default_factory=list)
