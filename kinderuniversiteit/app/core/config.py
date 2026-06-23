"""
Central settings — every configuration value the application reads.

All values are sourced from (in order of precedence):
  1. Real environment variables
  2. .env file in the project root
  3. Defaults declared here

Validation runs at construction time via Pydantic.  Two layers:
  - Field-level validators catch bad individual values (wrong type, out of range)
  - Model-level validator enforces production-specific requirements
    (strong secret key, all third-party keys present, etc.)

The application crashes at startup with a clear error message if any required
value is missing or invalid — rather than failing silently on the first request.

Usage
─────
  from app.core.config import settings

  settings.openai_api_key     # str
  settings.is_production      # bool property
  settings.masked_summary()   # dict — safe to log, secrets redacted

Startup check
─────────────
  from app.core.config import startup_validate
  startup_validate(settings)   # called once from FastAPI lifespan
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Case-insensitive env var matching: DATABASE_URL == database_url.
        case_sensitive=False,
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "kinderuniversiteit-ai"
    app_version: str = "1.0.0"
    app_port: int = 8000
    # Primary log-level control.  Also used as the structlog filtering level.
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # Must be a strong random value ≥ 32 chars in production.
    secret_key: str = "dev-secret-key-change-in-production-please"

    # ── Logging ───────────────────────────────────────────────────────────────
    # "json"  → machine-readable JSON (always used in production)
    # "text"  → human-readable coloured console (development default)
    log_format: Literal["json", "text"] = "text"
    # Empty string = stdout only.  Any path value enables RotatingFileHandler.
    log_file_path: str = ""
    log_max_bytes: int = 10_485_760   # 10 MB per file
    log_backup_count: int = 5         # keep 5 rotated files

    # ── Paths ─────────────────────────────────────────────────────────────────
    # All paths are resolved relative to the current working directory when the
    # app starts.  Use absolute paths in production to avoid ambiguity.
    prompts_dir: Path = Path("app/prompts")
    templates_dir: Path = Path("app/prompts/templates")
    knowledge_dir: Path = Path("data/knowledge")     # PDF upload/storage root
    chroma_persist_dir: Path = Path("data/chroma")   # embedded ChromaDB only

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: PostgresDsn | None = None
    database_pool_size: int = 10
    database_max_overflow: int = 20
    # Set True only for local debugging; never in production (logs every query).
    database_echo: bool = False

    # ── AI Provider ──────────────────────────────────────────────────────────
    ai_provider: Literal["openai", "anthropic"] = "openai"

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    # Optional base URL — override to use any OpenAI-compatible provider.
    # e.g. Google Gemini: https://generativelanguage.googleapis.com/v1beta/openai/
    # Leave empty to use the default OpenAI endpoint.
    openai_base_url: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_max_tokens: int = 1024
    openai_temperature: float = 0.3
    # Per-request HTTP timeout in seconds.
    openai_timeout: float = 30.0

    # ── Anthropic ────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-haiku-20240307"
    anthropic_max_tokens: int = 1024
    anthropic_temperature: float = 0.3

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    # Remote mode  : set CHROMA_HOST + CHROMA_PORT  (uses HttpClient)
    # Embedded mode: leave CHROMA_HOST empty         (uses PersistentClient
    #                                                 with chroma_persist_dir)
    chroma_host: str = ""
    chroma_port: int = 8001
    chroma_collection_name: str = "kinderuniversiteit_kb"

    # ── ManyChat ─────────────────────────────────────────────────────────────
    manychat_api_key: str = ""
    manychat_webhook_secret: str = ""
    manychat_base_url: str = "https://api.manychat.com"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: RedisDsn | None = None
    cache_ttl_seconds: int = 300

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_messages_per_minute: int = 20

    # ── Escalation ───────────────────────────────────────────────────────────
    escalation_email: str = ""
    escalation_confidence_threshold: float = 0.6
    # Optional webhook URL to POST escalation payloads (e.g. Slack / Teams).
    escalation_webhook_url: str = ""

    # ── Analytics ────────────────────────────────────────────────────────────
    analytics_enabled: bool = True

    # ── CRM (future) ─────────────────────────────────────────────────────────
    crm_api_key: str = ""
    crm_base_url: str = ""

    frontend_url: str = ""

    # ── Field validators ─────────────────────────────────────────────────────

    @field_validator("app_log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, v: object) -> str:
        return str(v).upper()

    @field_validator("openai_api_key", "anthropic_api_key")
    @classmethod
    def _validate_api_key(cls, v: str) -> str:
        # Allow empty key in development/demo mode; warn in production via model validator.
        return v

    @field_validator("openai_temperature")
    @classmethod
    def _validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(
                f"OPENAI_TEMPERATURE must be between 0.0 and 2.0, got {v}"
            )
        return v

    @field_validator("openai_max_tokens")
    @classmethod
    def _validate_max_tokens(cls, v: int) -> int:
        if not 1 <= v <= 32_768:
            raise ValueError(
                f"OPENAI_MAX_TOKENS must be between 1 and 32 768, got {v}"
            )
        return v

    @field_validator("openai_timeout")
    @classmethod
    def _validate_openai_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"OPENAI_TIMEOUT must be positive, got {v}")
        return v

    @field_validator("escalation_confidence_threshold")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                f"ESCALATION_CONFIDENCE_THRESHOLD must be 0.0–1.0, got {v}"
            )
        return v

    @field_validator("database_pool_size")
    @classmethod
    def _validate_pool_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError(
                f"DATABASE_POOL_SIZE must be at least 1, got {v}"
            )
        return v

    @field_validator("rate_limit_messages_per_minute")
    @classmethod
    def _validate_rate_limit(cls, v: int) -> int:
        if v < 1:
            raise ValueError(
                f"RATE_LIMIT_MESSAGES_PER_MINUTE must be at least 1, got {v}"
            )
        return v

    # ── Production gate (cross-field) ─────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_production_requirements(self) -> "Settings":
        """Enforce strict requirements that only apply in production.

        Fails loudly at startup so misconfiguration is caught during deployment,
        not discovered when the first real user message arrives.
        """
        if self.app_env != "production":
            return self

        errors: list[str] = []

        if self.ai_provider == "openai" and not self.openai_api_key.startswith(("sk-", "sk-proj-")):
            errors.append(
                "OPENAI_API_KEY does not look like a valid OpenAI key "
                "(must start with 'sk-' or 'sk-proj-')"
            )
        elif self.ai_provider == "anthropic" and not self.anthropic_api_key.startswith("sk-ant-"):
            errors.append(
                "ANTHROPIC_API_KEY does not look like a valid Anthropic key "
                "(must start with 'sk-ant-')"
            )

        if not self.manychat_api_key:
            errors.append("MANYCHAT_API_KEY must be set in production")

        if not self.manychat_webhook_secret:
            errors.append("MANYCHAT_WEBHOOK_SECRET must be set in production")

        weak = {"changeme", "change-me", "secret", "password", "dev", ""}
        if self.secret_key.lower() in weak or len(self.secret_key) < 32:
            errors.append(
                "SECRET_KEY must be a strong random value of at least 32 characters in production "
                "(generate with: python -c \"import secrets; print(secrets.token_hex(32))\")"
            )

        if errors:
            bullets = "\n".join(f"  • {e}" for e in errors)
            raise ValueError(f"Production configuration is invalid:\n{bullets}")

        return self

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def chroma_use_embedded(self) -> bool:
        """True when ChromaDB runs as an embedded process (no remote host)."""
        return not self.chroma_host

    @property
    def effective_log_format(self) -> Literal["json", "text"]:
        """Always JSON in production, regardless of LOG_FORMAT setting."""
        return "json" if self.is_production else self.log_format

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def masked_summary(self) -> dict:
        """Safe representation of the active config — suitable for startup logs.

        All secret values are redacted.  Paths are shown as absolute strings so
        the log is unambiguous regardless of working directory.
        """
        def _mask(v: str) -> str:
            if not v:
                return "<not set>"
            visible = min(6, max(0, len(v) - 4))
            return v[:visible] + "***"

        db_url = str(self.database_url) if self.database_url else "<not set>"
        redis_url = str(self.redis_url) if self.redis_url else "<not set>"
        db_url_safe = re.sub(r"://[^:@/]+:[^@/]+@", "://<redacted>@", db_url)
        redis_url_safe = re.sub(r"://[^:@/]+:[^@/]+@", "://<redacted>@", redis_url)

        chroma_mode = (
            f"embedded ({self.chroma_persist_dir.resolve()})"
            if self.chroma_use_embedded
            else f"remote ({self.chroma_host}:{self.chroma_port})"
        )

        return {
            "app_env": self.app_env,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "app_port": self.app_port,
            "log_level": self.app_log_level,
            "log_format": self.effective_log_format,
            "log_file_path": self.log_file_path or "<stdout only>",
            "ai_provider": self.ai_provider,
            "openai_model": self.openai_model,
            "openai_embedding_model": self.openai_embedding_model,
            "openai_api_key": _mask(self.openai_api_key),
            "openai_temperature": self.openai_temperature,
            "openai_max_tokens": self.openai_max_tokens,
            "openai_timeout": self.openai_timeout,
            "anthropic_model": self.anthropic_model,
            "anthropic_api_key": _mask(self.anthropic_api_key),
            "anthropic_temperature": self.anthropic_temperature,
            "anthropic_max_tokens": self.anthropic_max_tokens,
            "manychat_api_key": _mask(self.manychat_api_key),
            "manychat_base_url": self.manychat_base_url,
            "database_url": db_url_safe,
            "database_pool_size": self.database_pool_size,
            "redis_url": redis_url_safe,
            "chroma": chroma_mode,
            "chroma_collection": self.chroma_collection_name,
            "knowledge_dir": str(self.knowledge_dir.resolve()),
            "prompts_dir": str(self.prompts_dir.resolve()),
            "templates_dir": str(self.templates_dir.resolve()),
            "analytics_enabled": self.analytics_enabled,
            "escalation_confidence_threshold": self.escalation_confidence_threshold,
            "rate_limit_per_minute": self.rate_limit_messages_per_minute,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
# Construction runs all field + model validators immediately.  A bad .env will
# raise a ValidationError here with a clear message before any handler runs.

settings = Settings()  # type: ignore[call-arg]


# ── Startup validation ────────────────────────────────────────────────────────


def startup_validate(s: Settings = settings) -> None:
    """Validate runtime preconditions and ensure data directories exist.

    Called once from the FastAPI lifespan after logging is configured.  Checks
    things that cannot be done during Pydantic construction (file system state,
    directory creation) and emits a masked config summary to the structured log.

    Raises RuntimeError with all problems listed if any check fails.
    """
    errors: list[str] = []

    # Data directories must be writable — create them if they don't exist.
    for attr in ("knowledge_dir", "chroma_persist_dir"):
        path: Path = getattr(s, attr)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            errors.append(f"{attr} ({path}) cannot be created: {exc}")

    # Prompt directories ship with the application — they must exist.
    for attr in ("prompts_dir", "templates_dir"):
        path = getattr(s, attr)
        if not path.exists():
            errors.append(f"{attr} ({path}) does not exist — check PROMPTS_DIR / TEMPLATES_DIR")

    if errors:
        bullets = "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(f"Startup validation failed:\n{bullets}")

    # Emit config summary to structlog (logging is already configured by here).
    import structlog
    structlog.get_logger(__name__).info(
        "configuration_validated", **s.masked_summary()
    )
