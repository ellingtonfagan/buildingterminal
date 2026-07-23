"""Stage 1 orchestrator: ingest PLUTO + DOB filings + DOB NOW + permits, then
report row counts, date coverage, and the BIN->BBL match rate.

If the match rate is under 85%, STOP and report rather than proceeding on a bad
join (Stage 1 requirement).

Scope note: PLUTO is ingested for the full target ZIPs (all buildings) so the
match rate honestly measures join quality rather than the residential 5-50-unit
scope filter. The residential 5-50-unit band is applied downstream by the cost
model and comparable selection; the count of in-band buildings is reported here.

This module makes live network calls to NYC Open Data when run; field names vary
by dataset, so getters try several candidate keys and every raw row is stored.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone

from ..config import CONFIG, SOCRATA_DATASETS
from ..db import get_initialized_connection
from .bbl import make_bbl, normalize_bbl
from .socrata import SocrataClient

MATCH_RATE_THRESHOLD = 0.85


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first(row: dict, *keys: str) -> str | None:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return str(row[k])
    return None


def _money(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value if ch.isdigit() or ch == ".")
    if not cleaned or cleaned == ".":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _zip_in_clause(field: str) -> str:
    quoted = ",".join(f"'{z}'" for z in CONFIG.target_zips)
    return f"{field} in ({quoted})"


# --- PLUTO -----------------------------------------------------------------
def ingest_pluto(conn: sqlite3.Connection, client: SocrataClient) -> int:
    where = _zip_in_clause("zipcode")
    count = 0
    for row in client.query(SOCRATA_DATASETS["pluto"], where=where):
        bbl = normalize_bbl(_first(row, "bbl")) or make_bbl(
            _first(row, "borough"), _first(row, "block"), _first(row, "lot")
        )
        if not bbl:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO pluto
              (bbl, borough, block, lot, zipcode, address, year_built, num_floors,
               units_res, units_total, res_area, bldg_area, lot_area, bldg_class,
               land_use, ingested_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bbl,
                _first(row, "borough"),
                _int(_first(row, "block")),
                _int(_first(row, "lot")),
                _first(row, "zipcode"),
                _first(row, "address"),
                _int(_first(row, "yearbuilt", "year_built")),
                _float(_first(row, "numfloors", "num_floors")),
                _int(_first(row, "unitsres", "units_res")),
                _int(_first(row, "unitstotal", "units_total")),
                _int(_first(row, "resarea", "res_area")),
                _int(_first(row, "bldgarea", "bldg_area")),
                _int(_first(row, "lotarea", "lot_area")),
                _first(row, "bldgclass", "bldg_class"),
                _first(row, "landuse", "land_use"),
                _now(),
            ),
        )
        count += 1
    conn.commit()
    return count


# --- DOB filings (legacy + DOB NOW), unified table -------------------------
def ingest_filings(
    conn: sqlite3.Connection,
    client: SocrataClient,
    *,
    source: str,
    dataset_id: str,
    zip_field: str,
) -> int:
    where = _zip_in_clause(zip_field)
    for row in client.query(dataset_id, where=where):
        bbl = make_bbl(
            _first(row, "borough"),
            _first(row, "block"),
            _first(row, "lot"),
        ) or normalize_bbl(_first(row, "bbl"))
        external_id = _first(row, "job__", "job", "job_filing_number", "job_number")
        if external_id is None:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO filings
              (source, external_id, bin, bbl, borough, house_number, street_name,
               zipcode, dob_job_type, work_description, initial_cost, filing_date,
               status, ingested_at, raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                source,
                external_id,
                _first(row, "bin__", "bin"),
                bbl,
                _first(row, "borough"),
                _first(row, "house__", "house_no", "house_number"),
                _first(row, "street_name"),
                _first(row, zip_field),
                _first(row, "job_type", "job_type_description"),
                _first(row, "job_description", "work_description", "description") or "",
                _money(_first(row, "initial_cost", "estimated_job_cost", "total_est__fee")),
                _first(row, "pre__filing_date", "filing_date", "latest_action_date"),
                _first(row, "job_status", "filing_status", "job_status_descrp"),
                _now(),
                json.dumps(row),
            ),
        )
    conn.commit()
    return conn.execute(
        "SELECT COUNT(*) AS c FROM filings WHERE source = ?", (source,)
    ).fetchone()["c"]


# --- Permits ---------------------------------------------------------------
def ingest_permits(conn: sqlite3.Connection, client: SocrataClient) -> int:
    where = _zip_in_clause("zip_code")
    for row in client.query(SOCRATA_DATASETS["dob_permits"], where=where):
        external_id = _first(row, "job__", "job") or ""
        seq = _first(row, "permit_sequence__", "permit_si_no") or ""
        ext = f"{external_id}-{seq}" if seq else external_id
        if not ext:
            continue
        bbl = make_bbl(
            _first(row, "borough"), _first(row, "block"), _first(row, "lot")
        ) or normalize_bbl(_first(row, "bbl"))
        conn.execute(
            """
            INSERT OR IGNORE INTO permits
              (external_id, bin, bbl, borough, zipcode, permit_type, work_type,
               issuance_date, filing_date, ingested_at, raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ext,
                _first(row, "bin__", "bin"),
                bbl,
                _first(row, "borough"),
                _first(row, "zip_code"),
                _first(row, "permit_type"),
                _first(row, "work_type"),
                _first(row, "issuance_date"),
                _first(row, "filing_date"),
                _now(),
                json.dumps(row),
            ),
        )
    conn.commit()
    return conn.execute("SELECT COUNT(*) AS c FROM permits").fetchone()["c"]


# --- Reporting -------------------------------------------------------------
def match_rate(conn: sqlite3.Connection) -> tuple[int, int, float]:
    """Fraction of filings whose resolved BBL exists in the PLUTO table."""
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM filings WHERE bbl IS NOT NULL"
    ).fetchone()["c"]
    matched = conn.execute(
        "SELECT COUNT(*) AS c FROM filings f "
        "WHERE f.bbl IS NOT NULL AND EXISTS (SELECT 1 FROM pluto p WHERE p.bbl = f.bbl)"
    ).fetchone()["c"]
    rate = (matched / total) if total else 0.0
    return matched, total, rate


def date_coverage(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    row = conn.execute(
        "SELECT MIN(filing_date) AS lo, MAX(filing_date) AS hi FROM filings "
        "WHERE filing_date IS NOT NULL AND filing_date != ''"
    ).fetchone()
    return row["lo"], row["hi"]


def run() -> int:
    conn = get_initialized_connection()
    client = SocrataClient()

    print(f"Target ZIPs: {', '.join(CONFIG.target_zips)}")
    print("Ingesting PLUTO ...")
    n_pluto = ingest_pluto(conn, client)

    print("Ingesting DOB Job Application Filings ...")
    n_legacy = ingest_filings(
        conn, client,
        source="dob_job_applications",
        dataset_id=SOCRATA_DATASETS["dob_job_applications"],
        zip_field="zip_code",
    )

    print("Ingesting DOB NOW filings ...")
    n_now = ingest_filings(
        conn, client,
        source="dob_now",
        dataset_id=SOCRATA_DATASETS["dob_now"],
        zip_field="zip_code",
    )

    print("Ingesting DOB Permit Issuance ...")
    n_permits = ingest_permits(conn, client)

    in_band = conn.execute(
        "SELECT COUNT(*) AS c FROM pluto WHERE units_res BETWEEN ? AND ?",
        (CONFIG.min_units, CONFIG.max_units),
    ).fetchone()["c"]

    matched, total, rate = match_rate(conn)
    lo, hi = date_coverage(conn)

    print("\n=== Stage 1 report ===")
    print(f"PLUTO buildings (all in target ZIPs):      {n_pluto}")
    print(f"  of which residential {CONFIG.min_units}-{CONFIG.max_units} units:  {in_band}")
    print(f"DOB Job Application Filings:                {n_legacy}")
    print(f"DOB NOW filings:                           {n_now}")
    print(f"DOB Permit Issuance:                       {n_permits}")
    print(f"Filing date coverage:                      {lo}  ->  {hi}")
    print(f"BIN->BBL match rate:                       {matched}/{total} = {rate:.1%}")

    if rate < MATCH_RATE_THRESHOLD:
        print(
            f"\nSTOP: match rate {rate:.1%} is below the {MATCH_RATE_THRESHOLD:.0%} "
            "threshold. Do not proceed on this join.\n"
            "Investigate BBL resolution (borough codes, block/lot padding) and "
            "PLUTO coverage for these ZIPs before continuing to Stage 2."
        )
        return 1

    print("\nMatch rate OK. Proceed to Stage 2 (classification).")
    return 0


if __name__ == "__main__":
    sys.exit(run())
