"""Generate one Catalog item with FASHN (app/services/fashn_client.py).

1. Inputs: the item's product image and, for Try-On Max, the job's model image. Each path is
   checked again with ``input_paths.path_problem`` (our own storage, not another brand's) and
   handed to FASHN as a short-lived presigned S3 GET URL (``FASHN_INPUT_URL_TTL_SECONDS``),
   never a public or permanent URL. Local storage has no signed URLs: outside production the
   image is sent inline as a data URI; in production that is refused (the startup check also
   requires S3 while Catalog is on).
2. Model: ``engine_mode`` ``tryon_max`` -> ``tryon-max`` (product + model image), anything else
   -> ``product-to-model`` (product image). Resolution 1K/2K/4K -> 1k/2k/4k, generation mode
   studio_quality -> quality, fast_draft -> fast, one PNG image.
3. Output: FASHN's first output is downloaded (https, size-limited), checked to be a real image
   and stored in our storage under ``brands/<brand>/catalog/<job>/``. Only that storage path is
   kept and returned; the FASHN URL is never stored on the item or shown to the customer.

Any failure raises ``CatalogGenerationError`` with a customer-safe message; the caller marks the
item failed and refunds it once (job_refunds). Nothing here logs the key or a signed URL.
"""
import base64
import io
import uuid
from typing import Optional

from PIL import Image

from app.config import catalog_fashn_key, production_rules_apply, settings
from app.services.catalog_availability import CATALOG_GENERATION_FAILED
from app.services.fashn_client import FashnClient, FashnError
from app.services.input_paths import path_problem
from app.services.job_images import storage_key
from app.services.storage import storage_service

TRYON_MAX = "tryon_max"
RESOLUTIONS = {"1K": "1k", "2K": "2k", "4K": "4k"}
GENERATION_MODES = {"studio_quality": "quality", "fast_draft": "fast"}
PRODUCT_TO_MODEL_ASPECT_RATIOS = ("1:1", "3:4", "4:3", "9:16", "16:9", "2:3", "3:2", "4:5", "5:4")
MAX_INPUT_BYTES = 30 * 1024 * 1024  # FASHN's input limit
MAX_OUTPUT_BYTES = 64 * 1024 * 1024  # a 4k PNG stays well below this
MODEL_IMAGE_LABEL = "Model image"
PRODUCT_IMAGE_LABEL = "Product image"


class CatalogGenerationError(RuntimeError):
    """FASHN produced no stored image for a catalog item. ``str()`` is safe to show and store;
    ``code`` (e.g. ``http_401``, ``timeout``) is for logs."""

    def __init__(self, message: str = CATALOG_GENERATION_FAILED, code: str = "error"):
        super().__init__(message)
        self.code = code


def model_name(engine_mode: Optional[str]) -> str:
    return "tryon-max" if engine_mode == TRYON_MAX else "product-to-model"


def model_image_path(job) -> Optional[str]:
    return (job.meta or {}).get("model_image_path")


async def _input_image(db, job, path: Optional[str], label: str) -> str:
    """A URL (or, outside production on local storage, a data URI) FASHN may read ``path`` from."""
    problem = await path_problem(db, path, job.brand_id)
    if problem:
        raise CatalogGenerationError(f"{label} {problem}.", code="bad_input_path")
    key = storage_key(path)
    try:
        url = storage_service.presigned_get_url(key, settings.FASHN_INPUT_URL_TTL_SECONDS)
    except Exception:
        raise CatalogGenerationError(code="presign_failed")
    if url:
        return url
    if production_rules_apply():  # no signed URL without S3, and never a public one
        raise CatalogGenerationError(code="no_signed_urls")
    try:
        data = storage_service.read_file_bytes(key)
    except Exception:
        raise CatalogGenerationError(f"{label} could not be read.", code="input_unreadable")
    if len(data) > MAX_INPUT_BYTES:
        raise CatalogGenerationError(f"{label} is larger than 30 MB.", code="input_too_large")
    kind = (Image.open(io.BytesIO(data)).format or "png").lower()
    return f"data:image/{kind};base64,{base64.b64encode(data).decode()}"


async def build_inputs(db, job, item) -> tuple[str, dict]:
    """(FASHN model name, inputs) for the item. Raises CatalogGenerationError."""
    name = model_name(job.engine_mode)
    inputs = {
        "product_image": await _input_image(db, job, item.product_image_path, PRODUCT_IMAGE_LABEL),
        "prompt": f"professional fashion catalog, {job.pose}, {job.background}",
        "resolution": RESOLUTIONS.get((job.resolution or "").upper(), "2k"),
        "generation_mode": GENERATION_MODES.get(job.generation_mode, "balanced"),
        "num_images": 1,
        "output_format": "png",
    }
    if name == "tryon-max":
        model_path = model_image_path(job)
        if not model_path:
            raise CatalogGenerationError("Try-On Max needs a model image.", code="no_model_image")
        inputs["model_image"] = await _input_image(db, job, model_path, MODEL_IMAGE_LABEL)
    elif job.aspect_ratio in PRODUCT_TO_MODEL_ASPECT_RATIOS:
        inputs["aspect_ratio"] = job.aspect_ratio
    return name, inputs


OUTPUT_EXTENSIONS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


def _checked_image(data: bytes) -> str:
    """The extension of a real, decodable PNG/JPEG/WebP image; else CatalogGenerationError."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.load()
    except Exception:
        fmt = None
    if fmt not in OUTPUT_EXTENSIONS:
        raise CatalogGenerationError(code="invalid_output")
    return OUTPUT_EXTENSIONS[fmt]


async def generate_item(db, job, item) -> tuple[str, str]:
    """Generate the item with FASHN and store the image. Returns (our storage path, prediction id).

    Requires a configured key (the caller decides what happens without one)."""
    key = catalog_fashn_key()
    if not key:
        raise CatalogGenerationError(code="no_key")
    name, inputs = await build_inputs(db, job, item)
    client = FashnClient(key)
    try:
        prediction_id, outputs = await client.generate(name, inputs)
        data = await client.download(outputs[0], MAX_OUTPUT_BYTES)
    except FashnError as exc:
        raise CatalogGenerationError(code=exc.code)
    extension = _checked_image(data)
    filename = f"brands/{job.brand_id}/catalog/{job.id}/item-{item.id}-{uuid.uuid4().hex}.{extension}"
    try:
        stored = storage_service.save_file_bytes(filename, data, "image")
    except Exception:
        raise CatalogGenerationError(code="storage_failed")
    return stored, prediction_id

