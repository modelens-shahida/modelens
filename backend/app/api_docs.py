"""
Shared OpenAPI documentation helpers.

Everything in this module is documentation-only: response schemas used in
``responses=``, reusable query-parameter declarations that keep the exact
defaults/bounds each endpoint already had, and the app-level metadata
(description, tags, outgoing-webhook docs) consumed by ``app.main``.
"""
from typing import Any, Optional, Union

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


# ========================== Error Schemas =========================

class ErrorResponse(BaseModel):
    """
    Error body returned by the API.

    ``HTTPException`` errors return only ``detail``. The global database and
    unhandled-exception handlers also add ``error`` and ``request_id``.
    """
    detail: Union[str, dict, list] = Field(
        ...,
        description="Human-readable error message. A few endpoints return a structured object instead (e.g. insufficient-credit errors).",
        examples=["Brand not found"],
    )
    error: Optional[str] = Field(
        default=None,
        description="Machine-readable error class. Only set by the global exception handlers (e.g. `DatabaseIntegrityError`).",
        examples=["DatabaseIntegrityError"],
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID (mirrors the `X-Request-ID` response header). Only set by the global exception handlers.",
        examples=["3f2b8c1e-0000-4000-8000-000000000000"],
    )

    model_config = ConfigDict(json_schema_extra={"examples": [{"detail": "Brand not found"}]})


class ValidationErrorItem(BaseModel):
    loc: list[Union[str, int]] = Field(..., description="Location of the invalid field.", examples=[["query", "limit"]])
    msg: str = Field(..., description="Validation message.", examples=["Input should be less than or equal to 100"])
    type: str = Field(..., description="Validation error type.", examples=["less_than_equal"])


class ValidationErrorResponse(BaseModel):
    """FastAPI request-validation error body (HTTP 422)."""
    detail: list[ValidationErrorItem]


def _example(detail: Any) -> dict:
    return {"application/json": {"example": {"detail": detail}}}


_RATE_LIMIT_HEADERS = {
    "X-RateLimit-Limit": {"description": "Requests allowed in the current window.", "schema": {"type": "integer", "example": 60}},
    "X-RateLimit-Remaining": {"description": "Requests remaining in the current window (always 0 on a 429).", "schema": {"type": "integer", "example": 0}},
    "Retry-After": {"description": "Seconds to wait before retrying.", "schema": {"type": "integer", "example": 60}},
}

ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    400: {
        "model": ErrorResponse,
        "description": "Bad request: the input is well-formed but cannot be processed (business-rule violation).",
        "content": _example("Invalid request"),
    },
    401: {
        "model": ErrorResponse,
        "description": "Missing or invalid credentials (Bearer JWT, session cookie or `X-API-Key`).",
        "content": _example("Could not validate credentials"),
        "headers": {"WWW-Authenticate": {"description": "Authentication scheme, e.g. `Bearer`.", "schema": {"type": "string"}}},
    },
    402: {
        "model": ErrorResponse,
        "description": "Insufficient credits or monthly credit quota exhausted.",
        "content": _example("Insufficient credits. Need 5, have 2."),
    },
    403: {
        "model": ErrorResponse,
        "description": "Authenticated but not allowed: missing brand membership, insufficient role, or invalid internal secret.",
        "content": _example("You are not a member of this brand"),
    },
    404: {
        "model": ErrorResponse,
        "description": "The requested resource (or its parent brand) was not found.",
        "content": _example("Not found"),
    },
    409: {
        "model": ErrorResponse,
        "description": "Conflict with the current state of the resource (duplicate, or invalid state transition).",
        "content": _example("Resource already exists"),
    },
    422: {
        "model": ValidationErrorResponse,
        "description": "Request validation failed (path, query, header or body).",
    },
    429: {
        "model": ErrorResponse,
        "description": "Rate limit exceeded. Limits are per API key, user or IP and depend on the brand tier.",
        "content": _example("Too many requests. Please try again later."),
        "headers": _RATE_LIMIT_HEADERS,
    },
    500: {
        "model": ErrorResponse,
        "description": "The endpoint failed while calling a dependency (raised explicitly by this endpoint).",
        "content": _example("Proxy error: connection reset"),
    },
    502: {
        "model": ErrorResponse,
        "description": "An upstream service is unavailable or returned an error.",
        "content": _example("Templates service unavailable"),
    },
    504: {
        "model": ErrorResponse,
        "description": "An upstream service timed out.",
        "content": _example("Templates service request timed out"),
    },
}


def error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    """Build a ``responses=`` dict containing only the given error statuses."""
    return {code: ERROR_RESPONSES[code] for code in status_codes}


# ========================== Pagination Params =====================
# These keep each endpoint's existing default and bounds; only the docs differ.

def limit_query(default: int = 20, le: Optional[int] = 100, ge: Optional[int] = 1) -> Any:
    bounds = f" between {ge} and {le}" if ge is not None and le is not None else ""
    return Query(
        default,
        ge=ge,
        le=le,
        description=f"Maximum number of items to return{bounds}. Defaults to {default}.",
        examples=[default],
    )


def offset_query(default: int = 0, ge: Optional[int] = 0) -> Any:
    return Query(
        default,
        ge=ge,
        description="Number of items to skip before collecting results (zero-based). Use with `limit` to page through results.",
        examples=[40],
    )


def page_query(default: int = 1, ge: Optional[int] = 1) -> Any:
    return Query(
        default,
        ge=ge,
        description=f"1-based page number; items skipped = (page - 1) × limit. Defaults to {default}.",
        examples=[2],
    )


# ========================== App Metadata ==========================

API_TITLE = "ModeLens API"
API_VERSION = "1.0.0"

API_DESCRIPTION = """
## ModeLens — AI Fashion Content Production Platform

The ModeLens API powers brand workspaces, asset management, AI image/video
generation studios, credits & billing, and outbound webhooks.

### Authentication
Most endpoints require one of:

- **Bearer JWT** — `Authorization: Bearer <access_token>` from `POST /api/v1/auth/login`
  (the web dashboard may also send it as the `modelens_access_token` cookie).
- **API key** — `X-API-Key: <api_key>` for programmatic access. Create keys with
  `POST /api/v1/api-keys`; the plaintext key is shown only once.

Brand-scoped endpoints additionally enforce a brand role:
`owner` > `admin` > `editor` > `viewer`.

### Pagination
List endpoints use `limit` + `offset` (or `limit` + `page` on a few older
endpoints). Defaults and bounds are documented on each parameter.

### Errors
Errors return JSON with a `detail` field (see the `ErrorResponse` schema).
Request validation errors return HTTP 422 with a list of field errors.

### Rate limiting
Rate-limited endpoints return HTTP 429 with `X-RateLimit-Limit`,
`X-RateLimit-Remaining` and `Retry-After` headers. Limits scale with the
brand tier (free / growth / enterprise); API keys get 3× the per-minute limit.

### Webhooks
Outbound webhook deliveries are signed with HMAC-SHA256. See the
**Webhooks** tag and the `webhookDelivery` webhook for the
`X-Modelens-Signature-256` / `X-Modelens-Timestamp` headers and how to
verify them.
"""

API_CONTACT = {
    "name": "Modelens Support",
    "email": "support@modelens.ai",
}

API_LICENSE = {"name": "Proprietary / Modelens Enterprise"}

WEBHOOK_SIGNATURE_DOCS = """
Every delivery is a `POST` with a JSON body and these headers:

| Header | Example | Meaning |
|---|---|---|
| `X-Modelens-Timestamp` | `1767225600` | Unix time (seconds) when the delivery was signed. |
| `X-Modelens-Signature-256` | `sha256=5d41402abc4b2a76b9719d911017c592ab4f5c2e8b7d1e5f2a7c9e0b3d6f8a1c` | `sha256=` + hex HMAC-SHA256 of `"{timestamp}." + raw_body` using the subscription's signing secret. |

**Verifying a delivery**

1. Read the raw request body bytes — do not re-serialize the JSON.
2. Reject the request if `X-Modelens-Timestamp` is not an integer or is more
   than 300 seconds away from your current time (replay protection).
3. Compute `HMAC-SHA256(secret, f"{timestamp}.".encode() + raw_body)` and
   hex-encode it.
4. Compare `"sha256=" + hex_digest` with `X-Modelens-Signature-256` using a
   constant-time comparison.

```python
import hashlib, hmac, time

def verify(secret: str, raw_body: bytes, signature: str, timestamp: str) -> bool:
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 300:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())
```

The signing secret (`whsec_...`) is returned only when the subscription is
created or its secret is rotated. Respond with any 2xx status to acknowledge;
other statuses are retried.
"""

TAGS_METADATA = [
    {"name": "Auth", "description": "Registration, email/password and SSO login, token refresh, and the current user's profile."},
    {"name": "API Keys", "description": "Create, list and revoke API keys for programmatic access via the `X-API-Key` header."},
    {"name": "Brands", "description": "Brand workspaces: members and roles, invitations, SSO settings and audit timeline."},
    {"name": "Invitations", "description": "Accept brand invitations sent by email."},
    {"name": "Assets", "description": "Asset upload, listing, full-text and similarity search, tagging, soft-delete and restore."},
    {"name": "Presigned Upload", "description": "Direct-to-S3 presigned uploads and upload confirmation."},
    {"name": "Asset Registry", "description": "Asset versions, relationships, reference sets and touch-up jobs."},
    {"name": "Editorial Assets", "description": "Editorial metadata attached to assets."},
    {"name": "C2PA Provenance", "description": "Generate, retrieve and verify C2PA content-provenance manifests."},
    {"name": "Search", "description": "Unified full-text, vector and hybrid search with facets."},
    {"name": "Memory", "description": "Asset counts and tag-frequency analytics for brands and campaigns."},
    {"name": "Campaigns", "description": "Campaign management and linking assets, workflows and angle shots."},
    {"name": "Campaign Templates", "description": "Reusable campaign templates."},
    {"name": "Campaign Themes", "description": "Visual theme packages for campaign aesthetics."},
    {"name": "Campaign Studio", "description": "Multi-channel campaign generation jobs and ZIP export."},
    {"name": "Prompts", "description": "Reusable prompt template management."},
    {"name": "Jobs", "description": "AI generation job submission, workflow templates and status tracking."},
    {"name": "Generation API & WebSockets", "description": "Generation jobs with character/product/angle/environment inputs, plus presets for the Create Production UI."},
    {"name": "Realtime Generation Events", "description": "Generation step taxonomy and manual event emission for realtime progress."},
    {"name": "Phase 2 - Batch, QA & Export", "description": "Multi-angle batch generation, QA overrides, regeneration, collections and export."},
    {"name": "Pipeline Hardening", "description": "Job cancellation, lifecycle status, dead-letter queue and pipeline timeouts."},
    {"name": "Quality Tiers", "description": "Quality tier catalogue, legacy mode normalization and dispatch configuration."},
    {"name": "QA Scoring", "description": "Automated QA evaluations, human review, defect heatmaps and brand thresholds."},
    {"name": "Characters", "description": "Character reference sets, viewpoint coverage and LoRA training jobs."},
    {"name": "Brand Characters", "description": "Per-brand character templates, their training versions, embeddings and MLflow metrics."},
    {"name": "Character Registry", "description": "Character identity, body, skin, hair and runtime profiles (v1)."},
    {"name": "Character Registry V2", "description": "Character Library: versions (LOCKED versions are immutable), identity/body DNA, canonical assets, QA gates and promotion."},
    {"name": "Preservation & Credit Ledger", "description": "Garment, brand and identity preservation constraints, plus the immutable credit ledger."},
    {"name": "P3 Registry", "description": "Datasets, training experiments, model artifacts and rights records."},
    {"name": "Training Registry", "description": "Admin only. Training datasets, exports, runs, checkpoints, evaluations, layer adapters and runtime promotions for a Character Version (built on the P3 registry)."},
    {"name": "Styling Options", "description": "Customer-facing styling options (hair, makeup, expression, nails, jewelry, beauty direction) in PRODUCTION for a character's current locked version."},
    {"name": "Appearance Options", "description": "Admin only. Appearance option records, validation results, adapters and the IN_DEVELOPMENT → PRODUCTION → ARCHIVED lifecycle."},
    {"name": "Fluid Studio", "description": "Fluid Studio lighting presets and editorial generation jobs."},
    {"name": "ModeLens Fluid Studio", "description": "Interactive editorial sessions with non-destructive layers, and private brand models."},
    {"name": "Sketch Studio", "description": "Sketch-to-image and sketch-to-product generation jobs."},
    {"name": "Ghost Studio", "description": "Ghost mannequin generation jobs, including batch and volumetric jobs."},
    {"name": "Ghost Studio Batch", "description": "Multi-garment ghost batch jobs with credit estimation and reservation."},
    {"name": "Catalog Studio", "description": "Catalog batch jobs with per-SKU tracking."},
    {"name": "Catalog Export", "description": "Catalog ZIP and marketplace feed exports."},
    {"name": "Motion Video Studio", "description": "Motion presets and video generation jobs."},
    {"name": "FASHN Workflow Integration", "description": "FASHN virtual try-on jobs with credit estimation, reservation and callbacks."},
    {"name": "Rosanne Pipeline", "description": "Rosanne workflow configuration, scene prompts and generation jobs."},
    {"name": "Angle Shots", "description": "Angle shot preset management (only mounted in test environments; production traffic is proxied to the templates service)."},
    {"name": "Templates Proxy", "description": "Authenticated pass-through to the templates service for templates, generations, angle shots and shoots."},
    {"name": "Taxonomy", "description": "Taxonomy item management by type."},
    {"name": "Taxonomy Resolver", "description": "Resolve taxonomy selections into execution parameters and ComfyUI node mappings."},
    {"name": "Credits", "description": "User credit balance, transaction history, mock purchases and admin adjustments."},
    {"name": "Generation Credits Sync", "description": "Brand credit rates, estimates, sufficiency checks and billing summary."},
    {"name": "Low Credit Alerts", "description": "Low-credit alert status, thresholds and history."},
    {"name": "Billing", "description": "Stripe Checkout and Billing Portal sessions."},
    {"name": "Stripe Webhooks", "description": "Inbound Stripe events (verified with the `Stripe-Signature` header)."},
    {
        "name": "Webhooks",
        "description": "Brand webhook subscriptions, signing-secret rotation, delivery logs, retries and metrics.\n\n"
        "**Delivery signing**\n" + WEBHOOK_SIGNATURE_DOCS,
    },
    {"name": "Internal Callbacks", "description": "Service-to-service callbacks authenticated with the `X-Internal-Secret` header. Not for public use."},
    {"name": "Notifications", "description": "In-app notifications and notification preferences."},
    {"name": "Fix Requests", "description": "Fix/adjustment requests on assets and their review workflow."},
    {"name": "Audit Logs", "description": "Platform audit log search and event types."},
    {"name": "Analytics", "description": "Brand analytics export (JSON or CSV)."},
    {"name": "Admin Stats", "description": "Platform-wide statistics for admins."},
    {"name": "Admin Settings", "description": "Dynamic runtime settings for admins."},
    {"name": "Health", "description": "Service health checks."},
    {"name": "System", "description": "Root, liveness and Prometheus metrics endpoints."},
]


# ========================== Outgoing Webhooks =====================

class WebhookEventPayload(BaseModel):
    """
    Body of an outgoing webhook delivery. Subscriptions with
    ``payload_format="summary"`` receive exactly these fields; ``verbose``
    subscriptions receive the full event payload, which may include more.
    """
    type: str = Field(..., description="Event type.", examples=["job.completed"])
    brand_id: Optional[int] = Field(default=None, description="Brand the event belongs to.", examples=[42])
    job_id: Optional[Union[int, str]] = Field(default=None, description="Related job, when applicable.", examples=[1234])
    status: Optional[str] = Field(default=None, description="Resulting status, when applicable.", examples=["completed"])
    timestamp: Optional[str] = Field(default=None, description="When the event occurred (ISO 8601).", examples=["2026-01-01T00:00:00Z"])

    model_config = ConfigDict(extra="allow")


def add_webhook_docs(webhooks: Any) -> None:
    """Document outgoing webhook deliveries in the OpenAPI ``webhooks`` section."""
    from fastapi import Header

    @webhooks.post(
        "webhookDelivery",
        tags=["Webhooks"],
        summary="Webhook delivery (sent by ModeLens)",
        description=(
            "ModeLens sends this request to each active subscription URL when a subscribed "
            "event occurs (`job.completed`, `job.failed`, `asset.processed`, "
            "`character.training.completed`, `character.training.failed`).\n"
            + WEBHOOK_SIGNATURE_DOCS
        ),
        response_description="Any 2xx status acknowledges the delivery.",
        operation_id="webhook_delivery",
    )
    def webhook_delivery(
        payload: WebhookEventPayload,
        x_modelens_signature_256: str = Header(
            ...,
            alias="X-Modelens-Signature-256",
            description='`sha256=` followed by the hex HMAC-SHA256 of `"{X-Modelens-Timestamp}." + raw_body`, keyed with the subscription\'s signing secret.',
            examples=["sha256=5d41402abc4b2a76b9719d911017c592ab4f5c2e8b7d1e5f2a7c9e0b3d6f8a1c"],
        ),
        x_modelens_timestamp: str = Header(
            ...,
            alias="X-Modelens-Timestamp",
            description="Unix time in seconds when the delivery was signed. Reject deliveries more than 300 seconds old or in the future.",
            examples=["1767225600"],
        ),
    ) -> None:
        """Documentation only; ModeLens does not serve this route."""
