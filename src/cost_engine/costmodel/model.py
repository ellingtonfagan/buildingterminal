"""Deterministic cost model.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │ CAVEAT — this model returns a FLOOR-BIASED signal, not truth.            │
    │                                                                         │
    │ Every cost here derives from DOB "initial_cost", a DECLARED value.       │
    │ Owners systematically underdeclare job costs to reduce filing fees, so   │
    │ these percentiles sit BELOW real market cost — how far below is not      │
    │ constant and varies by job type. Until the collected-quote layer         │
    │ (Stage 5) provides real quotes to calibrate against, treat the output    │
    │ as a lower-bound-biased reference, and say so to the user.               │
    │                                                                         │
    │ No LLM is involved in this module. Every number is computed here.        │
    └─────────────────────────────────────────────────────────────────────────┘

Costs are normalized to present-day dollars (cost_index) before any percentile
is taken. Estimates are returned as p25/p50/p75 — never a single point estimate —
along with the sample size n and a confidence level that is a deterministic
function of n (n < 20 => low, and we say so explicitly).
"""

from __future__ import annotations

import sqlite3

from ..config import CONFIG, MIN_CONFIDENT_N
from ..models import BuildingCharacteristics, CostRange, Estimate
from .cost_index import normalize, year_from_date


def percentile(sorted_values: list[float], q: float) -> float | None:
    """Linear-interpolation percentile (q in [0,1]) over a sorted list."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def _unit_band(units: int | None) -> tuple[int, int]:
    """Bucket a residential unit count into a comparison band within 5-50."""
    if units is None:
        return (CONFIG.min_units, CONFIG.max_units)
    if units <= 10:
        return (5, 10)
    if units <= 20:
        return (11, 20)
    if units <= 35:
        return (21, 35)
    return (36, 50)


def confidence_for(n: int) -> str:
    if n < MIN_CONFIDENT_N:
        return "low"
    if n < 50:
        return "medium"
    return "high"


def _comparable_costs(
    conn: sqlite3.Connection,
    job_type: str,
    unit_lo: int,
    unit_hi: int,
    borough: str | None,
) -> tuple[list[float], list[float], list[float]]:
    """Return (normalized_total, per_unit, per_sqft) lists for comparables:
    classified filings of this job type on buildings in the unit band (and
    borough, if given), with a positive declared cost."""
    sql = (
        "SELECT f.initial_cost, f.filing_date, p.units_res, p.bldg_area, p.borough "
        "FROM filings f "
        "JOIN job_classifications c ON c.filing_id = f.filing_id "
        "JOIN pluto p ON p.bbl = f.bbl "
        "WHERE c.job_type = ? AND f.initial_cost IS NOT NULL AND f.initial_cost > 0 "
        "AND p.units_res BETWEEN ? AND ?"
    )
    params: list[object] = [job_type, unit_lo, unit_hi]
    if borough:
        sql += " AND p.borough = ?"
        params.append(borough)

    totals: list[float] = []
    per_unit: list[float] = []
    per_sqft: list[float] = []
    for r in conn.execute(sql, params):
        year = year_from_date(r["filing_date"]) or 2020
        cost = normalize(float(r["initial_cost"]), year)
        totals.append(cost)
        if r["units_res"]:
            per_unit.append(cost / float(r["units_res"]))
        if r["bldg_area"]:
            per_sqft.append(cost / float(r["bldg_area"]))
    return totals, per_unit, per_sqft


def estimate(
    conn: sqlite3.Connection,
    job_type: str,
    building: BuildingCharacteristics,
    clarifying_questions: list[str] | None = None,
) -> Estimate:
    unit_lo, unit_hi = _unit_band(building.units_res)
    totals, per_unit, per_sqft = _comparable_costs(
        conn, job_type, unit_lo, unit_hi, building.borough
    )

    # If the borough-scoped sample is thin, widen to all boroughs (still within
    # the unit band and job type) rather than return nothing.
    notes: list[str] = []
    if len(totals) < MIN_CONFIDENT_N and building.borough:
        w_totals, w_per_unit, w_per_sqft = _comparable_costs(
            conn, job_type, unit_lo, unit_hi, borough=None
        )
        if len(w_totals) > len(totals):
            notes.append(
                "Widened comparables to all boroughs because the borough-specific "
                f"sample was small (n={len(totals)})."
            )
            totals, per_unit, per_sqft = w_totals, w_per_unit, w_per_sqft

    totals.sort()
    per_unit.sort()
    per_sqft.sort()
    n = len(totals)

    cost_range = CostRange(
        p25=percentile(totals, 0.25),
        p50=percentile(totals, 0.50),
        p75=percentile(totals, 0.75),
        per_unit_p50=percentile(per_unit, 0.50),
        per_sqft_p50=percentile(per_sqft, 0.50),
    )
    conf = confidence_for(n)

    notes.append(
        "Costs derive from DOB declared costs, which are floor-biased due to "
        "owner underdeclaration; treat this range as a lower-bound-biased signal "
        "until real quote data calibrates it."
    )
    if conf == "low":
        notes.append(
            f"LOW CONFIDENCE: only {n} comparable records "
            f"(< {MIN_CONFIDENT_N}) for this job type and building profile."
        )

    return Estimate(
        job_type=job_type,  # type: ignore[arg-type]
        cost_range=cost_range,
        confidence=conf,
        n_comparables=n,
        building=building,
        clarifying_questions=clarifying_questions or [],
        notes=notes,
    )
