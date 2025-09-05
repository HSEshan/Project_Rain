from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.core.config import settings

# Create async engine
engine = create_async_engine(settings.ASYNC_DB_URL, echo=False)

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
