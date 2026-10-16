"""The ghost job worker sends the garment image(s) to Gemini with the prompt.

_process_ghost_job_async used to call generate_content([prompt]) with text
only. Now it loads each of the job's GhostJobAsset images from storage and
sends [prompt, image, ...] (upload order) as inline image parts
(google-genai types.Part.from_bytes since the production wiring PR). JPEG/PNG/WebP go as
they are; HEIC/HEIF and other formats are converted, and images over the
inline limits are downscaled. A job with no usable image fails once with a
clear error and a refund, without a retry and without calling Gemini.

The google-genai client is a fake (tests/gemini_fakes.py: no network, fake
key) and storage is an in-memory dict.
"""
import base64
import io
import types
from unittest.mock import MagicMock, patch

import celery.app.task
import gemini_fakes
import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import select

import app.models.db as models
from app.config import settings
from app.models.db import Asset, AssetRelationship, GhostJob, GhostJobAsset, GhostOutput, User
from app.services import job_images
from app.services.job_images import InputImageError, load_job_images, prepare_image, storage_key
from app.services.storage import storage_service
from app.worker import _process_ghost_job_async

FAKE_KEY = gemini_fakes.FAKE_KEY
OUTPUT_PNG = gemini_fakes.OUTPUT_PNG


def _image_bytes(fmt, size=(64, 48), color=(180, 30, 60), mode="RGB", noise=False, **save):
    img = Image.effect_noise(size, 100).convert(mode) if noise else Image.new(mode, size, color)
    out = io.BytesIO()
    img.save(out, format=fmt, **save)
    return out.getvalue()


def _decode(data):
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


# ========================== Fakes ===============================

@pytest.fixture
def store():
    """In-memory storage behind storage_service (local and S3 share these two methods)."""
    files = {}

    def save(name, data, file_type="image"):
        files[name] = data
        return f"/uploads/{name}"

    def read(name):
        if name not in files:
            raise FileNotFoundError(f"Local file not found: uploads/{name}")
        return files[name]

    with patch.object(storage_service, "save_file_bytes", side_effect=save), \
            patch.object(storage_service, "read_file_bytes", side_effect=read):
        yield files


@pytest.fixture
def gemini(monkeypatch):
    """A fake google-genai client and a configured (fake) key."""
    return gemini_fakes.install(monkeypatch)


@pytest.fixture
def queued(monkeypatch):
    delay = MagicMock(return_value=MagicMock(id="task-1"))
    monkeypatch.setattr(celery.app.task.Task, "delay", delay)
    return delay


async def _job(db_session, test_data, *paths, credits=4, **fields):
    job = GhostJob(user_id=test_data["users"]["editor"].id, brand_id=test_data["brand"].id, status="queued",
                   garment_type="dress", view="front", resolution="2K", credits_reserved=credits, **fields)
    db_session.add(job)
    await db_session.commit()
    for path in paths:
        db_session.add(GhostJobAsset(job_id=job.id, image_path=path))
    await db_session.commit()
    return job.id


async def _credits(db_session, user_id):
    return (await db_session.execute(select(User.credits).where(User.id == user_id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _run(db_session, job_id, task=None):
    """Run the worker in its own session, as in production."""
    task = task or MagicMock()
    db_session.expunge_all()
    with patch("app.worker.async_session_maker", models.async_session_maker):
        await _process_ghost_job_async(task, job_id)
    job = (await db_session.execute(select(GhostJob).where(GhostJob.id == job_id))).scalar_one()
    return job, task


def _sent(gemini, call=0):
    """(prompt, image parts) of one generate_content call."""
    _, prompt, images, _ = gemini.request(call)
    return prompt, images


# ========================== Images sent =========================

@pytest.mark.asyncio
async def test_single_job_sends_prompt_then_its_uploaded_image(client, db_session, test_data, store, gemini, queued):
    garment = _image_bytes("PNG")
    resp = await client.post("/api/v1/ghost-jobs", headers=test_data["get_headers"]("editor"),
                             files={"image": ("dress.png", garment, "image/png")},
                             data={"brand_id": str(test_data["brand"].id), "garment_type": "dress"})
    assert resp.status_code == 201, resp.text

    job, task = await _run(db_session, resp.json()["job_id"])

    assert job.status == "completed" and job.credits_consumed == 4
    task.retry.assert_not_called()
    assert gemini.client_cls.call_args.kwargs["api_key"] == FAKE_KEY
    gemini.generate_content.assert_called_once()
    prompt, images = _sent(gemini)
    assert isinstance(prompt, str) and "ghost mannequin" in prompt and "dress" in prompt
    assert images == [{"mime_type": "image/png", "data": garment}]
    output = (await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job.id))).scalar_one()
    assert store[output.output_url[len("/uploads/"):]] == OUTPUT_PNG  # output handling unchanged


@pytest.mark.asyncio
async def test_batch_jobs_each_send_their_own_image(client, db_session, test_data, store, gemini, queued):
    brand_id = test_data["brand"].id
    uploads = {"dress.jpg": _image_bytes("JPEG", color=(10, 10, 200)),
               "top.webp": _image_bytes("WEBP", color=(10, 200, 10))}
    garments = []
    for name, data in uploads.items():
        store[name] = data
        asset = Asset(brand_id=brand_id, filename=name, storage_path=f"/uploads/{name}", asset_type="image")
        db_session.add(asset)
        garments.append(asset)
    await db_session.commit()
    resp = await client.post("/api/v1/ghost-jobs/batch", headers=test_data["get_headers"]("editor"),
                             json={"brand_id": brand_id, "jobs": [{"image_key": g.storage_path} for g in garments]})
    assert resp.status_code == 201, resp.text
    garment_ids = [g.id for g in garments]

    for i, job_id in enumerate(resp.json()["job_ids"]):
        job, _ = await _run(db_session, job_id)
        assert job.status == "completed"
        _, images = _sent(gemini, i)
        assert images == [{"mime_type": ("image/jpeg", "image/webp")[i], "data": list(uploads.values())[i]}]
        output = (await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job_id))).scalar_one()
        rel = (await db_session.execute(select(AssetRelationship)
                                        .where(AssetRelationship.target_asset_id == output.asset_id))).scalar_one()
        assert rel.source_asset_id == garment_ids[i]  # lineage unchanged
    assert gemini.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_several_images_are_sent_in_upload_order(db_session, test_data, store, gemini):
    store.update({"front.png": _image_bytes("PNG", color=(1, 2, 3)), "back.png": _image_bytes("PNG", color=(4, 5, 6)),
                  "detail.jpg": _image_bytes("JPEG")})
    job_id = await _job(db_session, test_data, "/uploads/front.png", "/uploads/back.png", "/uploads/detail.jpg")
    job, _ = await _run(db_session, job_id)
    assert job.status == "completed"
    _, images = _sent(gemini)
    assert [p["data"] for p in images] == [store["front.png"], store["back.png"], store["detail.jpg"]]
    assert [p["mime_type"] for p in images] == ["image/png", "image/png", "image/jpeg"]


@pytest.mark.asyncio
async def test_mime_type_comes_from_the_image_not_the_filename(db_session, test_data, store, gemini):
    store["mislabelled.jpg"] = _image_bytes("PNG")
    job_id = await _job(db_session, test_data, "/uploads/mislabelled.jpg")
    await _run(db_session, job_id)
    assert _sent(gemini)[1] == [{"mime_type": "image/png", "data": store["mislabelled.jpg"]}]


@pytest.mark.asyncio
async def test_s3_paths_are_read_by_key(db_session, test_data, store, gemini, monkeypatch):
    monkeypatch.setattr(job_images.settings, "AWS_STORAGE_BUCKET_NAME", "modelens-test-bucket")
    store["brand/garment.png"] = _image_bytes("PNG")
    job_id = await _job(db_session, test_data, "s3://modelens-test-bucket/brand/garment.png")
    job, _ = await _run(db_session, job_id)
    assert job.status == "completed"
    assert _sent(gemini)[1][0]["data"] == store["brand/garment.png"]


# ========================== Format and size =====================

@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["HEIF", "GIF", "BMP"])
async def test_unsupported_formats_are_converted(db_session, test_data, store, gemini, fmt):
    store[f"garment.{fmt.lower()}"] = _image_bytes(fmt, size=(80, 60))
    job_id = await _job(db_session, test_data, f"/uploads/garment.{fmt.lower()}")
    job, _ = await _run(db_session, job_id)
    assert job.status == "completed"
    (part,) = _sent(gemini)[1]
    assert part["mime_type"] == "image/jpeg"
    sent = _decode(part["data"])
    assert (sent.format, sent.size) == ("JPEG", (80, 60))


def test_heic_from_an_iphone_is_converted():
    import pillow_heif
    assert pillow_heif  # installed with the app, so HEIC uploads can be decoded
    data, mime = prepare_image(_image_bytes("HEIF", size=(120, 90)))
    assert mime == "image/jpeg" and _decode(data).size == (120, 90)


def test_transparency_is_kept_as_png():
    data, mime = prepare_image(_image_bytes("GIF", mode="P", color=0, transparency=0))
    assert mime == "image/png" and _decode(data).mode == "RGBA"


@pytest.mark.asyncio
async def test_oversized_image_is_downscaled_keeping_aspect_ratio(db_session, test_data, store, gemini):
    store["huge.png"] = _image_bytes("PNG", size=(6000, 1500))
    job_id = await _job(db_session, test_data, "/uploads/huge.png")
    job, _ = await _run(db_session, job_id)
    assert job.status == "completed"
    (part,) = _sent(gemini)[1]
    assert _decode(part["data"]).size == (job_images.MAX_DIMENSION, 768)
    assert len(part["data"]) <= job_images.MAX_IMAGE_BYTES


def test_image_over_the_byte_limit_is_re_encoded_smaller():
    noisy = _image_bytes("PNG", size=(600, 400), noise=True)
    data, mime = prepare_image(noisy, max_bytes=30_000)
    assert len(noisy) > 30_000 >= len(data)
    assert mime == "image/jpeg"
    width, height = _decode(data).size
    assert abs(width / height - 1.5) < 0.02


def test_a_jobs_images_share_the_request_budget(monkeypatch):
    monkeypatch.setattr(job_images, "MAX_REQUEST_IMAGE_BYTES", 60_000)
    noisy = _image_bytes("PNG", size=(400, 400), noise=True)
    links = [types.SimpleNamespace(id=i, image_path=f"/uploads/{i}.png") for i in range(3)]
    parts = load_job_images(links, read=lambda key: noisy)
    assert len(parts) == 3 and all(len(p["data"]) <= 20_000 for p in parts)
    assert sum(len(p["data"]) for p in parts) <= 60_000


def test_limits_fit_the_gemini_inline_request_limit():
    # Inline bytes are base64-encoded; Gemini caps a whole inline request at 20 MB.
    assert job_images.MAX_REQUEST_IMAGE_BYTES * 4 / 3 < 19 * 1024 * 1024
    assert job_images.MAX_IMAGE_BYTES <= job_images.MAX_REQUEST_IMAGE_BYTES


def test_rotated_photos_are_sent_upright():
    img = Image.new("RGB", (60, 40))
    exif = img.getexif()
    exif[0x0112] = 6  # rotate 90 degrees on display
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    data, mime = prepare_image(out.getvalue())
    assert mime == "image/jpeg" and _decode(data).size == (40, 60)


@pytest.mark.parametrize("path", ["https://example.com/garment.png", "s3://someone-elses-bucket/g.png",
                                  "/uploads/../app/config.py", "/uploads/", "garment.png"])
def test_only_our_own_storage_paths_are_read(path):
    with pytest.raises(InputImageError):
        storage_key(path)


# ========================== Failures ============================

FAILURES = {
    "no image": ([], "No garment image is attached to this job."),
    "missing from storage": (["/uploads/gone.png"], "Garment image 1 could not be loaded from storage."),
    "not an image": (["/uploads/notes.png"], "Garment image 1 could not be decoded as an image."),
    "truncated": (["/uploads/truncated.jpg"], "Garment image 1 could not be decoded as an image."),
    "external url": (["https://example.com/g.png"], "Garment image 1 is not stored in ModeLens storage."),
    "second of two bad": (["/uploads/ok.png", "/uploads/notes.png"],
                          "Garment image 2 could not be decoded as an image."),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("gemini_configured", [True, False], ids=["gemini", "mock-mode"])
@pytest.mark.parametrize("case", list(FAILURES))
async def test_unusable_input_fails_once_refunds_and_never_calls_gemini(
        db_session, test_data, store, gemini, monkeypatch, case, gemini_configured):
    if not gemini_configured:
        monkeypatch.setattr(settings, "GEMINI_API_KEY", None)  # non-production (TESTING): mock mode
    store["notes.png"] = b"these are fit notes, not a picture"
    store["truncated.jpg"] = _image_bytes("JPEG", size=(200, 200), noise=True)[:300]
    store["ok.png"] = _image_bytes("PNG")
    paths, message = FAILURES[case]
    user_id = test_data["users"]["editor"].id
    start = await _credits(db_session, user_id)
    job_id = await _job(db_session, test_data, *paths, credits=7)

    with patch("app.worker.storage_service.save_file_bytes") as save:
        job, task = await _run(db_session, job_id)

    assert (job.status, job.error_message, job.progress, job.credits_consumed) == ("failed", message, 0, 0)
    assert await _credits(db_session, user_id) == start + 7  # refunded exactly once
    task.retry.assert_not_called()  # a retry would refund again and fail again
    gemini.generate_content.assert_not_called()
    save.assert_not_called()
    assert (await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job_id))).first() is None


@pytest.mark.asyncio
async def test_storage_errors_are_not_copied_into_the_job(db_session, test_data, gemini):
    job_id = await _job(db_session, test_data, "/uploads/garment.png")
    secret_ish = "S3 AccessDenied for s3://private-bucket/garment.png?X-Amz-Signature=abc123"
    with patch.object(storage_service, "read_file_bytes", side_effect=RuntimeError(secret_ish)):
        job, _ = await _run(db_session, job_id)
    assert job.error_message == "Garment image 1 could not be loaded from storage."


@pytest.mark.asyncio
async def test_other_failures_retry_without_refund(db_session, test_data, store, gemini):
    """A failure after the images loaded (here: saving the output) is retried by Celery; nothing is
    refunded until the last attempt fails (tests/test_idempotent_job_refunds.py)."""
    store["ok.png"] = _image_bytes("PNG")
    user_id = test_data["users"]["editor"].id
    start = await _credits(db_session, user_id)
    job_id = await _job(db_session, test_data, "/uploads/ok.png")
    task = MagicMock()
    task.retry.side_effect = RuntimeError("retry scheduled")
    with patch.object(storage_service, "save_file_bytes", side_effect=ValueError("disk full")), \
            pytest.raises(RuntimeError, match="retry scheduled"):
        await _run(db_session, job_id, task)
    job = (await db_session.execute(select(GhostJob).where(GhostJob.id == job_id))).scalar_one()
    assert (job.status, job.error_message) == ("queued", "disk full")
    assert await _credits(db_session, user_id) == start
    task.retry.assert_called_once()
    gemini.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_image_bytes_are_never_logged(db_session, test_data, store, gemini, capsys):
    store["ok.png"] = _image_bytes("PNG", color=(9, 9, 9))
    job_id = await _job(db_session, test_data, "/uploads/ok.png", "/uploads/notes.png")
    store["notes.png"] = b"not an image"
    await _run(db_session, job_id)
    logged = capsys.readouterr().out
    assert "[GhostJob]" in logged
    for leak in (base64.b64encode(store["ok.png"]).decode()[:40], repr(store["ok.png"])[:40], FAKE_KEY):
        assert leak not in logged
