"""Input images of a ghost or sketch job, prepared for Gemini.

Each image is read from our own storage (local or S3), decoded to prove it is
an image, and sent as an inline part: JPEG, PNG and WebP as they are,
everything else (HEIC/HEIF, which Gemini lists but rejects in practice, GIF,
...) converted.

Size limit: Gemini inline requests must stay under 20 MB in total, and inline
bytes are base64-encoded (x4/3). Images are kept to MAX_DIMENSION px on the
long side and MAX_IMAGE_BYTES each, and all of a job's images together to
MAX_REQUEST_IMAGE_BYTES (~18.7 MB once encoded, leaving room for the prompt).
Larger images are downscaled (aspect ratio kept) and re-encoded.

Problems with the input raise InputImageError, whose message is safe to show
the customer: the job fails and is refunded once, without a retry, since
retrying cannot fix the image.
"""
import io
from typing import Iterable, List, Optional

from PIL import Image, ImageOps

from app.config import settings
from app.services.storage import storage_service

try:  # HEIC/HEIF decoding (iPhone photos)
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # pragma: no cover - listed in requirements
    pass

MAX_DIMENSION = 3072
MAX_IMAGE_BYTES = 7 * 1024 * 1024
MAX_REQUEST_IMAGE_BYTES = 14 * 1024 * 1024
JPEG_QUALITY = 90
# Formats sent unchanged when within the limits; the mime type comes from the decoded image, not the filename.
PASSTHROUGH_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
_EXIF_ORIENTATION = 0x0112


class InputImageError(Exception):
    """A job input image that cannot be used. Retrying will not help."""


def storage_key(image_path: str) -> str:
    """The storage key of one of our own storage paths (`/uploads/<key>` or `s3://<bucket>/<key>`).
    Anything else (external URLs, other buckets, traversal) is rejected, never fetched."""
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    key = None
    if image_path.startswith("/uploads/"):
        key = image_path[len("/uploads/"):]
    elif bucket and image_path.startswith(f"s3://{bucket}/"):
        key = image_path[len(f"s3://{bucket}/"):]
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise InputImageError("is not stored in ModeLens storage")
    return key


def _encode(img: Image.Image, max_bytes: int) -> tuple[bytes, str]:
    """Re-encode, downscaling by 3/4 until it fits: PNG if it has transparency, else JPEG."""
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
    for _ in range(12):
        out = io.BytesIO()
        if has_alpha:
            img.save(out, format="PNG", optimize=True)
        else:
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        if out.tell() <= max_bytes:
            return out.getvalue(), "image/png" if has_alpha else "image/jpeg"
        img = img.resize((max(1, img.width * 3 // 4), max(1, img.height * 3 // 4)), Image.LANCZOS)
    raise InputImageError("is too large to send")


def prepare_image(data: bytes, max_bytes: int = MAX_IMAGE_BYTES) -> tuple[bytes, str]:
    """(bytes, mime type) ready for an inline Gemini part."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # unidentified, truncated, decompression bomb, ...
        raise InputImageError("could not be decoded as an image")
    mime = PASSTHROUGH_MIME.get(img.format)
    upright = img.getexif().get(_EXIF_ORIENTATION, 1) == 1
    if mime and upright and max(img.size) <= MAX_DIMENSION and len(data) <= max_bytes:
        return data, mime
    try:
        return _encode(ImageOps.exif_transpose(img), max_bytes)
    except InputImageError:
        raise
    except Exception:
        raise InputImageError("could not be converted")


def is_image(data: bytes) -> bool:
    """The bytes decode as an image the way prepare_image decodes them (any format Pillow reads,
    HEIC included), so an upload accepted here is one the worker can use."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
        return True
    except Exception:  # unidentified, truncated, decompression bomb, ...
        return False


def load_images(paths: List[str], label: str, read=None) -> List[dict]:
    """Inline parts ({"mime_type", "data"}) for ``paths``, in the given order. Errors name the
    image as "<label> <n>". Raises InputImageError if one cannot be loaded or decoded."""
    read = read or storage_service.read_file_bytes
    budget = min(MAX_IMAGE_BYTES, MAX_REQUEST_IMAGE_BYTES // max(1, len(paths)))
    parts = []
    for number, path in enumerate(paths, 1):
        try:
            key = storage_key(path)
            try:
                raw = read(key)
            except Exception:  # the storage error may name buckets/keys: keep it out of the job
                raise InputImageError("could not be loaded from storage")
            data, mime = prepare_image(raw, budget)
        except InputImageError as e:
            raise InputImageError(f"{label} {number} {e}.") from None
        parts.append({"mime_type": mime, "data": data})
    return parts


def load_job_images(job_assets: Iterable, read=None) -> List[dict]:
    """A ghost job's garment images (its GhostJobAssets), in upload order."""
    paths: List[Optional[str]] = [a.image_path for a in sorted(job_assets, key=lambda a: a.id) if a.image_path]
    if not paths:
        raise InputImageError("No garment image is attached to this job.")
    return load_images(paths, "Garment image", read)
