import os
import sys
from unittest.mock import AsyncMock

from dotenv import load_dotenv

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env.local"))


def pytest_collection_modifyitems(items):
    needs_mongo = {"test_database.py"}
    needs_livekit = {"test_agent.py"}
    for item in items:
        fname = item.location[0].split("/")[-1] if item.location[0] else ""
        if fname in needs_livekit and not os.environ.get("LIVEKIT_API_KEY"):
            item.add_marker(pytest.mark.skip(reason="LIVEKIT_API_KEY not set"))
        if fname in needs_mongo and not os.environ.get("MONGODB_URI"):
            item.add_marker(pytest.mark.skip(reason="MONGODB_URI not set"))


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.create_patient.return_value = "pat_001"
    db.find_patient_by_phone.return_value = None
    db.remember_fact.return_value = None
    db.recall_fact.return_value = None
    db.list_memories.return_value = []
    db.forget_fact.return_value = True
    db.add_booking.return_value = None
    db.get_recent_bookings.return_value = []
    db.add_summary.return_value = None
    return db


@pytest.fixture
def sample_patient_doc():
    return {
        "patient_id": "pat_001",
        "first_name": "Ahmed",
        "last_name": "Hassan",
        "phone": "923001112233",
        "bookings": [],
        "conversation_summaries": [],
        "memories": [],
    }


@pytest.fixture
def sample_memories():
    return [
        {"key": "allergy", "value": "penicillin", "created_at": None, "updated_at": None},
        {"key": "preferred_time", "value": "morning", "created_at": None, "updated_at": None},
    ]
