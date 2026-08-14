from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends
from libs.db import Base, create_engine, create_session_factory  # noqa: F401
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config import settings

engine = create_engine(settings.ASYNC_DB_URL)
AsyncSessionLocal = create_session_factory(engine)


# Dependency to get the database session
async def get_db() -> AsyncGenerator[Any, None]:
    async with AsyncSessionLocal() as db:
        yield db


# Dependency annotation
db_dependency = Annotated[AsyncSession, Depends(get_db)]
