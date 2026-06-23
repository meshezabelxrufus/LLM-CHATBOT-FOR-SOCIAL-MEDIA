"""
Structured logging via structlog.

configure_logging() is called once from the FastAPI lifespan.  After that,
every module can call get_logger(__name__) to get a bound structlog logger.

Format selection
────────────────
  JSON   — always used in production, or when LOG_FORMAT=json
  text   — coloured console output, used in development by default

File rotation
─────────────
  Set LOG_FILE_PATH to enable a RotatingFileHandler alongside stdout.
  LOG_MAX_BYTES  (default 10 MB) and LOG_BACKUP_COUNT (default 5) control
  rotation.  The file always receives plain-text log lines regardless of
  format so they're grep-friendly without a JSON parser.

stdlib integration
──────────────────
  Third-party libraries (httpx, SQLAlchemy, asyncpg, chromadb) use the stdlib
  logging module.  We route their output through structlog's processor chain so
  all log lines share the same format and context variables.

  Noisy libraries are clamped to WARNING so they don't flood the logs.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.core.config import Settings


# ── Public API ────────────────────────────────────────────────────────────────


def configure_logging(s: Settings | None = None) -> None:
    """Set up structlog and the stdlib root logger.

    Idempotent: safe to call multiple times (e.g. in tests).
    Accepts an optional Settings object for dependency injection in tests;
    falls back to the module-level singleton.
    """
    if s is None:
        from app.core.config import settings as s  # type: ignore[assignment]

    log_level = getattr(logging, s.app_log_level, logging.INFO)
    use_json = s.effective_log_format == "json"

    # ── structlog processor chain ─────────────────────────────────────────────
    shared_processors: list = [
        # Merge any context variables bound to the current async context
        # (e.g. request_id bound in the webhook handler).
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(colors=True, sort_keys=False)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── stdlib handlers ───────────────────────────────────────────────────────
    # Stdout handler — always present.
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)

    handlers: list[logging.Handler] = [stdout_handler]

    # File handler — only when LOG_FILE_PATH is configured.
    if s.log_file_path:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                s.log_file_path,
                maxBytes=s.log_max_bytes,
                backupCount=s.log_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            handlers.append(file_handler)
        except OSError as exc:
            # Don't crash the app on a bad log path — warn and continue.
            logging.warning("Could not open log file %s: %s", s.log_file_path, exc)

    # Use a human-readable format for the file handler regardless of log_format,
    # so operators can grep plain text without a JSON parser.
    stdlib_fmt = "%(levelname)s %(name)s %(message)s" if not use_json else "%(message)s"

    # force=True replaces any handlers registered by previous basicConfig calls
    # (e.g. from uvicorn starting before our lifespan runs).
    logging.basicConfig(
        level=log_level,
        format=stdlib_fmt,
        handlers=handlers,
        force=True,
    )

    # ── Silence noisy third-party libraries ───────────────────────────────────
    _QUIET_LIBS = (
        "httpx",
        "httpcore",
        "asyncpg",
        "chromadb",
        "openai._base_client",
        "uvicorn.access",        # Per-request access logs are too verbose
    )
    for lib in _QUIET_LIBS:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a structlog BoundLogger for the given module name."""
    return structlog.get_logger(name)
