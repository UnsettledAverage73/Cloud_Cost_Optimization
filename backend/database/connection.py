import os
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

logger = logging.getLogger("cloudpulse.database")

# Environment-configurable connection URIs
# Default connects to the local TimescaleDB container
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgrespassword")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "cloudpulse_db")

DEFAULT_SYNC_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
DEFAULT_ASYNC_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

raw_db_url = os.getenv("DATABASE_URL", DEFAULT_SYNC_URL)
if "dpg-" in raw_db_url and not os.getenv("RENDER"):
    # If Render private internal DB hostname is passed on local machine, fall back to local PostgreSQL container
    raw_db_url = DEFAULT_SYNC_URL
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = raw_db_url

if os.getenv("ASYNC_DATABASE_URL"):
    ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL")
else:
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Base class for declarative SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Synchronous Engine & Session
sync_engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_pre_ping=True
)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Asynchronous Engine & Session
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_pre_ping=True
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

def get_sync_db() -> Session:
    """Yield a synchronous database session."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an asynchronous database session for FastAPI endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def ping_database() -> dict:
    """Verify connectivity and TimescaleDB extension status."""
    try:
        with sync_engine.connect() as conn:
            version = conn.execute(text("SELECT version();")).scalar()
            timescale_version = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname='timescaledb';")
            ).scalar()
            return {
                "status": "connected",
                "postgres_version": version,
                "timescaledb_version": timescale_version or "not installed"
            }
    except Exception as e:
        logger.error(f"Database ping failed: {str(e)}")
        return {
            "status": "disconnected",
            "error": str(e)
        }
