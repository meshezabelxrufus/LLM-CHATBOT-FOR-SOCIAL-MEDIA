"""GET /api/v1/health — dependency health-checks for load balancer / Docker."""
from fastapi import APIRouter

from app.monitoring.health import check_chroma, check_database, check_redis

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    db_ok = await check_database()
    redis_ok = await check_redis()
    chroma_ok = await check_chroma()
    healthy = all([db_ok, redis_ok, chroma_ok])
    return {
        "status": "healthy" if healthy else "degraded",
        "dependencies": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "chroma": "ok" if chroma_ok else "error",
        },
    }
