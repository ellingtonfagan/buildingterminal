from datetime import datetime, timezone

from cost_engine.costmodel.model import confidence_for, estimate, percentile
from cost_engine.db import connect, init_db
from cost_engine.models import BuildingCharacteristics


def test_percentile_basic():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 0.5) == 3.0
    assert percentile(values, 1.0) == 5.0
    assert percentile([], 0.5) is None
    assert percentile([42.0], 0.5) == 42.0


def test_confidence_thresholds():
    assert confidence_for(0) == "low"
    assert confidence_for(19) == "low"
    assert confidence_for(20) == "medium"
    assert confidence_for(49) == "medium"
    assert confidence_for(50) == "high"


def _seed(conn, n, job_type="heating_system_replacement", units=8, borough="MN"):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO pluto (bbl, borough, zipcode, units_res, bldg_area, ingested_at) "
        "VALUES ('1000010001', ?, '10029', ?, 8000, ?)",
        (borough, units, now),
    )
    for i in range(n):
        cost = 1000.0 * (i + 1)
        conn.execute(
            "INSERT INTO filings (source, external_id, bbl, work_description, "
            "initial_cost, filing_date, ingested_at) "
            "VALUES ('dob_job_applications', ?, '1000010001', 'boiler', ?, '2026-01-01', ?)",
            (f"job-{i}", cost, now),
        )
        fid = conn.execute(
            "SELECT filing_id FROM filings WHERE external_id = ?", (f"job-{i}",)
        ).fetchone()["filing_id"]
        conn.execute(
            "INSERT INTO job_classifications (filing_id, job_type, prompt_version, "
            "model, input_hash, created_at) VALUES (?,?,?,?,?,?)",
            (fid, job_type, "test", "test", "h", now),
        )
    conn.commit()


def test_estimate_percentiles_and_confidence():
    conn = connect(":memory:")
    init_db(conn)
    _seed(conn, n=25)  # costs 1000..25000, filed in base year (no inflation shift)

    est = estimate(conn, "heating_system_replacement", BuildingCharacteristics(units_res=8, borough="MN"))

    assert est.n_comparables == 25
    assert est.confidence == "medium"  # 20 <= n < 50
    cr = est.cost_range
    assert cr.p25 is not None and cr.p50 is not None and cr.p75 is not None
    assert cr.p25 < cr.p50 < cr.p75
    # p50 of 1000..25000 is 13000
    assert abs(cr.p50 - 13000.0) < 1.0
    # per-unit p50 = 13000 / 8 units
    assert cr.per_unit_p50 is not None
    assert abs(cr.per_unit_p50 - 13000.0 / 8) < 1.0
    # The floor-bias caveat must always be present in the notes.
    assert any("floor-biased" in note for note in est.notes)


def test_estimate_low_confidence_when_thin():
    conn = connect(":memory:")
    init_db(conn)
    _seed(conn, n=5)

    est = estimate(conn, "heating_system_replacement", BuildingCharacteristics(units_res=8, borough="MN"))
    assert est.n_comparables == 5
    assert est.confidence == "low"
    assert any("LOW CONFIDENCE" in note for note in est.notes)
