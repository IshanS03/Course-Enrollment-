import json
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
        "capacity": row["capacity"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "drop_deadline": row["drop_deadline"],
      
        "learning_objectives": row["learning_objectives"],
        #Enrichment is nested here so that the API can 
        #return a single object with all enrichment data, but the database stores it in flat columns.
        "enrichment": {
            "status": row["enrichment_status"],
        
            "ai_generated": bool(row["ai_generated"]), #This is the 2nd safeguard. 
            "overview": row["enrichment_overview"],
            #Stored as a JSON array; SQLite has no array type. NULL on any
            #course that is still pending or whose enrichment failed.
            "learning_outcomes": json.loads(row["enrichment_outcomes"]) if row["enrichment_outcomes"] else None,
            "target_audience": row["enrichment_audience"],
            "confidence": row["enrichment_confidence"],
        },
    }

##### HELPER 
def _write_params(course: dict[str, Any]) -> dict[str, Any]:
    """Flatten a course dict for INSERT/UPDATE.

    Updates will call _row_to_course which will cause a mismatch in dict structure of course, 
    must adjust for update_course_sql() to work properly.
    """
    nested = course.get("enrichment") or {}
    outcomes = nested.get("learning_outcomes")
    from_nested = {
        "enrichment_status": nested.get("status"),
        "ai_generated": nested.get("ai_generated"),
        "enrichment_overview": nested.get("overview"),
        #Came out of _decode_outcomes as a list; goes back as JSON.
        "enrichment_outcomes": json.dumps(outcomes) if outcomes else None,
        "enrichment_audience": nested.get("target_audience"),
        "enrichment_confidence": nested.get("confidence"),
    }
    from_nested = {k: v for k, v in from_nested.items() if v is not None}

    params = {**_ENRICHMENT_DEFAULTS, **from_nested, **course}
    params.pop("enrichment", None)
    return params

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

#Enrichment column defaults for a course dict that has not been enriched
_ENRICHMENT_DEFAULTS: dict[str, Any] = {
    "learning_objectives": None,
    "enrichment_status": "pending",
    "ai_generated": 0,
    "enrichment_overview": None,
    "enrichment_outcomes": None,
    "enrichment_audience": None,
    "enrichment_confidence": None,
}


def create_course_sql(conn: sqlite3.Connection, course: dict[str, Any]) -> int:
    """Insert a single course into the database based on the course dict provided.
    Returns the id SQLite assigned to the new row."""
    cur = conn.execute(
        """
            INSERT INTO courses
                (course_code, title, instructor, semester,
                 days, drop_deadline, start_time, end_time, capacity,
                 learning_objectives, enrichment_overview, enrichment_outcomes,
                 enrichment_audience, enrichment_confidence, enrichment_status,
                 ai_generated)
            VALUES (:course_code, :title, :instructor, :semester,
                    :days, :drop_deadline, :start_time, :end_time, :capacity,
                    :learning_objectives, :enrichment_overview, :enrichment_outcomes,
                    :enrichment_audience, :enrichment_confidence, :enrichment_status,
                    :ai_generated)
        """,
        _write_params(course)
    )
    #returns the id SQLite assigned to the new row
    return cur.lastrowid

def update_course_sql(conn: sqlite3.Connection, course: dict[str, Any]) -> None:
    """Update a course and store the new fields into the database """

    conn.execute(
        """
        UPDATE courses
        SET course_code   = :course_code,
            title         = :title,
            instructor    = :instructor,
            semester      = :semester,
            days          = :days,
            drop_deadline = :drop_deadline,
            start_time    = :start_time,
            end_time      = :end_time,
            capacity      = :capacity,
            learning_objectives   = :learning_objectives,
            enrichment_overview   = :enrichment_overview,
            enrichment_outcomes   = :enrichment_outcomes,
            enrichment_audience   = :enrichment_audience,
            enrichment_confidence = :enrichment_confidence,
            enrichment_status     = :enrichment_status,
            ai_generated          = :ai_generated,
            updated_at    = :updated_at
        WHERE id = :id
        """,
        _write_params(course)
    )

def delete_course_sql(conn: sqlite3.Connection, id: dict[str, Any]) -> None:
    """Delete a course from the database"""

    conn.execute(
        """
        DELETE from courses WHERE id = :id

        """,
        {"id": id}
    )