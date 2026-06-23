"""Registers all v1 endpoint routers onto one APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import demo, health
from app.core.config import settings

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(demo.router)

# Only register DB-dependent routers when DATABASE_URL is configured.
if settings.database_url:
    from app.api.v1.endpoints import analytics, knowledge, webhook  # noqa: E402

    router.include_router(webhook.router)
    router.include_router(analytics.router)
    router.include_router(knowledge.router)
