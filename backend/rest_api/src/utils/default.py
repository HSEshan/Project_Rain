from datetime import datetime, timezone
from uuid import uuid4


def generate_id() -> str:
    return str(uuid4())


def generate_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
