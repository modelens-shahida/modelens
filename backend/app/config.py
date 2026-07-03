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
