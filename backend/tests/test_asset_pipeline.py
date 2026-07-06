import pytest
import io
from PIL import Image
from app.services.asset_pipeline import (
    extract_metadata,
    convert_to_webp,
    generate_thumbnail,
    generate_preview,
    process_image,
    THUMBNAIL_SIZE,
    PREVIEW_SIZE,
)


# ========================== Helper ===============================

def create_test_image(width=800, height=600, format="PNG") -> bytes:
    """Create a test image in memory."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


# ========================== Metadata Tests =======================

def test_extract_metadata_basic():
    """Metadata should include width, height, aspect_ratio."""
    img = Image.new("RGB", (800, 600))
    meta = extract_metadata(img)
    assert meta["width"] == 800
    assert meta["height"] == 600
    assert meta["aspect_ratio"] == "4:3"


def test_extract_metadata_square():
    """Square image should have 1:1 aspect ratio."""
    img = Image.new("RGB", (500, 500))
    meta = extract_metadata(img)
    assert meta["aspect_ratio"] == "1:1"


def test_extract_metadata_wide():
    """16:9 image should have correct aspect ratio."""
    img = Image.new("RGB", (1920, 1080))
    meta = extract_metadata(img)
    assert meta["aspect_ratio"] == "16:9"


# ========================== WebP Conversion Tests ================

def test_convert_to_webp_returns_bytes():
    """WebP conversion should return bytes."""
    img = Image.new("RGB", (100, 100), color="red")
    webp_bytes = convert_to_webp(img)
    assert isinstance(webp_bytes, bytes)
    assert len(webp_bytes) > 0


def test_convert_to_webp_valid_image():
    """Converted bytes should be valid WebP image."""
    img = Image.new("RGB", (200, 200), color="blue")
    webp_bytes = convert_to_webp(img)
    result = Image.open(io.BytesIO(webp_bytes))
    assert result.format == "WEBP"


def test_convert_rgba_to_webp():
    """RGBA images should be converted to WebP correctly."""
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    webp_bytes = convert_to_webp(img)
    result = Image.open(io.BytesIO(webp_bytes))
    assert result.format == "WEBP"


# ========================== Thumbnail Tests ======================

def test_generate_thumbnail_size():
    """Thumbnail should fit within THUMBNAIL_SIZE bounds."""
    img = Image.new("RGB", (1000, 800))
    thumb_bytes = generate_thumbnail(img)
    thumb = Image.open(io.BytesIO(thumb_bytes))
    assert thumb.width <= THUMBNAIL_SIZE[0]
    assert thumb.height <= THUMBNAIL_SIZE[1]


def test_generate_preview_size():
    """Preview should fit within PREVIEW_SIZE bounds."""
    img = Image.new("RGB", (2000, 1500))
    preview_bytes = generate_preview(img)
    preview = Image.open(io.BytesIO(preview_bytes))
    assert preview.width <= PREVIEW_SIZE[0]
    assert preview.height <= PREVIEW_SIZE[1]


def test_thumbnail_is_webp():
    """Thumbnail should be in WebP format."""
    img = Image.new("RGB", (500, 500))
    thumb_bytes = generate_thumbnail(img)
    thumb = Image.open(io.BytesIO(thumb_bytes))
    assert thumb.format == "WEBP"


def test_preview_is_webp():
    """Preview should be in WebP format."""
    img = Image.new("RGB", (500, 500))
    preview_bytes = generate_preview(img)
    preview = Image.open(io.BytesIO(preview_bytes))
    assert preview.format == "WEBP"


# ========================== Pipeline Tests =======================

def test_process_image_returns_all_keys():
    """process_image should return all expected keys."""
    image_bytes = create_test_image(800, 600, "PNG")
    result = process_image(image_bytes, "test_image.png")

    assert "webp_bytes" in result
    assert "thumbnail_bytes" in result
    assert "preview_bytes" in result
    assert "webp_filename" in result
    assert "thumbnail_filename" in result
    assert "preview_filename" in result
    assert "metadata" in result


def test_process_image_webp_filename():
    """WebP filename should have .webp extension."""
    image_bytes = create_test_image()
    result = process_image(image_bytes, "photo.jpg")
    assert result["webp_filename"] == "photo.webp"
    assert result["thumbnail_filename"] == "photo_thumb.webp"
    assert result["preview_filename"] == "photo_preview.webp"


def test_process_image_metadata_correct():
    """process_image should extract correct metadata."""
    image_bytes = create_test_image(800, 600, "PNG")
    result = process_image(image_bytes, "test.png")
    meta = result["metadata"]
    assert meta["width"] == 800
    assert meta["height"] == 600
    assert meta["aspect_ratio"] == "4:3"


def test_process_image_valid_webp_output():
    """process_image webp_bytes should be valid WebP."""
    image_bytes = create_test_image(400, 300, "JPEG")
    result = process_image(image_bytes, "test.jpg")
    img = Image.open(io.BytesIO(result["webp_bytes"]))
    assert img.format == "WEBP"


def test_process_image_thumbnail_within_bounds():
    """Thumbnail from process_image should fit within 250x250."""
    image_bytes = create_test_image(2000, 1500, "PNG")
    result = process_image(image_bytes, "large.png")
    thumb = Image.open(io.BytesIO(result["thumbnail_bytes"]))
    assert thumb.width <= 250
    assert thumb.height <= 250
