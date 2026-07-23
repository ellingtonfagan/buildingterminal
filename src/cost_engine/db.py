"""SQLite connection + schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import CONFIG

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def schema_sql() -> str:
    return SCHEMA_PATH.read_text()


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection with row access by name and foreign keys enabled."""
    path = Path(db_path) if db_path is not None else CONFIG.db_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they do not exist."""
    conn.executescript(schema_sql())
    conn.commit()


def get_initialized_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    conn = connect(db_path)
    init_db(conn)
    return conn
