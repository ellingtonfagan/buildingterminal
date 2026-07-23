"""BBL (Borough-Block-Lot) helpers.

A BBL is the 10-digit key PLUTO is keyed on: 1 borough digit + 5-digit block +
4-digit lot. DOB filings carry Borough/Block/Lot (sometimes as a name, sometimes
a code) plus a BIN. We resolve each filing to a BBL to join against PLUTO.
"""

from __future__ import annotations

_BOROUGH_CODES = {
    "1": "1", "MANHATTAN": "1", "MN": "1", "NEW YORK": "1",
    "2": "2", "BRONX": "2", "BX": "2",
    "3": "3", "BROOKLYN": "3", "BK": "3", "KINGS": "3",
    "4": "4", "QUEENS": "4", "QN": "4",
    "5": "5", "STATEN ISLAND": "5", "SI": "5", "RICHMOND": "5",
}


def borough_code(value: str | None) -> str | None:
    if value is None:
        return None
    return _BOROUGH_CODES.get(str(value).strip().upper())


def make_bbl(borough: str | None, block: str | int | None, lot: str | int | None) -> str | None:
    """Compose a 10-digit BBL, or None if any part is missing/invalid."""
    bc = borough_code(borough)
    if bc is None or block in (None, "") or lot in (None, ""):
        return None
    try:
        block_i = int(str(block).strip())
        lot_i = int(str(lot).strip())
    except (TypeError, ValueError):
        return None
    return f"{bc}{block_i:05d}{lot_i:04d}"


def normalize_bbl(value: str | int | float | None) -> str | None:
    """Normalize an already-present BBL value to the 10-digit string form."""
    if value in (None, ""):
        return None
    try:
        digits = str(int(float(value)))
    except (TypeError, ValueError):
        digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) != 10:
        return None
    return digits
