# 003 — Data pipeline hardening

**Status:** `backlog` — not detailed enough for Codex to start.

## Goal (draft)

Stage 1 ingestion (`cost_engine/ingest/run.py`) currently runs as a one-shot
manual script scoped to a handful of ZIPs, with no retry/backoff on Socrata
rate limits, no incremental/delta ingestion (every run re-queries everything
in scope), and no scheduling. Harden it toward something that can run
unattended and expand scope (more ZIPs, eventually full boroughs) without
babysitting.

Candidate scope (Claude to confirm before promoting to `ready`):
- Retry with backoff on Socrata 429s/5xxs (the `SocrataClient` in
  `ingest/socrata.py` currently has no error handling beyond
  `resp.raise_for_status()`).
- Incremental ingestion: only fetch filings/permits updated since the last
  successful run (Socrata datasets support `$where` on date fields — use the
  max `filing_date`/`issuance_date` already in the DB as the watermark)
  instead of re-pulling the full scope every time.
- A scheduled run (Fly.io scheduled machines, or a GitHub Actions cron job
  that calls a deploy-triggered endpoint) — depends on where 001's Postgres
  lands and how the app is deployed; sequence after 001.
- Expanding `TARGET_ZIPS` config to a borough-level or citywide scope, with a
  cost/runtime estimate for what that does to ingest time and DB size.

## Before this becomes `ready`

Claude needs to decide the incremental-ingestion watermark strategy and the
scheduling mechanism before this is safe for Codex to implement — both are
product/infra decisions, not just code.
