"""Construction cost index — normalize historical declared costs to present-day
dollars before comparing.

The table below is an annual construction cost index (indexed so a recent year =
100). These are approximate, ENR-Building-Cost-Index-style values suitable for
v0; replace with a maintained series (e.g. ENR BCI, RSMeans city index for NYC)
for production. The point is that ALL costs are put on the same present-day
footing deterministically before any percentile is taken.
"""

from __future__ import annotations

# year -> index (present base year = 100). Approximate; documented as such.
_INDEX: dict[int, float] = {
    2005: 62.0, 2006: 65.0, 2007: 67.0, 2008: 69.0, 2009: 68.0,
    2010: 70.0, 2011: 72.0, 2012: 74.0, 2013: 76.0, 2014: 78.0,
    2015: 80.0, 2016: 82.0, 2017: 84.0, 2018: 87.0, 2019: 89.0,
    2020: 90.0, 2021: 95.0, 2022: 99.0, 2023: 100.0, 2024: 102.0,
    2025: 104.0, 2026: 106.0,
}

BASE_YEAR = 2026  # present-day reference


def _index_for(year: int) -> float:
    if year in _INDEX:
        return _INDEX[year]
    years = sorted(_INDEX)
    if year < years[0]:
        return _INDEX[years[0]]
    if year > years[-1]:
        return _INDEX[years[-1]]
    # linear interpolation between neighbors
    lo = max(y for y in years if y <= year)
    hi = min(y for y in years if y >= year)
    if lo == hi:
        return _INDEX[lo]
    frac = (year - lo) / (hi - lo)
    return _INDEX[lo] + frac * (_INDEX[hi] - _INDEX[lo])


def normalize(cost: float, year: int, base_year: int = BASE_YEAR) -> float:
    """Scale a cost from `year` dollars to `base_year` dollars."""
    base = _index_for(base_year)
    y = _index_for(year)
    if y <= 0:
        return cost
    return cost * (base / y)


def year_from_date(date_str: str | None) -> int | None:
    """Extract a 4-digit year from an ISO-ish date string."""
    if not date_str:
        return None
    for token in str(date_str).replace("/", "-").replace("T", "-").split("-"):
        token = token.strip()
        if len(token) == 4 and token.isdigit():
            y = int(token)
            if 1900 <= y <= 2100:
                return y
    return None
