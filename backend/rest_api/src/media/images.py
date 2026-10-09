"""Turn an uploaded file into an image we are willing to serve.

**Everything is decoded and re-encoded; nothing the uploader sent is stored.**
The filename and the declared content type are claims made by the uploader, so
neither is read. Pillow decides what the bytes are, and the output is a fresh
WebP written by us. That one step does four jobs:

- a file that is not an image, or is one pretending to be another, fails to
  decode and is refused;
- EXIF is dropped, which matters more than it sounds: a phone photo carries
  the GPS position it was taken at, and a chat app should not publish where
  someone lives because they shared a picture of their dog;
- polyglot files (a valid image that is also valid HTML or a script) do not
  survive being re-encoded, so the edge never serves attacker-chosen bytes;
- every stored image is one format, so the edge only ever sends `image/webp`.

Animated GIFs and WebPs are flattened to their first frame. Keeping animation
means re-encoding every frame of an untrusted file, which is the expensive
path to have open on an unauthenticated-adjacent endpoint; it is a known limit
rather than an oversight.
"""

import io
from dataclasses import dataclass
from enum import Enum

from PIL import Image, ImageOps, UnidentifiedImageError
from src.utils.exceptions import UnsupportedMediaTypeException

# What Pillow is allowed to have decoded. Anything else, including formats
# Pillow could open (TIFF, BMP, ICO, PSD...), is refused rather than converted:
# each extra decoder is more attack surface for no feature anyone asked for.
ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}

# A decompression bomb is a small file that decodes to an enormous bitmap. The
# header is read before any pixels are, so this is checked before the cost is
# paid. 40 megapixels is a large phone photo with room to spare.
MAX_PIXELS = 40_000_000
MAX_SIDE = 12_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

OUTPUT_FORMAT = "WEBP"
OUTPUT_CONTENT_TYPE = "image/webp"
OUTPUT_QUALITY = 85


class ImageKind(Enum):
    """What the image is for, which decides its shape."""

    # Square, cropped to fill: shown as a circle at every size up to 80px, so
    # 256 covers a 2x display with a margin and keeps every avatar under ~30KB.
    AVATAR = "avatar"
    ICON = "icon"
    # Scaled to fit, never cropped: someone sharing a screenshot wants all of it.
    ATTACHMENT = "attachment"


SQUARE_SIDE = 256
ATTACHMENT_MAX_SIDE = 2048


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    width: int
    height: int
    content_type: str = OUTPUT_CONTENT_TYPE
    extension: str = "webp"


def process_image(raw: bytes, kind: ImageKind) -> ProcessedImage:
    """Decode, validate, normalise and re-encode. CPU-bound: run it in a thread."""
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ACCEPTED_FORMATS:
                raise UnsupportedMediaTypeException(
                    "Images must be PNG, JPEG, WebP or GIF"
                )
            width, height = image.size
            if width > MAX_SIDE or height > MAX_SIDE or width * height > MAX_PIXELS:
                raise UnsupportedMediaTypeException(
                    "That image is too large. Keep it under 40 megapixels"
                )

            # Loads the first frame only, which is the flattening described above
            image.seek(0)
            # Phones store "rotate me" as an EXIF tag rather than rotating the
            # pixels; applying it here is what stops portrait photos arriving
            # sideways once the EXIF has been stripped.
            image = ImageOps.exif_transpose(image)
            image = _normalise_mode(image)

            if kind is ImageKind.ATTACHMENT:
                image.thumbnail(
                    (ATTACHMENT_MAX_SIDE, ATTACHMENT_MAX_SIDE),
                    Image.Resampling.LANCZOS,
                )
            else:
                image = ImageOps.fit(
                    image, (SQUARE_SIDE, SQUARE_SIDE), Image.Resampling.LANCZOS
                )

            out = io.BytesIO()
            # No `exif=` argument, so none is written: see the module docstring.
            image.save(out, OUTPUT_FORMAT, quality=OUTPUT_QUALITY, method=4)
            return ProcessedImage(
                data=out.getvalue(), width=image.width, height=image.height
            )
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        # OSError covers truncated and corrupt files, which Pillow reports late,
        # while decoding pixels rather than while reading the header.
        raise UnsupportedMediaTypeException(
            "That file is not an image we can read. Use PNG, JPEG, WebP or GIF"
        )


def _normalise_mode(image: Image.Image) -> Image.Image:
    """RGB, or RGBA where there is transparency worth keeping."""
    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    target = "RGBA" if has_alpha else "RGB"
    return image if image.mode == target else image.convert(target)
