"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings, startup_validate
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 1. Configure logging first so every subsequent message is formatted.
    configure_logging(settings)
    # 2. Validate runtime preconditions (dirs, prompt files) and emit the
    #    masked config summary.  Crashes loudly if anything is wrong.
    startup_validate(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kinderuniversiteit AI Assistant",
        version=settings.app_version,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        lifespan=lifespan,
    )

    origins = ["*"] if not settings.is_production else []
    if settings.frontend_url:
        origins.append(settings.frontend_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)
    return app


app = create_app()
