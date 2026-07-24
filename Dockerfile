# Cost Engine v0 — container image for Fly.io.
#
# Storage: defaults to SQLite on the mounted volume at /data (see fly.toml).
# Once docs/codex-backlog/001-postgres-migration.md lands, set the DATABASE_URL
# secret and this same image talks to Postgres instead — no image changes.

FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies first so this layer caches across code-only changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/cost_engine.sqlite \
    UPLOAD_DIR=/data/uploads \
    PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "uvicorn cost_engine.api.app:app --host 0.0.0.0 --port ${PORT}"]
