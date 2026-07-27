# Working with Codex on this repo

This repo is set up for a two-agent split:

- **Claude (this session, or a future one)** plans, writes specs
  (`docs/codex-backlog/*.md`), and reviews the diffs Codex produces. This is
  the expensive/judgment-heavy work, so it's worth spending Claude usage on.
- **OpenAI Codex, run locally via its CLI** does the bulk implementation from
  those specs, on your machine, against a real clone. This is the mechanical,
  high-volume work — exactly what you want to offload so Claude usage goes
  toward direction, not typing. Local CLI iterates faster than a cloud
  sandbox: no queue, direct filesystem access, immediate feedback.
- **CI** (`.github/workflows/ci.yml`) gates every PR automatically — tests
  must pass before anything gets reviewed by a human or by Claude.
- **The PR is still the gate**, even running locally. Codex builds on a
  branch and opens a PR rather than committing straight to the trunk branch —
  that's the only checkpoint before untested code lands in the shared repo,
  and what lets CI (and me, on review) catch problems before merge. If you
  ever want to skip this for a specific task and let Codex push directly,
  that's your call — just know you're trading away the one safety net in
  this loop.

Everything — the specs, the code, the deploy config — lives in this repo.
Nothing is local-only once it's pushed.

## One-time setup

1. Install the Codex CLI (requires Node.js):
   ```bash
   npm install -g @openai/codex
   codex doctor   # confirms the install and tells you what's still missing
   ```
2. Authenticate — `codex doctor` will flag `auth` as missing until you do
   this:
   ```bash
   codex login
   ```
   (or set a supported API-key env var, if you'd rather not use the browser
   login — `codex login --help` shows the options on your version).
3. Clone this repo locally if you haven't:
   ```bash
   git clone <this-repo-url>
   cd buildingterminal
   git checkout claude/cost-engine-v0-repo-7eyoq9
   ```
   (There's no `main` branch yet — this is currently the trunk. Rename/merge
   it to `main` later if you want to standardize; either works, just be
   consistent about which branch tickets target.)
4. Confirm the local dev setup works before handing anything to Codex:
   ```bash
   uv sync --extra dev
   uv run pytest
   ```
5. Codex CLI reads **`AGENTS.md`** at the repo root automatically, the same
   way the cloud version does — nothing else to configure. That file is your
   standing instructions to Codex; edit it (or ask me to) if you want to
   change how it works.

## Running a ticket

1. Create a branch for the ticket, matching `AGENTS.md`'s convention:
   ```bash
   git checkout -b codex/001-postgres-migration
   ```
2. Launch Codex in the repo directory and point it at the ticket, e.g.:
   > Implement `docs/codex-backlog/001-postgres-migration.md` in this repo.
   > Follow the conventions in `AGENTS.md`.

   Use whichever mode fits — interactive (watch it work, approve steps) or a
   single non-interactive prompt if your CLI version supports one. Either
   way, let it run `uv run pytest` itself before you consider it done; don't
   take "I implemented it" on faith.
3. Once it's finished and tests pass locally, push the branch and open the
   PR yourself (or have Codex do it, if your CLI setup has `gh` configured
   and you're comfortable letting it):
   ```bash
   git push -u origin codex/001-postgres-migration
   gh pr create --fill
   ```
4. CI runs automatically on the PR.
5. Bring the PR back to a Claude session (paste the PR URL/diff, or connect
   this repo via the GitHub integration) and ask for a review against the
   ticket's acceptance criteria. Claude either approves it for merge or gives
   you (or Codex, in a follow-up local run) specific fix instructions.
6. Merge. Flip the ticket's `Status` to `done` if Codex didn't already do it
   in the PR.

## Picking the next ticket

`docs/codex-backlog/README.md` has the live list. Only tickets marked `ready`
are scoped enough for Codex to start cold — `backlog` tickets need a Claude
pass first (ask in a Claude session: "flesh out ticket 002 and mark it
ready"). Right now:

- **001 (Postgres migration)** is `ready` — start here.
- **002 (Web UI), 003 (data pipeline hardening), 004 (auth + quote UX)** are
  intentionally left as stubs — they involve product decisions (framework
  choice, auth model, scheduling strategy) that are worth a short back-and-forth
  with Claude before Codex burns a run on them.

## Cost/usage notes

- Keep Codex tickets scoped to one subsystem at a time (that's why the
  backlog is structured this way) — a tightly-scoped ticket is faster to run
  locally and much faster to review than "build the whole platform" in one
  shot.
- Claude's job is the parts that are expensive to get wrong and cheap to get
  right with good judgment: writing the spec, reviewing the diff, deciding
  what's in/out of scope. Don't have Claude re-implement what Codex already
  built — review it, and only step in to write code directly for things that
  need the specific judgment call this workflow exists to route to Claude in
  the first place.

## Deployment

Once a ticket's code is merged, deploying is separate from the Codex loop —
see `DEPLOY.md` for the Fly.io runbook (app creation, secrets, and the
Postgres cutover once ticket 001 lands).
