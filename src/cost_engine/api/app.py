"""FastAPI app: /estimate (Stage 4) and /quotes (Stage 5).

Pipeline for /estimate:
    geocode -> look up building characteristics -> LLM structures the job
    description into a spec -> deterministic model returns the range.

The LLM never sees or produces a dollar figure in this path.
"""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..costmodel.model import estimate as compute_estimate
from ..db import get_initialized_connection
from ..models import BuildingCharacteristics, Estimate
from .buildings import lookup as lookup_building
from .geocode import geocode_to_bbl
from .job_spec import structure_job
from .quotes import extract_pdf_text, extract_quote, store_quote

app = FastAPI(
    title="Cost Engine v0",
    description=(
        "Defensible cost ranges for NYC building jobs from public data. "
        "LLMs parse input; deterministic code produces every number. Declared "
        "DOB costs are floor-biased — ranges are lower-bound-biased until real "
        "quotes calibrate them."
    ),
    version="0.1.0",
)


class EstimateRequest(BaseModel):
    address: str | None = None
    bbl: str | None = None
    job_description: str


class QuoteResponse(BaseModel):
    quote_id: int
    job_type: str
    total: float | None
    bbl: str | None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/estimate", response_model=Estimate)
def estimate_endpoint(req: EstimateRequest) -> Estimate:
    if not req.address and not req.bbl:
        raise HTTPException(status_code=422, detail="Provide either `address` or `bbl`.")

    conn = get_initialized_connection()

    # 1. Resolve to a BBL (geocode if needed) and look up building characteristics.
    bbl = req.bbl
    if bbl is None and req.address:
        bbl = geocode_to_bbl(req.address)

    building = lookup_building(conn, bbl) if bbl else None
    if building is None:
        # No building match — still structure the job, but we cannot scope
        # comparables to a real building profile.
        building = BuildingCharacteristics(bbl=bbl)

    # 2. LLM structures the plain-language description (no dollars in this path).
    spec = structure_job(req.job_description)

    # 3. Deterministic model returns the range + confidence + n.
    est = compute_estimate(
        conn,
        spec.job_type.value,
        building,
        clarifying_questions=spec.missing_info_questions,
    )
    if bbl and building.units_res is None:
        est.notes.append(
            "Building found but PLUTO characteristics were incomplete; comparable "
            "scoping fell back to the full unit band."
        )
    if not bbl:
        est.notes.append("Address/BBL did not resolve to a PLUTO building.")
    return est


@app.post("/quotes", response_model=QuoteResponse)
async def quotes_endpoint(file: UploadFile = File(...)) -> QuoteResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream", None):
        # be lenient; some clients send octet-stream for PDFs
        pass
    pdf_bytes = await file.read()
    try:
        text = extract_pdf_text(pdf_bytes)
    except Exception as e:  # noqa: BLE001 — surface a clean 400
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {e}") from e

    record = extract_quote(text)
    conn = get_initialized_connection()
    quote_id = store_quote(conn, record, source_file=file.filename)
    stored_bbl = conn.execute(
        "SELECT bbl FROM quotes WHERE quote_id = ?", (quote_id,)
    ).fetchone()["bbl"]
    return QuoteResponse(
        quote_id=quote_id,
        job_type=record.job_type.value,
        total=record.total,
        bbl=stored_bbl,
    )
