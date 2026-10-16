"""Catalog and Sketch create routes check every input image before anything happens.

* A path (Sketch `reference_image_paths`, Catalog `products[].image_path`) must
  be one of our storage paths and an asset of the request's brand
  (app/services/input_paths.py, the same rules the Sketch worker re-checks).
  Another brand's file is reported exactly like an unknown one, and the path is
  never echoed.
* An upload must decode as a JPEG, PNG, WebP or HEIC image of at most 20 MB,
  whatever its name or content type says.
* A Sketch job takes at most 6 images (sketches and references together) and at
  least one sketch.
* A form post without a file (sent urlencoded) or a body that is not JSON is a
  422, not a 500.

Every rejection is a 422 with nothing charged, written, stored or queued. No
network: storage and Celery are patched.
"""
import io
from unittest.mock import MagicMock, patch

import celery.app.task
import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import func, select

from app.config import settings
from app.models.db import (
    Asset, CatalogJob, CatalogJobItem, CreditTransaction, GhostJob, GhostJobAsset, SketchJob,
    SketchJobReference, User,
)
from app.services.input_paths import NOT_FOUND, NOT_OURS
from app.services.job_images import InputImageError, MAX_UPLOAD_BYTES
from app.services.sketch_inputs import MAX_INPUT_IMAGES, load_sketch_images
from app.services.storage import storage_service

SKETCH_URL, CATALOG_URL, GHOST_URL = "/api/v1/sketch-jobs", "/api/v1/catalog-jobs", "/api/v1/ghost-jobs"
MINE = "/uploads/mine.png"
ROW_MODELS = (SketchJob, SketchJobReference, CatalogJob, CatalogJobItem, GhostJob, GhostJobAsset, Asset,
              CreditTransaction)


def _image(fmt, size=(16, 12)):
    out = io.BytesIO()
    Image.new("RGB", size, (120, 40, 200)).save(out, format=fmt)
    return out.getvalue()


PNG = _image("PNG")


@pytest.fixture(autouse=True)
def outside_production(monkeypatch):
    """Sketch creation runs outside production (it is 503 there while SKETCH_JOBS_ENABLED is off)."""
    monkeypatch.setattr(settings, "APP_ENV", "development")


@pytest.fixture
def queued(monkeypatch):
    delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr(celery.app.task.Task, "delay", delay)
    return delay


@pytest.fixture
def stored():
    names = iter(range(1000))
    with patch.object(storage_service, "save_file_bytes",
                      side_effect=lambda name, data, *a: f"/uploads/saved-{next(names)}-{name}") as save:
        yield save


@pytest_asyncio.fixture
async def setup(db_session, test_data):
    """The editor (100 credits) and an image asset of the test brand at MINE."""
    editor = await db_session.get(User, test_data["users"]["editor"].id)
    editor.credits = 100
    db_session.add(Asset(brand_id=test_data["brand"].id, filename="mine.png", storage_path=MINE, asset_type="image"))
    await db_session.commit()
    return test_data


async def _snapshot(db_session):
    counts = [(await db_session.execute(select(func.count()).select_from(m))).scalar() for m in ROW_MODELS]
    credits = (await db_session.execute(select(User.id, User.credits).order_by(User.id)
                                        .execution_options(populate_existing=True))).all()
    return counts, credits


def _headers(test_data):
    return test_data["get_headers"]("editor")


async def _other_brand_path(db_session, test_data, case):
    """A storage path tied to another brand: its asset, or an input of one of its jobs."""
    other, user_id = test_data["other_brand"].id, test_data["users"]["nonmember"].id
    path = f"/uploads/{case.replace(' ', '-')}.png"
    if case == "other brand asset":
        db_session.add(Asset(brand_id=other, filename="x.png", storage_path=path, asset_type="image"))
    elif case == "other brand ghost input":
        job = GhostJob(user_id=user_id, brand_id=other, status="completed")
        db_session.add(job)
        await db_session.flush()
        db_session.add(GhostJobAsset(job_id=job.id, image_path=path))
    elif case == "other brand sketch input":
        job = SketchJob(user_id=user_id, brand_id=other, status="completed")
        db_session.add(job)
        await db_session.flush()
        db_session.add(SketchJobReference(job_id=job.id, reference_type="sketch", image_path=path))
    elif case == "other brand catalog input":
        job = CatalogJob(user_id=user_id, brand_id=other, status="completed")
        db_session.add(job)
        await db_session.flush()
        db_session.add(CatalogJobItem(job_id=job.id, product_image_path=path))
    await db_session.commit()
    return path


# (case, path, message): another brand's path reads exactly like an unknown asset.
BAD_PATHS = [
    ("external url", "https://images.example.com/sketch.png", NOT_OURS),
    ("protocol-relative url", "//images.example.com/sketch.png", NOT_OURS),
    ("traversal", "/uploads/../app/config.py", NOT_OURS),
    ("absolute key", "/uploads//etc/passwd", NOT_OURS),
    ("bare absolute path", "/etc/passwd", NOT_OURS),
    ("another bucket", "s3://someone-elses-bucket/sketch.png", NOT_OURS),
    ("unknown asset", "/uploads/never-uploaded.png", NOT_FOUND),
    ("other brand asset", None, NOT_FOUND),
    ("other brand ghost input", None, NOT_FOUND),
    ("other brand sketch input", None, NOT_FOUND),
    ("other brand catalog input", None, NOT_FOUND),
]


async def _assert_rejected(db_session, res, before, queued, stored, field, message, path=None):
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert f"{field} {message}." in detail
    if path:
        assert path not in detail and path.rsplit("/", 1)[-1] not in detail
    assert await _snapshot(db_session) == before
    queued.assert_not_called()
    stored.assert_not_called()


# ========================== Sketch: paths ========================

@pytest.mark.asyncio
@pytest.mark.parametrize("case,path,message", BAD_PATHS)
async def test_sketch_rejects_paths_that_are_not_this_brands_assets(
        client, db_session, setup, queued, stored, case, path, message):
    path = path or await _other_brand_path(db_session, setup, case)
    before = await _snapshot(db_session)
    res = await client.post(SKETCH_URL, headers=_headers(setup), json={
        "brand_id": setup["brand"].id, "generation_mode": "fast_draft", "reference_image_paths": [MINE, path]})
    await _assert_rejected(db_session, res, before, queued, stored, "reference_image_paths[1]", message, path)
    assert "reference_image_paths[0]" not in res.json()["detail"]


@pytest.mark.asyncio
async def test_sketch_reports_every_bad_path_by_index(client, db_session, setup, queued, stored):
    res = await client.post(SKETCH_URL, headers=_headers(setup), json={
        "brand_id": setup["brand"].id, "reference_image_paths": ["https://x.example/a.png", MINE, "/uploads/nope.png"]})
    assert res.status_code == 422
    assert res.json()["detail"] == (f"reference_image_paths[0] {NOT_OURS}. reference_image_paths[2] {NOT_FOUND}.")


@pytest.mark.asyncio
async def test_sketch_rejects_a_deleted_asset_like_an_unknown_one(client, db_session, setup, queued, stored):
    from datetime import datetime
    asset = (await db_session.execute(select(Asset).where(Asset.storage_path == MINE))).scalar_one()
    asset.deleted_at = datetime.utcnow()
    await db_session.commit()
    before = await _snapshot(db_session)
    res = await client.post(SKETCH_URL, headers=_headers(setup),
                            json={"brand_id": setup["brand"].id, "reference_image_paths": [MINE]})
    await _assert_rejected(db_session, res, before, queued, stored, "reference_image_paths[0]", NOT_FOUND)


@pytest.mark.asyncio
async def test_sketch_accepts_an_asset_of_the_brand(client, db_session, setup, queued, stored):
    res = await client.post(SKETCH_URL, headers=_headers(setup), json={
        "brand_id": setup["brand"].id, "generation_mode": "fast_draft", "reference_image_paths": [MINE]})
    assert res.status_code == 201, res.text
    refs = (await db_session.execute(select(SketchJobReference.image_path))).scalars().all()
    assert refs == [MINE]
    queued.assert_called_once()
    stored.assert_not_called()


@pytest.mark.asyncio
async def test_another_brands_path_answers_like_an_unknown_one(client, db_session, setup, queued, stored):
    """The response cannot be used to learn whether another brand's file exists."""
    theirs = await _other_brand_path(db_session, setup, "other brand asset")
    answers = []
    for path in (theirs, "/uploads/other-brand-asset-nope.png"):
        res = await client.post(SKETCH_URL, headers=_headers(setup),
                                json={"brand_id": setup["brand"].id, "reference_image_paths": [path]})
        answers.append((res.status_code, res.json()["detail"]))
    assert answers[0] == answers[1] == (422, f"reference_image_paths[0] {NOT_FOUND}.")


# ========================== Sketch: uploads ======================

def _sketch_form(test_data, files, **data):
    return {"headers": _headers(test_data), "data": {"brand_id": str(test_data["brand"].id), **data},
            "files": files}


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt,extension", [("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp"), ("HEIF", ".heic")])
async def test_sketch_accepts_real_images_and_saves_them_by_their_decoded_type(
        client, db_session, setup, queued, stored, fmt, extension):
    res = await client.post(SKETCH_URL, **_sketch_form(setup, [
        ("sketches", ("front.bin", _image(fmt), "application/octet-stream")),
        ("fabric_refs", ("fabric.html", PNG, "text/html")),
    ]))
    assert res.status_code == 201, res.text
    saved = [call.args[0] for call in stored.call_args_list]
    assert [name.rsplit(".", 1)[-1] for name in saved] == [extension[1:], "png"]
    refs = (await db_session.execute(select(SketchJobReference.reference_type).order_by(SketchJobReference.id)))
    assert refs.scalars().all() == ["sketch", "fabric"]
    queued.assert_called_once()


# (name, bytes, content type, message)
BAD_UPLOADS = [
    ("not an image", ("sketch.png", b"just some text", "image/png"), "is not a JPEG, PNG, WebP or HEIC image"),
    ("html disguised as jpeg", ("sketch.jpg", b"<html><script>alert(1)</script></html>", "image/jpeg"),
     "is not a JPEG, PNG, WebP or HEIC image"),
    ("pdf disguised as png", ("sketch.png", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n", "image/png"),
     "is not a JPEG, PNG, WebP or HEIC image"),
    ("gif named png", ("sketch.png", _image("GIF"), "image/png"), "is not a JPEG, PNG, WebP or HEIC image"),
    ("bmp", ("sketch.bmp", _image("BMP"), "image/bmp"), "is not a JPEG, PNG, WebP or HEIC image"),
    ("truncated png", ("sketch.png", _image("PNG", (64, 64))[:60], "image/png"),
     "is not a JPEG, PNG, WebP or HEIC image"),
    ("empty", ("sketch.png", b"", "image/png"), "is empty"),
    ("oversized", ("sketch.png", PNG + b"\0" * MAX_UPLOAD_BYTES, "image/png"), "is larger than 20 MB"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case,upload,message", BAD_UPLOADS, ids=[c[0] for c in BAD_UPLOADS])
async def test_sketch_rejects_uploads_that_are_not_images(client, db_session, setup, queued, stored, case, upload,
                                                          message):
    before = await _snapshot(db_session)
    res = await client.post(SKETCH_URL, **_sketch_form(setup, [
        ("sketches", ("ok.png", PNG, "image/png")), ("print_refs", upload)]))
    await _assert_rejected(db_session, res, before, queued, stored, "print_refs[0]", message)


@pytest.mark.asyncio
async def test_sketch_rejects_a_text_field_in_place_of_a_file(client, db_session, setup, queued, stored):
    before = await _snapshot(db_session)
    res = await client.post(SKETCH_URL, **_sketch_form(setup, [("sketches", ("ok.png", PNG, "image/png"))],
                                                       fabric_refs="/uploads/mine.png"))
    await _assert_rejected(db_session, res, before, queued, stored, "fabric_refs[0]", "is not a file")


def test_upload_limit_is_20_mb():
    assert MAX_UPLOAD_BYTES == 20 * 1024 * 1024


# ========================== Sketch: image count ==================

@pytest.mark.asyncio
async def test_sketch_takes_six_images_in_all(client, db_session, setup, queued, stored):
    assert MAX_INPUT_IMAGES == 6
    files = [("sketches", ("s.png", PNG, "image/png"))] + [("fabric_refs", (f"f{i}.png", PNG, "image/png"))
                                                           for i in range(5)]
    res = await client.post(SKETCH_URL, **_sketch_form(setup, files))
    assert res.status_code == 201, res.text
    assert stored.call_count == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("sketches,references", [(1, 6), (7, 0), (2, 5)])
async def test_sketch_rejects_a_seventh_image_before_any_charge(client, db_session, setup, queued, stored,
                                                                sketches, references):
    files = [("sketches", (f"s{i}.png", PNG, "image/png")) for i in range(sketches)]
    files += [("construction_refs", (f"c{i}.png", PNG, "image/png")) for i in range(references)]
    before = await _snapshot(db_session)
    res = await client.post(SKETCH_URL, **_sketch_form(setup, files))
    assert res.status_code == 422
    assert res.json()["detail"] == ("A sketch job takes at most 6 images (sketches and references together); "
                                    "this request has 7.")
    assert await _snapshot(db_session) == before
    queued.assert_not_called()
    stored.assert_not_called()


@pytest.mark.asyncio
async def test_sketch_json_paths_count_too(client, db_session, setup, queued, stored):
    res = await client.post(SKETCH_URL, headers=_headers(setup),
                            json={"brand_id": setup["brand"].id, "reference_image_paths": [MINE] * 7})
    assert res.status_code == 422 and "at most 6 images" in res.json()["detail"]
    res = await client.post(SKETCH_URL, headers=_headers(setup),
                            json={"brand_id": setup["brand"].id, "reference_image_paths": [MINE] * 6})
    assert res.status_code == 201, res.text


# ========================== Sketch: no image / not a form =========

@pytest.mark.asyncio
@pytest.mark.parametrize("request_kind", ["urlencoded form", "form without a sketch", "json", "json empty list"])
async def test_sketch_without_a_sketch_is_422(client, db_session, setup, queued, stored, request_kind):
    brand_id = setup["brand"].id
    kwargs = {
        "urlencoded form": {"data": {"brand_id": str(brand_id)}},  # a form without files is sent urlencoded
        "form without a sketch": {"data": {"brand_id": str(brand_id)},
                                  "files": [("fabric_refs", ("f.png", PNG, "image/png"))]},
        "json": {"json": {"brand_id": brand_id}},
        "json empty list": {"json": {"brand_id": brand_id, "reference_image_paths": []}},
    }[request_kind]
    before = await _snapshot(db_session)
    res = await client.post(SKETCH_URL, headers=_headers(setup), **kwargs)
    assert res.status_code == 422, res.text
    assert res.json()["detail"].startswith("At least one sketch image is required")
    assert await _snapshot(db_session) == before
    queued.assert_not_called()
    stored.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [SKETCH_URL, CATALOG_URL, GHOST_URL])
@pytest.mark.parametrize("body", [b"", b"not json", b"{\"brand_id\": "])
async def test_a_body_that_is_not_json_or_a_form_is_422(client, db_session, setup, queued, stored, url, body):
    before = await _snapshot(db_session)
    res = await client.post(url, headers={**_headers(setup), "content-type": "application/json"}, content=body)
    assert res.status_code == 422, res.text
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [SKETCH_URL, CATALOG_URL])
async def test_a_non_numeric_form_brand_id_is_422(client, db_session, setup, queued, stored, url):
    field = "sketches" if url == SKETCH_URL else "products"
    res = await client.post(url, headers=_headers(setup), data={"brand_id": "abc"},
                            files=[(field, ("a.png", PNG, "image/png"))])
    assert res.status_code == 422, res.text
    stored.assert_not_called()


# ========================== Ghost: form without a file ===========

@pytest.mark.asyncio
async def test_ghost_form_post_without_a_file_is_422_not_500(client, db_session, setup, queued, stored):
    before = await _snapshot(db_session)
    res = await client.post(GHOST_URL, headers=_headers(setup),
                            data={"brand_id": str(setup["brand"].id), "resolution": "1K"})
    assert res.status_code == 422, res.text
    assert res.json()["detail"].startswith("A garment image is required")
    assert await _snapshot(db_session) == before
    queued.assert_not_called()


@pytest.mark.asyncio
async def test_ghost_urlencoded_form_with_an_asset_key_works(client, db_session, setup, queued, stored):
    res = await client.post(GHOST_URL, headers=_headers(setup),
                            data={"brand_id": str(setup["brand"].id), "resolution": "1K", "image_key": MINE})
    assert res.status_code == 201, res.text


# ========================== Catalog: paths =======================

def _catalog(test_data, *paths):
    return {"brand_id": test_data["brand"].id, "generation_mode": "fast_draft",
            "products": [{"sku_tag": f"SKU-{i}", "image_path": p} for i, p in enumerate(paths)]}


@pytest.mark.asyncio
@pytest.mark.parametrize("case,path,message", BAD_PATHS)
async def test_catalog_rejects_paths_that_are_not_this_brands_assets(
        client, db_session, setup, queued, stored, case, path, message):
    path = path or await _other_brand_path(db_session, setup, case)
    before = await _snapshot(db_session)
    res = await client.post(CATALOG_URL, headers=_headers(setup), json=_catalog(setup, MINE, path))
    await _assert_rejected(db_session, res, before, queued, stored, "products[1].image_path", message, path)


@pytest.mark.asyncio
@pytest.mark.parametrize("product", [{"sku_tag": "SKU-1"}, {"sku_tag": "SKU-1", "image_path": ""},
                                     {"sku_tag": "SKU-1", "image_path": None}])
async def test_catalog_requires_an_image_path(client, db_session, setup, queued, stored, product):
    before = await _snapshot(db_session)
    res = await client.post(CATALOG_URL, headers=_headers(setup),
                            json={"brand_id": setup["brand"].id, "products": [product]})
    assert res.status_code == 422
    assert res.json()["detail"] == "products[0].image_path: an image path is required."
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [123, ["/uploads/mine.png"], {"path": "/uploads/mine.png"}])
async def test_catalog_rejects_an_image_path_that_is_not_a_string(client, db_session, setup, queued, stored, value):
    res = await client.post(CATALOG_URL, headers=_headers(setup),
                            json={"brand_id": setup["brand"].id, "products": [{"image_path": value}]})
    assert (res.status_code, res.json()["detail"]) == (422, f"products[0].image_path {NOT_OURS}.")


@pytest.mark.asyncio
async def test_catalog_accepts_an_asset_of_the_brand(client, db_session, setup, queued, stored):
    res = await client.post(CATALOG_URL, headers=_headers(setup), json=_catalog(setup, MINE, MINE))
    assert res.status_code == 201, res.text
    items = (await db_session.execute(select(CatalogJobItem.product_image_path))).scalars().all()
    assert items == [MINE, MINE]
    queued.assert_called_once()


# ========================== Catalog: uploads =====================

@pytest.mark.asyncio
async def test_catalog_accepts_real_image_uploads(client, db_session, setup, queued, stored):
    res = await client.post(CATALOG_URL, headers=_headers(setup), data={"brand_id": str(setup["brand"].id)},
                            files=[("products", ("a.txt", _image("JPEG"), "text/plain")),
                                   ("products", ("b.png", _image("WEBP"), "image/png"))])
    assert res.status_code == 201, res.text
    assert [c.args[0].rsplit(".", 1)[-1] for c in stored.call_args_list] == ["jpg", "webp"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case,upload,message", BAD_UPLOADS, ids=[c[0] for c in BAD_UPLOADS])
async def test_catalog_rejects_uploads_that_are_not_images(client, db_session, setup, queued, stored, case, upload,
                                                           message):
    before = await _snapshot(db_session)
    res = await client.post(CATALOG_URL, headers=_headers(setup), data={"brand_id": str(setup["brand"].id)},
                            files=[("products", ("ok.png", PNG, "image/png")), ("products", upload)])
    await _assert_rejected(db_session, res, before, queued, stored, "products[1]", message)


@pytest.mark.asyncio
async def test_catalog_form_without_a_file_is_a_clean_error(client, db_session, setup, queued, stored):
    before = await _snapshot(db_session)
    res = await client.post(CATALOG_URL, headers=_headers(setup), data={"brand_id": str(setup["brand"].id)})
    assert res.status_code == 400 and res.json()["detail"] == "At least one product is required."
    res = await client.post(CATALOG_URL, headers=_headers(setup),
                            data={"brand_id": str(setup["brand"].id), "products": "/uploads/mine.png"})
    assert (res.status_code, res.json()["detail"]) == (422, "products[0] is not a file.")
    assert await _snapshot(db_session) == before
    queued.assert_not_called()


# ========================== Order: auth first ====================

@pytest.mark.asyncio
async def test_paths_are_checked_only_after_the_brand_role(client, db_session, setup, queued, stored):
    """A caller without access to the brand learns nothing about paths: 403 comes first."""
    for url, body in ((SKETCH_URL, {"reference_image_paths": ["https://x.example/a.png"]}),
                      (CATALOG_URL, {"products": [{"image_path": "https://x.example/a.png"}]})):
        res = await client.post(url, headers=setup["get_headers"]("viewer"),
                                json={"brand_id": setup["brand"].id, **body})
        assert res.status_code == 403, res.text


# ========================== Worker: second line ==================

@pytest.mark.asyncio
@pytest.mark.parametrize("case,path,message", BAD_PATHS)
async def test_the_sketch_worker_still_rejects_bad_paths(db_session, setup, case, path, message):
    """A job written before these checks (or by anything else) still fails in the worker, unread."""
    path = path or await _other_brand_path(db_session, setup, case)
    job = SketchJob(user_id=setup["users"]["editor"].id, brand_id=setup["brand"].id, status="queued")
    db_session.add(job)
    await db_session.flush()
    refs = [SketchJobReference(job_id=job.id, reference_type="sketch", image_path=MINE),
            SketchJobReference(job_id=job.id, reference_type="fabric", image_path=path)]
    db_session.add_all(refs)
    await db_session.commit()
    read = MagicMock(return_value=PNG)
    if message == NOT_FOUND and case == "unknown asset":
        # Not tied to another brand: the worker reads it (an upload of this job looks the same).
        parts, _ = await load_sketch_images(db_session, job, refs, read=read)
        assert len(parts) == 2
        return
    with pytest.raises(InputImageError) as err:
        await load_sketch_images(db_session, job, refs, read=read)
    expected = "is not stored in ModeLens storage" if message == NOT_OURS else \
        "is not stored in this brand's ModeLens storage"
    assert str(err.value) == f"Sketch input image 2 {expected}."
    read.assert_not_called()
