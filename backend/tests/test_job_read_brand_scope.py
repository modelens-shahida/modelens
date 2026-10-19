"""Job reads are scoped to the job's brand (app/services/job_access.py).

Every read path that returns a job, its items, outputs or exports by id/uuid:
members of the job's brand (any role, viewer included) and platform admins may
read it; anyone else gets exactly the same 404 as an unknown id; no login is a
401. Jobs without a brand of their own (an AIJob with NULL brand_id, Rosanne
and FASHN workflow rows written with the old brand-1 fallback) are readable by
their creator and platform admins only. Progress websockets check the same rule
before accepting and close with 1008 without sending anything. Lists only
return the caller's brands' jobs (platform admins: all).

Everything is local: no network.
"""
import json
from unittest.mock import AsyncMock, patch

import jwt
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.models.db import (
    AIJob, Asset, CatalogJob, CatalogJobItem, GhostJob, GhostOutput, Production, SketchJob, SketchOutput, User,
)

pytestmark = pytest.mark.integration  # many routes and websockets

POLICY_VIOLATION = 1008
OUTPUT = "/uploads/brand/output-1.png"


@pytest_asyncio.fixture
async def jobs(db_session, test_data):
    """One job of every kind in the test brand, created by the editor, with an output where it has one."""
    brand_id, editor_id = test_data["brand"].id, test_data["users"]["editor"].id
    gen = CatalogJob(job_id="gen-uuid-1", user_id=editor_id, brand_id=brand_id, status="queued", total_skus=1,
                     meta={"batch_mode": True, "angle_tiles": []})
    studio = CatalogJob(user_id=editor_id, brand_id=brand_id, status="completed", total_items=1, completed_items=1)
    ghost = GhostJob(user_id=editor_id, brand_id=brand_id, status="completed")
    ghost_batch = GhostJob(job_id="ghost-batch-uuid-1", user_id=editor_id, brand_id=brand_id, status="queued")
    sketch = SketchJob(user_id=editor_id, brand_id=brand_id, status="completed")
    ai_job = AIJob(user_id=editor_id, brand_id=brand_id, status="completed", job_type="generation")
    db_session.add_all([gen, studio, ghost, ghost_batch, sketch, ai_job])
    await db_session.commit()
    production = Production(production_id="prd_brand_scope_1", user_id=editor_id, brand_id=brand_id,
                            request_hash="h", character_id="EE-F-002", character_version="1.0",
                            product_type="dress", request={}, runtime_profile={}, estimated_credits=8)
    db_session.add_all([
        production,
        CatalogJobItem(job_id=studio.id, sku_tag="SKU-1", status="qa_passed", output_url=OUTPUT),
        GhostOutput(job_id=ghost.id, output_url=OUTPUT),
        SketchOutput(job_id=sketch.id, output_url=OUTPUT),
        Asset(brand_id=brand_id, filename="c.png", storage_path=OUTPUT, asset_type="generated",
              meta={"source": "campaign_studio"}),
    ])
    await db_session.commit()
    return {"gen": gen.job_id, "studio": studio.id, "ghost": ghost.id, "ghost_batch": ghost_batch.job_id,
            "sketch": sketch.id, "ai_job": ai_job.id, "production": production.production_id, "brand": brand_id}


def _read_paths(j):
    """name -> (url of the brand's job, url of an unknown id, the 404 message of both)."""
    b = j["brand"]
    return {
        "generate": (f"/api/v1/generate/{j['gen']}", "/api/v1/generate/nope", "Job not found."),
        "generate status": (f"/api/v1/generate/{j['gen']}/status", "/api/v1/generate/nope/status", "Job not found."),
        "generate batch": (f"/api/v1/generate/batch/{j['gen']}", "/api/v1/generate/batch/nope", "Job not found."),
        "rosanne": (f"/api/v1/rosanne/jobs/{j['gen']}", "/api/v1/rosanne/jobs/nope", "Job not found."),
        "fashn": (f"/api/v1/fashn/jobs/{j['gen']}", "/api/v1/fashn/jobs/nope", "Job not found."),
        "production": (f"/api/v1/productions/{j['production']}", "/api/v1/productions/prd_nope", None),
        "ai job": (f"/api/v1/jobs/{j['ai_job']}", "/api/v1/jobs/999999", "Job not found"),
        "ghost": (f"/api/v1/ghost-jobs/{j['ghost']}", "/api/v1/ghost-jobs/999999", "Ghost job not found."),
        "ghost outputs": (f"/api/v1/ghost-jobs/{j['ghost']}/outputs", "/api/v1/ghost-jobs/999999/outputs",
                          "Ghost job not found."),
        "ghost batch": (f"/api/v1/ghost/batch/{j['ghost_batch']}", "/api/v1/ghost/batch/nope", "Ghost job not found."),
        "sketch": (f"/api/v1/sketch-jobs/{j['sketch']}", "/api/v1/sketch-jobs/999999", "Sketch job not found."),
        "catalog": (f"/api/v1/catalog-jobs/{j['studio']}", "/api/v1/catalog-jobs/999999", "Catalog job not found."),
        "catalog zip": (f"/api/v1/catalog-jobs/{j['studio']}/export-zip", "/api/v1/catalog-jobs/999999/export-zip",
                        "Catalog job not found."),
        "catalog feed": (f"/api/v1/catalog-jobs/{j['studio']}/export-feed/shopify",
                         "/api/v1/catalog-jobs/999999/export-feed/shopify", "Catalog job not found."),
        "catalog feeds": (f"/api/v1/catalog-jobs/{j['studio']}/export-multi-feed",
                          "/api/v1/catalog-jobs/999999/export-multi-feed", "Catalog job not found."),
        "campaign zip": (f"/api/v1/campaigns/jobs/t1/export-zip?brand_id={b}",
                         "/api/v1/campaigns/jobs/t1/export-zip?brand_id=999999", "Campaign job not found."),
    }


PATHS = ["generate", "generate status", "generate batch", "rosanne", "fashn", "production", "ai job", "ghost",
         "ghost outputs", "ghost batch", "sketch", "catalog", "catalog zip", "catalog feed", "catalog feeds",
         "campaign zip"]


def _message(name, url, message):
    return message if message is not None else f"Production {url.rsplit('/', 1)[-1]} not found."


# ========================== HTTP read paths =====================================

@pytest.mark.parametrize("name", PATHS)
@pytest.mark.parametrize("role", ["viewer", "editor", "owner", "admin"])
@pytest.mark.asyncio
async def test_brand_members_can_read(client, test_data, jobs, name, role):
    url, _, _ = _read_paths(jobs)[name]
    res = await client.get(url, headers=test_data["get_headers"](role))
    assert res.status_code == 200, (name, res.text)


@pytest.mark.parametrize("name", PATHS)
@pytest.mark.asyncio
async def test_platform_admin_can_read(client, platform_admin_headers, jobs, name):
    url, _, _ = _read_paths(jobs)[name]
    res = await client.get(url, headers=platform_admin_headers)
    assert res.status_code == 200, (name, res.text)


@pytest.mark.parametrize("name", PATHS)
@pytest.mark.asyncio
async def test_other_brand_gets_the_same_404_as_an_unknown_id(client, test_data, jobs, name):
    url, unknown, message = _read_paths(jobs)[name]
    other = test_data["get_headers"]("nonmember")  # owner of the other brand
    res = await client.get(url, headers=other)
    assert (res.status_code, res.json()) == (404, {"detail": _message(name, url, message)}), name
    res = await client.get(unknown, headers=test_data["get_headers"]("owner"))
    assert (res.status_code, res.json()) == (404, {"detail": _message(name, unknown, message)}), name


@pytest.mark.parametrize("name", PATHS)
@pytest.mark.asyncio
async def test_unauthenticated_read_is_401(client, jobs, name):
    url, _, _ = _read_paths(jobs)[name]
    assert (await client.get(url)).status_code == 401, name


@pytest.mark.asyncio
async def test_other_brand_never_sees_output_urls(client, test_data, jobs):
    other = test_data["get_headers"]("nonmember")
    for name in PATHS:
        url, _, _ = _read_paths(jobs)[name]
        assert OUTPUT not in (await client.get(url, headers=other)).text, name


@pytest.mark.asyncio
async def test_cached_ai_job_status_follows_the_same_rule(client, test_data, jobs):
    cached = json.dumps({"id": 777, "user_id": test_data["users"]["editor"].id, "brand_id": jobs["brand"],
                         "status": "completed", "job_type": "generation", "inputs": {}, "outputs": {},
                         "workflow_template_id": None, "asset_id": None, "callback_url": None,
                         "error_message": None, "created_at": "2026-10-19T00:00:00",
                         "updated_at": "2026-10-19T00:00:00"})
    with patch("app.routers.jobs.redis_client.get", AsyncMock(return_value=cached)):
        res = await client.get("/api/v1/jobs/777", headers=test_data["get_headers"]("nonmember"))
        assert (res.status_code, res.json()) == (404, {"detail": "Job not found"})
        res = await client.get("/api/v1/jobs/777", headers=test_data["get_headers"]("viewer"))
        assert res.status_code == 200 and res.json()["id"] == 777


# ========================== Jobs without a brand of their own ===================

@pytest.mark.parametrize("meta,url", [
    ({"workflow_template_id": "rosanne-v1"}, "/api/v1/rosanne/jobs/legacy-1"),
    ({"fashn_mode": "product-to-model"}, "/api/v1/fashn/jobs/legacy-1"),
    ({"angle_slots": []}, "/api/v1/generate/legacy-1"),  # the removed POST /api/v1/generate
])
@pytest.mark.asyncio
async def test_brand_1_fallback_rows_are_readable_by_their_creator_only(
        client, db_session, test_data, platform_admin_headers, meta, url):
    creator = test_data["users"]["nonmember"]  # not a member of the brand the row was written to
    db_session.add(CatalogJob(job_id="legacy-1", user_id=creator.id, brand_id=test_data["brand"].id,
                              status="completed", meta=meta))
    await db_session.commit()
    assert (await client.get(url, headers=test_data["get_headers"]("nonmember"))).status_code == 200
    assert (await client.get(url, headers=platform_admin_headers)).status_code == 200
    for role in ("owner", "editor", "viewer"):  # members of that brand did not create it
        res = await client.get(url, headers=test_data["get_headers"](role))
        assert (res.status_code, res.json()) == (404, {"detail": "Job not found."}), role


@pytest.mark.asyncio
async def test_ai_job_without_brand_is_readable_by_its_creator_only(client, db_session, test_data,
                                                                    platform_admin_headers):
    job = AIJob(user_id=test_data["users"]["editor"].id, brand_id=None, status="queued", job_type="generation")
    db_session.add(job)
    await db_session.commit()
    url = f"/api/v1/jobs/{job.id}"
    assert (await client.get(url, headers=test_data["get_headers"]("editor"))).status_code == 200
    assert (await client.get(url, headers=platform_admin_headers)).status_code == 200
    res = await client.get(url, headers=test_data["get_headers"]("owner"))
    assert (res.status_code, res.json()) == (404, {"detail": "Job not found"})


# ========================== Lists ===============================================

@pytest.mark.asyncio
async def test_dlq_list_only_has_the_callers_brands_and_own_brandless_jobs(
        client, db_session, test_data, platform_admin_headers):
    nonmember = test_data["users"]["nonmember"]
    db_session.add_all([
        CatalogJob(job_id="dlq-brand", user_id=test_data["users"]["editor"].id, brand_id=test_data["brand"].id,
                   status="dlq"),
        CatalogJob(job_id="dlq-other", user_id=nonmember.id, brand_id=test_data["other_brand"].id, status="dlq"),
        CatalogJob(job_id="dlq-rosanne", user_id=nonmember.id, brand_id=test_data["brand"].id, status="dlq",
                   meta={"workflow_template_id": "rosanne-v1"}),
    ])
    await db_session.commit()

    async def listed(headers):
        res = await client.get("/api/v1/pipeline/dlq", headers=headers)
        assert res.status_code == 200
        return {j["job_id"] for j in res.json()["dlq_jobs"]}

    assert await listed(test_data["get_headers"]("viewer")) == {"dlq-brand"}
    assert await listed(test_data["get_headers"]("nonmember")) == {"dlq-other", "dlq-rosanne"}
    assert await listed(platform_admin_headers) == {"dlq-brand", "dlq-other", "dlq-rosanne"}


@pytest.mark.asyncio
async def test_ai_job_list_does_not_leak_other_brands(client, test_data, jobs):
    res = await client.get("/api/v1/jobs", headers=test_data["get_headers"]("nonmember"))
    assert res.status_code == 200 and jobs["ai_job"] not in {j["id"] for j in res.json()}
    res = await client.get("/api/v1/jobs", headers=test_data["get_headers"]("viewer"))
    assert jobs["ai_job"] in {j["id"] for j in res.json()}


# ========================== Websockets ==========================================

class _OneEventPubSub:
    async def subscribe(self, channel):
        self.channel = channel

    async def unsubscribe(self, channel):
        pass

    async def close(self):
        pass

    async def listen(self):
        yield {"type": "message", "data": json.dumps({"event": "generation.completed", "percent": 100})}


class _FakeRedis:
    def pubsub(self):
        return _OneEventPubSub()


async def _fake_redis():
    return _FakeRedis()


def _token(email):
    import time
    return jwt.encode({"sub": email, "exp": int(time.time()) + 3600}, settings.SECRET_KEY, algorithm="HS256")


@pytest.fixture
def tc():
    with patch("app.routers.realtime_generation.generation_events._get_redis", _fake_redis):
        with TestClient(app) as client:
            yield client


def _rejected(tc, url):
    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect(url) as ws:
            ws.receive_json()  # nothing must arrive before the close
    return exc.value.code


@pytest_asyncio.fixture
async def finished_job(db_session, test_data):
    db_session.add(CatalogJob(job_id="ws-job-1", user_id=test_data["users"]["editor"].id,
                              brand_id=test_data["brand"].id, status="completed", total_skus=1, completed_skus=1,
                              meta={"batch_mode": True}))
    await db_session.commit()
    return "ws-job-1"


def _ws_urls(job_id, token, brand_id):
    return {
        "generation": f"/api/v1/ws/generation/{job_id}?token={token}",
        "batch": f"/api/v1/ws/batch/{job_id}?token={token}",
        "progress": f"/api/v1/ws/generation/{job_id}/progress?token={token}&brand_id={brand_id}",
    }


@pytest.mark.parametrize("kind", ["generation", "batch", "progress"])
@pytest.mark.parametrize("role", ["viewer", "editor", "owner"])
@pytest.mark.asyncio
async def test_member_receives_progress(tc, test_data, finished_job, kind, role):
    url = _ws_urls(finished_job, _token(test_data["users"][role].email), test_data["brand"].id)[kind]
    with tc.websocket_connect(url) as ws:
        events = [ws.receive_json() for _ in range(3 if kind != "progress" else 2)]
    assert events[0]["event"] in ("connected", "connection.established")
    assert any(e.get("status") == "completed" or e.get("event") == "generation.completed" for e in events[1:])


@pytest.mark.parametrize("kind", ["generation", "batch", "progress"])
@pytest.mark.asyncio
async def test_platform_admin_receives_progress(tc, db_session, finished_job, kind):
    admin = User(email="ws-platform-admin@modelens.ai", hashed_password="x", full_name="PA", role="admin")
    db_session.add(admin)
    await db_session.commit()
    job = (await db_session.execute(select(CatalogJob).where(CatalogJob.job_id == finished_job))).scalar_one()
    url = _ws_urls(finished_job, _token(admin.email), job.brand_id)[kind]
    with tc.websocket_connect(url) as ws:
        assert ws.receive_json()["event"] in ("connected", "connection.established")


@pytest.mark.parametrize("kind", ["generation", "batch"])
@pytest.mark.asyncio
async def test_non_member_unknown_job_and_bad_token_close_with_1008(tc, test_data, finished_job, kind):
    brand = test_data["brand"].id
    nonmember = _token(test_data["users"]["nonmember"].email)
    owner = _token(test_data["users"]["owner"].email)
    assert _rejected(tc, _ws_urls(finished_job, nonmember, brand)[kind]) == POLICY_VIOLATION
    assert _rejected(tc, _ws_urls("no-such-job", owner, brand)[kind]) == POLICY_VIOLATION
    assert _rejected(tc, _ws_urls(finished_job, "not-a-jwt", brand)[kind]) == POLICY_VIOLATION
    no_token = _ws_urls(finished_job, "", brand)[kind].split("?")[0]
    assert _rejected(tc, no_token) == POLICY_VIOLATION


@pytest.mark.asyncio
async def test_progress_stream_checks_the_job_not_only_the_brand(tc, test_data, finished_job):
    nonmember = test_data["users"]["nonmember"]  # owns the other brand: passes that brand's check
    url = _ws_urls(finished_job, _token(nonmember.email), test_data["other_brand"].id)["progress"]
    assert _rejected(tc, url) == POLICY_VIOLATION
    owner = _token(test_data["users"]["owner"].email)
    assert _rejected(tc, _ws_urls("no-such-job", owner, test_data["brand"].id)["progress"]) == POLICY_VIOLATION
    # Not a member of the requested brand: unchanged (4003)
    assert _rejected(tc, _ws_urls(finished_job, _token(nonmember.email), test_data["brand"].id)["progress"]) == 4003


@pytest.mark.asyncio
async def test_progress_stream_of_a_production_for_its_brand(tc, test_data, jobs):
    url = _ws_urls(jobs["production"], _token(test_data["users"]["viewer"].email), jobs["brand"])["progress"]
    with tc.websocket_connect(url) as ws:
        assert ws.receive_json()["event"] == "connection.established"
    nonmember = _token(test_data["users"]["nonmember"].email)
    assert _rejected(tc, _ws_urls(jobs["production"], nonmember, test_data["other_brand"].id)["progress"]) \
        == POLICY_VIOLATION
