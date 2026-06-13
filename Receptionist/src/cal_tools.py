from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated

import httpx
from livekit.agents import llm
from livekit.agents.llm.tool_context import ToolError

CAL_API_BASE = "https://api.cal.com/v2"
CAL_API_VERSION = "2024-06-14"


class CalToolset(llm.Toolset):
    def __init__(self) -> None:
        super().__init__(id="cal")
        api_key = os.environ.get("CAL_API_KEY")
        if not api_key:
            raise RuntimeError("CAL_API_KEY not set in environment")
        self._api_key = api_key
        self._username = os.environ.get("CAL_USERNAME", "hamza-saleem-d7nmkw")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "cal-api-version": CAL_API_VERSION,
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CAL_API_BASE}{path}",
                headers=self._headers,
                params=params,
            )
            if resp.status_code >= 400:
                raise ToolError(f"Cal.com API error ({resp.status_code}): {resp.text}")
            return resp.json()

    async def _post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CAL_API_BASE}{path}",
                headers=self._headers,
                json=body,
            )
            if resp.status_code >= 400:
                raise ToolError(f"Cal.com API error ({resp.status_code}): {resp.text}")
            return resp.json()

    @llm.function_tool
    async def list_event_types(self) -> str:
        """List all available appointment types offered by the clinic."""
        data = await self._get("/event-types", {"username": self._username})
        types = data.get("data", [])
        if not types:
            return "No event types found for this user."
        lines = []
        for et in types:
            lines.append(f"- {et['slug']}: {et['title']} ({et['lengthInMinutes']} min)")
        return "Available appointment types:\n" + "\n".join(lines)

    @llm.function_tool
    async def check_availability(
        self,
        event_type_slug: Annotated[str, "Slug of the event type to check (e.g. 'checkup', 'follow-up', 'new-patient')"],
        date: Annotated[str, "Date in YYYY-MM-DD format"],
        timezone: Annotated[str, "IANA timezone, e.g. 'Asia/Karachi'"] = "Asia/Karachi",
    ) -> str:
        """Check available time slots for a specific appointment type on a given date.

        Args:
            event_type_slug: The slug of the event type (e.g. 'checkup', 'follow-up').
            date: The date to check availability for, in YYYY-MM-DD format.
            timezone: IANA timezone for slot display (default Asia/Karachi).
        """
        params = {
            "username": self._username,
            "eventTypeSlug": event_type_slug,
            "start": date,
            "end": date,
            "timeZone": timezone,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CAL_API_BASE}/slots",
                params=params,
                headers={"cal-api-version": "2024-09-04"},
            )
            if resp.status_code >= 400:
                raise ToolError(f"Cal.com slots API error ({resp.status_code}): {resp.text}")
            data = resp.json()

        slots = data.get("data", {}).get(date, [])
        if not slots:
            return f"No available slots on {date} for {event_type_slug}."

        times = [s["start"] for s in slots]
        formatted = "\n".join(f"  {i+1}. {_format_time(t)}" for i, t in enumerate(times))
        return f"Available slots on {date} ({event_type_slug}):\n{formatted}"

    @llm.function_tool
    async def create_booking(
        self,
        event_type_slug: Annotated[str, "Slug of the event type to book (e.g. 'checkup', 'follow-up', 'new-patient')"],
        start_time: Annotated[str, "Start time in ISO 8601 UTC format, e.g. '2024-08-13T09:00:00Z'"],
        attendee_name: str,
        attendee_email: str,
        attendee_timezone: Annotated[str, "IANA timezone, e.g. 'America/New_York'"],
        attendee_phone: Annotated[str | None, "Phone number in international format"] = None,
        notes: Annotated[str | None, "Additional notes or reason for the visit"] = None,
    ) -> str:
        """Book an appointment at Shifa Clinic.

        Args:
            event_type_slug: The slug of the event type (e.g. 'checkup', 'follow-up').
            start_time: Start time in ISO 8601 UTC format.
            attendee_name: Full name of the patient.
            attendee_email: Email address of the patient.
            attendee_timezone: IANA timezone of the patient.
            attendee_phone: Phone number in international format (optional).
            notes: Additional notes or reason for the visit (optional).
        """
        body = {
            "eventTypeSlug": event_type_slug,
            "username": self._username,
            "start": start_time,
            "attendee": {
                "name": attendee_name,
                "email": attendee_email,
                "timeZone": attendee_timezone,
            },
        }
        if attendee_phone:
            body["attendee"]["phoneNumber"] = attendee_phone
        if notes:
            body["bookingFieldsResponses"] = {"notes": notes}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CAL_API_BASE}/bookings",
                json=body,
                headers={"cal-api-version": "2026-02-25"},
            )
            if resp.status_code >= 400:
                raise ToolError(f"Booking failed ({resp.status_code}): {resp.text}")
            data = resp.json()

        booking = data.get("data", {})
        uid = booking.get("uid", "unknown")
        start = booking.get("start", start_time)
        return (
            f"Appointment booked successfully!\n"
            f"Booking UID: {uid}\n"
            f"Start: {start}\n"
            f"Patient: {attendee_name}\n"
            f"Confirmation sent to {attendee_email}"
        )

    @llm.function_tool
    async def reschedule_booking(
        self,
        booking_uid: str,
        new_start: Annotated[str, "New start time in ISO 8601 UTC format"],
        reason: Annotated[str | None, "Reason for rescheduling"] = None,
    ) -> str:
        """Reschedule an existing booking to a new time.

        Args:
            booking_uid: The UID of the booking to reschedule.
            new_start: New start time in ISO 8601 UTC format.
            reason: Reason for rescheduling (optional).
        """
        body = {"start": new_start}
        if reason:
            body["reschedulingReason"] = reason

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CAL_API_BASE}/bookings/{booking_uid}/reschedule",
                json=body,
                headers={"cal-api-version": "2026-02-25"},
            )
            if resp.status_code >= 400:
                raise ToolError(f"Reschedule failed ({resp.status_code}): {resp.text}")
            data = resp.json()

        booking = data.get("data", {})
        new_start_val = booking.get("start", new_start)
        return f"Booking rescheduled successfully! New time: {new_start_val}"

    @llm.function_tool
    async def cancel_booking(
        self,
        booking_uid: str,
        reason: Annotated[str | None, "Reason for cancellation"] = None,
    ) -> str:
        """Cancel an existing booking.

        Args:
            booking_uid: The UID of the booking to cancel.
            reason: Reason for cancellation (optional).
        """
        body = {}
        if reason:
            body["cancellationReason"] = reason

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CAL_API_BASE}/bookings/{booking_uid}/cancel",
                json=body,
                headers={"cal-api-version": "2026-02-25"},
            )
            if resp.status_code >= 400:
                raise ToolError(f"Cancellation failed ({resp.status_code}): {resp.text}")
            data = resp.json()

        return "Booking cancelled successfully."


def _format_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%I:%M %p %Z").lstrip("0")
    except ValueError:
        return iso_str
