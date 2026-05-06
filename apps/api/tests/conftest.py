"""Test fixtures.

Strategy:
- Build a separate test database `miaf_test` once per session (via a sync fixture
  that drives async setup with `asyncio.run`, so no loop crosses test boundaries).
- Each test gets its own short-lived async engine + connection. A nested
  transaction is opened at the start and rolled back at the end, so tests are
  isolated even though they hit a real Postgres.

Test DB lives on the same Postgres instance the api container uses.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from urllib.parse import urlparse, urlunparse

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def _build_test_db_url(base_url: str, db_name: str) -> str:
    parsed = urlparse(base_url)
    return urlunparse(parsed._replace(path=f"/{db_name}"))


def _admin_url(base_url: str) -> str:
    return _build_test_db_url(base_url, "postgres")


TEST_DB_NAME = os.getenv("TEST_DB_NAME", "miaf_test")


async def _setup_db(test_url: str, admin_url: str) -> None:
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with admin_engine.connect() as conn:
            await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
            await conn.exec_driver_sql(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await admin_engine.dispose()

    from app import models  # noqa: F401  populate metadata
    from app.models.base import Base

    test_engine = create_async_engine(test_url, poolclass=NullPool)
    try:
        async with test_engine.begin() as conn:
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await test_engine.dispose()


async def _teardown_db(admin_url: str) -> None:
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with admin_engine.connect() as conn:
            await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
    finally:
        await admin_engine.dispose()


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Sync session fixture: builds the test DB once, returns the URL.

    Uses `asyncio.run` for setup/teardown so no event loop is held between tests.
    """
    base = os.environ["DATABASE_URL"]
    test_url = _build_test_db_url(base, TEST_DB_NAME)
    admin_url = _admin_url(base)

    asyncio.run(_setup_db(test_url, admin_url))
    yield test_url
    asyncio.run(_teardown_db(admin_url))


@pytest_asyncio.fixture
async def db(test_db_url: str) -> AsyncIterator[AsyncSession]:
    """Per-test session: fresh engine, transaction rolled back at the end."""
    engine = create_async_engine(test_db_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            trans = await connection.begin()
            try:
                Session = async_sessionmaker(
                    bind=connection, expire_on_commit=False, class_=AsyncSession
                )
                async with Session() as session:
                    yield session
            finally:
                await trans.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def seeded(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> dict:
    from app.services.seed import run_seed

    monkeypatch.setenv("SEED_USER_EMAIL", "owner@example.com")
    monkeypatch.setenv("SEED_USER_NAME", "Demo Owner")
    monkeypatch.setenv("SEED_USER_PASSWORD", "change-me-on-first-login")
    result = await run_seed(db)
    await db.flush()
    return result
