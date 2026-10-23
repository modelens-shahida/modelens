#!/bin/sh
# Celery worker container start.
#
# * Same command as the worker in docker-compose.yml and kubernetes/deployments.yaml.
# * No migrations: the API container (scripts/start-api.sh) owns those.
# * celery replaces this shell (exec), so it receives the container's signals
#   and shuts down warm on SIGTERM.
# * Refuses (exit 3) when SERVICE_ROLE is set to anything other than "worker",
#   so an API service pointed here by mistake fails loudly.
# * Extra arguments go to celery (e.g. --concurrency=2).
set -eu

ROLE="${SERVICE_ROLE:-}"
if [ -n "$ROLE" ] && [ "$ROLE" != "worker" ]; then
    echo "[start-worker] SERVICE_ROLE=$ROLE, but this is the worker start script; refusing to start." >&2
    echo "[start-worker] The API starts with: sh scripts/start-api.sh (the image's default command)." >&2
    exit 3
fi

exec celery -A app.worker.celery_app worker --loglevel=info "$@"
