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
# * This is the image's default command, so a worker service deployed from the
#   same image with no start command of its own would land here and run a
#   second API instead of Celery. The script refuses (exit 3, before migrating)
#   when the container says it is not the API:
#     - SERVICE_ROLE is set to anything other than "api" (explicit, wins), or
#     - SERVICE_ROLE is unset and RAILWAY_SERVICE_NAME (set by Railway on every
#       deployment) contains "worker", e.g. modelens-worker.
#   Workers start with scripts/start-worker.sh.
set -eu

ROLE="${SERVICE_ROLE:-}"
if [ -n "$ROLE" ]; then
    if [ "$ROLE" != "api" ]; then
        echo "[start-api] SERVICE_ROLE=$ROLE, but this is the API start script; refusing to start." >&2
        echo "[start-api] Workers start with: sh scripts/start-worker.sh (set it as the service's start command)." >&2
        exit 3
    fi
else
    case "$(printf '%s' "${RAILWAY_SERVICE_NAME:-}" | tr '[:upper:]' '[:lower:]')" in
        *worker*)
            echo "[start-api] RAILWAY_SERVICE_NAME=$RAILWAY_SERVICE_NAME looks like a worker service, but it is running the API start script (the image's default command); refusing to start." >&2
            echo "[start-api] Set the service's Start Command to: sh scripts/start-worker.sh" >&2
            echo "[start-api] If this service really is the API, set SERVICE_ROLE=api." >&2
            exit 3
            ;;
    esac
fi

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
