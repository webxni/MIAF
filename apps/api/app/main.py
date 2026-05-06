import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.accounts import router as accounts_router
from app.api.audit import router as audit_router
from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.business import router as business_router
from app.api.documents import router as documents_router
from app.api.entities import router as entities_router
from app.api.heartbeat import internal_router as internal_heartbeat_router
from app.api.heartbeat import router as heartbeat_router
from app.api.journal import router as journal_router
from app.api.ledger import router as ledger_router
from app.api.memory import router as memory_router
from app.api.personal import router as personal_router
from app.api.skills import router as skills_router
from app.api.telegram import router as telegram_router
from app.api.user_settings import router as user_settings_router
from app.config import get_settings
from app.errors import install_error_handlers
from app.health import router as health_router
from app.services.skills import load_skill_manifests

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api starting (env=%s)", settings.environment)
    manifests = load_skill_manifests()
    log.info("loaded %s skills", len(manifests))
    yield
    log.info("api shutting down")


app = FastAPI(
    title="FinClaw API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

install_error_handlers(app)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(entities_router)
app.include_router(accounts_router)
app.include_router(journal_router)
app.include_router(ledger_router)
app.include_router(personal_router)
app.include_router(business_router)
app.include_router(documents_router)
app.include_router(agent_router)
app.include_router(memory_router)
app.include_router(heartbeat_router)
app.include_router(internal_heartbeat_router)
app.include_router(skills_router)
app.include_router(telegram_router)
app.include_router(user_settings_router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"name": "FinClaw API", "version": app.version, "env": settings.environment}
