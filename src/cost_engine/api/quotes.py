"""Stage 5 — contractor quote PDF -> structured record, stored separately.

The LLM transcribes STATED figures from the quote (contractor name, line items,
materials with spec tier where stated, labor hours/rate, soft costs, total,
date, address). It does not estimate; a field is null when the quote does not
state it.

Quote records are written to the `quotes` table with source = 'contractor_quote'
and on the SAME comparable fields as DOB filings (job_type, bbl, total, date),
so declared costs and real quotes can be compared. This is the calibration set.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..config import CONFIG
from ..llm.prompts import QUOTE_PROMPT_VERSION, quote_system, quote_user
from ..models import QuoteRecord
from .geocode import geocode_to_bbl


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_quote(pdf_text: str) -> QuoteRecord:
    if not pdf_text.strip():
        return QuoteRecord()
    if CONFIG.allow_heuristic_fallback and not CONFIG.anthropic_api_key:
        # Offline dev aid: no structured extraction available without the LLM.
        return QuoteRecord()

    from ..llm.client import structured_call

    return structured_call(
        model=CONFIG.quote_model,
        system=quote_system(),
        user=quote_user(pdf_text),
        response_model=QuoteRecord,
        prompt_version=QUOTE_PROMPT_VERSION,
        max_tokens=2048,
    )


def store_quote(
    conn: sqlite3.Connection,
    record: QuoteRecord,
    *,
    source_file: str | None = None,
) -> int:
    bbl = geocode_to_bbl(record.address) if record.address else None
    cur = conn.execute(
        """
        INSERT INTO quotes
          (source, contractor_name, job_type, address, bbl, quote_date,
           total_cost, labor_hours, labor_rate, soft_costs, source_file,
           raw_extraction, created_at)
        VALUES ('contractor_quote',?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            record.contractor_name,
            record.job_type.value,
            record.address,
            bbl,
            record.quote_date,
            record.total,
            record.labor_hours,
            record.labor_rate,
            record.soft_costs,
            source_file,
            json.dumps(record.model_dump(mode="json")),
            _now(),
        ),
    )
    quote_id = int(cur.lastrowid)
    for item in record.line_items:
        conn.execute(
            """
            INSERT INTO quote_line_items
              (quote_id, description, material_spec_tier, quantity, unit_cost, amount)
            VALUES (?,?,?,?,?,?)
            """,
            (
                quote_id,
                item.description,
                item.material_spec_tier,
                item.quantity,
                item.unit_cost,
                item.amount,
            ),
        )
    conn.commit()
    return quote_id
