import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.health import router as health_router

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api starting (env=%s)", settings.environment)
    yield
    log.info("api shutting down")


app = FastAPI(
    title="FinClaw API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"name": "FinClaw API", "version": app.version, "env": settings.environment}
