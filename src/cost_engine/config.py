"""Central configuration. Values come from the environment (see .env.example).

No secrets are hard-coded here. Nothing in this file should ever be committed
with a real key in it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader so we don't add a dependency just for this.

    Only sets variables that are not already present in the environment.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _zips() -> list[str]:
    raw = os.environ.get("TARGET_ZIPS", "10029,10035,10037")
    return [z.strip() for z in raw.split(",") if z.strip()]


# Socrata dataset IDs. Defaults are the well-known NYC Open Data datasets; verify
# against opendata.cityofnewyork.us before a production run.
SOCRATA_DATASETS = {
    "dob_job_applications": "ic3t-wcy2",  # DOB Job Application Filings
    "dob_now": "w9ak-ipjd",               # DOB NOW: Build – Job Application Filings
    "dob_permits": "ipu4-2q9a",           # DOB Permit Issuance
    "pluto": "64uk-42ks",                 # PLUTO (tabular)
}
SOCRATA_DOMAIN = "data.cityofnewyork.us"


@dataclass(frozen=True)
class Config:
    # LLM
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    classifier_model: str = field(default_factory=lambda: os.environ.get("LLM_CLASSIFIER_MODEL", "claude-haiku-4-5"))
    jobspec_model: str = field(default_factory=lambda: os.environ.get("LLM_JOBSPEC_MODEL", "claude-haiku-4-5"))
    quote_model: str = field(default_factory=lambda: os.environ.get("LLM_QUOTE_MODEL", "claude-opus-4-8"))
    allow_heuristic_fallback: bool = field(
        default_factory=lambda: os.environ.get("ALLOW_HEURISTIC_FALLBACK", "0") == "1"
    )

    # Ingestion scope
    target_zips: list[str] = field(default_factory=_zips)
    min_units: int = field(default_factory=lambda: int(os.environ.get("MIN_UNITS", "5")))
    max_units: int = field(default_factory=lambda: int(os.environ.get("MAX_UNITS", "50")))
    socrata_app_token: str = field(default_factory=lambda: os.environ.get("SOCRATA_APP_TOKEN", ""))

    # Storage
    db_path: str = field(default_factory=lambda: os.environ.get("DB_PATH", "data/cost_engine.sqlite"))
    upload_dir: str = field(default_factory=lambda: os.environ.get("UPLOAD_DIR", "uploads"))

    def db_file(self) -> Path:
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


CONFIG = Config()

# Minimum comparable sample size below which the cost model must report low
# confidence and say so explicitly (Stage 3 requirement).
MIN_CONFIDENT_N = 20
