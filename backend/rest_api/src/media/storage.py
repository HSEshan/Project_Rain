"""Where uploaded bytes live. Three operations and two implementations.

The seam exists so image upload could ship on the VPS without waiting on AWS
(tasks.md, Phase 19). `LocalStorage` writes to a volume that Caddy serves at
`/media`; `S3Storage` writes to a private bucket that CloudFront serves at the
same path. Nothing outside this module knows which is running: callers store
the key, and `libs.media.media_url` turns a key into `/media/{key}` for both.

Objects are write-once. A key is never overwritten, so both edges can mark every
object `immutable` and cache it forever; replacing an image means a new key and
a delete of the old one.
"""

import asyncio
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import structlog
from src.core.config import settings

logger = structlog.get_logger()

# One year, and immutable: a key is never reused, so there is nothing to revalidate.
CACHE_CONTROL = "public, max-age=31536000, immutable"


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...


class LocalStorage:
    """A directory on disk, served by the edge. The VPS and dev backend.

    Blocking file I/O runs in a thread so a large write does not stall the
    event loop every other request is waiting on.
    """

    def __init__(self, root: str):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        # Keys are built by this service from uuids, but resolve and check anyway:
        # a key that escapes the root is a write anywhere on the filesystem.
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"Storage key escapes the media root: {key}")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._write, self._path(key), data)

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written beside the target and renamed into place, so the edge can never
        # serve a half-written file to a browser that asked at the wrong moment.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, missing_ok=True)


class S3Storage:
    """A private S3 bucket, read through CloudFront. The AWS backend (aws/).

    boto3 is synchronous, so each call runs in a thread. The client is built
    lazily and without credentials: boto3's default chain finds the EC2 instance
    role, which is the only credential this backend is designed to use.
    """

    # CloudFront forwards the whole path to the bucket, so `/media/avatars/x`
    # is requested as the object `media/avatars/x`. Writing under the same
    # prefix is what makes the URL `libs.media` builds resolve, with no
    # rewrite function on the edge.
    KEY_PREFIX = "media/"

    def __init__(self, bucket: str, region: str | None):
        if not bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 needs S3_BUCKET")
        self.bucket = bucket
        self.region = region or None
        self._client = None

    def _s3(self):
        if self._client is None:
            # Imported here so the local backend never needs boto3 at import time
            import boto3

            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._s3().put_object,
            Bucket=self.bucket,
            Key=self.KEY_PREFIX + key,
            Body=data,
            ContentType=content_type,
            CacheControl=CACHE_CONTROL,
        )

    async def delete(self, key: str) -> None:
        # Deleting a key that does not exist succeeds in S3, which is the
        # behaviour the local backend's missing_ok matches.
        await asyncio.to_thread(
            self._s3().delete_object, Bucket=self.bucket, Key=self.KEY_PREFIX + key
        )


@lru_cache
def get_storage() -> Storage:
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "local":
        return LocalStorage(settings.MEDIA_ROOT)
    if backend == "s3":
        return S3Storage(settings.S3_BUCKET, settings.S3_REGION)
    raise RuntimeError(f"Unknown STORAGE_BACKEND: {settings.STORAGE_BACKEND}")


def check_media_writable() -> bool:
    """Log an error at startup if the local media root cannot be written.

    rest_api runs as a non-root user in production, and a named volume keeps the
    ownership it was created with. A volume first made by a root container stays
    root's, and every upload then fails with a 500 that names nothing useful.
    This turns that into one line at boot that says what to run. It does not
    stop startup: an API that cannot store images should still serve messages.
    """
    if settings.STORAGE_BACKEND.lower() != "local":
        return True
    root = Path(settings.MEDIA_ROOT)
    try:
        root.mkdir(parents=True, exist_ok=True)
        fd, probe = tempfile.mkstemp(dir=root, prefix=".write-check-")
        os.close(fd)
        os.unlink(probe)
        return True
    except OSError as error:
        logger.error(
            "Media root is not writable, every upload will fail. If the volume "
            "predates the non-root image, chown it to the image user once "
            "(DEPLOY.md, non-root containers)",
            media_root=str(root),
            uid=os.getuid() if hasattr(os, "getuid") else None,
            error=str(error),
        )
        return False


async def delete_quietly(keys: list[str | None]) -> None:
    """Delete objects after a commit, logging rather than raising.

    Called once the database no longer points at these keys. A failure here
    leaves an unreferenced object, which costs storage and nothing else, while
    raising would fail a request whose change has already been committed. Same
    rule as publishing after commit.
    """
    storage = get_storage()
    for key in keys:
        if not key:
            continue
        try:
            await storage.delete(key)
        except Exception:
            logger.exception("Failed to delete stored object", key=key)
