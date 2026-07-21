
from flask import Blueprint

bp = Blueprint("course", __name__)


@bp.route("", methods=["GET"])
def get_courses():

@bp.route("<course_id>", methods = ["GET"])
def get_course():

@bp.route("", methods=["POST"])
def create_course():

@bp.route("<course_id>", methods = ["PATCH"])
def edit_course():

@bp.route("<course_id", methods = ["DELETE"])
def delete_course():





