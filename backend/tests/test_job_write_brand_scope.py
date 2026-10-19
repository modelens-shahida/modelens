"""Job writes are scoped to the job's brand and role (app/services/job_access.py).

Cancel, retry, QA review/evaluate and touch-up need at least the editor role in
the job's (or asset's) brand; DLQ needs the brand's admin or owner role;
platform admins may do all of them. A viewer of that brand gets 403; another
brand's job or an unknown id gets exactly the same 404. /emit and the canonical
QA override are platform-admin only, and /emit publishes only to the job's own
brand channel. A cancelled job is refunded at most once.

Everything is mocked: no network, no Celery, no templates service.
"""
import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.config import settings
from app.models.db import (
    Asset, Brand, CatalogJob, CatalogJobItem, CreditTransaction, GhostJob, QAEvaluation, QAProfile, SketchJob,
)
from app.services.credits_sync_service import credits_sync_service
from app.services.pipeline_hardening import pipeline_hardening

pytestmark = pytest.mark.integration  # many write routes


@pytest.fixture(autouse=True)
def outside_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")


EDITOR_UP = {"owner", "admin", "editor", "platform_admin"}
ADMIN_UP = {"owner", "admin", "platform_admin"}
PLATFORM_ONLY = {"platform_admin"}
ROLES = ["owner", "admin", "editor", "viewer", "nonmember", "platform_admin"]


async def _add(db_session, *rows):
    db_session.add_all(rows)
    await db_session.commit()
    return rows[0] if len(rows) == 1 else rows


async def _catalog(db, t, status="queued", **kw):
    return await _add(db, CatalogJob(user_id=t["users"]["editor"].id, brand_id=t["brand"].id, status=status,
                                     job_id=str(uuid.uuid4()), meta={"batch_mode": True}, **kw))


async def _asset(db, t):
    return await _add(db, Asset(brand_id=t["brand"].id, filename="a.png", storage_path="/uploads/a.png",
                                asset_type="generated"))


# Each write path: async factory(db, test_data) -> (method, url, json body), unknown (method, url, body), 404
# message, roles allowed, success status, patches (route mocks: no Celery / templates service).

async def _gen_cancel(db, t):
    job = await _catalog(db, t)
    return ("post", f"/api/v1/generate/{job.job_id}/cancel", {}), ("post", "/api/v1/generate/nope/cancel", {})


async def _gen_dlq(db, t):
    job = await _catalog(db, t, status="failed")
    body = {"error": "unrecoverable"}
    return ("post", f"/api/v1/generate/{job.job_id}/dlq", body), ("post", "/api/v1/generate/nope/dlq", body)


async def _emit(db, t):
    job = await _catalog(db, t)
    q = "?event=generation.progress&percent=50"
    return (("post", f"/api/v1/generation/{job.job_id}/emit{q}", None),
            ("post", f"/api/v1/generation/nope/emit{q}", None))


async def _catalog_cancel(db, t):
    job = await _catalog(db, t, credits_reserved=0)
    return ("post", f"/api/v1/catalog-jobs/{job.id}/cancel", {}), ("post", "/api/v1/catalog-jobs/999999/cancel", {})


async def _catalog_retry(db, t):
    job = await _catalog(db, t, status="failed")
    return ("post", f"/api/v1/catalog-jobs/{job.id}/retry", {}), ("post", "/api/v1/catalog-jobs/999999/retry", {})


async def _catalog_item_retry(db, t):
    job = await _catalog(db, t, status="failed")
    item = await _add(db, CatalogJobItem(job_id=job.id, status="failed", product_image_path="/uploads/p.png"))
    return (("post", f"/api/v1/catalog-jobs/{job.id}/items/{item.id}/retry", {}),
            ("post", f"/api/v1/catalog-jobs/999999/items/{item.id}/retry", {}))


async def _ghost(db, t, status):
    return await _add(db, GhostJob(user_id=t["users"]["editor"].id, brand_id=t["brand"].id, status=status))


async def _ghost_cancel(db, t):
    job = await _ghost(db, t, "queued")
    return ("post", f"/api/v1/ghost-jobs/{job.id}/cancel", {}), ("post", "/api/v1/ghost-jobs/999999/cancel", {})


async def _ghost_retry(db, t):
    job = await _ghost(db, t, "failed")
    return ("post", f"/api/v1/ghost-jobs/{job.id}/retry", {}), ("post", "/api/v1/ghost-jobs/999999/retry", {})


async def _sketch(db, t, status):
    return await _add(db, SketchJob(user_id=t["users"]["editor"].id, brand_id=t["brand"].id, status=status))


async def _sketch_cancel(db, t):
    job = await _sketch(db, t, "queued")
    return ("post", f"/api/v1/sketch-jobs/{job.id}/cancel", {}), ("post", "/api/v1/sketch-jobs/999999/cancel", {})


async def _sketch_retry(db, t):
    job = await _sketch(db, t, "failed")
    return ("post", f"/api/v1/sketch-jobs/{job.id}/retry", {}), ("post", "/api/v1/sketch-jobs/999999/retry", {})


async def _qa_review(db, t):
    asset = await _asset(db, t)
    profile = await _add(db, QAProfile(qa_profile_id=f"QA-{uuid.uuid4().hex[:8]}"))
    evaluation = await _add(db, QAEvaluation(qa_profile_id=profile.id, asset_id=asset.id, decision="HOLD"))
    body = {"decision": "PASS"}
    return (("post", f"/api/v1/qa/evaluations/{evaluation.id}/review", body),
            ("post", "/api/v1/qa/evaluations/999999/review", body))


async def _qa_evaluate(db, t):
    asset = await _asset(db, t)
    return ("post", "/api/v1/qa/evaluate", {"asset_id": asset.id}), ("post", "/api/v1/qa/evaluate", {"asset_id": 999999})


async def _touch_up(db, t):
    asset = await _asset(db, t)
    return ("post", f"/api/v1/assets/{asset.id}/touch-up", {}), ("post", "/api/v1/assets/999999/touch-up", {})


async def _qa_override(db, t):
    body = {"override_status": "PASS", "reviewer_note": "ok"}
    return ("patch", "/api/v1/qa/evaluations/AST-1/override", body), None


async def _generations_cancel(db, t):
    generation_id = f"gen-{uuid.uuid4().hex[:8]}"
    await _add(db, CreditTransaction(user_id=t["users"]["editor"].id, brand_id=t["brand"].id, amount=-5,
                                     transaction_type="reserved", status="pending", reference_id=generation_id))
    return (("post", f"/api/v1/generations/{generation_id}/cancel", {}),
            ("post", "/api/v1/generations/nope/cancel", {}))


WRITE_PATHS = {
    #  name: (factory, 404 message, roles allowed, success status, patches)
    "generate cancel": (_gen_cancel, "Job not found.", EDITOR_UP, 200, ()),
    "generate dlq": (_gen_dlq, "Job not found.", ADMIN_UP, 200, ()),
    "emit": (_emit, "Job not found.", PLATFORM_ONLY, 200, ("app.services.generation_events.generation_events.publish",)),
    "catalog cancel": (_catalog_cancel, "Catalog job not found.", EDITOR_UP, 200, ()),
    "catalog retry": (_catalog_retry, "Catalog job not found.", EDITOR_UP, 200,
                      ("app.routers.catalog_jobs.process_catalog_job",)),
    "catalog item retry": (_catalog_item_retry, "Catalog item not found.", EDITOR_UP, 200,
                           ("app.routers.catalog_jobs.process_catalog_item",)),
    "ghost cancel": (_ghost_cancel, "Ghost job not found.", EDITOR_UP, 200, ()),
    "ghost retry": (_ghost_retry, "Ghost job not found.", EDITOR_UP, 200, ("app.routers.ghost_jobs.process_ghost_job",)),
    "sketch cancel": (_sketch_cancel, "Sketch job not found.", EDITOR_UP, 200, ()),
    "sketch retry": (_sketch_retry, "Sketch job not found.", EDITOR_UP, 200,
                     ("app.routers.sketch_jobs.process_sketch_job",)),
    "qa review": (_qa_review, "QA evaluation not found.", EDITOR_UP, 200, ()),
    "qa evaluate": (_qa_evaluate, "Asset not found.", EDITOR_UP, 201, ()),
    "touch-up": (_touch_up, "Asset not found.", EDITOR_UP, 202, ("app.worker.run_touchup_job",)),
    "qa override": (_qa_override, None, PLATFORM_ONLY, 200, ()),
    "generations cancel": (_generations_cancel, "Generation not found.", EDITOR_UP, 200, ()),
}


def _patches(stack, names):
    mocks = {}
    for name in names:
        mocks[name] = stack.enter_context(patch(name, new_callable=AsyncMock if name.endswith("publish") else MagicMock))
    proxy = stack.enter_context(patch("app.routers.templates_proxy._proxy_request",
                                      AsyncMock(return_value=JSONResponse({"forwarded": True}))))
    return mocks, proxy


async def _send(client, request, headers):
    method, url, body = request
    kwargs = {"headers": headers} if headers is not None else {}
    if body is not None:
        kwargs["json"] = body
    return await getattr(client, method)(url, **kwargs)


def _headers(test_data, platform_admin_headers, role):
    return platform_admin_headers if role == "platform_admin" else test_data["get_headers"](role)


@pytest.mark.parametrize("name", list(WRITE_PATHS))
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.asyncio
async def test_write_needs_the_role_in_the_jobs_brand(client, db_session, test_data, platform_admin_headers, name, role):
    factory, message, allowed, success, names = WRITE_PATHS[name]
    request, _ = await factory(db_session, test_data)
    with ExitStack() as stack:
        mocks, proxy = _patches(stack, names)
        res = await _send(client, request, _headers(test_data, platform_admin_headers, role))
    if role in allowed:
        assert res.status_code == success, (name, role, res.text)
    elif allowed == PLATFORM_ONLY:
        assert res.status_code == 403, (name, role, res.text)  # a route for platform admins, not a job check
    elif role == "nonmember":  # another brand: exactly like an unknown id
        assert (res.status_code, res.json()) == (404, {"detail": message}), (name, role)
    else:  # a member with too low a role
        assert res.status_code == 403, (name, role, res.text)
    if role not in allowed:
        for mock in mocks.values():
            assert not mock.called and not mock.delay.called, (name, role)
        proxy.assert_not_called()


@pytest.mark.parametrize("name", [n for n, p in WRITE_PATHS.items() if p[1] is not None])
@pytest.mark.asyncio
async def test_unknown_id_is_the_same_404(client, db_session, test_data, platform_admin_headers, name):
    factory, message, _, _, names = WRITE_PATHS[name]
    _, unknown = await factory(db_session, test_data)
    with ExitStack() as stack:
        _, proxy = _patches(stack, names)
        headers = platform_admin_headers if name == "emit" else test_data["get_headers"]("owner")
        res = await _send(client, unknown, headers)
    assert (res.status_code, res.json()) == (404, {"detail": message}), name
    proxy.assert_not_called()


@pytest.mark.parametrize("name", list(WRITE_PATHS))
@pytest.mark.asyncio
async def test_unauthenticated_write_is_401(client, db_session, test_data, name):
    factory, _, _, _, names = WRITE_PATHS[name]
    request, _ = await factory(db_session, test_data)
    with ExitStack() as stack:
        _patches(stack, names)
        assert (await _send(client, request, None)).status_code == 401, name


# ========================== Jobs without a brand of their own ===================

@pytest.mark.asyncio
async def test_brandless_job_is_changed_by_its_creator_only(client, db_session, test_data):
    creator = test_data["users"]["nonmember"]  # not in the brand the brand-1 fallback wrote
    job = await _add(db_session, CatalogJob(job_id="rosanne-legacy", user_id=creator.id, brand_id=test_data["brand"].id,
                                            status="queued", meta={"workflow_template_id": "rosanne-v1"}))
    res = await client.post("/api/v1/generate/rosanne-legacy/cancel", json={}, headers=test_data["get_headers"]("owner"))
    assert (res.status_code, res.json()) == (404, {"detail": "Job not found."})
    res = await client.post("/api/v1/generate/rosanne-legacy/cancel", json={},
                            headers=test_data["get_headers"]("nonmember"))
    assert res.status_code == 200, res.text
    assert job.id


# ========================== /emit ===============================================

@pytest.mark.asyncio
async def test_emit_publishes_only_to_the_jobs_own_brand(client, db_session, test_data, platform_admin_headers):
    job = await _catalog(db_session, test_data)
    url = f"/api/v1/generation/{job.job_id}/emit?event=generation.progress"
    with patch("app.services.generation_events.generation_events.publish", new_callable=AsyncMock) as publish:
        res = await client.post(url, headers=platform_admin_headers)
        assert res.status_code == 200 and res.json()["brand_id"] == test_data["brand"].id
        assert publish.call_args.kwargs["brand_id"] == test_data["brand"].id
        # Another brand's channel is never chosen by the caller
        res = await client.post(f"{url}&brand_id={test_data['other_brand'].id}", headers=platform_admin_headers)
        assert res.status_code == 422
        # A member of the other brand cannot publish anything, for any job
        other = test_data["get_headers"]("nonmember")
        res = await client.post(f"{url}&brand_id={test_data['other_brand'].id}", headers=other)
        assert res.status_code == 403
        res = await client.post(f"{url}&brand_id={test_data['brand'].id}", headers=test_data["get_headers"]("owner"))
        assert res.status_code == 403
        bad = await client.post(f"/api/v1/generation/{job.job_id}/emit?event=nonsense", headers=platform_admin_headers)
        assert bad.status_code == 422
    assert publish.call_count == 1


# ========================== Refunded at most once ===============================

async def _brand_credits(db_session, brand_id):
    return (await db_session.execute(select(Brand.credits).where(Brand.id == brand_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _refund_rows(db_session, generation_id):
    return (await db_session.execute(select(func.count(CreditTransaction.id)).where(
        CreditTransaction.transaction_type == "refund",
        CreditTransaction.refund_key == f"generation:{generation_id}"))).scalar()


@pytest.mark.asyncio
async def test_cancel_twice_and_cancel_then_worker_failure_refund_once(client, db_session, test_data):
    brand = await db_session.get(Brand, test_data["brand"].id)
    brand.credits = 100
    await db_session.commit()
    job = await _catalog(db_session, test_data)
    await credits_sync_service.reserve_credits(brand_id=brand.id, user_id=test_data["users"]["editor"].id, amount=10,
                                               generation_id=job.job_id, description="test", db=db_session)
    reserved = await _brand_credits(db_session, brand.id)
    editor = test_data["get_headers"]("editor")

    res = await client.post(f"/api/v1/generate/{job.job_id}/cancel", json={}, headers=editor)
    assert (res.status_code, res.json()["credits_refunded"]) == (200, 10)
    res = await client.post(f"/api/v1/generate/{job.job_id}/cancel", json={}, headers=editor)
    assert res.status_code == 400  # already terminal
    # The worker's failure path afterwards (route_to_dlq refunds the reservation too)
    db_session.expunge_all()
    fresh = (await db_session.execute(select(CatalogJob).where(CatalogJob.job_id == job.job_id))).scalar_one()
    result = await pipeline_hardening.route_to_dlq(fresh, "worker failed", db_session, brand.id)
    assert result["credits_refunded"] == 0

    assert await _brand_credits(db_session, brand.id) == reserved + 10
    assert await _refund_rows(db_session, job.job_id) == 1


@pytest.mark.asyncio
async def test_dlq_after_cancel_refunds_nothing_more(client, db_session, test_data):
    brand = await db_session.get(Brand, test_data["brand"].id)
    brand.credits = 100
    await db_session.commit()
    job = await _catalog(db_session, test_data, status="queued")
    await credits_sync_service.reserve_credits(brand_id=brand.id, user_id=test_data["users"]["editor"].id, amount=6,
                                               generation_id=job.job_id, description="test", db=db_session)
    reserved = await _brand_credits(db_session, brand.id)
    assert (await client.post(f"/api/v1/generate/{job.job_id}/cancel", json={},
                              headers=test_data["get_headers"]("editor"))).status_code == 200
    res = await client.post(f"/api/v1/generate/{job.job_id}/dlq", json={"error": "x"},
                            headers=test_data["get_headers"]("owner"))
    assert res.status_code == 200 and res.json()["credits_refunded"] == 0
    assert await _brand_credits(db_session, brand.id) == reserved + 6
    assert await _refund_rows(db_session, job.job_id) == 1


@pytest.mark.asyncio
async def test_catalog_cancel_twice_refunds_once(client, db_session, test_data):
    from app.models.db import User
    editor = await db_session.get(User, test_data["users"]["editor"].id)
    editor.credits = 0
    await db_session.commit()
    job = await _catalog(db_session, test_data, credits_reserved=8)
    headers = test_data["get_headers"]("owner")  # a teammate may cancel it now
    first = await client.post(f"/api/v1/catalog-jobs/{job.id}/cancel", headers=headers)
    second = await client.post(f"/api/v1/catalog-jobs/{job.id}/cancel", headers=headers)
    assert (first.status_code, first.json()["credits_refunded"], second.status_code) == (200, 8, 409)
    db_session.expunge_all()
    assert (await db_session.get(User, editor.id)).credits == 8
