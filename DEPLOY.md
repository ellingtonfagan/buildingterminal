# Deploying Cost Engine v0 (Fly.io)

## Prerequisites

- A Fly.io account and the `flyctl` CLI (`curl -L https://fly.io/install.sh | sh`).
- `fly auth login`.
- An Anthropic API key for `ANTHROPIC_API_KEY`.

## First deploy (SQLite, single machine)

This works today, before the Postgres migration lands, and is enough to get a
real URL up.

```bash
# 1. Pick a globally-unique app name and put it in fly.toml's `app =` line.
#    (fly launch --no-deploy will also offer to do this interactively.)

# 2. Create the app and the persistent volume once.
fly apps create <your-app-name>
fly volumes create cost_engine_data --region iad --size 1   # 1 GB is plenty for v0

# 3. Set secrets (never commit these — see .env.example for the full list).
fly secrets set ANTHROPIC_API_KEY=sk-ant-...

# 4. Deploy.
fly deploy

# 5. Verify.
curl https://<your-app-name>.fly.dev/health
```

`fly.toml` already points `DB_PATH`/`UPLOAD_DIR` at the mounted volume at
`/data`, so the SQLite file and uploaded quote PDFs survive redeploys as long
as you don't delete the volume.

**Caveat with this mode:** `min_machines_running = 0` means Fly can scale the
app to zero when idle and spin it back up on the next request. A single
SQLite file on a single volume is fine for that (only one machine ever
touches it), but it means you can't scale to multiple machines without hitting
SQLite's single-writer limits. That's exactly what the Postgres migration
(`docs/codex-backlog/001-postgres-migration.md`) fixes — see below.

## After the Postgres migration lands

Once `docs/codex-backlog/001-postgres-migration.md` is merged, the app reads
`DATABASE_URL` and uses Postgres instead of SQLite whenever it's set. Nothing
else about the deploy changes.

```bash
# Option A — Fly Postgres (simplest, same platform, same billing)
fly postgres create --name <your-app-name>-db --region iad
fly postgres attach <your-app-name>-db --app <your-app-name>
# `fly postgres attach` sets DATABASE_URL as a secret on the app automatically.

# Option B — an external managed Postgres (Neon, Supabase, RDS, ...)
fly secrets set DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```

Either way, redeploy (`fly deploy`) so the running machine picks up the new
secret. After this, you can raise `min_machines_running` above 0 and/or run
multiple machines, since Postgres (not a single local SQLite file) is now the
source of truth. The `/data` volume is then only used for `UPLOAD_DIR`
(uploaded quote PDFs) — worth revisiting whether uploads should move to
object storage (Fly's Tigris, S3, etc.) as usage grows; that's a fast-follow,
not required for v0.

## Environment variables / secrets reference

See `.env.example` for the full list with descriptions. The ones that matter
for a production deploy specifically:

| Variable | Set via | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | `fly secrets set` | required |
| `DATABASE_URL` | `fly secrets set` (or `fly postgres attach`) | unset = SQLite; set = Postgres, once ticket 001 lands |
| `TARGET_ZIPS`, `MIN_UNITS`, `MAX_UNITS` | `fly.toml` `[env]` or `fly secrets set` | ingestion scope — ingestion itself is run manually/out-of-band for now (see `docs/codex-backlog/003-data-pipeline-hardening.md`) |
| `SOCRATA_APP_TOKEN` | `fly secrets set` | optional, raises NYC Open Data rate limits |
| `LLM_CLASSIFIER_MODEL`, `LLM_JOBSPEC_MODEL`, `LLM_QUOTE_MODEL` | `fly.toml` `[env]` | override only if the production model choice should differ from the local-dev default |

`ALLOW_HEURISTIC_FALLBACK` should never be set to `1` in production — it's a
dev-only offline aid and silently degrades classification quality.

## Ingestion in production

Stage 1 ingestion (`python -m cost_engine.ingest.run`) is a manual/one-shot
script for now — it is **not** wired to run automatically on deploy. Run it
against the production database via `fly ssh console -C "python -m
cost_engine.ingest.run"` (SQLite mode) or by pointing a local run at
`DATABASE_URL` (Postgres mode) until
`docs/codex-backlog/003-data-pipeline-hardening.md` adds scheduling.
