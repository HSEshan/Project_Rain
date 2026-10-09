"""The upload pipeline's promises, checked without a database or a server.

Every stored image is decoded and re-encoded (src/media/images.py). These pin
down the parts of that which are security properties rather than cosmetics:
what is refused, and what does not survive the re-encode.
"""

import io

import pytest
from PIL import Image
from src.media.images import (
    ATTACHMENT_MAX_SIDE,
    SQUARE_SIDE,
    ImageKind,
    process_image,
)
from src.utils.exceptions import UnsupportedMediaTypeException


def encode(fmt: str, size=(40, 30), mode="RGB", **kwargs) -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, (200, 40, 40) if mode == "RGB" else (200, 40, 40, 128)).save(
        out, fmt, **kwargs
    )
    return out.getvalue()


def decode(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "GIF"])
def test_accepted_formats_come_out_as_webp(fmt):
    result = process_image(encode(fmt), ImageKind.ATTACHMENT)
    assert result.content_type == "image/webp"
    assert decode(result.data).format == "WEBP"


def test_html_named_png_is_refused():
    with pytest.raises(UnsupportedMediaTypeException):
        process_image(b"<html><script>alert(1)</script></html>", ImageKind.AVATAR)


def test_decodable_but_unlisted_format_is_refused():
    # Pillow reads BMP happily; the allowlist is what refuses it
    with pytest.raises(UnsupportedMediaTypeException):
        process_image(encode("BMP"), ImageKind.AVATAR)


def test_truncated_image_is_refused():
    with pytest.raises(UnsupportedMediaTypeException):
        process_image(encode("PNG", (400, 400))[:200], ImageKind.ATTACHMENT)


def png_header_only(width: int, height: int) -> bytes:
    """A few dozen bytes that claim to be a huge PNG: the shape of a bomb.

    Only the header is real. Refusing it must happen from the header alone,
    before any pixel is allocated, which is also why this test does not build
    a real 400-megapixel image to prove it.
    """
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00"))


def test_oversized_dimensions_are_refused_before_decoding():
    # 20000 x 20000 is 400 megapixels, declared by a file under 100 bytes
    with pytest.raises(UnsupportedMediaTypeException):
        process_image(png_header_only(20000, 20000), ImageKind.ATTACHMENT)


def test_exif_is_not_carried_through():
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"  # Make
    exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPSInfo, latitude
    result = process_image(encode("JPEG", exif=exif), ImageKind.ATTACHMENT)
    assert b"SecretCameraMaker" not in result.data
    assert not decode(result.data).getexif()


def test_exif_orientation_is_applied_before_it_is_dropped():
    # A phone photo stored landscape with "rotate 90" in EXIF must arrive as
    # portrait, or stripping the tag would leave it sideways.
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 CW
    result = process_image(encode("JPEG", (80, 40), exif=exif), ImageKind.ATTACHMENT)
    assert (result.width, result.height) == (40, 80)


def test_avatar_is_a_fixed_square():
    result = process_image(encode("PNG", (900, 300)), ImageKind.AVATAR)
    assert (result.width, result.height) == (SQUARE_SIDE, SQUARE_SIDE)


def test_attachment_keeps_its_shape_within_the_limit():
    result = process_image(encode("PNG", (4000, 1000)), ImageKind.ATTACHMENT)
    assert result.width == ATTACHMENT_MAX_SIDE
    assert result.height == ATTACHMENT_MAX_SIDE // 4


def test_small_attachment_is_not_upscaled():
    result = process_image(encode("PNG", (40, 30)), ImageKind.ATTACHMENT)
    assert (result.width, result.height) == (40, 30)


def test_transparency_survives():
    result = process_image(encode("PNG", mode="RGBA"), ImageKind.ICON)
    assert decode(result.data).mode == "RGBA"
