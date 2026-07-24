# AGENTS.md — instructions for coding agents (Codex) working in this repo

You are the implementation agent on this project. A separate planning agent
(Claude, via Anthropic) writes specs and reviews your PRs. This file is your
persistent brief — read it before starting any task.

## What this project is

Cost Engine v0 — a defensible cost-range estimator for NYC building repair and
capital work, built from public DOB/PLUTO data. Full context: `README.md`.

**The one rule that overrides everything else in this repo:** LLMs parse
unstructured input into structured data. Deterministic code produces every
dollar figure and every confidence level. If a task would have an LLM call
return, compute, or influence a cost number or a confidence label directly,
stop and flag it instead of implementing it — that breaks the core product
guarantee.

## How work reaches you

Work is defined as **tickets** under `docs/codex-backlog/NNN-slug.md`. Each
ticket is a complete, scoped spec: goal, non-goals, concrete file-level
changes, acceptance criteria. Always implement from a ticket.

- If you're asked to do something with no matching ticket, write one first
  (copy the format from an existing ticket) describing what you're about to
  do, commit it alongside your change, and reference it in the PR. This keeps
  a written trail the planning agent can review against.
- If a ticket is ambiguous on a product decision (pricing model, UX copy,
  which vendor, which model tier) — don't guess. Leave the ticket's "Open
  questions" section filled in, implement the parts that aren't blocked, and
  say clearly in the PR description what's blocked and why.

## Setup & verification

```bash
uv sync --extra dev
uv run pytest
```

`uv run pytest` must pass with zero failures before you open a PR. The test
suite runs entirely offline (no API key, no network) — if a change makes tests
require a live Anthropic key or network access, that's a regression, not a
feature.

## Repo map

```
src/cost_engine/
  config.py        # all env-driven config — never hardcode secrets or values that belong here
  db.py             # SQLite connection + schema init (Postgres migration: see ticket 001)
  schema.sql        # source of truth for the schema — update this, not ad-hoc DDL
  models.py         # pydantic models shared across the app — LLM output shapes + API shapes
  ingest/           # Stage 1 — Socrata + PLUTO ingestion, BBL resolution
  classify/         # Stage 2 — taxonomy + LLM classifier + cache
  costmodel/        # Stage 3 — deterministic percentile model, cost-index normalization
  llm/              # structured-output client, versioned prompts, cache
  api/              # Stage 4/5 — FastAPI app, /estimate, /quotes
scripts/            # none yet at repo root — operational scripts live in src/cost_engine/scripts/
evals/              # Stage 2 eval harness + hand-labeled data + committed results
tests/              # pytest — deterministic-only, no API key required
docs/codex-backlog/ # your work queue
Dockerfile, fly.toml, DEPLOY.md   # deployment (Fly.io)
```

## Conventions

- Python 3.11+, type hints on public functions, `from __future__ import annotations`.
- No comments explaining *what* code does — only *why*, when it's genuinely
  non-obvious (matches the existing codebase; check nearby files for tone).
- Config always flows through `cost_engine.config.CONFIG` / env vars — never a
  hardcoded API key, connection string, or file path.
- Every LLM call goes through `cost_engine.llm.client.structured_call`
  (schema-validated, retried, prompt-version-logged) or a documented
  equivalent — don't hand-roll a new raw `client.messages.create` path.
- Schema changes go in `src/cost_engine/schema.sql` first; if the project has
  moved to Postgres by the time you're reading this (check `db.py` and
  `docs/codex-backlog/001-postgres-migration.md` status), follow whatever
  migration mechanism that ticket established instead of hand-editing the
  live schema.
- Keep PRs scoped to one ticket. Don't drive-by refactor unrelated code.

## PR checklist

1. Branch name: `codex/<ticket-id>-<short-slug>` (e.g. `codex/001-postgres-migration`).
2. PR description links the ticket file and summarizes the diff.
3. Paste the output of `uv run pytest` in the PR description.
4. Update the ticket file's status/checklist in the same PR (see
   `docs/codex-backlog/README.md` for the status convention).
5. If you touched deploy config (`Dockerfile`, `fly.toml`, env vars), update
   `DEPLOY.md` in the same PR.
6. Never commit `.env`, real credentials, or a populated SQLite/Postgres dump.

## Boundaries — do not

- Do not add a new LLM provider or swap the Anthropic SDK without an explicit
  ticket asking for it.
- Do not weaken the strict JSON-schema / validation path in
  `cost_engine.llm.client` to "make it easier to parse."
- Do not remove the floor-bias caveats/comments around declared DOB costs —
  they're load-bearing documentation, not clutter.
- Do not merge your own PR. Open it and stop; the planning agent (Claude) or
  the repo owner reviews and merges.
