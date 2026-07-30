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


def list_enrollments_for_course(
        conn: sqlite3.Connection, 
        course_id: str,
        limit: int = 100,) -> list[dict[str, Any]]:
    """The service function that will facilitate getting a list of enrollments."""

    #idx_enrollments_course_status used here 
    sql = f"SELECT * FROM enrollments where course_id = ? ORDER BY enrolled_at DESC LIMIT ?"

    return [_row_to_enrollment(row) for row in conn.execute(sql, (course_id, limit)).fetchall()] # want to get a list of dicts not a list of sqlite3.Row's

def count_enrolled_for_course(conn: sqlite3.Connection, course_id: int) -> int:
    """Count active enrolled students in a course."""
    
     #idx_enrollments_course_status used here 
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM enrollments WHERE course_id = ? AND status = 'enrolled'",
        (course_id,)
    ).fetchone()
    return row["cnt"]


def create_enrollment_sql(conn: sqlite3.Connection, enrollment: dict[str, Any]) -> None:
    """Insert a single enrollment into the database based on the enrollment dict provided."""
    conn.execute(
        """
            INSERT INTO enrollments
                (course_id, student_id, student_name, status,
                 grade, waitlist_position, enrolled_at)
            VALUES (:course_id, :student_id, :student_name, :status,
                    :grade, :waitlist_position, :enrolled_at)
        """,
        {**enrollment}
    )
    
    return

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