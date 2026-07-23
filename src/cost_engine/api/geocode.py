"""Geocode a NYC address to a BBL using NYC Planning's GeoSearch API.

GeoSearch is free and needs no key. It returns a BBL in the feature's
`addendum.pad.bbl` when available. This is deterministic infrastructure, not an
LLM step.
"""

from __future__ import annotations

import requests

from ..ingest.bbl import normalize_bbl

GEOSEARCH_URL = "https://geosearch.planning.nyc.gov/v2/search"


def geocode_to_bbl(address: str) -> str | None:
    try:
        resp = requests.get(
            GEOSEARCH_URL, params={"text": address, "size": 1}, timeout=20
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None
    features = resp.json().get("features") or []
    if not features:
        return None
    props = features[0].get("properties", {})
    pad = (props.get("addendum") or {}).get("pad") or {}
    bbl = pad.get("bbl")
    return normalize_bbl(bbl) if bbl else None
