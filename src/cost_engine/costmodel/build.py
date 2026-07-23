"""Report deterministic cost-model summaries per job type and unit band.

The estimate itself is computed live from the DB by `model.estimate`; this
script materializes a human-readable summary so you can eyeball the ranges (and
show them to a contractor).
"""

from __future__ import annotations

import sys

from ..classify.taxonomy import TAXONOMY_VALUES
from ..db import get_initialized_connection
from ..models import BuildingCharacteristics
from .model import estimate

_UNIT_BANDS = [(5, 10), (11, 20), (21, 35), (36, 50)]


def run() -> int:
    conn = get_initialized_connection()
    print("Deterministic cost model summary (present-day $, floor-biased).\n")
    print(f"{'job_type':35s} {'units':>7s} {'n':>5s} {'p25':>12s} {'p50':>12s} {'p75':>12s} conf")
    print("-" * 95)
    for job_type in TAXONOMY_VALUES:
        for lo, hi in _UNIT_BANDS:
            mid = (lo + hi) // 2
            est = estimate(
                conn,
                job_type,
                BuildingCharacteristics(units_res=mid),
            )
            cr = est.cost_range

            def fmt(v: float | None) -> str:
                return f"${v:,.0f}" if v is not None else "-"

            print(
                f"{job_type:35s} {f'{lo}-{hi}':>7s} {est.n_comparables:>5d} "
                f"{fmt(cr.p25):>12s} {fmt(cr.p50):>12s} {fmt(cr.p75):>12s} {est.confidence}"
            )
    print(
        "\nReminder: these are declared-cost percentiles (floor-biased). Upload "
        "real quotes via POST /quotes to build the calibration set."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
