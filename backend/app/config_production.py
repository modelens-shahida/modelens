"""
Production configuration checklist, run at API startup (app/main.py lifespan).

With APP_ENV=production (or prod), a FATAL issue stops the API from booting
and the log lists every problem by variable name. Values are never logged.
WARNING issues are logged but do not stop the boot: they cover settings
Railway may legitimately leave unset. Outside production every issue is
only a warning, so the test suite and local development start as before.

Run ``python -m app.config_production`` to print the checklist.
"""
import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.config import (
    DEFAULT_INTERNAL_CALLBACK_SECRET, DEFAULT_SECRET_KEY, DEFAULT_STRIPE_SECRET_KEY, DEFAULT_STRIPE_WEBHOOK_SECRET,
    app_env, catalog_fashn_key, is_production, production_rules_apply, settings,
)
from app.services.gemini_client import GEMINI_IMAGE_MODELS, gemini_api_key
from app.services.rosanne_availability import rosanne_pipeline_configured

logger = logging.getLogger(__name__)

PLACEHOLDER_PREFIXES = ("your-", "change-me", "changeme")
MIN_SECRET_KEY_LENGTH = 32


class ProductionConfigError(RuntimeError):
    """Raised at startup when APP_ENV=production and a fatal check fails."""


@dataclass(frozen=True)
class Issue:
    name: str
    problem: str
    fatal: bool

    def __str__(self) -> str:
        return f"{self.name}: {self.problem}"


def _unset_or_default(value: Optional[str], *defaults: str) -> bool:
    value = (value or "").strip()
    return not value or value in defaults or value.lower().startswith(PLACEHOLDER_PREFIXES)


def _setting(name: str) -> Optional[str]:
    """A setting from app.config, or the raw environment for names it does not define."""
    value = getattr(settings, name, None)
    return os.getenv(name) if value is None else str(value)


def _image_model(value: Optional[str]) -> bool:
    return (value or "").strip() in GEMINI_IMAGE_MODELS


def check_config() -> List[Issue]:
    """Every production problem in the current configuration."""
    issues: List[Issue] = []

    def add(name: str, problem: str, fatal: bool) -> None:
        issues.append(Issue(name, problem, fatal))

    # --- Fatal: credits, payments or authentication are open with these ---
    if settings.STRIPE_MOCK_MODE:
        add("STRIPE_MOCK_MODE", "is on; must be false (mock checkout, unsigned webhooks)", True)
    if _unset_or_default(settings.STRIPE_SECRET_KEY, DEFAULT_STRIPE_SECRET_KEY):
        add("STRIPE_SECRET_KEY", "is unset or the repository default", True)
    if _unset_or_default(settings.STRIPE_WEBHOOK_SECRET, DEFAULT_STRIPE_WEBHOOK_SECRET):
        add("STRIPE_WEBHOOK_SECRET", "is unset or the repository default", True)
    if _unset_or_default(settings.INTERNAL_CALLBACK_SECRET, DEFAULT_INTERNAL_CALLBACK_SECRET):
        add("INTERNAL_CALLBACK_SECRET", "is unset or the repository default", True)
    if _unset_or_default(settings.SECRET_KEY, DEFAULT_SECRET_KEY):
        add("SECRET_KEY", "is unset or the repository default (anyone could sign login tokens)", True)
    if settings.TESTING:
        add("TESTING", "is true; test-only routes and shortcuts would be enabled", True)
    if _unset_or_default(gemini_api_key()):  # None when unset, blank or "mock"
        add("GEMINI_API_KEY", "is unset or mock; ghost jobs would fail and be refunded", True)
    for name in ("GEMINI_GHOST_MODEL", "GEMINI_SKETCH_MODEL", "GEMINI_SKETCH_FAST_MODEL"):
        if not _image_model(getattr(settings, name)):
            add(name, f"is empty or not an image-output model (one of: {', '.join(GEMINI_IMAGE_MODELS)})", True)

    # --- Warnings: weak or missing, but Railway may not set these ---
    if not _unset_or_default(settings.SECRET_KEY, DEFAULT_SECRET_KEY) \
            and len(settings.SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
        add("SECRET_KEY", f"is shorter than {MIN_SECRET_KEY_LENGTH} characters", False)
    if (settings.STRIPE_SECRET_KEY or "").startswith("sk_test_") \
            and settings.STRIPE_SECRET_KEY != DEFAULT_STRIPE_SECRET_KEY:
        add("STRIPE_SECRET_KEY", "is a Stripe test-mode key", False)
    if settings.SSO_MOCK_MODE:
        add("SSO_MOCK_MODE", "is on (mock SSO credentials are still refused in production)", False)
    if settings.GHOST_BATCH_ENABLED:
        add("GHOST_BATCH_ENABLED", "is on; no worker processes ghost batches, so their credits stay reserved", False)
    if settings.SKETCH_JOBS_ENABLED and (_unset_or_default(gemini_api_key())
                                         or not _image_model(settings.GEMINI_SKETCH_MODEL)
                                         or not _image_model(settings.GEMINI_SKETCH_FAST_MODEL)):
        add("SKETCH_JOBS_ENABLED", "is on, but GEMINI_API_KEY, GEMINI_SKETCH_MODEL or GEMINI_SKETCH_FAST_MODEL "
            "is not usable; "
            "Sketch jobs would fail and be refunded", False)
    if settings.CATALOG_JOBS_ENABLED and not catalog_fashn_key():
        add("CATALOG_JOBS_ENABLED", "is on, but the Catalog worker has no FASHN key (FASHN_API_KEY is not a "
            "declared setting); Catalog items would fail and be refunded", False)
    if settings.ROSANNE_JOBS_ENABLED and not rosanne_pipeline_configured():
        add("ROSANNE_JOBS_ENABLED", "is on, but there is no real Rosanne ComfyUI pipeline (the dispatcher only "
            "mocks); Rosanne jobs would fail and be refunded", False)
    if settings.COMFYUI_MOCK_MODE:
        add("COMFYUI_MOCK_MODE", "is on; ComfyUI generation is mocked", False)
    if (settings.STORAGE_BACKEND or "").lower() != "s3":
        add("STORAGE_BACKEND", "is not s3; uploads are stored on the local disk", False)
    if "localhost" in (settings.POSTGRES_URL or ""):
        add("POSTGRES_URL", "points at localhost (the default)", False)
    if "localhost" in (settings.REDIS_URL or ""):
        add("REDIS_URL", "points at localhost (the default)", False)
    if _unset_or_default(settings.OPENAI_API_KEY, "sk.mock"):
        add("OPENAI_API_KEY", "is unset or the mock default", False)
    if "*" in settings.ALLOWED_ORIGINS:
        add("ALLOWED_ORIGINS", "allows every origin (*)", False)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET", "SENDGRID_API_KEY", "CDN_BASE_URL"):
        if _unset_or_default(_setting(name)):
            add(name, "is unset", False)

    return issues


def run_startup_checks() -> None:
    """Refuse to boot with a fatal issue in production; otherwise log what is wrong."""
    issues = check_config()
    fatal = [i for i in issues if i.fatal]
    warnings = [i for i in issues if not i.fatal]

    if is_production():
        for issue in warnings:
            logger.warning("Production config warning: %s", issue)
        if fatal:
            listing = "\n".join(f"  - {issue}" for issue in fatal)
            logger.critical("Refusing to start: APP_ENV=production but %d critical setting(s) are wrong:\n%s",
                            len(fatal), listing)
            raise ProductionConfigError(
                f"APP_ENV=production but critical settings are wrong: {', '.join(i.name for i in fatal)}")
        return

    env = app_env() or "unset"
    if issues:
        logger.warning("Production checklist not enforced (APP_ENV=%s); would fail in production: %s",
                       env, ", ".join(sorted({i.name for i in fatal})) or "nothing")
    if production_rules_apply():
        logger.warning(
            "APP_ENV is %s: mock purchases, unsigned Stripe webhooks and the default internal callback secret "
            "are refused as in production. Set APP_ENV=development for local development.", env)


def validate_production_config() -> Tuple[bool, List[str]]:
    """(no fatal issues, every issue as text)."""
    issues = check_config()
    return not any(i.fatal for i in issues), [f"{'FATAL' if i.fatal else 'WARNING'}: {i}" for i in issues]


def print_production_checklist() -> bool:
    """Print production readiness checklist."""
    is_valid, issues = validate_production_config()

    print("\n" + "=" * 60)
    print("MODELENS PRODUCTION READINESS CHECKLIST")
    print("=" * 60)
    if not issues:
        print("ALL PRODUCTION CONFIGS VALID - READY TO LAUNCH!")
    else:
        print(f"{len(issues)} ISSUES FOUND ({'none' if is_valid else 'some'} fatal):")
        for issue in issues:
            print(f"  - {issue}")
    print("=" * 60 + "\n")
    return is_valid


if __name__ == "__main__":
    print_production_checklist()
