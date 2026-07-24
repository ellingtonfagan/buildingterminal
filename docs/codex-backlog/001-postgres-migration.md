# 001 — Postgres migration

**Status:** `ready`
**Depends on:** nothing

## Goal

The app currently persists everything to a local SQLite file (`cost_engine/db.py`,
`schema.sql`). That's fine for local dev but wrong for the Fly.io deploy — a
single SQLite file on a container disk isn't durable across redeploys/multiple
machines the way a managed Postgres instance is. Migrate the storage backend so
that:

- **When `DATABASE_URL` is set**, the app connects to Postgres.
- **When `DATABASE_URL` is not set**, the app keeps working exactly as it does
  today against local SQLite (`DB_PATH`). Local dev and CI must remain
  zero-setup — no one should need a running Postgres to run `uv run pytest`.

This is a storage-layer migration, not a feature change. No API contract,
response shape, or business logic changes.

## Non-goals

- Do not change `/estimate` or `/quotes` request/response shapes.
- Do not change the cost model, classifier, or any LLM prompt.
- Do not add an ORM (no full SQLAlchemy Core expression-language rewrite of
  every query) — see "Approach" below for the intentionally scoped design.
- Do not provision the actual Postgres instance (Fly Postgres / Neon /
  Supabase) — that's a deploy-time step, documented separately in
  `DEPLOY.md`. This ticket only makes the code able to talk to Postgres via a
  connection string.
- Do not add connection pooling tuning, read replicas, or migrations
  tooling (Alembic etc.) — a single `CREATE TABLE IF NOT EXISTS` schema
  application at startup is enough for v0. (A future ticket can add real
  migrations once the schema needs to change on a live database with data in
  it.)

## Approach

Use **SQLAlchemy Core** (`sqlalchemy>=2.0`) as a thin, dialect-aware layer —
not the ORM, not the expression-builder for every query. Concretely:

1. Add dependencies: `sqlalchemy>=2.0`, `psycopg[binary]>=3.1` (Postgres
   driver; SQLite needs no extra driver — SQLAlchemy uses the stdlib `sqlite3`
   under the hood).

2. `cost_engine/config.py`: add `database_url: str | None` read from
   `DATABASE_URL`. Normalize the scheme — some providers (Fly Postgres,
   Heroku-style) hand you `postgres://...`; SQLAlchemy needs
   `postgresql+psycopg://...`. Rewrite `postgres://` → `postgresql+psycopg://`
   and bare `postgresql://` → `postgresql+psycopg://` at config-load time.

3. `cost_engine/db.py` — replace the `sqlite3`-based implementation with:
   - `get_engine() -> Engine`: a **module-level singleton**, lazily created.
     If `CONFIG.database_url` is set, `create_engine(CONFIG.database_url)`.
     Otherwise `create_engine(f"sqlite:///{CONFIG.db_file()}")` — except for
     the **in-memory test path**, which needs
     `create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})`
     so the same in-memory database persists across checkouts (plain
     `sqlite://` without `StaticPool` gives every connection a *fresh* empty
     in-memory DB, which will silently break tests). Support this via
     `get_engine(url: str | None = None)` accepting an override, defaulting to
     `CONFIG`-derived behavior when `None`.
   - `init_db(engine)`: applies the schema. `CREATE TABLE IF NOT EXISTS` is
     idempotent, so this can run at process startup once — see the
     "per-request connection" fix below, this must **not** run on every API
     request as it does today.
   - Keep a `connect()` / `get_initialized_connection()`-shaped API so most
     call sites change minimally, but the object returned should be a
     SQLAlchemy `Connection` (from `engine.connect()`), not a raw
     `sqlite3.Connection`.

4. **Two schema files**, both hand-written (not generated), so the DDL is
   explicit and reviewable per dialect:
   - `src/cost_engine/schema_sqlite.sql` — rename the existing `schema.sql`
     to this. No content changes needed.
   - `src/cost_engine/schema_postgres.sql` — the Postgres-dialect equivalent.
     Translation notes for every construct that differs:
     - `PRAGMA journal_mode = WAL;` / `PRAGMA foreign_keys = ON;` → drop
       entirely (not applicable to Postgres; foreign keys are enforced by
       default).
     - `INTEGER PRIMARY KEY AUTOINCREMENT` → `INTEGER GENERATED ALWAYS AS
       IDENTITY PRIMARY KEY` (applies to: `pluto` has no autoincrement PK —
       skip; `filings.filing_id`, `permits.permit_id`,
       `quote_line_items.id`, `quotes.quote_id`, `eval_runs.id`).
     - `TEXT` stays `TEXT` (Postgres supports it natively).
     - `REAL` → `DOUBLE PRECISION`.
     - Everything else (`UNIQUE(...)`, `CREATE INDEX IF NOT EXISTS`,
       `REFERENCES`, column lists) is portable as-is.
   - `db.py`'s `init_db`/`get_engine` picks the right file based on
     `engine.dialect.name` (`"sqlite"` vs `"postgresql"`).
   - Update `src/cost_engine/scripts/show_schema.py` to print both, labeled,
     or accept a `--dialect sqlite|postgres` flag (default `sqlite`) — either
     is fine, pick one and keep it simple.

5. **Query call sites** — every one needs two mechanical changes:
   - `?`-positional placeholders → named placeholders (`:name`), and
     `sqlalchemy.text(sql)` wrapping the SQL string. Tuple params → dict
     params.
   - Row access `row["col"]` on a fetched row: SQLAlchemy 2.0 `Row` objects
     support this via `.mappings()` — call `.mappings().fetchone()` /
     `.mappings().fetchall()` / iterate `.mappings()` in a for-loop, instead
     of bare `.fetchone()` / `.fetchall()` / iterating the result directly.
   - Every `conn.commit()` call stays as `conn.commit()` — SQLAlchemy 2.0
     `Connection` supports this directly in "commit-as-you-go" style, no
     change needed there.

   **Worked example** (from `src/cost_engine/api/buildings.py`):
   ```python
   # Before
   row = conn.execute("SELECT * FROM pluto WHERE bbl = ?", (bbl,)).fetchone()
   ...
   return BuildingCharacteristics(bbl=row["bbl"], ...)

   # After
   from sqlalchemy import text
   row = conn.execute(text("SELECT * FROM pluto WHERE bbl = :bbl"), {"bbl": bbl}).mappings().fetchone()
   ...
   return BuildingCharacteristics(bbl=row["bbl"], ...)
   ```

   **Complete list of files/functions to update** (every one currently does
   raw `sqlite3`-flavored `conn.execute(...)`  — grep for `conn.execute`,
   `conn.executescript`, `sqlite3\.` to confirm you got everything before
   opening the PR):
   - `src/cost_engine/db.py` — full rewrite per above.
   - `src/cost_engine/costmodel/model.py` — `_comparable_costs` (the `for r in
     conn.execute(sql, params):` loop — needs `.mappings()`).
   - `src/cost_engine/classify/run.py` — `run()` and `_print_distribution()`.
   - `src/cost_engine/classify/classifier.py` — type hints only
     (`sqlite3.Connection` → `sqlalchemy.engine.Connection`); the actual
     execute calls live in `llm/cache.py`.
   - `src/cost_engine/llm/cache.py` — `get()` and `put()`.
   - `src/cost_engine/api/quotes.py` — `store_quote()` (note: uses
     `cur.lastrowid` after an INSERT to get the new `quote_id` — SQLAlchemy
     doesn't have `.lastrowid` uniformly across dialects; use
     `INSERT ... RETURNING quote_id` on Postgres and keep `.lastrowid` on
     SQLite, or simplest: add `RETURNING quote_id` to the INSERT everywhere —
     SQLite 3.35+ supports `RETURNING` too, and the project's SQLite version
     should be new enough; verify with a quick local check, and if not,
     branch on `engine.dialect.name`).
   - `src/cost_engine/api/buildings.py` — `lookup()`.
   - `src/cost_engine/api/app.py` — the inline query in `quotes_endpoint()`
     for `stored_bbl`.
   - `src/cost_engine/ingest/run.py` — `ingest_pluto`, `ingest_filings`,
     `ingest_permits`, `match_rate`, `date_coverage`, `run()`. Note:
     `ingest_filings`/`ingest_permits` use `INSERT OR IGNORE` (SQLite) to
     dedupe on a UNIQUE constraint — on Postgres this becomes
     `INSERT ... ON CONFLICT (source, external_id) DO NOTHING` (filings) /
     `ON CONFLICT (external_id) DO NOTHING` (permits). `ingest_pluto` uses
     `INSERT OR REPLACE` — becomes
     `INSERT ... ON CONFLICT (bbl) DO UPDATE SET ... `. Write one small
     helper per statement type (e.g. `_upsert_ignore(conn, table, sql_sqlite,
     sql_postgres, params)` or simpler: just write the dialect-specific SQL
     string inline behind an `if engine.dialect.name == "postgresql":`
     branch at each of these 3 call sites — don't over-engineer a generic
     upsert abstraction for 3 call sites).
   - `evals/run_classifier_eval.py` — the `eval_runs` INSERT.
   - `src/cost_engine/scripts/show_schema.py` — per point 4 above.

6. **Fix the "new connection per request" bug while you're in here.** Today
   `api/app.py` calls `get_initialized_connection()` inside every request
   handler, which opens a brand-new SQLite connection and re-runs the whole
   schema-init script on every single API call. Replace this with: create the
   engine + run `init_db` once at FastAPI startup (a `@app.on_event("startup")`
   handler or, if using a newer FastAPI version already in the lockfile, a
   lifespan context manager — check what's idiomatic for the installed
   FastAPI version), store the engine on `app.state`, and have each request
   handler check out a connection from the pool via a small dependency
   function (`def get_conn(): with engine.connect() as conn: yield conn`)
   instead of calling `get_initialized_connection()`. This is a real
   performance/correctness fix, not scope creep — leaving it as-is against a
   real Postgres instance would mean hammering it with a fresh connection +
   schema check per request.

7. **Tests** (`tests/test_cost_model.py` is the only file that constructs a DB
   directly): update to the new `db.py` API. It already uses `connect(":memory:")`
   — after this migration that should route through the `StaticPool`
   in-memory-SQLite path described in point 3. Confirm `uv run pytest` passes
   with zero network/Postgres dependency.

8. **Optional but nice-to-have**: a Postgres integration test, skipped by
   default, that only runs when a `TEST_DATABASE_URL` env var is set (so CI
   doesn't need a live Postgres). If you add this, gate it with
   `@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason=...)`
   and document how to run it locally (e.g. `docker run -e
   POSTGRES_PASSWORD=x -p 5432:5432 postgres:16` +
   `TEST_DATABASE_URL=postgresql+psycopg://postgres:x@localhost/postgres uv
   run pytest -m postgres`). Don't make CI depend on it.

9. Update `.env.example`: add `DATABASE_URL=` (empty, commented, with a note
   that it overrides `DB_PATH` when set) near the existing `DB_PATH` entry.

10. Update `README.md`'s "Setup" section with one sentence: local dev still
    defaults to SQLite; setting `DATABASE_URL` switches to Postgres, no other
    code changes needed. Update `DEPLOY.md` if it already exists by the time
    you pick this up (it may — deploy scaffolding was set up in a separate,
    parallel piece of work) to note that `DATABASE_URL` is the one env var/
    Fly secret that needs to be set for production.

## Acceptance criteria

- [ ] `uv sync --extra dev` installs cleanly with the new dependencies.
- [ ] `uv run pytest` passes with **no** `DATABASE_URL` set and **no** network
      access (confirms the SQLite path still works standalone).
- [ ] `DATABASE_URL` unset → app behaves exactly as before (SQLite at
      `DB_PATH`), verified by running `uv run uvicorn cost_engine.api.app:app`
      locally and hitting `GET /health` and `POST /estimate`.
- [ ] `DATABASE_URL` set to a real Postgres connection string (manually
      verified by whoever picks this up — a local `docker run postgres`
      instance is enough) → `uv run python -m cost_engine.scripts.show_schema`
      and a full `ingest` → `classify` → `estimate` round trip work against
      Postgres. Paste evidence of this manual check in the PR description
      (schema created, a row inserted and read back) since CI won't run it.
  - [ ] `schema_postgres.sql` applies cleanly to a fresh Postgres database
      with no errors.
- [ ] No remaining `import sqlite3` outside of what SQLAlchemy needs
      internally — grep the diff for `sqlite3\.` in `src/` and confirm
      nothing is left except inside `db.py`'s dialect-detection comments, if
      any.
- [ ] `api/app.py` no longer calls `get_initialized_connection()` per
      request; the engine/schema-init happens once at startup.
- [ ] PR description includes the `uv run pytest` output and the manual
      Postgres verification notes from above.

## Open questions

- None blocking. If Fly Postgres vs. an external managed provider (Neon,
  Supabase) turns out to matter for connection-string quirks (e.g. Fly
  Postgres requiring `sslmode=require` or a specific host format), note it in
  the PR — that's a deploy-time detail, not a reason to change this ticket's
  code.
