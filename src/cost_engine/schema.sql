-- Cost Engine v0 — SQLite schema.
--
-- Review this before ingesting anything (Stage 1 requirement).
--
-- Join model: DOB filings carry Borough/Block/Lot which compose a 10-digit BBL,
-- and a BIN. PLUTO is keyed by BBL. We resolve each filing to a BBL and join to
-- PLUTO on BBL; the "BIN->BBL match rate" is the fraction of filings whose
-- resolved BBL exists in the ingested PLUTO table.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Building characteristics (PLUTO), keyed by BBL.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pluto (
    bbl          TEXT PRIMARY KEY,      -- 10-digit borough-block-lot
    borough      TEXT,
    block        INTEGER,
    lot          INTEGER,
    zipcode      TEXT,
    address      TEXT,
    year_built   INTEGER,
    num_floors   REAL,
    units_res    INTEGER,               -- residential units
    units_total  INTEGER,
    res_area     INTEGER,               -- residential sq ft
    bldg_area    INTEGER,               -- gross building sq ft
    lot_area     INTEGER,
    bldg_class   TEXT,
    land_use     TEXT,
    ingested_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pluto_zip ON pluto(zipcode);

-- ---------------------------------------------------------------------------
-- DOB job filings (legacy Job Application Filings + DOB NOW), unified so they
-- can be compared on the same fields. `source` distinguishes them.
--
-- CAVEAT: initial_cost is a DECLARED cost. Owners systematically underdeclare to
-- reduce filing fees, so treat it as a FLOOR-BIASED signal, not truth. The
-- quote layer (see `quotes`) exists to quantify and correct this bias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS filings (
    filing_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL,     -- 'dob_job_applications' | 'dob_now'
    external_id      TEXT NOT NULL,     -- job number / job filing number
    bin              TEXT,
    bbl              TEXT,              -- resolved; joins to pluto.bbl
    borough          TEXT,
    house_number     TEXT,
    street_name      TEXT,
    zipcode          TEXT,
    dob_job_type     TEXT,             -- raw DOB job-type code (A1/A2/NB/...)
    work_description TEXT,             -- FREE TEXT — the classifier's input
    initial_cost     REAL,             -- DECLARED cost (floor-biased; see caveat)
    filing_date      TEXT,             -- ISO date
    status           TEXT,
    ingested_at      TEXT NOT NULL,
    raw              TEXT,             -- raw source row as JSON, for audit
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_filings_bbl ON filings(bbl);
CREATE INDEX IF NOT EXISTS idx_filings_zip ON filings(zipcode);

-- ---------------------------------------------------------------------------
-- DOB Permit Issuance — separate shape from job filings.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS permits (
    permit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id    TEXT NOT NULL UNIQUE,
    bin            TEXT,
    bbl            TEXT,
    borough        TEXT,
    zipcode        TEXT,
    permit_type    TEXT,
    work_type      TEXT,
    issuance_date  TEXT,
    filing_date    TEXT,
    ingested_at    TEXT NOT NULL,
    raw            TEXT
);
CREATE INDEX IF NOT EXISTS idx_permits_bbl ON permits(bbl);

-- ---------------------------------------------------------------------------
-- Classifier output (Stage 2). One row per classified filing.
-- We never store an LLM-produced numeric "confidence" — the model returns a
-- taxonomy label only; confidence is a deterministic function of sample size.
-- `rationale` is kept for audit and is never used as a number.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_classifications (
    filing_id      INTEGER PRIMARY KEY REFERENCES filings(filing_id),
    job_type       TEXT NOT NULL,      -- value from the fixed taxonomy
    prompt_version TEXT NOT NULL,
    model          TEXT NOT NULL,
    input_hash     TEXT NOT NULL,
    rationale      TEXT,               -- audit only, never a number
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_class_jobtype ON job_classifications(job_type);

-- ---------------------------------------------------------------------------
-- Aggressive LLM cache keyed by (prompt_version, normalized input). Ensures we
-- never pay to reclassify an identical description under the same prompt.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key      TEXT PRIMARY KEY,   -- hash(prompt_version + '\0' + input)
    prompt_version TEXT NOT NULL,
    model          TEXT NOT NULL,
    input_text     TEXT NOT NULL,
    output_json    TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Contractor quotes (Stage 5). Stored SEPARATELY from DOB data with a source
-- flag, and on the SAME comparable fields (job_type, bbl, total, date) so DOB
-- declared costs and real quotes can be compared directly. This is the eventual
-- calibration set for correcting the DOB underdeclaration bias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quotes (
    quote_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL DEFAULT 'contractor_quote',
    contractor_name TEXT,
    job_type        TEXT,              -- value from the fixed taxonomy
    address         TEXT,
    bbl             TEXT,
    quote_date      TEXT,
    total_cost      REAL,              -- transcribed from the quote (a stated figure)
    labor_hours     REAL,
    labor_rate      REAL,
    soft_costs      REAL,
    source_file     TEXT,
    raw_extraction  TEXT,              -- full structured extraction as JSON
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quotes_jobtype ON quotes(job_type);

CREATE TABLE IF NOT EXISTS quote_line_items (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id           INTEGER NOT NULL REFERENCES quotes(quote_id),
    description        TEXT,
    material_spec_tier TEXT,           -- e.g. builder-grade / mid / high, where stated
    quantity           REAL,
    unit_cost          REAL,
    amount             REAL
);

-- ---------------------------------------------------------------------------
-- Eval runs (Stage 2). Every run logs its prompt version so versions can be
-- compared over time. Results are also committed under evals/results/.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eval_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version TEXT NOT NULL,
    model          TEXT NOT NULL,
    n_examples     INTEGER NOT NULL,
    accuracy       REAL NOT NULL,
    report_json    TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
