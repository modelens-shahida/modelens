import io
import os
from typing import Tuple, Optional
from PIL import Image

# Configurable settings
WEBP_QUALITY = int(os.getenv("WEBP_QUALITY", "80"))
THUMBNAIL_SIZE = (250, 250)
PREVIEW_SIZE = (800, 800)


def extract_metadata(image: Image.Image) -> dict:
    """Extract image metadata: width, height, aspect_ratio, format."""
    width, height = image.size
    gcd = _gcd(width, height)
    aspect_ratio = f"{width // gcd}:{height // gcd}"
    return {
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "format": image.format or "UNKNOWN",
    }


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def convert_to_webp(image: Image.Image, quality: int = WEBP_QUALITY) -> bytes:
    """Convert image to WebP format with specified quality."""
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGBA")
    else:
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=quality)
    return buffer.getvalue()


def generate_thumbnail(image: Image.Image, size: Tuple[int, int] = THUMBNAIL_SIZE) -> bytes:
    """Generate a WebP thumbnail at the given size (maintains aspect ratio)."""
    thumb = image.copy()
    thumb.thumbnail(size, Image.LANCZOS)
    if thumb.mode in ("RGBA", "P"):
        thumb = thumb.convert("RGBA")
    else:
        thumb = thumb.convert("RGB")
    buffer = io.BytesIO()
    thumb.save(buffer, format="WEBP", quality=WEBP_QUALITY)
    return buffer.getvalue()


def generate_preview(image: Image.Image, size: Tuple[int, int] = PREVIEW_SIZE) -> bytes:
    """Generate a WebP preview at the given size (maintains aspect ratio)."""
    preview = image.copy()
    preview.thumbnail(size, Image.LANCZOS)
    if preview.mode in ("RGBA", "P"):
        preview = preview.convert("RGBA")
    else:
        preview = preview.convert("RGB")
    buffer = io.BytesIO()
    preview.save(buffer, format="WEBP", quality=WEBP_QUALITY)
    return buffer.getvalue()


def process_image(image_bytes: bytes, original_filename: str) -> dict:
    """
    Full asset pipeline processing:
    1. Load image and extract metadata
    2. Convert to WebP
    3. Generate thumbnail (250x250) and preview (800x800)

    Returns dict with processed bytes and metadata.
    """
    image = Image.open(io.BytesIO(image_bytes))
    metadata = extract_metadata(image)

    webp_bytes = convert_to_webp(image)
    thumbnail_bytes = generate_thumbnail(image)
    preview_bytes = generate_preview(image)

    base_name = os.path.splitext(original_filename)[0]

    return {
        "webp_bytes": webp_bytes,
        "thumbnail_bytes": thumbnail_bytes,
        "preview_bytes": preview_bytes,
        "webp_filename": f"{base_name}.webp",
        "thumbnail_filename": f"{base_name}_thumb.webp",
        "preview_filename": f"{base_name}_preview.webp",
        "metadata": metadata,
    }
