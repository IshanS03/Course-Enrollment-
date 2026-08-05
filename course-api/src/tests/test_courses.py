"""CRUD tests for the /courses endpoints."""

import pytest

from tests.conftest import course_payload


def test_create_course(client):
    """POST /courses inserts body and returns id."""
    response = client.post("/courses", json=course_payload())

    assert response.status_code == 201
    body = response.get_json()
    assert isinstance(body["id"], int)
    assert body["student_id"] == "CS-301"
    assert body["capacity"] == 2
    assert body["enrichment"]["status"] == "pending"


def test_get_course(client, course):
    """GET /courses/{id} reads back exactly what POST created."""
    response = client.get(f"/courses/{course['id']}")

    assert response.status_code == 200
    assert response.get_json() == course


def test_get_missing_course_returns_404(client):
    """A miss returns the error envelope"""
    response = client.get("/courses/9999")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "course_not_found"
    assert "message" in body


def test_patch_course(client, course):
    """PATCH is partial so untouched fields keep their original values."""
    response = client.patch(f"/courses/{course['id']}", json={"instructor": "Alan Turing"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["instructor"] == "Alan Turing"
    assert body["title"] == course["title"]
    assert body["capacity"] == course["capacity"]


def test_delete_course(client, course):
    """DELETE returns 204 and the course is then unreachable."""
    assert client.delete(f"/courses/{course['id']}").status_code == 204
    assert client.get(f"/courses/{course['id']}").status_code == 404


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("course_code", "cs301"),        # must match regex
        ("title", "abc"),                # min_length=5
        ("capacity", -1),                # ge=0
        ("semester", "Winter 2026"),     # not in the Semester Literal
        ("days", "SAT"),                 # not in the Days Literal
        ("start_time", 3),               # ge=8
    ],
)
def test_create_course_rejects_bad_fields(client, field, bad_value):
    """Pydantic rejects input with a 422 envelope."""
    response = client.post("/courses", json=course_payload(**{field: bad_value}))

    assert response.status_code == 422
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert field in [detail["field"] for detail in body["details"]]
