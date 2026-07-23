"""Aggressive LLM cache backed by SQLite, keyed by (prompt_version, input).

Ensures identical inputs under the same prompt version are never re-sent to the
model — so you are not paying to reclassify.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cache_key(prompt_version: str, input_text: str) -> str:
    h = hashlib.sha256()
    h.update(prompt_version.encode("utf-8"))
    h.update(b"\x00")
    h.update(input_text.encode("utf-8"))
    return h.hexdigest()


def get(conn: sqlite3.Connection, prompt_version: str, input_text: str) -> dict | None:
    key = cache_key(prompt_version, input_text)
    row = conn.execute(
        "SELECT output_json FROM llm_cache WHERE cache_key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["output_json"])


def put(
    conn: sqlite3.Connection,
    prompt_version: str,
    model: str,
    input_text: str,
    output: dict,
) -> None:
    key = cache_key(prompt_version, input_text)
    conn.execute(
        """
        INSERT OR REPLACE INTO llm_cache
            (cache_key, prompt_version, model, input_text, output_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (key, prompt_version, model, input_text, json.dumps(output), _now()),
    )
    conn.commit()
