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


@dataclass
class BookingData:
    patient_id: str
    cal_booking_uid: str
    event_type_slug: str
    start_time: datetime
    status: str = "confirmed"
    attendee_name: str = ""
    attendee_email: str = ""
    attendee_timezone: str = "UTC"
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class SummaryData:
    patient_id: str
    summary: str
    booking_id: str | None = None
    created_at: datetime | None = None
