# Kinderuniversiteit AI Customer Support

Production-grade AI assistant for Kinderuniversiteit that handles customer support across **email**, **WhatsApp**, and **live chat** channels using RAG-augmented OpenAI responses and automatic human escalation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  FastAPI  (app/main.py)                                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐  │
│  │  /chat   │  │/knowledge│  │/escalations│  │ /health │  │
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘  └─────────┘  │
│       │              │              │                        │
│  ┌────▼──────────────▼──────────────▼──────────────────┐   │
│  │  Application layer  (use-cases / orchestrators)      │   │
│  └────┬──────────────────────────────────────────┬──────┘   │
│       │                                          │           │
│  ┌────▼──────────────┐         ┌─────────────────▼──────┐  │
│  │  OpenAI Service   │         │  PostgreSQL  (SQLAlchemy│  │
│  │  (Responses API   │         │  async + Alembic)       │  │
│  │  + RAG retrieval) │         └────────────────────────┘  │
│  └────┬──────────────┘                                      │
│       │                                                      │
│  ┌────▼──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  ChromaDB         │  │  Redis       │  │  Structlog  │  │
│  │  (vector store)   │  │  (rate limit │  │  (JSON logs)│  │
│  └───────────────────┘  │   + cache)   │  └─────────────┘  │
│                          └──────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- Clean Architecture: domain → application → infrastructure, no upward imports.
- Async throughout: `asyncpg`, `aioredis`, `httpx`, `asyncio.to_thread` for ChromaDB.
- RAG pipeline: cosine-similarity retrieval from ChromaDB → injected into system prompt → confidence score drives auto-escalation.
- Escalation signals: low RAG confidence **or** `[ESCALATE]` block in AI output triggers human hand-off.
- Multi-tenant: every row carries a `tenant_id`; middleware injects it from the request context.

---

## Quick start (Docker)

### 1. Prerequisites

- Docker 24+ and Docker Compose v2
- An OpenAI API key

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY at minimum.
```

Minimum `.env` for local development:

```dotenv
OPENAI_API_KEY=sk-...
SECRET_KEY=change-me-in-production
```

### 3. Start all services

```bash
docker compose up -d
```

Docker Compose starts:
| Service | Port (host) | Purpose |
|---------|-------------|---------|
| `app` | 8000 | FastAPI application |
| `postgres` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Redis 7 |
| `chromadb` | 8001 | ChromaDB vector store |

### 4. Run database migrations

```bash
docker compose run --rm migrate
```

### 5. Verify

```bash
curl http://localhost:8000/api/v1/health
# → {"status":"healthy","database":true,"redis":true,"chroma":true}
```

---

## Local development (no Docker)

### 1. Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. External services

Spin up Postgres and Redis however you prefer (Homebrew, Docker, etc.), then set their URLs in `.env`.

ChromaDB defaults to **embedded mode** (`data/chroma/`) when `CHROMA_HOST` is empty — no separate service needed locally.

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI secret key |
| `OPENAI_MODEL` | `gpt-4o` | Model used for Responses API calls |
| `OPENAI_TEMPERATURE` | `0.3` | Sampling temperature |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/kinderuniversiteit` | Async SQLAlchemy URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CHROMA_HOST` | *(empty)* | ChromaDB host; empty → embedded mode |
| `CHROMA_PORT` | `8000` | ChromaDB port (remote mode only) |
| `CHROMA_COLLECTION_NAME` | `kinderuniversiteit_kb` | ChromaDB collection |
| `CHROMA_PERSIST_DIR` | `data/chroma` | Embedded ChromaDB data directory |
| `SECRET_KEY` | *(required)* | JWT signing key |
| `APP_ENV` | `development` | `development` / `production` |
| `LOG_LEVEL` | `INFO` | Structlog level |
| `RATE_LIMIT_REQUESTS` | `60` | Requests per minute per IP |
| `CONFIDENCE_THRESHOLD` | `0.7` | RAG score below this triggers escalation |
| `MAX_CONVERSATION_TURNS` | `20` | History truncation limit |

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat` | Send a message in a conversation |
| `GET` | `/api/v1/conversations/{id}` | Fetch conversation + message history |
| `POST` | `/api/v1/knowledge/upload` | Ingest a document into the knowledge base |
| `GET` | `/api/v1/knowledge` | List knowledge documents |
| `DELETE` | `/api/v1/knowledge/{id}` | Remove a document and its chunks |
| `GET` | `/api/v1/escalations` | List pending escalations |
| `PUT` | `/api/v1/escalations/{id}/resolve` | Mark an escalation resolved |
| `GET` | `/api/v1/analytics/dashboard` | Metrics summary |
| `GET` | `/api/v1/health` | Health probe (database + Redis + ChromaDB) |

Interactive docs: `http://localhost:8000/docs`

---

## Knowledge base

Documents are ingested via `POST /api/v1/knowledge/upload` (PDF, plain text, or JSON).

The pipeline:
1. Extracts text (PyPDF for PDFs, UTF-8 decode for text).
2. Splits into overlapping chunks (~500 tokens, 50-token overlap).
3. Embeds with `text-embedding-3-small` via OpenAI.
4. Stores vectors in ChromaDB and metadata in PostgreSQL.

---

## Running tests

```bash
pytest -v --cov=app --cov-report=term-missing
```

Integration tests require a running Postgres and Redis. Set `DATABASE_URL` and `REDIS_URL` in your environment or a `.env.test` file.

---

## Linting

```bash
ruff check .
ruff format --check .
mypy app/
```

---

## Deployment

The application is stateless between requests — all state lives in Postgres, Redis, and ChromaDB. Recommended topology:

- **App**: any container platform (Render, DigitalOcean App Platform, Fly.io, ECS). Scale horizontally.
- **Postgres**: managed instance (RDS, Supabase, Neon, etc.).
- **Redis**: managed instance (Upstash, ElastiCache, etc.).
- **ChromaDB**: single container with persistent volume, or replace with Pinecone/Weaviate by swapping `IKnowledgeBase`.

Set `CHROMA_HOST` and `CHROMA_PORT` to point to your managed ChromaDB. Leave `CHROMA_HOST` empty only for local/single-node where embedded mode is acceptable.
