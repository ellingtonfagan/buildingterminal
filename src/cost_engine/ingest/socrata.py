"""Minimal Socrata (NYC Open Data) client with paging.

Uses the SoQL query API. An app token is optional but raises rate limits.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import requests

from ..config import CONFIG, SOCRATA_DOMAIN


class SocrataClient:
    def __init__(self, domain: str = SOCRATA_DOMAIN, app_token: str | None = None):
        self.domain = domain
        self.app_token = app_token if app_token is not None else CONFIG.socrata_app_token
        self.session = requests.Session()
        if self.app_token:
            self.session.headers["X-App-Token"] = self.app_token

    def _url(self, dataset_id: str) -> str:
        return f"https://{self.domain}/resource/{dataset_id}.json"

    def query(
        self,
        dataset_id: str,
        *,
        where: str | None = None,
        select: str | None = None,
        order: str | None = None,
        page_size: int = 5000,
        max_rows: int | None = None,
    ) -> Iterator[dict]:
        """Yield rows from a dataset, paging with $limit/$offset."""
        url = self._url(dataset_id)
        offset = 0
        yielded = 0
        while True:
            params: dict[str, str | int] = {"$limit": page_size, "$offset": offset}
            if where:
                params["$where"] = where
            if select:
                params["$select"] = select
            if order:
                params["$order"] = order
            resp = self.session.get(url, params=params, timeout=60)
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                return
            for row in rows:
                yield row
                yielded += 1
                if max_rows is not None and yielded >= max_rows:
                    return
            if len(rows) < page_size:
                return
            offset += page_size
            time.sleep(0.1)  # be polite to the API
