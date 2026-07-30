import json
import sqlite3
from pathlib import Path
from flask import g, current_app
import os


_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "courses.db"

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
def _resolve_db_path(db_path: Path | str | None) -> Path | str:
   """Priortiy: Explicit arg > DB_PATH env > Module default"""
   return db_path or os.environ.get("DB_PATH") or _DEFAULT_DB_PATH

def _resolve_data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR") or _DATA_DIR)



#connection 
def connect(db_path: Path | str = _DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level = None) #isolation_level = None -> control when transactions start. Necessary to prevent race conditions. 
    conn.row_factory = sqlite3.Row # w/o this rows comeback as tuples rather than dict row [""]
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA budy_timeout = 5000")
    return conn

#get an already existing connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect(current_app.config["DB_PATH"])
    return db


def close_connection(exception = None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

#initialize db
def init_db(db_path: Path | str | None = None) -> None:


    db_path = _resolve_db_path(db_path)
    schema_path = _resolve_data_dir() / "schema.sql" #schema.sql resides in /app/data/ in docker
    conn = connect(db_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
    finally:
        conn.close()


def seed_from_json(db_path: Path | str | None = None) -> int:


    """Seed the courses table from data/courses.json.
    """

    db_path = _resolve_db_path(db_path)
        
    data_dir = _resolve_data_dir()
    courses = json.loads((data_dir / "courses.json").read_text(encoding="utf-8"))
    conn = connect(db_path)
    try:
        # courses
        conn.executemany(
            """
                INSERT OR REPLACE INTO courses
                    (course_code, title, instructor, semester,
                     days, start_time, end_time, capacity)
                    VALUES (:course_code, :title, :instructor, :semester,
                            :days, :start_time, :end_time, :capacity)
            """, courses
        )
       
        conn.commit()
    finally:
        conn.close()
    return len(courses)
