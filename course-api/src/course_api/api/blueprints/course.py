
from datetime import datetime, timezone

from flask import Blueprint, g, current_app, request
from course_api.db import connect
from course_api.repository.courses import list_courses_sql, get_course_sql
from course_api.models.course import CourseCreate

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
        semester = request.args.get("semseter"),
        limit = int(request.args.get("limit", 100)),

        )
    
    return { "count": len(courses), "items": courses }


@bp.route("<course_id>", methods = ["GET"])
def get_course(course_id: str):
    """GET /courses/{id}
        returns an individual course based on the ID provided.
    """
    course = get_course_sql( _db(),  course_id) 

    if course is None:
        #create custom CourseNotFound exception here
        return
    else:
        return course

@bp.route("", methods=["POST"])
def create_course():
    """POST /courses
        creates a course with specified parameters and returns it.
    """
    data = CourseCreate.model_validate(request.get_json(silent=True) or {})
    conn = _db()
    conn = conn.execute()
    count = conn.execute("SELECT COUNT(*) AS n FROM courses").fetchone()["n"] # how many courses are in the database
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    new_course = {
        **data.model_dump(),
        "id": f"" #CHANGE THIS 
    }
    return

@bp.route("<course_id>", methods = ["PATCH"])
def edit_course():
    """PATCH /courses/{id}
        updates a course based on the ID provided.
    """
    return

@bp.route("<course_id>", methods = ["DELETE"])
def delete_course():
    """DELETE /courses/{id}
        deletes an individual course based on the ID provided.
    """
    return





