
from datetime import datetime, timezone

from flask import Blueprint, g, current_app, request
from course_api.db import connect
from course_api.repository.courses import list_courses_sql, get_course_sql, create_course_sql, update_course_sql, delete_course_sql
from course_api.service.course_handling import update_course_service, enrich_course_fields
from course_api.models.course import CourseCreate, CourseUpdate
from course_api.api.errors import CourseNotFound

bp = Blueprint("course", __name__)

def _db():
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"]) #flask env variable
    return g.db


@bp.route("", methods=["GET"])
def get_courses():
    """GET /courses
        returns all courses in the DB/JSON file.
    """
    courses = list_courses_sql(
        _db(),
        instructor = request.args.get("instructor"),
        semester = request.args.get("semester"),
        limit = int(request.args.get("limit", 100)),
        )
    
    return { "count": len(courses), "items": courses }


@bp.route("/<course_id>", methods = ["GET"])
def get_course(course_id: str):
    """GET /courses/{id}
        returns an individual course based on the ID provided.
    """
    course = get_course_sql( _db(),  course_id)

    if course is None:
        raise CourseNotFound(course_id)

    return course

@bp.route("", methods=["POST"])
def create_course():
    """POST /courses
        creates a course with specified parameters and returns it.
    """
    data = CourseCreate.model_validate(request.get_json(silent=True) or {})
    conn = _db()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    new_course = {
        **data.model_dump(),
        "created_at": now,
        "updated_at": now,
    }

    #Enrich before the INSERT so the course is written once
    new_course.update(enrich_course_fields(new_course, current_app.config.get("ENRICHMENT_CLIENT")))

    #SQLite assigns the id via AUTOINCREMENT, read it back so the response
    #carries the real row id
    course_id = create_course_sql(conn, new_course)
    conn.commit()

    return get_course_sql(conn, course_id), 201

@bp.route("/<course_id>", methods = ["PATCH"])
def edit_course(course_id):
    """PATCH /courses/{id}
        updates a course based on the ID provided.
    """
    conn = _db()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    data = CourseUpdate.model_validate(request.get_json(silent = True) or {})
   
    # CAN raise CourseNotFound OR CapacityBelowEnrolled
    update_course_service(conn, course_id, data.model_dump(exclude_unset=True), now,
                               client=current_app.config.get("ENRICHMENT_CLIENT"))

    #Re-read from database so we can get updates to enrichment fields   
    return get_course_sql(conn, course_id), 200

@bp.route("/<course_id>", methods = ["DELETE"])
def delete_course(course_id):
    """DELETE /courses/{id}
        deletes an individual course based on the ID provided.
    """
    conn = _db()
    course = get_course_sql(conn,  course_id)

    if course is None:
        raise CourseNotFound(course_id)

    delete_course_sql(conn, course_id)
    conn.commit()
    return "", 204





