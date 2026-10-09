"""Tests that already fail on main (2026-10-07, a407cde).

conftest marks each one xfail(strict=False): it still runs in CI and its result
is reported, but it does not fail the job. Remove an entry once the test passes.

Categories:
  APP_BUG  - the application code is wrong; the test describes the intended behaviour.
             Fixed in separate app PRs, not by changing the test.
  PENDING  - the endpoint the test targets was removed or replaced; whether to restore
             the behaviour or drop the test is still to be decided.
"""

APP_BUG = "app bug"
PENDING = "pending decision"

_MOVE_STUDIO = (PENDING, "/api/v1/video-projects router replaced in 1ed5029; Move Studio page still calls it "
                         "- pending decision from Indra")

KNOWN_FAILURES = {
    "tests/test_video_projects.py::test_create_video_project": _MOVE_STUDIO,
    "tests/test_video_projects.py::test_create_storyboard": _MOVE_STUDIO,
    "tests/test_video_projects.py::test_generate_video_insufficient_credits": _MOVE_STUDIO,
    "tests/test_video_projects.py::test_get_generation_job_status": _MOVE_STUDIO,
    "tests/test_video_projects.py::test_list_video_projects": _MOVE_STUDIO,
    "tests/test_video_projects.py::test_generate_video_success": _MOVE_STUDIO,
    "tests/test_video_projects.py::test_render_video_project": _MOVE_STUDIO,
}
