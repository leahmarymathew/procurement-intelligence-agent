import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from .config import settings


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Run migration 001 (and any future migrations) on startup."""
    migration_path = Path(__file__).parent.parent / "migrations" / "001_initial_schema.sql"
    sql = migration_path.read_text()

    async with engine.begin() as conn:
        # SQLite doesn't support multi-statement execute natively via text(); split on ';'
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            await conn.execute(text(stmt))
