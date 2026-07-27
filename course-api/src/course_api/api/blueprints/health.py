from flask import Blueprint, current_app

bp = Blueprint("health", __name__)

#liveness
@bp.route("/live", methods = ["GET"])
def liveness():
    """Checks that the process is serving information, if not 
    orchestration should kill the container."""

    return {"status": "OK"}

#readiness
@bp.route("/ready", methods = ["GET"])
def readiness():
    """Determines whether the application is fit to receive and 
    process traffic, specifically if the connection to the database is established and interactable.
    """
    from course_api.db import connect

    try:
        conn = connect(current_app.config["DB_PATH"])
        try:
            #check if the database is interactable
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception as err:
        return {"status": "unready", "error": str(err)}, 503
    return {"status": "OK"}



