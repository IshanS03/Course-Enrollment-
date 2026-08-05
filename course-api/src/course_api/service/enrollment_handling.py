
import sqlite3
from datetime import datetime, timezone
from typing import Any

import structlog

from course_api.api.errors import CourseNotFound, EnrollmentNotFound
from course_api.repository.courses import get_course_sql
from course_api.repository.enrollments import create_enrollment_sql, get_enrollment_sql, update_enrollment_sql, count_enrolled_for_course, get_first_in_line, promote_student, renumber_waitlist

log = structlog.get_logger(__name__)

#A student holding one of these is still in the course.
_ACTIVE = ("enrolled", "waitlisted")

#Either one of these statuses will free a seat
_FREES_A_SEAT = ("dropped", "late_drop")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def create_enrollment_service(conn: sqlite3.Connection, enrollment: dict[str, Any]):

    """Service function for create enrollment route in order to prevent race conditions 
    as well as update potential waitlists"""

#Must wrap this function in a single operation as to prevent race conditions
    conn.execute("BEGIN IMMEDIATE")
    try:
        course = get_course_sql(conn, enrollment["course_id"])
        if course is None:
            raise CourseNotFound(enrollment["course_id"])

        #No grade is set when a student enrolls, and the default value for grade is None. 
        enrollment.setdefault("grade", None)

        enrolled_count = count_enrolled_for_course(conn, course_id=course["id"])
        #check if course capacity would be exceeded
        if enrolled_count >= course["capacity"]:
            enrollment["status"] = "waitlisted"
            enrollment["waitlist_position"] = _next_waitlist_position(conn, course["id"])
        else:
            enrollment["status"] = "enrolled"
            enrollment["waitlist_position"] = None

        #SQLite assigns the id via AUTOINCREMENT, read it back so the response
        #carries the real row id.
        enrollment_id = create_enrollment_sql(conn, enrollment)
        #Recall enrollment_id so the response carries the timestamps SQLite actually stored
        #rather than the in-memory ones.
        stored = get_enrollment_sql(conn, enrollment_id)
        conn.execute("COMMIT")
        return stored

    except Exception:
        conn.execute("ROLLBACK")
        raise

def update_enrollment_service(conn: sqlite3.Connection, enrollment_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:

    """Service function for update enrollment route in order to prevent race conditions
        as well as update potential waitlists"""

    now = _now()
    #Must wrap this function in a single operation as to prevent race conditions
    conn.execute("BEGIN IMMEDIATE")
    try:
        enrollment = get_enrollment_sql(conn, enrollment_id)
        if enrollment is None:
            raise EnrollmentNotFound(enrollment_id)

        old_position = enrollment["waitlist_position"]

        old_status = enrollment["status"]
        new_status = updates.get("status", old_status)
        course_id = enrollment["course_id"]

        #Dropping frees a seat, but completing the course does not.
        freed_seat = old_status == "enrolled" and new_status in _FREES_A_SEAT
        left_waitlist = old_status == "waitlisted" and new_status not in _ACTIVE

        #Want this to be a null value if they are no longer part of a waitlist
        if new_status not in _ACTIVE:
            updates["waitlist_position"] = None

        #.update overwrites existing keys and adds new ones, leaves unchanged ones in place
        enrollment.update(updates)
        enrollment["updated_at"] = now
        update_enrollment_sql(conn, enrollment)

        if freed_seat:
            #must promote a new student from the waitlist, change their status, and reorder (all happen in helper function)
            promote_next_waitlisted(conn, course_id, now)

        if left_waitlist:
            #a student has already been chosen and has had their status updated. Just reorder waitlist.
            renumber_waitlist(conn, course_id, old_position, now)

        conn.execute("COMMIT")
        return enrollment

    except Exception:
        conn.execute("ROLLBACK")
        raise

def drop_enrollment_service(conn: sqlite3.Connection, enrollment_id: str) -> dict[str, Any]:

    """Service function for the drop enrollment route. Rows are never deleted,
    and the partial unique index excludes them so the student can re-enroll later."""

    enrollment = get_enrollment_sql(conn, enrollment_id)
    if enrollment is None:
        raise EnrollmentNotFound(enrollment_id)
    course = get_course_sql(conn, enrollment["course_id"])
    if course is None:
        raise CourseNotFound(enrollment["course_id"])
    #A course with no deadline set can be dropped normally
    deadline = course["drop_deadline"]
    status = "late_drop" if deadline is not None and _now() > deadline else "dropped"

    return update_enrollment_service(conn, enrollment_id, {"status": status})


######  HELPERS  ######

#Helper to create route
def _next_waitlist_position(conn: sqlite3.Connection, course_id: int) -> int:
    """Derive next waitlist position for an enrollment to a course that's at max capacity"""

    #Uses idx_enrollments_course_status
    row = conn.execute(
        "SELECT MAX(waitlist_position) AS max_pos "
        "FROM enrollments WHERE course_id = ? AND status = 'waitlisted'",
        (course_id,)
    ).fetchone()
    max_pos = row["max_pos"]
    return 1 if max_pos is None else max_pos + 1


#Helper to update route
def promote_next_waitlisted(conn: sqlite3.Connection, course_id: int, now: str):
    "Fill one freed seat from a waitlist if anyone is waiting and there is room"

    #None here is helps flow, should not raise an exception.
    #callers loop until this returns None.

    course = get_course_sql(conn, course_id)
    if course is None:
        return None

    #Ensure that a seat ACTUALLY opened
    if count_enrolled_for_course(conn, course_id) >= course["capacity"]:
        return None 

    #Get first student in line
    eligible_student = get_first_in_line(conn, course_id)
    if eligible_student is None:
        return None #There is no student waiting

    #take their status off of waitlisted
    vacated_pos = eligible_student["waitlist_position"]
    promote_student(conn, eligible_student["id"], updated_at = now)

    #renumber the waitlist
    renumber_waitlist(conn, course["id"], vacated_pos, now)

    #Should be logged since user isn't immediately notified
    log.info(
        "waitlist_promoted",
        course_id=course_id,
        enrollment_id=eligible_student["id"],
        from_position=vacated_pos,
    )
    return eligible_student

