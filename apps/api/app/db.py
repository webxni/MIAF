from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings


def make_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        future=True,
    )


engine: AsyncEngine = make_engine()
