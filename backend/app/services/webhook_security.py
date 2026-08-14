import hmac
import hashlib
import time
from typing import Optional


SIGNATURE_HEADER = "X-Modelens-Signature"
TIMESTAMP_HEADER = "X-Modelens-Timestamp"
REPLAY_WINDOW_SECONDS = 300  # 5 minutes


def generate_signature(secret: str, payload: str, timestamp: Optional[int] = None) -> tuple[str, int]:
    """
    Generate HMAC-SHA256 signature for webhook payload.
    Returns (signature, timestamp).
    """
    if timestamp is None:
        timestamp = int(time.time())

    message = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={signature}", timestamp


def verify_signature(
    secret: str,
    payload: str,
    signature_header: str,
    timestamp_header: str,
    enforce_replay_protection: bool = True,
) -> tuple[bool, str]:
    """
    Verify HMAC-SHA256 signature of incoming webhook payload.
    Returns (is_valid, reason).
    """
    # Validate timestamp
    try:
        timestamp = int(timestamp_header)
    except (ValueError, TypeError):
        return False, "Invalid timestamp header"

    # Replay attack protection
    if enforce_replay_protection:
        current_time = int(time.time())
        if abs(current_time - timestamp) > REPLAY_WINDOW_SECONDS:
            return False, f"Timestamp expired. Must be within {REPLAY_WINDOW_SECONDS} seconds"

    # Validate signature format
    if not signature_header.startswith("sha256="):
        return False, "Invalid signature format. Expected sha256=<hash>"

    # Generate expected signature
    expected_signature, _ = generate_signature(secret, payload, timestamp)

    # Constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(
        signature_header.encode("utf-8"),
        expected_signature.encode("utf-8"),
    )

    if not is_valid:
        return False, "Signature mismatch"

    return True, "Valid"


def build_webhook_headers(secret: str, payload: str) -> dict:
    """
    Build the full set of security headers for outgoing webhook delivery.
    """
    signature, timestamp = generate_signature(secret, payload)
    return {
        SIGNATURE_HEADER: signature,
        TIMESTAMP_HEADER: str(timestamp),
        "Content-Type": "application/json",
        "User-Agent": "ModelLens-Webhook/1.0",
    }
