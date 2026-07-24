# Codex backlog

This is the work queue for the implementation agent (Codex). Claude (planning)
writes and refines tickets here; Codex implements them as PRs; CI gates; Claude
or the repo owner reviews and merges.

## Ticket format

Each ticket is one file: `NNN-slug.md`, numbered in the order they were
created (not necessarily the order they're worked). A ticket has:

- **Status** — `backlog` (not detailed enough to start) / `ready` (fully
  scoped, Codex can start) / `in_progress` / `done`.
- **Goal** — one paragraph, plain language.
- **Non-goals** — explicitly out of scope, to stop scope creep.
- **Changes** — concrete, file-level where possible.
- **Acceptance criteria** — a checklist; the PR should be able to check every
  box before merge.
- **Open questions** — anything Codex should stop and flag rather than guess.

## Current tickets

| # | Title | Status | Notes |
|---|---|---|---|
| [001](001-postgres-migration.md) | Postgres migration | `ready` | First up — durable DB for the Fly.io deploy. |
| [002](002-web-ui.md) | Web UI | `backlog` | Needs scoping before Codex starts — see file. |
| [003](003-data-pipeline-hardening.md) | Data pipeline hardening | `backlog` | Needs scoping before Codex starts — see file. |
| [004](004-auth-quote-ux.md) | Auth + quote upload UX | `backlog` | Needs scoping before Codex starts — see file. |

## Workflow

1. Pick the highest-priority `ready` ticket (or ask Claude to promote a
   `backlog` ticket to `ready` by fleshing it out).
2. Implement on a branch `codex/<ticket-id>-<slug>`.
3. `uv run pytest` must pass.
4. Open a PR following `AGENTS.md`'s PR checklist; flip the ticket's Status to
   `in_progress` in that PR.
5. On merge, flip Status to `done`.

See `../codex-workflow.md` for how the human operator connects Codex to this
repo and runs this loop end to end.
