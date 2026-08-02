import os
from pathlib import Path

from flask import Flask
from course_api.api.blueprints.course import bp as course_bp
from course_api.api.blueprints.enrollment import bp as enrollment_bp
from course_api.api.blueprints.health import bp as h
from course_api.api.errors import register_error_handlers
from course_api.db import init_db, close_connection
from course_api.api.middleware import register_request_logging

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


_DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "courses.db"
)

def create_app(db_path : str | None  = None) -> Flask:

    #need to set up logging
    #configure_logging()

    app = Flask(__name__)

    app.config["DB_PATH"] = str(
        db_path or os.environ.get("DB_PATH") or _DEFAULT_DB_PATH
    )

    init_db(app.config["DB_PATH"])


    # mount the blueprints to the flask app
    app.register_blueprint(course_bp, url_prefix= "/courses") #localhost:5000/courses
    app.register_blueprint(enrollment_bp, url_prefix= "/enrollments") #localhost:5000/enrollments
    app.register_blueprint(h) 

    Limiter(
        key_func = get_remote_address,
        app=app,
        default_limits=["200 per minute"],
        storage_uri="memory://"
    )

    register_request_logging(app)
    register_error_handlers(app)
    app.teardown_appcontext(close_connection)

    # tiny top level route for smoke-testing
    @app.route("/", methods=["GET"]) # root
    def index() -> dict[str, str]:
        return {"service": "support-api", "version": "1.0.0"}

    return app
 