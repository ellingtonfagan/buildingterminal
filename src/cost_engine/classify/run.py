"""Batch-classify unclassified filings into the taxonomy, using the cache.

Idempotent: only classifies filings that lack a row in job_classifications.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
from datetime import datetime, timezone

from ..config import CONFIG
from ..db import get_initialized_connection
from ..llm.prompts import CLASSIFIER_PROMPT_VERSION
from .classifier import classify


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _input_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(limit: int | None = None) -> int:
    conn = get_initialized_connection()
    query = (
        "SELECT f.filing_id, f.work_description FROM filings f "
        "LEFT JOIN job_classifications c ON c.filing_id = f.filing_id "
        "WHERE c.filing_id IS NULL"
    )
    if limit:
        query += f" LIMIT {int(limit)}"
    rows = conn.execute(query).fetchall()
    print(f"Classifying {len(rows)} filings (model={CONFIG.classifier_model}, "
          f"prompt={CLASSIFIER_PROMPT_VERSION}) ...")

    done = 0
    for row in rows:
        desc = row["work_description"] or ""
        result = classify(desc, conn=conn)
        model_used = "heuristic" if (CONFIG.allow_heuristic_fallback and not CONFIG.anthropic_api_key) else CONFIG.classifier_model
        conn.execute(
            """
            INSERT OR REPLACE INTO job_classifications
              (filing_id, job_type, prompt_version, model, input_hash, rationale, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                row["filing_id"],
                result.job_type.value,
                CLASSIFIER_PROMPT_VERSION,
                model_used,
                _input_hash(desc),
                result.rationale,
                _now(),
            ),
        )
        done += 1
        if done % 100 == 0:
            conn.commit()
            print(f"  {done}/{len(rows)}")
    conn.commit()

    print(f"Classified {done} filings.")
    _print_distribution(conn)
    return 0


def _print_distribution(conn: sqlite3.Connection) -> None:
    print("\nClass distribution:")
    for r in conn.execute(
        "SELECT job_type, COUNT(*) AS n FROM job_classifications GROUP BY job_type ORDER BY n DESC"
    ):
        print(f"  {r['job_type']:35s} {r['n']}")


if __name__ == "__main__":
    sys.exit(run())
