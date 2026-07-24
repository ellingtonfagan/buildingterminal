# 004 — Auth + quote upload UX

**Status:** `backlog` — not detailed enough for Codex to start.

## Goal (draft)

Two related problems once this is a deployed, internet-reachable service
instead of a local script:

1. **`/estimate` and `/quotes` are currently wide open.** Anyone who finds
   the URL can call them. At minimum, `/quotes` (which writes to the DB and
   costs an LLM call per upload) needs some form of access control before a
   public deploy — an API key check is the simplest thing that works for v0.
2. **The quote upload flow is the whole business case** (per `README.md`'s
   "After v0" section — every real quote uploaded corrects the DOB
   underdeclaration bias). Right now it's a bare `POST /quotes` with a raw
   PDF file and nothing else — no confirmation of what was extracted, no way
   to correct a bad extraction, no acknowledgment to whoever uploaded it.

## Candidate scope (Claude to confirm before promoting to `ready`)

- A simple API-key header check (`X-API-Key` against a set of keys in config
  or a small `api_keys` table) gating `/quotes` at minimum, `/estimate`
  optionally.
- After extraction, return the structured record in the response (already
  partially true — expand `QuoteResponse` in `api/app.py`) so an uploader can
  see what was parsed, not just a bare `quote_id`.
- Depends on [002](002-web-ui.md) if the "confirm/correct extraction" flow
  needs a UI step rather than just a richer JSON response.

## Before this becomes `ready`

Claude needs to decide: is this real user accounts (out of scope for a
while) or just static API keys for known partner contractors (much simpler,
probably right for v0)? Pin that down first.
