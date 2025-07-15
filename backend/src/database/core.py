from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.core.config import settings

# Create async engine
engine = create_async_engine(settings.ASYNC_DB_URL, echo=True)

# Create async session maker
AsyncSessionLocal: AsyncSession = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Define Base class for ORM models
Base = declarative_base()


# Dependency to get the database session
async def get_db() -> AsyncGenerator[Any, None]:
    async_session = AsyncSessionLocal
    async with async_session() as db:
        yield db


# Dependency annotation
db_dependency = Annotated[AsyncSession, Depends(get_db)]
