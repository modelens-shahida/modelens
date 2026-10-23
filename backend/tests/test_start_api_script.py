"""scripts/start-api.sh (the image's default CMD): migrate, then exec uvicorn on ${PORT:-8000}.

The script runs for real under ``sh`` with stub ``alembic`` and ``uvicorn`` commands first on PATH, so
nothing touches a database or opens a port. The advisory lock that makes concurrent upgrades safe is
checked through ``take_migration_lock`` and the alembic env.
"""
import os
import re
import shutil
import subprocess

import pytest
import sqlalchemy as sa

from app.migration_guard import MIGRATION_LOCK_KEY, take_migration_lock

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(BACKEND, "scripts", "start-api.sh")
WORKER_SCRIPT = os.path.join(BACKEND, "scripts", "start-worker.sh")

pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")

STUB = """#!/bin/sh
echo "$0 $*" >> "$CALLS"
case "$(basename "$0")" in
  alembic) [ "$1" = "upgrade" ] && exit "${ALEMBIC_EXIT:-0}"; echo "stub-$1"; exit 0 ;;
  uvicorn|celery) echo "pid=$$" >> "$CALLS"; exit 0 ;;
esac
"""


@pytest.fixture
def run(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("alembic", "uvicorn", "celery"):
        stub = bin_dir / name
        stub.write_text(STUB)
        stub.chmod(0o755)
    calls = tmp_path / "calls.txt"

    def _run(*args, script=SCRIPT, **env):
        environment = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "CALLS": str(calls)}
        environment.update({k: str(v) for k, v in env.items()})
        proc = subprocess.Popen(["sh", script, *args], cwd=BACKEND, env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=30)
        lines = calls.read_text().splitlines() if calls.exists() else []
        return proc, out, err, lines

    return _run


def _uvicorn(lines):
    return [line.split(" ", 1)[1] for line in lines if line.split(" ", 1)[0].endswith("/uvicorn")]


def test_migrates_then_serves_on_port_8000_by_default(run):
    proc, _, _, lines = run()
    assert proc.returncode == 0
    assert lines[0].endswith("/alembic upgrade head")
    assert _uvicorn(lines) == ["app.main:app --host 0.0.0.0 --port 8000"]


def test_port_comes_from_the_environment(run):
    proc, _, _, lines = run(PORT=4321)
    assert proc.returncode == 0
    assert _uvicorn(lines) == ["app.main:app --host 0.0.0.0 --port 4321"]


def test_uvicorn_replaces_the_shell(run):
    proc, _, _, lines = run()
    assert f"pid={proc.pid}" in lines  # exec: uvicorn runs as the container's main process


def test_failed_migration_never_starts_uvicorn(run):
    proc, _, err, lines = run(ALEMBIC_EXIT=3)
    assert proc.returncode == 1
    assert _uvicorn(lines) == []
    assert "alembic upgrade head FAILED - the API was not started." in err
    assert "stub-current" in err and "stub-heads" in err  # where the DB stands, for recovery


def test_extra_arguments_pass_through_in_development(run):
    proc, _, _, lines = run("--reload", APP_ENV="development")
    assert proc.returncode == 0
    assert _uvicorn(lines) == ["app.main:app --host 0.0.0.0 --port 8000 --reload"]


def test_reload_is_refused_in_production_before_migrating(run):
    proc, _, err, lines = run("--reload", APP_ENV="production")
    assert proc.returncode == 2
    assert lines == []
    assert "--reload is for development only" in err


def test_production_without_arguments_serves(run):
    proc, _, _, lines = run(APP_ENV="production", PORT=9000)
    assert proc.returncode == 0
    assert _uvicorn(lines) == ["app.main:app --host 0.0.0.0 --port 9000"]


# ========================== Worker service on the API image ======

@pytest.mark.parametrize("name", ["modelens-worker", "modelens-worker-staging", "ModeLens-Worker", "celery-worker"])
def test_railway_worker_service_refuses_before_migrating(run, name):
    proc, _, err, lines = run(RAILWAY_SERVICE_NAME=name)
    assert proc.returncode == 3
    assert lines == []  # neither alembic nor uvicorn ran
    assert f"RAILWAY_SERVICE_NAME={name} looks like a worker service" in err
    assert "Start Command to: sh scripts/start-worker.sh" in err


@pytest.mark.parametrize("name", ["modelens-api", "modelens-api-staging", ""])
def test_railway_api_service_starts(run, name):
    proc, _, _, lines = run(RAILWAY_SERVICE_NAME=name, PORT=8080)
    assert proc.returncode == 0
    assert _uvicorn(lines) == ["app.main:app --host 0.0.0.0 --port 8080"]


@pytest.mark.parametrize("role", ["worker", "beat", "API"])
def test_non_api_service_role_refuses(run, role):
    proc, _, err, lines = run(SERVICE_ROLE=role, RAILWAY_SERVICE_NAME="modelens-api")
    assert proc.returncode == 3
    assert lines == []
    assert f"SERVICE_ROLE={role}, but this is the API start script" in err


def test_service_role_api_overrides_a_worker_like_name(run):
    proc, _, _, lines = run(SERVICE_ROLE="api", RAILWAY_SERVICE_NAME="worker-facing-api")
    assert proc.returncode == 0
    assert lines[0].endswith("/alembic upgrade head")
    assert _uvicorn(lines) == ["app.main:app --host 0.0.0.0 --port 8000"]


def test_role_check_runs_before_the_reload_check(run):
    proc, _, err, lines = run("--reload", APP_ENV="production", RAILWAY_SERVICE_NAME="modelens-worker")
    assert proc.returncode == 3
    assert lines == []
    assert "--reload" not in err


def _celery(lines):
    return [line.split(" ", 1)[1] for line in lines if line.split(" ", 1)[0].endswith("/celery")]


def test_worker_script_execs_celery_without_migrating(run):
    proc, _, _, lines = run(script=WORKER_SCRIPT, RAILWAY_SERVICE_NAME="modelens-worker")
    assert proc.returncode == 0
    assert _celery(lines) == ["-A app.worker.celery_app worker --loglevel=info"]
    assert not any(line.split(" ", 1)[0].endswith(("/alembic", "/uvicorn")) for line in lines)
    assert f"pid={proc.pid}" in lines  # exec: celery runs as the container's main process


def test_worker_script_passes_arguments_and_accepts_its_role(run):
    proc, _, _, lines = run("--concurrency=2", script=WORKER_SCRIPT, SERVICE_ROLE="worker")
    assert proc.returncode == 0
    assert _celery(lines) == ["-A app.worker.celery_app worker --loglevel=info --concurrency=2"]


def test_worker_script_refuses_the_api_role(run):
    proc, _, err, lines = run(script=WORKER_SCRIPT, SERVICE_ROLE="api")
    assert proc.returncode == 3
    assert lines == []
    assert "SERVICE_ROLE=api, but this is the worker start script" in err


def test_worker_script_matches_compose_and_kubernetes():
    root = os.path.join(BACKEND, "..")
    with open(WORKER_SCRIPT) as fh:
        assert "exec celery -A app.worker.celery_app worker --loglevel=info \"$@\"" in fh.read()
    compose = os.path.join(root, "docker-compose.yml")
    if os.path.exists(compose):
        with open(compose) as fh:
            assert "command: celery -A app.worker.celery_app worker --loglevel=info" in fh.read()
    k8s = os.path.join(root, "kubernetes", "deployments.yaml")
    if os.path.exists(k8s):
        with open(k8s) as fh:
            assert '["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info"]' in fh.read()


def test_start_scripts_are_executable_posix_sh():
    for path in (SCRIPT, WORKER_SCRIPT):
        with open(path) as fh:
            assert fh.readline().strip() == "#!/bin/sh"
        assert os.access(path, os.X_OK)


def test_dockerfile_default_command_is_the_start_script():
    with open(os.path.join(BACKEND, "app", "Dockerfile")) as fh:
        commands = re.findall(r"^CMD (.+)$", fh.read(), re.M)
    assert commands == ['["sh", "scripts/start-api.sh"]']


COMPOSE = os.path.join(BACKEND, "..", "docker-compose.yml")


@pytest.mark.skipif(not os.path.exists(COMPOSE), reason="docker-compose.yml is outside this checkout")
def test_compose_keeps_running_the_script_with_reload():
    with open(COMPOSE) as fh:
        compose = fh.read()
    assert "command: sh scripts/start-api.sh --reload" in compose


# ========================== Concurrent upgrades ==================

class _Recorder:
    def __init__(self, dialect):
        self.dialect = type("D", (), {"name": dialect})()
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params))


def test_postgres_upgrades_take_the_advisory_lock():
    conn = _Recorder("postgresql")
    assert take_migration_lock(conn) is True
    assert conn.statements == [("SELECT pg_advisory_xact_lock(:key)", {"key": MIGRATION_LOCK_KEY})]


def test_sqlite_needs_no_lock():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        assert take_migration_lock(conn) is False


def test_alembic_env_locks_inside_the_migration_transaction():
    with open(os.path.join(BACKEND, "alembic", "env.py")) as fh:
        env = fh.read()
    body = env.split("def do_run_migrations", 1)[1].split("\n\n\n", 1)[0]
    assert re.search(r"with context\.begin_transaction\(\):\n(?:\s+#.*\n)*\s+take_migration_lock\(connection\)\n"
                     r"\s+context\.run_migrations\(\)", body), body
