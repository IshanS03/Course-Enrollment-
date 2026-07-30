
from datetime import datetime, timezone

from flask import Blueprint, g, current_app, request
from course_api.db import connect
from course_api.repository.enrollments import list_enrollments_sql, get_enrollment_sql, create_enrollment_sql, update_enrollment_sql, delete_enrollment_sql
from course_api.models.enrollment import EnrollmentCreate, Enrollment, EnrollmentCreate
from course_api.service.enrollment_handling import create_enrollment_service
import uuid

bp = Blueprint("enrollment", __name__)

def _db():
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"]) #flask env variable
    return g.db


@bp.route("", methods=["GET"])
def get_enrollments():
    """GET /enrollments
        returns all enrollments in the DB/JSON file.
    """
    enrollments = list_enrollments_sql(
        _db(),
        instructor = request.args.get("instructor"),
        semester = request.args.get("semseter"),
        limit = int(request.args.get("limit", 100)),
        )
    
    return { "count": len(enrollments), "items": enrollments }


@bp.route("<enrollment_id>", methods = ["GET"])
def get_enrollment(enrollment_id: str):
    """GET /enrollments/{id}
        returns an individual enrollment based on the ID provided.
    """
    enrollment = get_enrollment_sql( _db(),  enrollment_id) 

    if enrollment is None:
        #create custom enrollmentNotFound exception here
        return
    else:
        return enrollment

@bp.route("", methods=["POST"])
def create_enrollment():
    """POST /enrollments
        creates a enrollment with specified parameters and returns it.
    """
    data = EnrollmentCreate.model_validate(request.get_json(silent=True) or {})
    conn = _db()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    id = str(uuid.uuid4())
    new_enrollment = {
        **data.model_dump(),
        "id": id, # will possibly change this
        "updated_at": now,
    }
    create_enrollment_service(conn, new_enrollment)
    return new_enrollment, 201

@bp.route("<enrollment_id>", methods = ["PATCH"])
def edit_enrollment(enrollment_id):
    """PATCH /enrollments/{id}
        updates a enrollment based on the ID provided.
    """
    conn = _db()
    enrollment = get_enrollment_sql(conn,  enrollment_id) 

    if enrollment is None:
        #create custom enrollmentNotFound exception here
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    data = enrollmentUpdate.model_validate(request.get_json(silent = True) or {})
    #data is a pydantic object, must dump it into dict
    #exclude_unset set so that only fields the client sent will change 
    for field, value in data.model_dump(exclude_unset=True).items():
        enrollment[field] = value

    enrollment["updated_at"] = now
    update_enrollment_sql(conn, enrollment)

    conn.commit()
    return enrollment, 200

@bp.route("<enrollment_id>", methods = ["DELETE"])
def delete_enrollment(enrollment_id):
    """DELETE /enrollments/{id}
        deletes an individual enrollment based on the ID provided.
    """
    conn = _db()
    enrollment = get_enrollment_sql(conn,  enrollment_id) 

    if enrollment is None:
        #create custom enrollmentNotFound exception here
        return

    delete_enrollment_sql(conn, enrollment_id)
    conn.commit()
    return 204

