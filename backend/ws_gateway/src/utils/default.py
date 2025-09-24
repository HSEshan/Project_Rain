from datetime import datetime, timedelta, timezone
from uuid import uuid4


def generate_id() -> str:
    return str(uuid4())


def generate_timestamp(timedelta: timedelta = timedelta(0)) -> datetime:
    return datetime.now(timezone.utc) + timedelta


def generate_timestamp_iso(timedelta: timedelta = timedelta(0)) -> str:
    return (datetime.now(timezone.utc) + timedelta).isoformat()
