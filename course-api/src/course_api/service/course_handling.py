
import sqlite3
from typing import Any
from course_api.repository.courses import get_course_sql, update_course_sql
from course_api.repository.enrollments import count_enrolled_for_course
from course_api.service.enrollment_handling import promote_next_waitlisted

def update_course_service(conn: sqlite3.Connection, course_id, updates: dict[str, Any], now: str):

    """Service function for update course route in order to prevent race conditions
        as well as update potential waitlists"""

    conn.execute("BEGIN IMMEDIATE")
    try:
        course = get_course_sql(conn, course_id)
        if course is None:
            # raise custom exception here
            return

        capacity = course["capacity"]
        new_capacity = updates.get("capacity", capacity)

        #You're trying to reduce capacity below the number of students in the course (NOT VALID)
        if new_capacity < count_enrolled_for_course(conn, course_id):
            # raise custom exception here
            return

        #.update overwrites existing keys and adds new ones, leaves unchanged ones in place
        course.update(updates)
        course["updated_at"] = now
        update_course_sql(conn, course)

        #ADDING students from the waitlist one by one until you can't 
        if new_capacity > capacity:

            while promote_next_waitlisted(conn, course_id, now) is not None:
                pass

        conn.execute("COMMIT")
        return course

    except Exception:
        conn.execute("ROLLBACK")
        raise
