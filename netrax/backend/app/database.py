"""
NETRA-X Database Configuration
Async SQLAlchemy engine and session management.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine_kwargs = {"echo": settings.DEBUG}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency that provides a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


import logging

logger = logging.getLogger(__name__)


async def init_db():
    """Initialize database tables (for development only, use Alembic in production)."""
    global engine
    import app.models  # noqa: F401

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully with %s", engine.url)
    except (OSError, ConnectionRefusedError, Exception) as exc:
        if not str(engine.url).startswith("sqlite"):
            logger.warning(
                "Could not connect to PostgreSQL (%s: %s). Falling back to SQLite for local development: sqlite+aiosqlite:///./netrax.db",
                type(exc).__name__,
                exc,
            )
            sqlite_url = "sqlite+aiosqlite:///./netrax.db"
            engine = create_async_engine(sqlite_url, echo=settings.DEBUG)
            async_session_factory.configure(bind=engine)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully with SQLite fallback: %s", sqlite_url)
        else:
            raise
