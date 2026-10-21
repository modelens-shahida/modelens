#!/bin/sh
# API container start: migrate to head, then serve.
#
# * The image's default CMD (app/Dockerfile) and docker-compose both run this.
# * uvicorn listens on 0.0.0.0:${PORT:-8000} (Railway injects PORT; compose
#   and local runs get 8000) and replaces this shell (exec), so it receives
#   the container's signals directly.
# * If `alembic upgrade head` fails, the API is not started on a half-migrated
#   schema: print where the DB stands and where the recovery steps are, then
#   exit non-zero. Two replicas starting at once are safe: alembic/env.py
#   takes a Postgres advisory lock for the migration transaction, so the second
#   waits and then finds the database already at head.
# * Extra arguments go to uvicorn (docker-compose passes --reload in dev).
#   --reload is refused when APP_ENV is production.
set -eu

PORT="${PORT:-8000}"

if [ "${APP_ENV:-}" = "production" ]; then
    for arg in "$@"; do
        if [ "$arg" = "--reload" ]; then
            echo "[start-api] --reload is for development only; refusing to start with APP_ENV=production." >&2
            exit 2
        fi
    done
fi

if ! alembic upgrade head; then
    echo "" >&2
    echo "[start-api] alembic upgrade head FAILED - the API was not started." >&2
    echo "[start-api] Recorded DB revision:" >&2
    alembic current >&2 2>&1 || true
    echo "[start-api] Repository head(s):" >&2
    alembic heads >&2 2>&1 || true
    echo "[start-api] See 'If local migrations fail' in README.md for recovery steps." >&2
    exit 1
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" "$@"
