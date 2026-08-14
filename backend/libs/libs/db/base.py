from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names. Without these, Postgres invents names and
# Alembic cannot reliably drop or alter a constraint it did not create.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def generate_id() -> str:
    return str(uuid4())


def generate_timestamp(offset: timedelta = timedelta(0)) -> datetime:
    return datetime.now(timezone.utc) + offset


def generate_timestamp_iso(offset: timedelta = timedelta(0)) -> str:
    return (datetime.now(timezone.utc) + offset).isoformat()
