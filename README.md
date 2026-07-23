# Cost Engine v0 — NYC Building Cost Estimation

Produce a **defensible cost range** for a NYC building repair/capital job, from
public data, with an explicit confidence level and the number of comparable
records supporting it.

> **The one design principle, never violated:** LLMs parse unstructured input
> into structured data. **Deterministic code produces every number.** No model
> output is ever used directly as a dollar figure or a confidence level.

```
Natural language in   →  [LLM]   →  structured job spec
structured job spec   →  [CODE]  →  cost range + confidence
messy quote PDF       →  [LLM]   →  structured quote record
structured quotes     →  [CODE]  →  recalibrated model
```

## Data caveats (read these — they are written into the code as comments too)

1. **Declared cost ≠ actual cost.** Owners underdeclare DOB job costs to reduce
   filing fees. Treat the DOB `initial_cost` as a **floor-biased signal**, not
   truth. The collected-quote layer (Stage 5) exists to correct this bias, and
   quantifying the gap is itself the first publishable finding.
2. **Only documented/permitted work is covered.** Unpermitted work is invisible
   to this dataset. That is a deliberate scope decision, not an oversight.
3. **Work descriptions are inconsistent free text.** Mapping them to a fixed job
   taxonomy is the main LLM task (Stage 2).
4. **Inflation.** All historical costs are normalized to present-day dollars
   with a construction cost index before any comparison (Stage 3).

## Scope of v0

- A few ZIP codes to start (configure `TARGET_ZIPS`), residential, 5–50 units.
- 7-value job taxonomy (see `src/cost_engine/classify/taxonomy.py`).
- No user accounts, no payments, no UI polish.

## Architecture / stages

| Stage | What | Module |
|---|---|---|
| 1 | Ingest DOB filings + DOB NOW + permits + PLUTO into SQLite; report row counts, date coverage, BIN→BBL match rate | `cost_engine.ingest` |
| 2 | LLM classifier: free-text work description → fixed taxonomy, cached, validated, with an eval harness | `cost_engine.classify`, `evals/` |
| 3 | Deterministic cost model: percentiles (p25/p50/p75) by job type & building profile, inflation-normalized, sample-size aware | `cost_engine.costmodel` |
| 4 | FastAPI `/estimate` endpoint: geocode → building lookup → LLM job spec → deterministic range | `cost_engine.api` |
| 5 | Quote ingestion: PDF → structured quote record, stored separately with a source flag for calibration | `cost_engine.api.quotes` |

## Setup

Uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env      # then edit — no secrets are committed
```

Configuration lives in environment variables (see `.env.example`). Nothing
secret is hard-coded. The Anthropic API key is read from `ANTHROPIC_API_KEY`.

### Show the schema before ingesting anything

```bash
uv run python -m cost_engine.scripts.show_schema
```

### Stage 1 — ingest

```bash
uv run python -m cost_engine.ingest.run
```

Reports per-source row counts, date coverage, and the BIN→BBL match rate
against PLUTO. **If the match rate is under 85% it stops and tells you** rather
than proceeding on a bad join.

### Stage 2 — classify + eval

```bash
uv run python -m cost_engine.classify.run           # classify unlabeled filings (cached)
uv run python -m evals.run_classifier_eval          # score against evals/labels/*.csv
```

Hand-label rows in `evals/labels/classifier_labels_template.csv` (copy it to
`classifier_labels.csv`). The harness reports per-class precision/recall and
logs the prompt version with each run into `evals/results/`.

### Stage 3 — build the cost model

```bash
uv run python -m cost_engine.costmodel.build
```

### Stage 4 / 5 — API

```bash
uv run uvicorn cost_engine.api.app:app --reload
```

- `POST /estimate` — `{address | bbl, job_description}` → job type, p25/p50/p75,
  confidence, `n_comparables`, building characteristics used, and clarifying
  questions the model still has. The LLM in this path **never sees or produces a
  dollar figure.**
- `POST /quotes` — upload a contractor quote PDF; returns and stores a
  structured quote record (`source = 'contractor_quote'`) for calibration.

## Model choice

The classifier and the job-spec parser are **configurable** (`LLM_*_MODEL` in
`.env`). The classifier defaults to `claude-haiku-4-5` because it is a
high-volume, cache-heavy classification task and the prompt explicitly optimizes
for cost. Bump it to `claude-opus-4-8` for maximum accuracy — it is one env var.

## Testing

```bash
uv run pytest
```

Tests cover the deterministic pieces (percentile model, inflation
normalization, taxonomy validation). They run without an API key.

## Data sources

| Source | Socrata dataset | Gives |
|---|---|---|
| DOB Job Application Filings | `ic3t-wcy2` | job type, work description, initial cost, BIN/BBL, filing date |
| DOB NOW: Build – Job Application Filings | `w9ak-ipjd` | same, post-2017 filings |
| DOB Permit Issuance | `ipu4-2q9a` | permit type, work type, issuance date |
| PLUTO (tabular) | `64uk-42ks` | year built, floors, units, areas, building class |

Dataset IDs are configurable in `src/cost_engine/config.py`; verify them against
[NYC Open Data](https://opendata.cityofnewyork.us/) before a production run.
