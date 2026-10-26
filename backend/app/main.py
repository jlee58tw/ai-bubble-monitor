from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings
from .db import session_factory
from .logging_setup import configure_logging, get_logger
from .registry.registry import sync_registry
from .api.datasets_routes import router as datasets_router
from .scheduler import start_scheduler

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
log = get_logger("aibm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic (`alembic upgrade head`); here we only sync registry definitions.
    s = session_factory()()
    try:
        sync_registry(s)
    finally:
        s.close()
    sched = start_scheduler()
    log.info("api_started")
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="AI Bubble Monitor API", version="0.1.0", lifespan=lifespan,
              description="Research dashboard data API. Not investment advice.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(router)
app.include_router(datasets_router)
