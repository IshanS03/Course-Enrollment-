"""Shared pytest fixtures.

Every test gets its own SQLite file and a Flask test client. Azure is not connected in testing. 
"""

from pathlib import Path
from typing import Any

import pytest

from course_api import create_app

# schema.sql and courses.json live here
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Creates a Flask app with a throwaway SQLite database and no Azure."""
    monkeypatch.setenv("DATA_DIR", str(_DATA_DIR))
    # No Azure credentials
    for var in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
    ):
        #Need to do this because .env files are set in enrich.py and we want to test without them initially
        monkeypatch.delenv(var, raising=False)

    app = create_app(db_path=str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Entry for each api test"""
    return app.test_client()

# for course creation
def course_payload(**updates: Any) -> dict[str, Any]:
    """A valid POST /courses body. Override any field per test.
    """
    payload = {
        "course_code": "CS-311",
        "title": "Operating Systems",
        "instructor": "Ada Lovelace",
        "capacity": 2,
        "semester": "Fall 2026",
        "days": "MWF",
        "drop_deadline": "2026-12-01",
    }
    payload.update(updates)
    return payload

#for enrollment creation
def enrollment_payload(course_id: int, **updates: Any) -> dict[str, Any]:
    """A valid POST /enrollments body for the given course."""
    payload = {
        "course_id": course_id,
        "student_id": "S-10001",
        "student_name": "Grace Hopper",
    }
    payload.update(updates)
    return payload


@pytest.fixture
def course(client) -> dict[str, Any]:
    """A course that already exists in the database"""
    response = client.post("/courses", json=course_payload())
    assert response.status_code == 201
    return response.get_json()


@pytest.fixture
def enrollment(client, course) -> dict[str, Any]:
    """An enrollment that already exists in the database"""
    response = client.post(
        "/enrollments", json=enrollment_payload(course_id=course["id"])
    )
    assert response.status_code == 201
    return response.get_json()
