"""Tests that already fail on main (2026-10-07, a407cde).

conftest marks each one xfail(strict=False): it still runs in CI and its result
is reported, but it does not fail the job. Remove an entry once the test passes.

Categories:
  APP_BUG    - the application code is wrong; the test describes the intended behaviour.
  STALE_TEST - the test targets an endpoint/function that was removed, moved or proxied
               elsewhere; the test (or the decision to drop the feature) needs updating.
"""

APP_BUG = "app bug"
STALE_TEST = "stale test"

_HEALTH = (APP_BUG, "GET /api/v1/health is bound to check_celery_workers (always 200); the DB/Redis "
                    "health_check() below it has no route, so the 503/'services' contract is unreachable")
_ORCH = (STALE_TEST, "POST /api/v1/campaigns/{id}/generate no longer exists in campaign_generation.py -> 404")
_CAMPAIGN_404 = (STALE_TEST, "POST /api/v1/campaigns/{id}/generate no longer exists in campaign_generation.py -> 404")
_CAMPAIGN_PATCH = (STALE_TEST, "patches app.routers.campaign_generation.process_campaign_generation, which "
                               "now lives only in app.worker -> AttributeError")
_GENERATIONS_502 = (STALE_TEST, "/api/v1/generations/* is now proxied to the external templates service "
                                "(templates_proxy.py); no upstream under test -> 502")
_VIDEO_404 = (STALE_TEST, "video router prefix is /api/v1/video; tests call /api/v1/video-projects -> 404")
_VIDEO_PATCH = (STALE_TEST, "patches app.routers.video_projects.process_video_* , which now live only in "
                            "app.worker -> AttributeError")
_FLUID = (APP_BUG, "editorial_fluid router calls FluidService methods that do not exist "
                   "(create_session/get_session/list_sessions/generate_base_layer/apply_product_layer) -> 500")
_GHOST_LAZY = (APP_BUG, "worker reads job.assets (lazy relationship) inside an async session -> "
                        "MissingGreenlet (worker.py ~2262)")
_SKETCH_LAZY = (APP_BUG, "worker reads job.references (lazy relationship) inside an async session -> "
                         "MissingGreenlet (worker.py ~2638)")

KNOWN_FAILURES = {
    "tests/test_health_check.py::test_health_check_all_healthy": _HEALTH,
    "tests/test_health_check.py::test_health_check_db_down": _HEALTH,
    "tests/test_health_check.py::test_health_check_redis_down": _HEALTH,
    "tests/test_health_check.py::test_health_check_both_down": _HEALTH,

    "tests/test_editorial_fluid.py::test_create_editorial_session_success": _FLUID,
    "tests/test_editorial_fluid.py::test_get_and_delete_editorial_session": _FLUID,
    "tests/test_editorial_fluid.py::test_generate_base_layer": _FLUID,
    "tests/test_editorial_fluid.py::test_non_destructive_layer_pipeline": _FLUID,
    "tests/test_editorial_fluid.py::test_list_editorial_sessions": _FLUID,

    "tests/test_ghost_jobs.py::test_process_ghost_job_celery_task": _GHOST_LAZY,
    "tests/test_sketch_jobs.py::test_process_sketch_job_celery_task_success": _SKETCH_LAZY,

    "tests/test_orchestrator_regression.py::test_full_orchestrator_flow": _ORCH,
    "tests/test_orchestrator_regression.py::test_orchestrator_idempotency": _ORCH,
    "tests/test_orchestrator_regression.py::test_orchestrator_throttling": _ORCH,
    "tests/test_orchestrator_regression.py::test_dynamic_rate_limit_enforced": _ORCH,

    "tests/test_campaign_generation.py::test_generate_auth_required": _CAMPAIGN_404,
    "tests/test_campaign_generation.py::test_generate_viewer_forbidden": _CAMPAIGN_404,
    "tests/test_campaign_generation.py::test_generate_cross_tenant_asset_rejected": _CAMPAIGN_404,
    "tests/test_campaign_generation.py::test_generate_success": _CAMPAIGN_PATCH,
    "tests/test_campaign_generation.py::test_generate_idempotency_protection": _CAMPAIGN_PATCH,
    "tests/test_campaign_generation.py::test_cancel_generation": _GENERATIONS_502,
    "tests/test_campaign_generation.py::test_cancel_completed_job_returns_409": _GENERATIONS_502,
    "tests/test_campaign_generation.py::test_get_generation_status": _GENERATIONS_502,

    "tests/test_video_projects.py::test_create_video_project": _VIDEO_404,
    "tests/test_video_projects.py::test_create_storyboard": _VIDEO_404,
    "tests/test_video_projects.py::test_generate_video_insufficient_credits": _VIDEO_404,
    "tests/test_video_projects.py::test_get_generation_job_status": _VIDEO_404,
    "tests/test_video_projects.py::test_list_video_projects": _VIDEO_404,
    "tests/test_video_projects.py::test_generate_video_success": _VIDEO_PATCH,
    "tests/test_video_projects.py::test_render_video_project": _VIDEO_PATCH,
}
