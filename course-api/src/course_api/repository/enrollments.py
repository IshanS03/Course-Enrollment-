import sqlite3
from typing import Any


def _row_to_enrollment(row: sqlite3.Row) -> dict[str, Any]:
    """Maps a sqlite3.Row to a dict[str, Any]"""
    return {
        "id": row["id"],
        "course_id": row["course_id"],
        "student_id": row["student_id"],
        "student_name": row["student_name"],
        "status": row["status"],
        "grade": row["grade"],
        "waitlist_position": row["waitlist_position"],
        "enrolled_at": row["enrolled_at"],
        "updated_at": row["updated_at"],
    }


def list_enrollments_sql(
        conn: sqlite3.Connection,
        course_id: int | None = None,
        student_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
) -> list[dict[str, Any]]:
    """The function that will facilitate getting and filtering a list of enrollments."""
    where, params = [], []
    if course_id:
        where.append("course_id = ?") # placeholder string for the where which will be filled with
        params.append(course_id) # the value of course_id that we will filter on
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if status:
        where.append("status = ?")
        params.append(status)

    #course_id alone uses idx_enrollments_course, course_id + status uses idx_enrollments_course_status,
    #student_id alone uses idx_enrollments_student
    sql = "SELECT * FROM enrollments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY enrolled_at DESC LIMIT ?"

    params.append(limit)
    return [_row_to_enrollment(row) for row in conn.execute(sql, params).fetchall()] # want to get a list of dicts not a list of sqlite3.Row's


def get_enrollment_sql(conn: sqlite3.Connection, enrollment_id: str) -> dict[str, Any] | None:
    """Get a single enrollment by ID and return it as a DICT"""
    row = conn.execute("SELECT * FROM enrollments WHERE id = ?", (enrollment_id,)).fetchone()
    return _row_to_enrollment(row) if row else None



def create_enrollment_sql(conn: sqlite3.Connection, enrollment: dict[str, Any]) -> int:
    """Insert a single enrollment into the database based on the enrollment dict provided.
    Returns the id SQLite assigned to the new row."""
    cur = conn.execute(
        """
            INSERT INTO enrollments
                (course_id, student_id, student_name, status,
                 grade, waitlist_position, enrolled_at)
            VALUES (:course_id, :student_id, :student_name, :status,
                    :grade, :waitlist_position, :enrolled_at)
        """,
        {**enrollment}
    )

    return cur.lastrowid

def update_enrollment_sql(conn: sqlite3.Connection, enrollment: dict[str, Any]) -> None:
    """Update a enrollment and store the new fields into the database """

    conn.execute(
        """
        UPDATE enrollments
        SET course_id         = :course_id,
            student_id        = :student_id,
            student_name      = :student_name,
            status            = :status,
            grade             = :grade,
            waitlist_position = :waitlist_position,
            enrolled_at       = :enrolled_at,
            updated_at        = :updated_at
        WHERE id = :id
        """,
        {**enrollment}
    )

def delete_enrollment_sql(conn: sqlite3.Connection, id: dict[str, Any]) -> None:
    """Delete a enrollment from the database"""

    conn.execute(
        """
        DELETE from enrollments WHERE id = :id

        """,
        {"id": id}
    )


######      HELPERS       ######

def count_enrolled_for_course(conn: sqlite3.Connection, course_id: int) -> int:
    """Count active enrolled students in a course."""

     #idx_enrollments_course_status used here 
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM enrollments WHERE course_id = ? AND status = 'enrolled'",
        (course_id,)
    ).fetchone()
    return row["cnt"]

def get_first_in_line(conn: sqlite3.Connection, course_id: int) -> dict[str, Any] | None:
    "Get the student that should have their status updated"

    #idx_enrollments_course_status used here
    row = conn.execute(
        """
        SELECT * FROM enrollments WHERE course_id = ? AND status = 'waitlisted'
        ORDER BY waitlist_position ASC LIMIT 1
        """,
        (course_id,)
    ).fetchone()
    return _row_to_enrollment(row) if row else None


def promote_student(conn: sqlite3.Connection, enrollment_id: int, updated_at: str) -> None:
    "Move a waitlisted enrollment into a student seat"

    conn.execute(
        """
        UPDATE enrollments 
        SET status = 'enrolled', waitlist_position = NULL, updated_at = :updated_at
        WHERE id = :enrollment_id
        """,
        {"enrollment_id": enrollment_id, "updated_at": updated_at}
    )
    return 

def renumber_waitlist(conn: sqlite3.Connection, course_id: int, vacated_position: int, updated_at: str) -> None:
    """ Shift every one below the vacated spots by one """

    conn.execute(
        """
        UPDATE enrollments
        SET waitlist_position = waitlist_position - 1, updated_at = :updated_at
        WHERE waitlist_position > :vacated AND course_id = :course_id AND status = 'waitlisted'
        """,
        {"vacated": vacated_position, "course_id": course_id, "updated_at": updated_at}
    )    