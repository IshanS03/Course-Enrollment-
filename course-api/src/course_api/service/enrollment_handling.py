
import sqlite3
from typing import Any
from course_api.repository.courses import get_course_sql
from course_api.repository.enrollments import create_enrollment_sql, count_enrolled_for_course

def create_enrollment_service(conn: sqlite3.Connection, enrollment: dict[str, Any]):

    """Helper function for create enrollment route in order to prevent race conditions 
    as well as update potential waitlists"""

#Must wrap this function in a single operation as to prevent race conditions
    conn.execute("BEGIN IMMEDIATE")
    try:
        course = get_course_sql(conn, enrollment["course_id"])
        if course is None:
            #raise custom error here
            return

        enrolled_count = count_enrolled_for_course(conn, course_id=course["id"])
        #check if course capacity would be exceeded
        if enrolled_count >= course["capacity"]:
            enrollment["status"] = "waitlisted"
            enrollment["waitlist_position"] = next_waitlist_position(conn, course["id"])

        create_enrollment_sql(conn, enrollment)
        conn.execute("COMMIT")
        return enrollment

    except Exception:
        conn.execute("ROLLBACK")
        raise

#Helper to create function
def next_waitlist_position(conn: sqlite3.Connection, course_id: int) -> int:
    """Derive next waitlist position for an enrollment to a course that's at max capacity"""

    #Uses idx_enrollments_course_status
    row = conn.execute(
        "SELECT MAX(waitlist_position) AS max_pos "
        "FROM enrollments WHERE course_id = ? AND status = 'waitlisted'",
        (course_id,)
    ).fetchone()
    max_pos = row["max_pos"]
    return 1 if max_pos is None else max_pos + 1

