import sqlite3
from pathlib import Path
from flask import g, current_app
import os

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "schema.sql"

_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "courses.db"

#_DATA_DIR = 
#def _resolve_db_path(db_path: Path | str | None) -> Path | str:
 #    """Priortiy: Explicit arg > DB_PATH env > Module default"""
 #    return db_path or os.environ.get("DB_PATH") or DEFAULT_DB_PATH

#def _resolve_data_dir() -> Path:
 #    return Path(os.environ.get("DATA_DIR") or _DATA_DIR)


#connection 
def connect(db_path: Path | str = _DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level = None) #isolation_level = None -> control when transactions start. Necessary to prevent race conditions. 
    conn.row_factory = sqlite3.Row # w/o this rows comeback as tuples rather than dict row [""]
    conn.execute("PRAGMA foreign_keys = ON")
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
def init_db(db_path: Path | str = _DEFAULT_DB_PATH) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    