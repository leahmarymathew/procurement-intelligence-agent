from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables (database-agnostic) and stamp the migration log."""
    # Import models so their metadata is registered before create_all
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Stamp migration log (idempotent)
    from sqlalchemy import select
    from .models import MigrationLog
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MigrationLog).where(MigrationLog.version == "001"))
        if not result.scalar_one_or_none():
            db.add(MigrationLog(
                version="001",
                description="Initial schema: all core tables",
                executed_by="system",
            ))
            await db.commit()
