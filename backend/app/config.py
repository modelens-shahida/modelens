import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

# Resolve the absolute path of the .env file in the same directory as config.py
ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

class Settings(BaseSettings):
    # Database
    POSTGRES_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/modelens"
    )

    # Redis / Celery
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Security
    SECRET_KEY: str = Field(default="generate-a-secure-secret-key-for-production-here")
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
    STRIPE_API_KEY: str = Field(default="sk_test_mock_key")
    STRIPE_WEBHOOK_SECRET: str = Field(default="whsec_mock_secret")
    STRIPE_MOCK_MODE: bool = Field(default=True)

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
    ORCHESTRATOR_RATE_LIMIT: int = Field(default=10)

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

    # Email Provider (for low-credit alerts)
    EMAIL_PROVIDER: str = Field(default="sendgrid")  # 'sendgrid' or 'ses'
    SENDGRID_API_KEY: Optional[str] = Field(default=None)
    SES_REGION: str = Field(default="us-east-1")
    FROM_EMAIL: str = Field(default="no-reply@modelens.com")

    # Load configuration settings from the resolved .env file path
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
