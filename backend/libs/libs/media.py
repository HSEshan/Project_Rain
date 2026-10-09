"""Where uploaded images are served from, shared by every service that names one.

**Every stored object is reachable at `/media/{key}` on the app's own origin**,
whichever backend holds the bytes. On the VPS and in dev, Caddy serves the
media volume at that path; on AWS, CloudFront routes it to the S3 bucket. That
is what lets rest_api and ws_gateway build a URL without knowing which backend
is running, and what keeps a backend change out of the database, the event
payloads and the frontend: rows store the *key*, never a URL.

A key is written once and never overwritten. Replacing an avatar writes a new
key and deletes the old one, so the edge can cache every object forever
(`immutable`) and a browser can never be served a stale image under a new name.
"""

MEDIA_URL_PREFIX = "/media"


def media_url(key: str | None) -> str | None:
    """The public path for a stored key, or None when there is no object."""
    if not key:
        return None
    return f"{MEDIA_URL_PREFIX}/{key}"
