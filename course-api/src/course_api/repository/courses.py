import sqlite3
from typing import Any


def _row_to_course(row: sqlite3.Row) -> dict[str, Any]:
    """Maps a sqlite3.Row to a dict[str, Any]"""
    return {
        "id": row["id"],
        "course_code": row["course_code"],
        "title": row["title"],
        "instructor": row["instructor"],
        "semester": row["semester"],
        "days": row["days"],
        "schedule": row["schedule"],
        "capacity": row["capacity"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_courses_sql(
        conn: sqlite3.Connection, 
        instructor: str | None = None, 
        semester: str | None = None, 
        limit: int = 100
) -> list[dict[str, Any]]:
    """The service function that will facilitate getting and filtering a list of courses."""
    where, params = [], []
    if instructor:
        where.append("instructor = ?") # placeholder string for the where which will be filled with
        params.append(instructor) # the value of priority that we will be filter on
    if semester:
        where.append("semester = ?")
        params.append(semester)
 
    sql = "SELECT * FROM courses"
    if where:
        sql += " WHERE " + " AND ".join(where) # SELECT * FROM tickets WHERE instructor/semester = ?
    sql += " ORDER BY created_at DESC LIMIT ?" # sorts our results by when they were created in decending order

    params.append(limit)
    return [_row_to_course(row) for row in conn.execute(sql, params).fetchall()] # want to get a list of dicts not a list of sqlite3.Row's

def get_course_sql(conn: sqlite3.Connection, course_id: str) -> dict[str, Any]:
    """Get an individual ticket by ID and return it as a DICT"""
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    return _row_to_course(row) if row else None
