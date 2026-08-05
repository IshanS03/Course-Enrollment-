
import json
import sqlite3
from typing import Any

import structlog

from course_api.api.errors import CapacityBelowEnrolled, CourseNotFound
from course_api.repository.courses import get_course_sql, update_course_sql
from course_api.repository.enrollments import count_enrolled_for_course
from course_api.service.enrollment_handling import promote_next_waitlisted
from course_api.enrich import AzureEnrichmentClient

log = structlog.get_logger(__name__)

#Changing any of these invalidates an existing enrichment
_ENRICHMENT_TRIGGERS = {"learning_objectives", "title", "instructor", "semester"}


def update_course_service(conn: sqlite3.Connection, course_id, updates: dict[str, Any], now: str, client: AzureEnrichmentClient | None = None) -> dict[str, Any] | None:

    """Service function for update course route in order to prevent race conditions
        as well as update potential waitlists"""

   
    current = get_course_sql(conn, course_id)
    if current is None:
        raise CourseNotFound(course_id)

   #Enriches fields if any of the relevant trigger keys are changed; 
   #must do this before transaction begins
    if any(key in updates and updates[key] != current[key] for key in _ENRICHMENT_TRIGGERS):
        updates = {**updates, **enrich_course_fields({**current, **updates}, client)}

    conn.execute("BEGIN IMMEDIATE")
    try:
        course = get_course_sql(conn, course_id)
        if course is None:
            raise CourseNotFound(course_id)

        capacity = course["capacity"]
        new_capacity = updates.get("capacity", capacity)

        #You're trying to reduce capacity below the number of students in the course (NOT VALID)
        enrolled_count = count_enrolled_for_course(conn, course_id)
        if new_capacity < enrolled_count:
            raise CapacityBelowEnrolled(course_id, new_capacity, enrolled_count)

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


def enrich_course_fields(
    course: dict[str, Any],
    client: AzureEnrichmentClient | None = None,
) -> dict[str, Any]:
    """Generate the enrichment column values for a course.

    Takes the course rather than an id so it can run *before* the
    row is written, which keeps a create to a single INSERT.
    """
    #No client configured or nothing to ground on.
    #Inventing outcomes is forbiddeny system_prompt.
    if client is None or not course.get("learning_objectives"):
        return {
        "enrichment_status": "pending",
        "enrichment_overview": None,
        "enrichment_outcomes": None,
        "enrichment_audience": None,
        "enrichment_confidence": None,
    }

    try:
        enrichment = client.generate_enrichment(
            course["title"],
            course["course_code"],
            course["learning_objectives"],
        )
   
    #saved. structlog carries the request_id bound by the request middleware.
    except Exception:
        log.warning(
            "enrichment_failed",
            course_code=course.get("course_code"),
            exc_info=True,
        )
        return {
        "enrichment_status": "failed",
        "enrichment_overview": None,
        "enrichment_outcomes": None,
        "enrichment_audience": None,
        "enrichment_confidence": None,
    }

   
    log.info(
        "enrichment_completed",
        course_code=course.get("course_code"),
        confidence=enrichment.confidence,
    )

    #Only validated model output is persisted. Outcomes are a list and SQLite
    #has no array type, so they go in as a JSON array.
    return {
        "enrichment_status": "complete",
        "enrichment_overview": enrichment.overview,
        "enrichment_outcomes": json.dumps(enrichment.learning_outcomes),
        "enrichment_audience": enrichment.target_audience,
        "enrichment_confidence": enrichment.confidence,
    }