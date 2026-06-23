"""Registers all v1 endpoint routers onto one APIRouter."""
from fastapi import APIRouter

from app.api.v1.endpoints import analytics, demo, health, knowledge, webhook

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(webhook.router)
router.include_router(analytics.router)
router.include_router(knowledge.router)
router.include_router(demo.router)
