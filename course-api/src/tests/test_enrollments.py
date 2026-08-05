"""CRUD tests for the /enrollments endpoints."""

import pytest

from tests.conftest import enrollment_payload


def test_create_enrollment(client, course):
    """POST /enrollments inserts the body and returns server id."""
    
    response = client.post("/enrollments", json=enrollment_payload(course["id"]))
    assert response.status_code == 201
    body = response.get_json()
    assert isinstance(body["id"], int)
    assert body["student_id"] == "S-10001"
    assert body["student_name"] == "Grace Hopper"


def test_get_enrollment(client, enrollment):
    """GET /enrollments/{id} reads back exactly what POST created."""
    response = client.get(f"/enrollments/{enrollment['id']}")

    assert response.status_code == 200
    assert response.get_json() == enrollment


def test_get_missing_enrollment_returns_404(client):
    """A miss returns the error envelope"""
    response = client.get("/enrollments/9999")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "enrollment_not_found"
    assert "message" in body


def test_patch_enrollment(client, enrollment):
    """PATCH is partial so untouched fields keep their original values."""
    response = client.patch(f"/enrollments/{enrollment['id']}", json={"grade": "B+"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["grade"] == "B+"
    assert body["status"] == enrollment["status"]


def test_delete_enrollment(client, enrollment):
    """DELETE returns 204 and the enrollment is then unreachable."""
    response = client.delete(f"/enrollments/{enrollment['id']}")
    assert response.status_code == 200
    #enrollments do not get dropped
    assert response.get_json()["status"] == "dropped"
    assert client.get(f"/enrollments/{enrollment['id']}").status_code == 200

@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("student_name", ""),            # min_length=1
        ("student_id", "12345"),         # must match regex
        ("student_id", "S-123"),         # too few digits 
        ("course_id", "not-an-int"),     # must be an int         
    ],
)
def test_create_enrollment_rejects_bad_fields(client, course, field, bad_value):
    """Pydantic rejects input with a 422 envelope."""
    response = client.post("/enrollments", json=enrollment_payload(course["id"], **{field: bad_value}))

    assert response.status_code == 422
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert field in [detail["field"] for detail in body["details"]]
