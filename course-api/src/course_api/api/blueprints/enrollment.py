
from datetime import datetime, timezone
from typing import get_args
from flask import Blueprint, g, current_app, request
from course_api.db import connect
from course_api.repository.enrollments import list_enrollments_sql, get_enrollment_sql
from course_api.models.enrollment import EnrollmentCreate, EnrollmentUpdate, Status
from course_api.api.errors import EnrollmentNotFound
from course_api.service.enrollment_handling import create_enrollment_service, update_enrollment_service, drop_enrollment_service, bulk_create_enrollments_service
from course_api.limiter import limiter
from pydantic import TypeAdapter

bp = Blueprint("enrollment", __name__)

def _db():
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"]) #flask env variable
    return g.db



@bp.route("", methods=["GET"])
def get_enrollments():
    """GET /enrollments
        returns enrollments in the DB, optionally filtered by course, student, or status.
    """

    #No pydantic dto created for this query so need to validate status
    status = request.args.get("status")
    if status is not None and status not in get_args(Status):
        return {"error": "invalid_status", 
                "message": f"status must be on of {','.join(get_args(Status))}"}
    
    enrollments = list_enrollments_sql(
        _db(),
        course_id = request.args.get("course_id", type=int),
        student_id = request.args.get("student_id"),
        status = status,
        limit = (request.args.get("limit", 100, type=int)),
        )

    return { "count": len(enrollments), "items": enrollments }


@bp.route("/<enrollment_id>", methods = ["GET"])
def get_enrollment(enrollment_id: str):
    """GET /enrollments/{id}
        returns an individual enrollment based on the ID provided.
    """
    enrollment = get_enrollment_sql( _db(),  enrollment_id)

    if enrollment is None:
        raise EnrollmentNotFound(enrollment_id)

    return enrollment

@bp.route("", methods=["POST"])
@limiter.limit("100 per minute")
def create_enrollment():
    """POST /enrollments
        creates a enrollment with specified parameters and returns it.
    """
    data = EnrollmentCreate.model_validate(request.get_json(silent=True) or {})
    conn = _db()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    new_enrollment = {
        **data.model_dump(),
        "enrolled_at": now,
        "updated_at": now,
    }
    enrollment = create_enrollment_service(conn, new_enrollment)
    return enrollment, 201

@bp.route("/bulk", methods=["POST"])
@limiter.limit("100 per minute")
def bulk_create_enrollments():
    """POST /enrollments/bulk
    creates enrollments from a list"""
    enrollments = request.get_json(silent=True)
    
    #check if enrollments is a list or is empty somehow
    if not isinstance(enrollments, list) or not enrollments:
        return {"error": "invalid_body", "message": "expected a non-empty JSON array"}, 400

    #Type adapter allows us to check if payload is a LIST OF EnrollmentCreates
    items = TypeAdapter(list[EnrollmentCreate]).validate_python(enrollments)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    new_enrollments = [
        {**i.model_dump(), 
         "enrolled_at": now, 
         "updated_at": now} 
        for i in items]

    enrollments = bulk_create_enrollments_service(_db(), new_enrollments)
    return {"count": len(enrollments), "items": enrollments}, 201

@bp.route("/<enrollment_id>", methods = ["PATCH"])
def edit_enrollment(enrollment_id):
    """PATCH /enrollments/{id}
        updates a enrollment based on the ID provided.
    """
    data = EnrollmentUpdate.model_validate(request.get_json(silent = True) or {})
    #data is a pydantic object, must dump it into dict
    #exclude_unset set so that only fields the client sent will change
    
    # CAN raise EnrollmentNotFound
    enrollment = update_enrollment_service(
        _db(), enrollment_id, data.model_dump(exclude_unset=True)
    )

    return enrollment, 200

@bp.route("/<enrollment_id>", methods = ["DELETE"])
def drop_enrollment(enrollment_id):
    """DELETE /enrollments/{id}
        drops a student from a course. The row is retained for auditing rather than
        deleted, and the freed seat promotes the first student off the waitlist.
    """
    #CAN Raises EnrollmentNotFound OR CourseNotFound
    enrollment = drop_enrollment_service(_db(), enrollment_id)

    return enrollment, 200

