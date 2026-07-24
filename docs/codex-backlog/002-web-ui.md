# 002 — Web UI

**Status:** `backlog` — not detailed enough for Codex to start. Claude will
flesh this out into a `ready` ticket before handing it off; this stub exists
so the backlog index has a placeholder and the priority order is visible.

## Goal (draft)

A minimal frontend so a contractor or managing agent can use the estimator
without curling the API: enter an address and a plain-language job
description, see the returned cost range / confidence / n comparables /
clarifying questions; separately, upload a contractor quote PDF and see the
extracted record.

## Known constraints going in

- Depends on [001](001-postgres-migration.md) being merged if this ships
  after the platform is on a real deploy target, so the UI is talking to a
  durable backend — not a hard dependency for local dev, but sequence it
  after 001 for the deployed version.
- Must not violate the core rule in `AGENTS.md`: the UI displays numbers the
  API returns; it does not call an LLM directly or compute anything.
- Keep it boring: server-rendered or a single static page hitting the
  existing FastAPI JSON endpoints is enough for v0. No new frontend framework
  without an explicit decision from Claude/the repo owner first.

## Before this becomes `ready`

Claude needs to pin down: framework choice (plain HTML+fetch vs. a small
Jinja2 template served by FastAPI itself vs. a separate static frontend),
where it's hosted (same Fly app vs. separate), and whether quote upload needs
any auth (see ticket 004). Don't start implementation until this section is
replaced with a concrete spec and Status flips to `ready`.
