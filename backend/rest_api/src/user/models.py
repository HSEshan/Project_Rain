from sqlalchemy import UUID, Column, DateTime, String
from src.database.core import Base
from src.utils.default import generate_id, generate_timestamp


class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, index=True, default=generate_id)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime(timezone=True), default=generate_timestamp)
    updated_at = Column(
        DateTime(timezone=True),
        default=generate_timestamp,
        onupdate=generate_timestamp,
    )
