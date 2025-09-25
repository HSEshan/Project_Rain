from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.ASYNC_DB_URL,
    echo=False,
    pool_size=2,
    max_overflow=15,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

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
