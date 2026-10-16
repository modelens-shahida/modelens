"""Gemini production wiring for ghost jobs (google-genai).

GEMINI_API_KEY was read with getattr() but never declared, so settings dropped
it and every ghost job got the 1x1 mock image. Now:
- GEMINI_API_KEY (secret) and GEMINI_GHOST_MODEL are declared settings.
- One client helper (app/services/gemini_client.py) sends the prompt plus the
  image parts and asks for an IMAGE response from the configured model.
- The mock image is only used outside production, when no key is set. Where
  production rules apply, a missing key, API error, timeout, safety block or a
  response without an image fails the job with a safe message and refunds it
  once, without a Celery retry.
- Production refuses to boot without a key or with a non-image model.

google.genai.Client is faked (no network, fake key); storage is in memory.
"""
import logging
import pathlib
from unittest.mock import MagicMock, patch

import gemini_fakes
import httpx
import pytest
from google.genai import errors, types
from pydantic import SecretStr
from sqlalchemy import func, select

import app.models.db as models
from app.config import DEFAULT_GEMINI_GHOST_MODEL, Settings, settings
from app.config_production import check_config
from app.models.db import Asset, GhostJob, GhostJobAsset, GhostOutput, User
from app.services import gemini_client
from app.services.storage import storage_service
from app.worker import _process_ghost_job_async

FAKE_KEY = gemini_fakes.FAKE_KEY
PROVIDER_BODY = gemini_fakes.PROVIDER_BODY


def _png():
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (32, 24), (200, 40, 40)).save(out, format="PNG")
    return out.getvalue()


GARMENT = _png()


# ========================== Fixtures ============================

@pytest.fixture
def store():
    files = {"garment.png": GARMENT}

    def save(name, data, file_type="image"):
        files[name] = data
        return f"/uploads/{name}"

    with patch.object(storage_service, "save_file_bytes", side_effect=save) as saved, \
            patch.object(storage_service, "read_file_bytes", side_effect=lambda name: files[name]):
        saved.files = files
        yield saved


@pytest.fixture
def gemini(monkeypatch):
    return gemini_fakes.install(monkeypatch)


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")


async def _job(db_session, test_data, credits=7):
    job = GhostJob(user_id=test_data["users"]["editor"].id, brand_id=test_data["brand"].id, status="queued",
                   garment_type="coat", view="front", resolution="4K", credits_reserved=credits)
    db_session.add(job)
    await db_session.commit()
    db_session.add(GhostJobAsset(job_id=job.id, image_path="/uploads/garment.png"))
    await db_session.commit()
    return job.id


async def _credits(db_session, test_data):
    return (await db_session.execute(select(User.credits).where(User.id == test_data["users"]["editor"].id)
                                     .execution_options(populate_existing=True))).scalar_one()


async def _run(db_session, job_id, retries=0, retry_error=None):
    """One worker attempt in its own session; `retries` is Celery's attempt counter."""
    task = MagicMock()
    task.request.retries = retries
    task.retry.side_effect = retry_error or RuntimeError("retry scheduled")
    db_session.expunge_all()
    with patch("app.worker.async_session_maker", models.async_session_maker):
        try:
            await _process_ghost_job_async(task, job_id)
        except RuntimeError as e:
            assert str(e) == "retry scheduled"
    job = (await db_session.execute(select(GhostJob).where(GhostJob.id == job_id)
                                    .execution_options(populate_existing=True))).scalar_one()
    return job, task


async def _outputs(db_session, job_id):
    return (await db_session.execute(select(func.count()).select_from(GhostOutput)
                                     .where(GhostOutput.job_id == job_id))).scalar()


# ========================== Settings ============================

def test_settings_are_declared():
    fields = Settings.model_fields
    assert "GEMINI_API_KEY" in fields and "GEMINI_GHOST_MODEL" in fields
    assert fields["GEMINI_GHOST_MODEL"].default == DEFAULT_GEMINI_GHOST_MODEL == "gemini-3-pro-image"
    assert DEFAULT_GEMINI_GHOST_MODEL in gemini_client.GEMINI_IMAGE_MODELS
    assert "gemini-2.5-flash" not in gemini_client.GEMINI_IMAGE_MODELS  # text-only model


def test_key_from_the_environment_is_kept_and_secret(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GEMINI_GHOST_MODEL", "gemini-nano-banana-2.1")
    loaded = Settings()
    assert isinstance(loaded.GEMINI_API_KEY, SecretStr)
    assert loaded.GEMINI_API_KEY.get_secret_value() == FAKE_KEY
    assert loaded.GEMINI_GHOST_MODEL == "gemini-nano-banana-2.1"
    assert FAKE_KEY not in repr(loaded) and FAKE_KEY not in str(loaded.model_dump())


def test_nothing_imports_the_deprecated_sdk():
    app_dir = pathlib.Path(gemini_client.__file__).resolve().parents[1]
    offenders = [str(p) for p in app_dir.rglob("*.py") if "google.generativeai" in p.read_text()]
    assert offenders == []


# ========================== Request =============================

@pytest.mark.asyncio
async def test_request_has_prompt_images_image_modality_and_configured_model(
        db_session, test_data, store, gemini, production, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_GHOST_MODEL", "gemini-nano-banana-2.1")
    job_id = await _job(db_session, test_data)
    job, task = await _run(db_session, job_id)

    assert job.status == "completed", job.error_message
    gemini.generate_content.assert_called_once()
    model, prompt, images, config = gemini.request()
    assert model == "gemini-nano-banana-2.1"
    assert isinstance(prompt, str) and "ghost mannequin" in prompt and "coat" in prompt
    assert images == [{"mime_type": "image/png", "data": GARMENT}]
    assert config.response_modalities == ["IMAGE"]
    options = gemini.client_cls.call_args.kwargs["http_options"]
    assert gemini.client_cls.call_args.kwargs["api_key"] == FAKE_KEY
    assert options.timeout == gemini_client.REQUEST_TIMEOUT_SECONDS * 1000 == 120_000
    assert options.retry_options.attempts == gemini_client.REQUEST_ATTEMPTS


@pytest.mark.asyncio
@pytest.mark.parametrize("mime,ext", [("image/png", "png"), ("image/jpeg", "jpg")])
async def test_returned_image_is_saved_and_job_completed(
        db_session, test_data, store, gemini, production, mime, ext):
    generated = b"\x89PNG generated garment" if ext == "png" else b"\xff\xd8 generated garment"
    gemini.generate_content.return_value = gemini_fakes.image_response(
        data=generated, mime=mime, text="Here is your ghost mannequin.", response_id="resp-42")
    start = await _credits(db_session, test_data)
    job_id = await _job(db_session, test_data)
    job, task = await _run(db_session, job_id)

    assert (job.status, job.progress, job.credits_consumed, job.error_message) == ("completed", 100, 7, None)
    task.retry.assert_not_called()
    output = (await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job_id))).scalar_one()
    name = output.output_url[len("/uploads/"):]
    assert name.startswith(f"ghost_{job_id}_") and name.endswith(f".{ext}")
    assert store.files[name] == generated
    assert output.api_interaction_id == "resp-42"
    asset = (await db_session.execute(select(Asset).where(Asset.id == output.asset_id))).scalar_one()
    assert (asset.storage_path, asset.asset_type) == (output.output_url, "generated")
    assert await _credits(db_session, test_data) == start  # reserved at creation, consumed now


# ========================== Production failures =================

FAILURES = gemini_fakes.FAILURES
_arrange = gemini_fakes.arrange_failure


@pytest.mark.asyncio
@pytest.mark.parametrize("case", list(FAILURES))
async def test_production_failure_fails_cleanly_and_refunds_once(
        db_session, test_data, store, gemini, production, monkeypatch, caplog, capsys, case):
    message = _arrange(gemini, monkeypatch, case)
    start = await _credits(db_session, test_data)
    job_id = await _job(db_session, test_data)

    with caplog.at_level(logging.DEBUG):
        job, task = await _run(db_session, job_id)

    assert (job.status, job.error_message, job.progress, job.credits_consumed) == ("failed", message, 0, 0)
    assert await _credits(db_session, test_data) == start + 7
    task.retry.assert_not_called()  # no Celery retry, so no second refund
    store.assert_not_called()  # no mock (or any) image saved
    assert await _outputs(db_session, job_id) == 0
    if case in ("no key", "mock key"):
        gemini.client_cls.assert_not_called()
    logged = caplog.text + capsys.readouterr().out
    assert FAKE_KEY not in logged and PROVIDER_BODY not in logged and "AIza" not in logged


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["server error", "timeout", "text only", "image safety", "no key"])
async def test_gemini_failure_never_refunds_twice_across_retries(
        db_session, test_data, store, gemini, production, monkeypatch, case):
    """Attempt 1 fails on something retryable (re-queued for a retry, no refund); attempt 2 fails in
    Gemini: final, failed and refunded exactly once."""
    start = await _credits(db_session, test_data)
    job_id = await _job(db_session, test_data)
    with patch.object(storage_service, "save_file_bytes", side_effect=OSError("storage blip")):
        job, task = await _run(db_session, job_id, retries=0)
    assert (job.status, job.error_message) == ("queued", "storage blip") and task.retry.call_count == 1
    assert await _credits(db_session, test_data) == start

    _arrange(gemini, monkeypatch, case)
    job, task = await _run(db_session, job_id, retries=1)
    assert job.status == "failed"
    task.retry.assert_not_called()
    assert await _credits(db_session, test_data) == start + 7  # exactly one refund

    job, task = await _run(db_session, job_id, retries=2)  # a stray redelivery: still one refund
    assert await _credits(db_session, test_data) == start + 7


@pytest.mark.asyncio
async def test_unknown_model_fails_without_calling_gemini(
        db_session, test_data, store, gemini, production, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_GHOST_MODEL", "gemini-2.5-flash")  # text-only
    start = await _credits(db_session, test_data)
    job, task = await _run(db_session, await _job(db_session, test_data))
    assert (job.status, job.error_message) == ("failed", "Image generation is not configured.")
    assert await _credits(db_session, test_data) == start + 7
    gemini.generate_content.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("app_env", [None, "", "prod", "somewhere-new"])
async def test_production_rules_fail_closed_without_a_key(db_session, test_data, store, gemini, monkeypatch, app_env):
    """Production, or a missing/unknown APP_ENV outside tests, never gets the mock image."""
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    job, _ = await _run(db_session, await _job(db_session, test_data))
    assert (job.status, job.error_message) == ("failed", "Image generation is not configured.")
    store.assert_not_called()


# ========================== Outside production ==================

@pytest.mark.asyncio
@pytest.mark.parametrize("app_env,testing", [("development", False), ("local", False), (None, True)])
async def test_mock_image_still_works_outside_production_without_a_key(
        db_session, test_data, store, gemini, monkeypatch, app_env, testing):
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "TESTING", testing)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    job, _ = await _run(db_session, await _job(db_session, test_data))
    assert job.status == "completed"
    gemini.client_cls.assert_not_called()
    output = (await db_session.execute(select(GhostOutput).where(GhostOutput.job_id == job.id))).scalar_one()
    assert store.files[output.output_url[len("/uploads/"):]] == gemini_fakes.OUTPUT_PNG
    assert output.api_interaction_id == f"mock_{job.id}"


@pytest.mark.asyncio
async def test_with_a_key_outside_production_gemini_is_used_and_errors_are_not_masked(
        db_session, test_data, store, gemini, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    gemini.generate_content.side_effect = errors.ServerError(503, {"error": {"message": PROVIDER_BODY}})
    job, _ = await _run(db_session, await _job(db_session, test_data))
    assert (job.status, job.error_message) == ("failed", "The image service returned an error.")
    store.assert_not_called()


# ========================== Startup checklist ===================

def _fatal(name):
    return [i for i in check_config() if i.name == name and i.fatal]


@pytest.mark.parametrize("key", [None, "", "   ", "mock", SecretStr(""), SecretStr("mock")])
def test_missing_key_is_fatal(monkeypatch, key):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", key)
    assert _fatal("GEMINI_API_KEY")


@pytest.mark.parametrize("model", ["", "  ", "gemini-2.5-flash", "gemini-3-pro-image-preview", "imagen-4.0"])
def test_empty_or_unknown_model_is_fatal(monkeypatch, model):
    monkeypatch.setattr(settings, "GEMINI_GHOST_MODEL", model)
    assert _fatal("GEMINI_GHOST_MODEL")


@pytest.mark.parametrize("model", gemini_client.GEMINI_IMAGE_MODELS)
def test_key_and_image_model_pass(monkeypatch, model):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr(FAKE_KEY))
    monkeypatch.setattr(settings, "GEMINI_GHOST_MODEL", model)
    assert not _fatal("GEMINI_API_KEY") and not _fatal("GEMINI_GHOST_MODEL")


def test_production_refuses_to_boot_without_the_key_and_never_logs_it(monkeypatch, caplog):
    from app.config_production import ProductionConfigError, run_startup_checks
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    with caplog.at_level(logging.WARNING), pytest.raises(ProductionConfigError) as err:
        run_startup_checks()
    assert "GEMINI_API_KEY" in str(err.value)

    caplog.clear()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr(FAKE_KEY))
    with caplog.at_level(logging.DEBUG), pytest.raises(ProductionConfigError) as err:
        run_startup_checks()  # other repository defaults are still fatal here
    assert "GEMINI_API_KEY" not in str(err.value)
    assert FAKE_KEY not in caplog.text and FAKE_KEY not in str(err.value)
