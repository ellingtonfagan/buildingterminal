# Working with Codex on this repo

This repo is set up for a two-agent split:

- **Claude (this session, or a future one)** plans, writes specs
  (`docs/codex-backlog/*.md`), and reviews the diffs Codex produces. This is
  the expensive/judgment-heavy work, so it's worth spending Claude usage on.
- **OpenAI Codex (cloud)** does the bulk implementation from those specs and
  opens PRs. This is the mechanical, high-volume work — exactly what you want
  to offload so Claude usage goes toward direction, not typing.
- **CI** (`.github/workflows/ci.yml`) gates every PR automatically — tests
  must pass before anything gets reviewed by a human or by Claude.

Everything — the specs, the code, the deploy config — lives in this repo.
Nothing is local-only.

I can't drive the Codex connection myself (no tool gives me access to your
OpenAI/ChatGPT account or GitHub App installs), so this doc is the exact
runbook for you to do it — it should take about two minutes the first time.

## One-time setup: connect Codex to this repo

1. Go to **chatgpt.com/codex** (or the Codex tab inside ChatGPT), signed in
   with the account that should own these tasks.
2. **Connect a repository** → authorize the "OpenAI Codex" GitHub App if you
   haven't already → when GitHub asks which repos to grant access to, choose
   **"Only select repositories"** and pick
   `ellingtonfagan/buildingterminal` (don't grant org-wide access unless you
   want Codex able to touch other repos too).
3. Codex will ask you to pick/create an **environment** for the repo — this is
   the container image + setup commands it uses per task. Defaults are fine;
   if it asks for a setup command, use:
   ```
   uv sync --extra dev
   ```
4. **Base branch**: this repo currently has no `main` — the only branch is
   `claude/cost-engine-v0-repo-7eyoq9`, which is effectively the trunk right
   now. Point Codex's environment at that branch (or merge/rename it to
   `main` first if you'd rather standardize — either works, just be
   consistent about which branch tickets target).
5. Codex automatically reads **`AGENTS.md`** at the repo root on every task —
   nothing else to configure. That file is your standing instructions to
   Codex; if you want to change how it works, edit that file (or ask me to).

## Running a ticket

1. Open a new Codex task. Point it at a ticket, e.g.:
   > Implement `docs/codex-backlog/001-postgres-migration.md` in this repo.
   > Follow the conventions in `AGENTS.md`. Open a PR when finished.
2. Codex works async in its own sandbox, then opens a PR against the base
   branch.
3. CI runs automatically on the PR.
4. Bring the PR back to a Claude session (paste the PR URL/diff, or connect
   this repo via the GitHub integration) and ask for a review against the
   ticket's acceptance criteria. Claude either approves it for merge or gives
   you (or Codex, in a follow-up task) specific fix instructions.
5. Merge. Flip the ticket's `Status` to `done` if Codex didn't already do it
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
  with Claude before Codex burns a task on them.

## Cost/usage notes

- Keep Codex tickets scoped to one subsystem at a time (that's why the
  backlog is structured this way) — a tightly-scoped ticket is cheaper to run
  and much faster to review than "build the whole platform" in one shot.
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
