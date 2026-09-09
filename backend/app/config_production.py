"""
Production Configuration Checklist & Validator
Ensures all required production settings are configured.
"""
import os
from typing import List, Tuple


REQUIRED_PRODUCTION_VARS = [
    ("DATABASE_URL", "PostgreSQL connection string"),
    ("REDIS_URL", "Redis connection string"),
    ("SECRET_KEY", "Application secret key"),
    ("STRIPE_SECRET_KEY", "Stripe live secret key"),
    ("STRIPE_WEBHOOK_SECRET", "Stripe webhook secret"),
    ("AWS_ACCESS_KEY_ID", "AWS access key for S3"),
    ("AWS_SECRET_ACCESS_KEY", "AWS secret key for S3"),
    ("AWS_S3_BUCKET", "S3 bucket name"),
    ("OPENAI_API_KEY", "OpenAI API key"),
    ("SENDGRID_API_KEY", "SendGrid API key"),
    ("INTERNAL_CALLBACK_SECRET", "Internal callback secret"),
]

MOCK_MODE_VARS = [
    ("STRIPE_MOCK_MODE", "false"),
    ("COMFYUI_MOCK_MODE", "false"),
    ("STORAGE_BACKEND", "s3"),
    ("APP_ENV", "production"),
]


def validate_production_config() -> Tuple[bool, List[str]]:
    """
    Validate all required production environment variables are set.
    Returns (is_valid, list_of_errors)
    """
    errors = []

    # Check required vars
    for var_name, description in REQUIRED_PRODUCTION_VARS:
        value = os.getenv(var_name, "")
        if not value or value.startswith("your-"):
            errors.append(f"MISSING: {var_name} ({description})")

    # Check mock modes are disabled
    for var_name, expected_value in MOCK_MODE_VARS:
        value = os.getenv(var_name, "")
        if value.lower() != expected_value.lower():
            errors.append(f"MOCK MODE ACTIVE: {var_name} should be '{expected_value}', got '{value}'")

    return len(errors) == 0, errors


def print_production_checklist():
    """Print production readiness checklist."""
    is_valid, errors = validate_production_config()

    print("\n" + "="*60)
    print("MODE LENS PRODUCTION READINESS CHECKLIST")
    print("="*60)

    if is_valid:
        print("✅ ALL PRODUCTION CONFIGS VALID - READY TO LAUNCH!")
    else:
        print(f"❌ {len(errors)} ISSUES FOUND:")
        for error in errors:
            print(f"  - {error}")

    print("="*60 + "\n")
    return is_valid


if __name__ == "__main__":
    print_production_checklist()
