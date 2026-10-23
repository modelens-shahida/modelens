"""Every Celery task must land on a queue the default worker consumes.

A worker started without ``-Q`` (docker-compose, Kubernetes, scripts/start-worker.sh) reads only
``task_queues``. A task that resolves anywhere else, e.g. Celery's built-in ``celery`` queue,
is accepted by the broker and never runs. Routes are resolved through Celery's own router, the
same call ``apply_async`` makes, so decorator options, ``task_routes`` and the default all count.
"""
import os
import re

import pytest

from app.services import batch_concurrency
from app.worker import celery_app

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONSUMED = {q.name for q in celery_app.conf.task_queues}
APP_TASKS = sorted(name for name in celery_app.tasks if not name.startswith("celery."))


def _resolved_queue(name, **call_options):
    task = celery_app.tasks[name]
    options = {**task._get_exec_options(), **call_options}  # what apply_async starts from
    route = celery_app.amqp.router.route(options, name, (), {})
    queue = route["queue"]
    return queue if isinstance(queue, str) else queue.name


def test_the_default_worker_consumes_the_expected_queues():
    assert CONSUMED == {"high_priority", "default", "processing", "bulk_batch"}
    assert "celery" not in CONSUMED


def test_every_task_in_the_source_is_registered():
    defined = 0
    for root, _, files in os.walk(os.path.join(BACKEND, "app")):
        for filename in files:
            if filename.endswith(".py"):
                with open(os.path.join(root, filename)) as fh:
                    defined += len(re.findall(r"^@(?:celery_app\.task|shared_task)\b", fh.read(), re.M))
    assert defined == len(APP_TASKS) == 29


@pytest.mark.parametrize("name", APP_TASKS)
def test_every_registered_task_resolves_to_a_consumed_queue(name):
    assert _resolved_queue(name) in CONSUMED


@pytest.mark.parametrize("name", APP_TASKS)
def test_every_task_is_routed_explicitly(name):
    # The default queue is a safety net, not a routing decision.
    assert name in celery_app.conf.task_routes


def test_unrouted_tasks_fall_back_to_a_consumed_queue():
    assert celery_app.conf.task_default_queue == "default"
    assert celery_app.conf.task_default_queue in CONSUMED

    @celery_app.task(name="tests.unrouted_probe")
    def probe():
        return None

    try:
        assert _resolved_queue("tests.unrouted_probe") == "default"
    finally:
        celery_app.tasks.pop("tests.unrouted_probe", None)


@pytest.mark.parametrize("name, queue", [
    ("app.worker.process_production_job", "processing"),
    ("app.worker.process_generation_job", "processing"),
    ("app.worker.process_ghost_job", "processing"),
    ("app.worker.process_sketch_job", "processing"),
    ("app.worker.process_catalog_job", "processing"),
    ("app.worker.dispatch_webhook", "high_priority"),
    ("app.worker.send_invitation_email", "high_priority"),
    ("app.worker.process_catalog_item_single", "bulk_batch"),
    ("app.worker.run_campaign_generation_job", "bulk_batch"),
    ("app.worker.reset_monthly_brand_credits", "default"),
])
def test_key_routes(name, queue):
    assert _resolved_queue(name) == queue


def test_beat_tasks_are_registered_and_consumed():
    for entry in celery_app.conf.beat_schedule.values():
        assert _resolved_queue(entry["task"]) in CONSUMED


def test_batch_dispatch_queues_are_consumed():
    # dispatch_catalog_batch picks a queue per call with .set(queue=...), which overrides the route.
    for queue in (batch_concurrency.QUEUE_HIGH_PRIORITY, batch_concurrency.QUEUE_BULK_BATCH,
                  batch_concurrency.QUEUE_DEFAULT):
        assert queue in CONSUMED
        assert _resolved_queue("app.worker.process_catalog_item_single", queue=queue) == queue
    for count, mode in ((1, "studio_quality"), (5, "studio_quality"), (10, "studio_quality"), (3, "fast_draft")):
        assert batch_concurrency.get_queue_for_job(count, mode) in CONSUMED


def test_no_task_is_pinned_on_its_decorator():
    # Decorator queue= options override task_routes; keep task_routes the single place to read.
    assert [n for n in APP_TASKS if getattr(celery_app.tasks[n], "queue", None)] == []
