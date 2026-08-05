"""Capacity and waitlist tests.
"""

from tests.conftest import course_payload, enrollment_payload


def enroll(client, course_id: int, n: int) -> list[dict]:
    """Enroll n students with distinct ids and return the created rows."""

    #list of enrollments created
    return [
        client.post(
            "/enrollments",
            #Need to add dummy students to test waitlist functionality
            json=enrollment_payload(course_id, student_id=f"S-2000{i}", student_name=f"Student {i}"),
        ).get_json()
        for i in range(n)
    ]


def test_enrolling_beyond_capacity_waitlists(client):
    """The seat goes to the first student, and the next is queued."""
    course = client.post("/courses", json=course_payload(capacity=1)).get_json()

    first, second = enroll(client, course["id"], 2)

    assert first["status"] == "enrolled"
    assert first["waitlist_position"] is None
    assert second["status"] == "waitlisted"
    assert second["waitlist_position"] == 1


def test_drop_promotes_waitlisted_student(client):
    """Dropping an enrolled student frees a seat, filled FIFO from the waitlist."""
    course = client.post("/courses", json=course_payload(capacity=1)).get_json()
    #Unpack the two students into variables
    enrolled, waitlisted = enroll(client, course["id"], 2)

    assert client.delete(f"/enrollments/{enrolled['id']}").status_code == 200

    promoted = client.get(f"/enrollments/{waitlisted['id']}").get_json()
    assert promoted["status"] == "enrolled"
    assert promoted["waitlist_position"] is None



def test_cannot_shrink_capacity_below_waitlist(client):
    """Capacity cannot shrink past the students already holding seats."""
    course = client.post("/courses", json=course_payload(capacity=2)).get_json()
    enroll(client, course["id"], 2)

    response = client.patch(f"/courses/{course['id']}", json={"capacity": 1})

    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "capacity_below_enrolled"
    assert body["enrolled_count"] == 2
    # The rejected change is rolled back
    assert client.get(f"/courses/{course['id']}").get_json()["capacity"] == 2

