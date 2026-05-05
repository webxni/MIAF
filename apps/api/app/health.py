import asyncio
import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.cache import redis
from app.config import get_settings
from app.db import engine
from app.storage import ensure_bucket, minio_client

log = logging.getLogger("api.health")
router = APIRouter()


@router.get("/health", tags=["health"])
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
async def readiness() -> dict:
    settings = get_settings()
    checks: dict[str, str] = {}

    # Postgres
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            ext = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            checks["postgres"] = "ok" if ext.first() else "missing-pgvector"
    except Exception as e:
        log.exception("postgres check failed")
        checks["postgres"] = f"error: {type(e).__name__}"

    # Redis
    try:
        pong = await redis.ping()
        checks["redis"] = "ok" if pong else "no-pong"
    except Exception as e:
        log.exception("redis check failed")
        checks["redis"] = f"error: {type(e).__name__}"

    # MinIO — minio client is sync; run in a thread so we don't block the event loop.
    try:
        await asyncio.to_thread(ensure_bucket, minio_client, settings.minio_bucket)
        checks["minio"] = "ok"
    except Exception as e:
        log.exception("minio check failed")
        checks["minio"] = f"error: {type(e).__name__}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
