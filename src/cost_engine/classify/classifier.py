"""Classify a single free-text work description into the fixed taxonomy.

Primary path: the LLM (structured output, validated, cached). Off-taxonomy
labels are rejected by the validation step and fall back to OTHER.

Offline dev aid (only when ALLOW_HEURISTIC_FALLBACK=1 and no API key): a
transparent keyword heuristic so the pipeline and tests can run without spending
money or requiring network. This is NOT a substitute for the LLM classifier and
must never be relied on for real classification.
"""

from __future__ import annotations

import re
import sqlite3

from ..config import CONFIG
from ..llm import cache
from ..llm.prompts import (
    CLASSIFIER_PROMPT_VERSION,
    classifier_system,
    classifier_user,
)
from ..models import Classification
from .taxonomy import JobType, coerce

# Keyword patterns for the offline heuristic ONLY. Ordered most-specific first.
_HEURISTIC_PATTERNS: list[tuple[JobType, re.Pattern[str]]] = [
    (JobType.HEATING_REPLACEMENT, re.compile(r"\b(boiler|burner|heating|hot water heater|hvac)\b", re.I)),
    (JobType.ROOF, re.compile(r"\b(roof|re-?roof|recoat|roofing|parapet coping)\b", re.I)),
    (JobType.FACADE, re.compile(r"\b(facade|fa[cç]ade|pointing|parapet|ll11|local law 11|fisp|exterior wall|brick)\b", re.I)),
    (JobType.PLUMBING_RISER, re.compile(r"\b(risers?|plumbing|water main|waste line|gas line|piping)\b", re.I)),
    (JobType.ELECTRICAL_UPGRADE, re.compile(r"\b(electrical service|service upgrade|amperage|meter|service entrance|amps?)\b", re.I)),
    (JobType.INTERIOR_RENO, re.compile(r"\b(interior|renovation|renovate|apartment|kitchen|bathroom|gut)\b", re.I)),
]


def _heuristic(work_description: str) -> Classification:
    for job_type, pattern in _HEURISTIC_PATTERNS:
        if pattern.search(work_description):
            return Classification(job_type=job_type, rationale="offline keyword heuristic")
    return Classification(job_type=JobType.OTHER, rationale="offline keyword heuristic: no match")


def _use_heuristic() -> bool:
    return CONFIG.allow_heuristic_fallback and not CONFIG.anthropic_api_key


def classify(
    work_description: str,
    conn: sqlite3.Connection | None = None,
) -> Classification:
    """Classify one work description, using the cache when a connection is given."""
    text = (work_description or "").strip()
    if not text:
        return Classification(job_type=JobType.OTHER, rationale="empty description")

    if _use_heuristic():
        return _heuristic(text)

    # Cache lookup keyed by (prompt_version, description).
    if conn is not None:
        cached = cache.get(conn, CLASSIFIER_PROMPT_VERSION, text)
        if cached is not None:
            return _validated(cached)

    from ..llm.client import structured_call

    result = structured_call(
        model=CONFIG.classifier_model,
        system=classifier_system(),
        user=classifier_user(text),
        response_model=Classification,
        prompt_version=CLASSIFIER_PROMPT_VERSION,
    )
    # Validation step: reject any off-taxonomy label (coerce raises if invalid).
    coerce(result.job_type.value)

    if conn is not None:
        cache.put(
            conn,
            CLASSIFIER_PROMPT_VERSION,
            CONFIG.classifier_model,
            text,
            result.model_dump(mode="json"),
        )
    return result


def _validated(payload: dict) -> Classification:
    result = Classification.model_validate(payload)
    coerce(result.job_type.value)  # reject off-taxonomy even from cache
    return result
