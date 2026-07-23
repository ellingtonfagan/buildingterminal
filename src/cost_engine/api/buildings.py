"""Look up building characteristics (PLUTO) by BBL."""

from __future__ import annotations

import sqlite3

from ..models import BuildingCharacteristics


def lookup(conn: sqlite3.Connection, bbl: str) -> BuildingCharacteristics | None:
    row = conn.execute("SELECT * FROM pluto WHERE bbl = ?", (bbl,)).fetchone()
    if row is None:
        return None
    return BuildingCharacteristics(
        bbl=row["bbl"],
        zipcode=row["zipcode"],
        borough=row["borough"],
        year_built=row["year_built"],
        num_floors=row["num_floors"],
        units_res=row["units_res"],
        units_total=row["units_total"],
        res_area=row["res_area"],
        bldg_area=row["bldg_area"],
        bldg_class=row["bldg_class"],
    )
