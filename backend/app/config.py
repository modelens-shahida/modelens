import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import Optional

# Resolve the absolute path of the .env file in the same directory as config.py
ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# Repository defaults that must never be used in production.
DEFAULT_INTERNAL_CALLBACK_SECRET = "modelens-internal-secret"
DEFAULT_SECRET_KEY = "generate-a-secure-secret-key-for-production-here"
DEFAULT_STRIPE_SECRET_KEY = "sk_test_mock_key"
DEFAULT_STRIPE_WEBHOOK_SECRET = "whsec_mock_secret"
DEFAULT_GEMINI_GHOST_MODEL = "gemini-3-pro-image"

class Settings(BaseSettings):
    TEMPLATES_BACKEND_URL: str = "http://localhost:4000"
    INTERNAL_CALLBACK_SECRET: str = DEFAULT_INTERNAL_CALLBACK_SECRET
    # Database
    POSTGRES_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/modelens"
    )

    # Redis / Celery
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Security
    SECRET_KEY: str = Field(default=DEFAULT_SECRET_KEY)
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # CORS Configuration
    ALLOWED_ORIGINS: list[str] = Field(default=["*"])

    # Storage Configurations
    STORAGE_BACKEND: str = Field(default="local")  # Can be 'local' or 's3'

    # AWS S3 (Optional if STORAGE_BACKEND='local', required for 's3')
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None)
    AWS_STORAGE_BUCKET_NAME: Optional[str] = Field(default=None)
    AWS_S3_REGION_NAME: Optional[str] = Field(default=None)

    # MLflow Tracking
    MLFLOW_URI: str = Field(default="http://localhost:5000")

    # Stripe Billing
    STRIPE_SECRET_KEY: str = Field(default=DEFAULT_STRIPE_SECRET_KEY)
    STRIPE_WEBHOOK_SECRET: str = Field(default=DEFAULT_STRIPE_WEBHOOK_SECRET)
    STRIPE_MOCK_MODE: bool = Field(default=True)

    # Ghost Studio batches (POST /api/v1/ghost/batch). Off: creation answers 503 before
    # reserving credits, because no worker processes these batches yet. Turn on only
    # once a batch worker exists; single ghost jobs are not affected either way.
    GHOST_BATCH_ENABLED: bool = Field(default=False)

    # Sketch Studio job creation (POST /api/v1/sketch-jobs, its /retry, POST /api/v1/sketch/jobs).
    # Off: in production those answer 503 before anything is charged, written or queued, and
    # the worker fails (and refunds) queued Sketch jobs without calling Gemini, until the
    # Sketch multimodal pipeline lands. Outside production Sketch works either way.
    SKETCH_JOBS_ENABLED: bool = Field(default=False)

    # Database Connection Pool
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=1800)

    # Cache TTL
    CACHE_TTL_BRAND_MEMORY: int = Field(default=300)
    CACHE_TTL_ADMIN_STATS: int = Field(default=600)

    # Database Connection Pool
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=1800)

    # Cache TTL
    CACHE_TTL_BRAND_MEMORY: int = Field(default=300)
    CACHE_TTL_ADMIN_STATS: int = Field(default=600)

    # Log Retention
    WEBHOOK_LOG_RETENTION_DAYS: int = Field(default=30)
    WEBHOOK_LOG_PRUNE_BATCH_SIZE: int = Field(default=1000)

    # Orchestrator throttling settings
    # Default per-brand limit for POST /api/v1/productions/dispatch, in dispatches
    # per minute. Admins override it at runtime (POST /api/v1/admin/settings,
    # stored in Redis as settings:orchestrator_rate_limit).
    ORCHESTRATOR_RATE_LIMIT: int = Field(default=10, ge=1)
    # Per-user limit for POST /api/v1/productions/dispatch, across all brands.
    DISPATCH_RATE_LIMIT_USER_REQUESTS: int = Field(default=5, ge=1)
    DISPATCH_RATE_LIMIT_USER_WINDOW_SECONDS: int = Field(default=60, ge=1)

    # Stripe Price IDs
    STRIPE_PRICE_LITE_MONTHLY: str = Field(default="price_lite_monthly_mock")
    STRIPE_PRICE_LITE_YEARLY: str = Field(default="price_lite_yearly_mock")
    STRIPE_PRICE_PLUS_MONTHLY: str = Field(default="price_plus_monthly_mock")
    STRIPE_PRICE_PLUS_YEARLY: str = Field(default="price_plus_yearly_mock")
    STRIPE_PRICE_PRO_MONTHLY: str = Field(default="price_pro_monthly_mock")
    STRIPE_PRICE_PRO_YEARLY: str = Field(default="price_pro_yearly_mock")
    STRIPE_SUCCESS_URL: str = Field(default="https://modelens-xi.vercel.app/billing/success")
    STRIPE_CANCEL_URL: str = Field(default="https://modelens-xi.vercel.app/billing/cancel")

    # ComfyUI
    COMFYUI_URL: str = Field(default="http://localhost:8188")
    COMFYUI_MOCK_MODE: bool = Field(default=True)

    # OpenAI
    OPENAI_API_KEY: str = Field(default="sk.mock")

    # Gemini (google-genai). The key is a secret: SecretStr keeps it out of reprs and logs.
    # Ghost jobs need an image-output model (app/services/gemini_client.GEMINI_IMAGE_MODELS).
    GEMINI_API_KEY: Optional[SecretStr] = Field(default=None)
    GEMINI_GHOST_MODEL: str = Field(default=DEFAULT_GEMINI_GHOST_MODEL)

    # Email Provider (for low-credit alerts)
    EMAIL_PROVIDER: str = Field(default="sendgrid")  # 'sendgrid' or 'ses'
    SENDGRID_API_KEY: Optional[str] = Field(default=None)
    SES_REGION: str = Field(default="us-east-1")
    FROM_EMAIL: str = Field(default="no-reply@modelens.com")

    # Environment (development | local | staging | production)
    APP_ENV: Optional[str] = Field(default=None)
    TESTING: bool = Field(default=False)

    # SSO identity verification
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None)
    GITHUB_CLIENT_ID: Optional[str] = Field(default=None)
    GITHUB_CLIENT_SECRET: Optional[str] = Field(default=None)
    # Accept "mock:<email>" SSO credentials. Only honored with TESTING=true or
    # APP_ENV=development/local; always refused when APP_ENV is production.
    SSO_MOCK_MODE: bool = Field(default=False)

    # SSO login rate limits (POST /api/v1/auth/sso-login)
    # Per client IP, checked before the provider credential is verified.
    SSO_RATE_LIMIT_REQUESTS: int = Field(default=10, ge=1)
    SSO_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)
    # Per account (provider-verified email), checked before a session is issued.
    SSO_RATE_LIMIT_ACCOUNT_REQUESTS: int = Field(default=5, ge=1)
    SSO_RATE_LIMIT_ACCOUNT_WINDOW_SECONDS: int = Field(default=300, ge=1)
    # Comma-separated proxy IPs/CIDRs whose X-Forwarded-For is trusted. Empty:
    # X-Forwarded-For is ignored and the socket peer is the client IP.
    SSO_RATE_LIMIT_TRUSTED_PROXIES: str = Field(default="")

    # Load configuration settings from the resolved .env file path
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()


# ========================== Environment ==========================

PRODUCTION_ENVS = {"production", "prod"}
# APP_ENV values that are known not to be production.
NON_PRODUCTION_ENVS = {"development", "dev", "local", "staging", "test", "testing"}


def app_env() -> str:
    return (settings.APP_ENV or "").strip().lower()


def is_production() -> bool:
    """APP_ENV says production."""
    return app_env() in PRODUCTION_ENVS


def production_rules_apply() -> bool:
    """Fail closed: production, and a missing or unknown APP_ENV outside tests, get production behaviour.

    Only a known non-production APP_ENV (or TESTING=true, unless APP_ENV is
    production) turns on development conveniences such as mock purchases,
    unsigned Stripe webhooks or the default internal callback secret.
    """
    if is_production():
        return True
    return not (app_env() in NON_PRODUCTION_ENVS or settings.TESTING)

