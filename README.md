# SecureVoice AI

**Browser-based autonomous customer care — conversational LLM + RAG + LLM alert classification,
with a voice-first React UI.**

SecureVoice AI is a full-stack customer-support platform. Customers talk (or type) to an
autonomous voice agent in the browser; the agent answers using a locally-hosted instruct LLM
(Ollama) grounded by a RAG knowledge base, while every user utterance is asynchronously classified
to raise **alerts** for the human support team. Staff triage those alerts from an
agent dashboard; admins manage users and the knowledge base.

Speech recognition (STT) and speech synthesis (TTS) both run **in the browser** via the Web Speech
API — raw audio never leaves the client; only the recognised text is sent to the server.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Backend](#backend)
  - [Application structure](#application-structure)
  - [Middleware pipeline](#middleware-pipeline)
  - [Database schema](#database-schema)
  - [AI / ML subsystem](#ai--ml-subsystem)
  - [Background tasks (Celery)](#background-tasks-celery)
  - [Configuration](#configuration)
- [API reference](#api-reference)
- [Authentication & RBAC](#authentication--rbac)
- [Frontend](#frontend)
- [Getting started](#getting-started)
- [Testing](#testing)
- [Production deployment](#production-deployment)
- [Observability & health](#observability--health)
- [Security notes](#security-notes)

---

## Features

- 🎙️ **Voice-first console** — push-to-talk speech recognition with live interim captions and
  browser TTS playback of every reply (graceful text fallback on unsupported browsers).
- 🤖 **Autonomous agent** — a local Ollama server runs `Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M`;
  replies are generated with a **structured-output schema** (JSON-constrained) under a curated
  system prompt that enforces empathy, brevity and safe escalation behaviour.
- 📚 **RAG knowledge base** — documents are chunked (700 chars / 120 overlap), embedded by the
  local Ollama embedding model (`Qwen3-Embedding-0.6B-GGUF:Q8_0`) and stored in a PostgreSQL
  `knowledge_chunks` table; retrieval is top-4 cosine similarity with a distance cutoff and
  Redis-cached results — **no separate vector database**.
- 🛡️ **LLM alert classification** — every customer utterance is classified by the same Ollama chat
  model (JSON-schema-constrained category + confidence) into one of eight support categories;
  severity blends the verdict with keyword heuristics. Alerts above the high-severity threshold
  surface on the agent dashboard (keyword `heuristic_classify` is the fallback).
- 🔐 **JWT auth + RBAC** — access/refresh token pair (bcrypt password hashing), three roles
  (`customer` / `agent` / `admin`) enforced by dependency guards on every protected route.
- ⚡ **Background processing** — Celery (Redis broker) handles alert classification and knowledge
  ingestion with retries and automatic synchronous fallback when the broker is down.
- 🚦 **Operational hardening** — Redis-backed per-IP rate limiting (fail-open), request IDs,
  structured logging, gzip compression, CORS allow-list and liveness/readiness probes.
- 📱 **Responsive UI** — dark-theme React 19 SPA with mobile bottom navigation, Android-style
  bottom sheets, confirm/input dialogs and toast notifications.

---

## Architecture

```mermaid
flowchart LR
  subgraph Browser["Browser — React 19 SPA"]
    UI["Voice console · dashboards"]
    STT["SpeechRecognition (STT)"]
    TTS["SpeechSynthesis (TTS)"]
  end
  PROXY["Nginx (prod) / Vite proxy (dev)"]

  subgraph FASTAPI["FastAPI backend :8000"]
    REST["REST /api/v1/*"]
    WSS["WS /api/v1/ws/{session_id}"]
    SVC["services: conversation · rag · llm · auth · cache · alerts"]
  end

  WORKER["Celery worker"]
  PG[("PostgreSQL 16")]
  REDIS[("Redis 7")]
  OLLAMA["Ollama server :11434<br/>(chat + embedding GGUF models)"]

  Browser -- "REST + WSS (/api)" --> PROXY
  PROXY --> REST
  PROXY <--> WSS
  STT --> UI
  UI --> TTS
  REST --> SVC
  WSS --> SVC
  SVC --> PG
  SVC --> REDIS
  SVC --> OLLAMA
  REST -- "enqueue tasks" --> REDIS
  REDIS --> WORKER
  WORKER --> PG
  WORKER --> OLLAMA
```

**Conversation pipeline** (one user utterance → one reply):

1. Client sends the recognised text (`POST /api/v1/chat/message`, or a WebSocket `user_transcript`).
2. Text is sanitised: control characters stripped, whitespace collapsed, capped at 2 000 chars.
3. The user turn is persisted; the last 8 turns are loaded as conversation history.
4. The RAG index is queried (Redis-cached); relevant excerpts are formatted into the system prompt.
5. The Ollama chat engine generates the reply **in a threadpool** (the event loop stays responsive),
   with the response constrained to a structured-output JSON schema.
6. The assistant turn is persisted with its latency and model name.
7. A Celery task classifies the utterance (Ollama structured output; heuristic fallback) and creates
   an `Alert` row.
8. The reply (text, source citations, latency, `alert_pending`) is returned and spoken via TTS.

## Tech stack

| Layer | Technology | Notes |
| --- | --- | --- |
| Backend framework | FastAPI ≥ 0.115 · Starlette · Uvicorn | App factory in `backend/app/main.py` (`app.main:app`) |
| Language | Python 3.11 | Fully annotated, `from __future__ import annotations` everywhere |
| Database | PostgreSQL 16 · SQLAlchemy 2.0 (ORM 2.0 style) | Local PostgreSQL database, PostgreSQL-only |
| Cache / broker | Redis 7 | JSON cache, RAG result cache, rate limiting, Celery broker + result backend |
| Task queue | Celery ≥ 5.4 | JSON-only, `task_acks_late`, prefetch = 1 |
| Auth | PyJWT (HS256) · bcrypt | Bearer tokens; access 30 min, refresh 7 days |
| LLM | `hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M` via the Ollama client | Structured-output JSON schemas; no torch/transformers in the app |
| Classifier | Same Ollama chat model, classification JSON schema | Runs inside the Celery worker only; heuristic fallback |
| Vector search | Ollama `hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0` + PostgreSQL `knowledge_chunks` table | In-process cosine similarity; no external vector DB |
| Frontend | React 19 · Vite 8 | SPA in `frontend/` |
| Routing | react-router-dom 7 | Auth + role guards on nested routes |
| Styling | Tailwind CSS 3 (PostCSS + Autoprefixer) | Dark slate theme, custom `pulse-ring` animation |
| Speech | Web Speech API (`SpeechRecognition`, `SpeechSynthesis`) | Chrome/Edge/Safari 14.1+ for STT |
| Linting | ESLint 10 (js-recommended, react-hooks, react-refresh) | `npm run lint` |
| Tests | pytest ≥ 8 | Unit tests, no ML stack required |
| Dev infra | docker compose — `postgres:16-alpine` + `redis:7-alpine` | Only infrastructure is containerised |
| Images | backend `python:3.11-slim` · frontend `node:20-alpine` → `nginx:1.27-alpine` | Build context is the repo root |

---

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI factory, lifespan, middlewares, routers
│   │   ├── api/
│   │   │   ├── deps.py              # DB session, auth, RBAC guards, pagination
│   │   │   ├── middleware.py        # request logging (X-Request-ID) + rate limiting
│   │   │   └── v1/                  # auth, users, sessions, chat, alerts, knowledge, health, ws, router
│   │   ├── core/                    # config.py (pydantic-settings), logging.py
│   │   ├── db/                      # base.py (Base + TimestampMixin), session.py (engine, init_db)
│   │   ├── models/                  # User, ConversationSession, Message, Alert, KnowledgeDocument, KnowledgeChunk
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── services/                # auth, cache, ollama_client, llm, classifier, rag, conversation, alerts, customers
│   │   ├── tasks/                   # celery_app.py + tasks.py (5 tasks)
│   │   ├── utils/text.py            # sanitisation, chunking, prompt assembly, severity heuristics
│   │   └── data/knowledge_seed.json # 9 starter knowledge-base documents
│   ├── scripts/                     # migrate_auth.py, seed_knowledge.py (admin-gated CLI)
│   ├── tests/                       # pytest units (auth + text utils; no Ollama or DB required)
│   ├── requirements.txt
│   └── Dockerfile                   # python:3.11-slim, thin client image, non-root user
├── frontend/
│   ├── src/
│   │   ├── main.jsx                 # React root: BrowserRouter → Toast → Auth → App
│   │   ├── app/                     # App.jsx, routes.jsx, providers/ (AuthProvider, ToastProvider)
│   │   ├── components/              # layout/ (AppShell, BottomNav, ProtectedRoute), ui/, feedback/
│   │   ├── features/                # auth/, chat/, dashboard/, knowledge/, profile/, users/
│   │   └── lib/                     # api.js (fetch + token rotation), auth.js, format.js
│   ├── index.html · vite.config.js · tailwind.config.js · postcss.config.js · eslint.config.js
│   ├── package.json · package-lock.json
│   └── Dockerfile                   # node build stage → nginx runtime
├── nginx/nginx.conf                 # reverse proxy for the production web tier
├── docker-compose.yml               # local dev infra (PostgreSQL + Redis; optional Ollama profile)
└── README.md
```

## Backend

### Application structure

The backend is a strictly layered FastAPI application:

| Layer | Location | Responsibility |
| --- | --- | --- |
| Presentation | `app/api/v1/*` + `app/api/deps.py` | Routers, Pydantic validation, dependency injection, RBAC guards, pagination |
| Cross-cutting | `app/api/middleware.py` | Request logging (`X-Request-ID`) and Redis-backed rate limiting |
| Business logic | `app/services/*` | Conversation pipeline, auth, RAG, LLM, classifier, cache, alert/customer queries |
| Background | `app/tasks/*` | Celery app + tasks (classification, ingestion, reindex/delete, summarisation) |
| Data | `app/models/*`, `app/db/*` | SQLAlchemy 2.0 models, engine/session factory, startup schema creation |
| Contracts | `app/schemas/*` | Pydantic v2 request/response models (validation limits live here) |
| Utilities | `app/utils/text.py` | Dependency-free text helpers (unit-testable without the ML stack) |
| Configuration | `app/core/config.py` | Typed 12-factor settings loaded from env / `.env` (cached singleton) |

Heavy AI/IO resources are **lazy, thread-safe singletons** — `llm_engine`, `llm_classifier`,
`knowledge_index` (PostgreSQL-backed vectors) and `redis_cache` — so the `ollama` client only
contacts the server on first use and the API can boot and answer health checks before any model
is pulled.

Entry point `backend/app/main.py` → `create_app()`:

- **Lifespan**: optionally creates the schema (`CREATE_TABLES_ON_STARTUP`) and optionally pre-warms
  the LLM + classifier in background threads (`PRELOAD_MODELS`) so startup stays responsive.
- **Middleware stack** (see below), routers mounted under `API_V1_PREFIX` (`/api/v1`).
- `GET /` returns a service descriptor (name, version, API prefix, docs URL when enabled).
- A global exception handler converts unhandled errors into a generic
  `500 {"detail": "Internal server error"}` — internals are never leaked.
- In `ENVIRONMENT=production` the OpenAPI docs (`/docs`, `/redoc`, `/openapi.json`) are disabled.

### Middleware pipeline

Executed in this order (CORS wraps everything):

| Middleware | Behaviour |
| --- | --- |
| `CORSMiddleware` | Allow-list from `CORS_ORIGINS`, credentials enabled, all methods/headers |
| `RequestLoggingMiddleware` | One structured log line per request (`METHOD path → status (ms) request_id=…`) and an `X-Request-ID` response header (12 hex chars) |
| `RateLimitMiddleware` | Fixed 60-second window per client IP for `/api/*` paths (health endpoints excluded); budget `RATE_LIMIT_PER_MINUTE` (default 60); responds `429` + `Retry-After: 60`; **fails open** when Redis is unreachable |
| `GZipMiddleware` | Compresses responses ≥ 1 024 bytes |

### Database schema

```mermaid
erDiagram
    users           ||--o{ sessions  : "owns (user_id, ON DELETE SET NULL)"
    sessions        ||--o{ messages  : "contains (ON DELETE CASCADE)"
    sessions        ||--o{ alerts    : "raises (ON DELETE CASCADE)"
    messages        ||--o| alerts    : "classified (message_id, ON DELETE SET NULL)"
```

Every model inherits `TimestampMixin` (`created_at`, `updated_at`, server-side `now()`), and the
metadata uses deterministic constraint naming (Alembic-friendly).

| Table | Columns |
| --- | --- |
| `users` | `id` int PK · `email` varchar(255) unique + indexed · `hashed_password` (bcrypt) · `full_name` varchar(120) nullable · `role` varchar(16) indexed, default `customer` · `is_active` bool, default true |
| `sessions` | `id` varchar(36) UUID PK · `user_id` FK → `users.id` ON DELETE SET NULL, indexed · `customer_name` varchar(120) nullable · `channel` varchar(32) default `voice` · `language` varchar(16) default `en-US` · `status` varchar(16) default `active` (`active` \| `closed`) |
| `messages` | `id` int PK · `session_id` FK → `sessions.id` ON DELETE CASCADE, indexed · `role` varchar(16) (`user` \| `assistant`) · `content` text · `latency_ms` int nullable · `model` varchar(128) nullable |
| `alerts` | `id` int PK · `session_id` FK → `sessions.id` ON DELETE CASCADE, indexed · `message_id` FK → `messages.id` ON DELETE SET NULL · `category` varchar(64) indexed · `severity` float · `confidence` float · `scores` JSON · `summary` text nullable · `status` varchar(16) indexed, default `open` (`open` \| `acknowledged` \| `resolved`) · `provider` varchar(32) default `ollama` (`ollama` \| `heuristic` \| `manual`) |
| `knowledge_documents` | `id` int PK · `title` varchar(200) · `source` varchar(200) default `""` · `content` text · `chunk_count` int |
| `knowledge_chunks` | `id` int PK · `document_id` FK → `knowledge_documents.id` ON DELETE CASCADE, indexed · `chunk_index` int · `content` text · `title` varchar(200) · `source` varchar(200) · `embedding` JSONB (float vector from the Ollama embedding model) |

Schema management: `Base.metadata.create_all` runs at startup when
`CREATE_TABLES_ON_STARTUP=true`, followed by an idempotent dev-time patch that adds
`sessions.user_id` (+ FK on PostgreSQL) to databases created before auth existed. For production,
use Alembic migrations instead; `scripts/migrate_auth.py` performs the same migration manually and
is safe to re-run.

### AI / ML subsystem

**LLM engine — `app/services/llm.py`**

- Model `hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M` (configurable via `LLM_MODEL_NAME`),
  served by the local Ollama server at `OLLAMA_BASE_URL` (default `http://localhost:11434`) and
  accessed through the `ollama` Python client.
- Thread-safe lazy singleton. `generate()` calls `client.chat(..., format=REPLY_SCHEMA)` — a
  **structured-output JSON schema** (`{"reply": "..."}`) with `temperature=0.7` (floor 0.05),
  `top_p=0.9`, `repeat_penalty=1.1`, `num_predict=220` (all configurable). `chat_structured()`
  exposes the same path for arbitrary schemas. Parsed replies are sanitised afterwards — markdown
  fences stripped, responses truncated at `num_predict` repaired, stray quotes/newlines
  normalised — so the chat UI and TTS only ever receive clean plain text, never raw JSON.
- `load()` verifies the server and pulls the model once if missing (`PRELOAD_MODELS=true` warms
  it at startup); generation runs via `run_in_threadpool` so the async event loop is never
  blocked, and any failure is replaced by the static `FALLBACK_REPLY` — the conversation never
  breaks.

**Classifier — `app/services/classifier.py`**

- Uses the same Ollama chat model with a **classification JSON schema** (enum `category` +
  numeric `confidence`), loaded **only inside the Celery worker** (the API process never pays
  the inference cost).
- Candidate labels: `billing`, `technical issue`, `account access`, `refund or cancellation`,
  `product question`, `complaint`, `urgent escalation`, `general inquiry`.
- Output per message: top label, confidence, score map and a blended severity from
  `estimate_severity()` — category baseline + keyword boosts (legal threats, fraud, "cancel my
  account", … raise severity; medium keywords such as "refund", "broken" cap it at ≥ 0.5; low
  classifier confidence < 0.4 dampens it), clamped to 0–1.
- If Ollama is unreachable or returns an off-enum category, the Celery task degrades to
  `heuristic_classify()` (keyword mapping, provider `heuristic`) so **alerts are never lost**.

**RAG index — `app/services/rag.py`**

- Vectors are produced by the Ollama embedding model `EMBEDDING_MODEL_NAME`
  (`hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0`) and stored in the PostgreSQL `knowledge_chunks`
  table (`embedding JSONB`) — there is **no separate vector database**.
- **Single-writer pattern**: all writes (ingest/reindex/delete) are performed by the Celery worker;
  the API process only reads and queries.
- Query flow: embed the query, compute plain-python cosine similarity against every stored chunk
  (cosine distance = 1 − similarity, identical semantics to the previous ChromaDB store),
  take top-4 (`RAG_TOP_K`) filtered by `RAG_MAX_DISTANCE=1.2`, and cache in Redis under
  `rag:<sha1(text)>` with `CACHE_TTL_SECONDS=300`.
- `format_context_block()` renders hits as a numbered excerpt block appended to the system prompt;
  each snippet is capped at 500 chars in the prompt and 180 chars in API responses.

**Prompt assembly — `app/utils/text.py`**

- `SYSTEM_PROMPT` defines the agent persona: warm, concise spoken style (2–5 sentences), ground
  answers in the provided excerpts, never invent policies/prices/promises, apologise and offer a
  human escalation on sensitive topics, never reveal system internals.
- `build_chat_messages()` assembles `system (+ context block) → last HISTORY_WINDOW=8 turns → user`.
- `sanitize_user_text()` strips control characters, collapses whitespace and caps length.

### Background tasks (Celery)

`app/tasks/celery_app.py` — Redis broker (`db 1`) + result backend (`db 2`), JSON-only
serialisation, UTC, `task_acks_late=True`, `worker_prefetch_multiplier=1`:

```bash
celery -A app.tasks.celery_app:app worker --loglevel=INFO
```

| Task | Trigger | Retries | Behaviour |
| --- | --- | --- | --- |
| `tasks.classify_and_alert` | after every user message | 2 × 5 s | Ollama classification → creates an `alerts` row (`provider=ollama` or `heuristic`) |
| `tasks.ingest_knowledge` | `POST /knowledge/ingest`, `/knowledge/ingest-default` | 3 × 10 s | Persist `knowledge_documents` row and vector chunks in one transaction |
| `tasks.reindex_knowledge_document` | `PATCH /knowledge/documents/{id}` | 3 × 5 s | Re-chunk and re-index updated content |
| `tasks.delete_knowledge_document` | `DELETE /knowledge/documents/{id}` | 3 × 5 s | Remove the document's vector chunks and its metadata row |
| `tasks.summarize_session` | manual / ops invocation | — | ≤ 3-sentence CRM-style summary via the LLM |

**Graceful degradation:** when the broker is unreachable, the API falls back in-line — chat skips
classification and returns `alert_pending: false`, while knowledge ingest/update/delete are
processed synchronously (the response notes the fallback in `detail`).

### Configuration

All settings live in `backend/app/core/config.py` (`pydantic-settings`) and can be overridden via
environment variables or a `backend/.env` file (`case_sensitive`, unknown keys ignored).

| Variable | Default | Description |
| --- | --- | --- |
| `PROJECT_NAME` | `SecureVoice AI` | Service name (OpenAPI title, health payload) |
| `VERSION` | `1.0.0` | Reported by `/` and `/health` |
| `ENVIRONMENT` | `development` | `development` \| `production` (production disables the docs) |
| `DEBUG` | `false` | Debug flag |
| `API_V1_PREFIX` | `/api/v1` | Mount prefix for every router |
| `LOG_LEVEL` | `INFO` | Root logger level |
| `DATABASE_URL` | `postgresql+psycopg2://securevoice:securevoice@localhost:5432/securevoice` | SQLAlchemy URL (local PostgreSQL) |
| `DB_POOL_SIZE` | `10` | PostgreSQL pool size |
| `DB_MAX_OVERFLOW` | `20` | Pool overflow slots |
| `DB_ECHO` | `false` | SQL statement echo |
| `CREATE_TABLES_ON_STARTUP` | `true` | Dev convenience — use Alembic in production |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache + rate limiting |
| `CACHE_TTL_SECONDS` | `300` | JSON / RAG cache TTL |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-IP request budget per fixed minute window |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery results |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server (serves both models) |
| `OLLAMA_TIMEOUT` | `300` | Client timeout in seconds (CPU inference can be slow) |
| `LLM_MODEL_NAME` | `hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M` | Ollama chat model (structured output) |
| `EMBEDDING_MODEL_NAME` | `hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0` | Ollama embedding model (RAG vectors) |
| `LLM_MAX_NEW_TOKENS` | `220` | Generation cap (Ollama `num_predict`) |
| `LLM_TEMPERATURE` | `0.7` | Sampling temperature (floor 0.05) |
| `PRELOAD_MODELS` | `false` | Verify/pull the Ollama models in background threads at startup |
| `HISTORY_WINDOW` | `8` | Chat turns kept in the LLM prompt |
| `RAG_CHUNK_SIZE` | `700` | Chunk size in characters |
| `RAG_CHUNK_OVERLAP` | `120` | Chunk overlap in characters |
| `RAG_TOP_K` | `4` | Chunks retrieved per query |
| `RAG_MAX_DISTANCE` | `1.2` | Cosine distance cutoff for relevance |
| `ALERT_HIGH_SEVERITY` | `0.75` | "High severity open" dashboard threshold |
| `JWT_SECRET_KEY` | `change-me-in-production` | HS256 signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access-token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh-token TTL |
| `MAX_MESSAGE_CHARS` | `2000` | User-message cap (schema + sanitiser) |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost", "http://127.0.0.1"]` | JSON list of allowed origins |

Two extra keys are consumed **only by the `postgres` compose service** from the same
`backend/.env` file: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (the app itself ignores
them). Keep them consistent with `DATABASE_URL`.

## API reference

Base URL: **`/api/v1`** (dev proxy: Vite forwards `/api` → `http://localhost:8000`; production:
Nginx does the same). Interactive OpenAPI docs at `http://localhost:8000/docs` (disabled in
production). All request/response bodies are JSON; all timestamps are ISO-8601 UTC.

### REST endpoints

**Auth** (`backend/app/api/v1/auth.py`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | public | Create an account — always role `customer`. `201` → `UserOut`; `409` duplicate email |
| `POST` | `/auth/login` | public | JSON login `{email, password}` → `TokenPair` |
| `POST` | `/auth/token` | public | OAuth2 password form (`username` = email) — powers Swagger's *Authorize* |
| `POST` | `/auth/refresh` | public | `{refresh_token}` → fresh `TokenPair` |
| `GET` | `/auth/me` | bearer | Current user profile |
| `PATCH` | `/auth/me` | bearer | Update `full_name`; password change requires `current_password` (`400` when wrong) |

**Users** (`users.py`, admin only)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/users?limit=&offset=` | List accounts, newest first |
| `POST` | `/users` | Create an account with any role (`201`); `409` duplicate email |
| `PATCH` | `/users/{user_id}` | Change role / activation / name / password. Admins cannot demote or deactivate themselves (`400`) |
| `DELETE` | `/users/{user_id}` | Delete an account (`204`). Admins cannot delete themselves (`400`) |

**Health** (`health.py`, public)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness — always cheap, no dependency checks |
| `GET` | `/health/ready` | Readiness — checks PostgreSQL, Redis, the `knowledge_chunks` table and Ollama; `200 ready` or `503 degraded` with per-component status |

**Sessions** (`sessions.py`, bearer; ownership-aware)

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/sessions` | Start a session (`customer_name`, `channel`, `language` optional) → `201` |
| `GET` | `/sessions?limit=&offset=` | Customers see their own; agents/admins see all |
| `GET` | `/sessions/{session_id}` | Session detail incl. full transcript (customers: own only, else `404`) |
| `PATCH` | `/sessions/{session_id}` | Partial update — name / channel / language / status (`active` \| `closed`) |
| `POST` | `/sessions/{session_id}/close` | Mark the session `closed` (owner or staff) |
| `DELETE` | `/sessions/{session_id}` | Delete session + transcript (`204`; owner or admin) |

**Chat** (`chat.py`, bearer)

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/chat/message` | Body `{text (1–2000 chars), session_id?}` — omit `session_id` to auto-start a session. `404` unknown session · `422` empty after sanitisation |

**Alerts** (`alerts.py`, agent/admin; delete = admin only)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/alerts/summary` | Aggregated counters: total/open/acknowledged/resolved, `high_severity_open` (severity ≥ `ALERT_HIGH_SEVERITY`), total sessions/messages |
| `POST` | `/alerts` | Manually raise an alert on an existing session (`session_id`, `category`, `severity` 0–1, `summary`) — `404` unknown session |
| `GET` | `/alerts` | Filters: `status=open\|acknowledged\|resolved`, `session_id`, `min_severity`, `limit` ≤ 200, `offset`; newest first; includes enriched customer profiles |
| `PATCH` | `/alerts/{alert_id}` | Triage update — status and/or category / severity / summary (`422` when no fields) |
| `DELETE` | `/alerts/{alert_id}` | Permanently delete an alert (`204`, admin only) |

**Knowledge base** (`knowledge.py`; read = agent/admin, writes = admin)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/knowledge/documents` | List ingested documents incl. content and chunk counts |
| `GET` | `/knowledge/stats` | `{documents, indexed_chunks}` — PostgreSQL counts (documents + embedded chunks) |
| `PATCH` | `/knowledge/documents/{document_id}` | Update title/source/content; vectors are re-indexed asynchronously |
| `POST` | `/knowledge/ingest` | Ingest 1–50 documents `{documents: [{title, source?, content}]}` — Celery-queued with synchronous fallback |
| `POST` | `/knowledge/ingest-default` | Ingest the bundled starter set (`backend/app/data/knowledge_seed.json`, 9 policy documents) |
| `DELETE` | `/knowledge/documents/{document_id}` | Remove vector chunks + metadata row (`204`) |

**Root** — `GET /` (public): `{service, version, api, docs}`.

### Representative payloads

`TokenPair` — returned by login/refresh:

```json
{
  "access_token": "eyJhbGciOi…",
  "refresh_token": "eyJhbGciOi…",
  "token_type": "bearer",
  "role": "customer",
  "expires_in": 1800
}
```

`ChatReply` — returned by `POST /chat/message` (and the WebSocket `assistant_reply` frame):

```json
{
  "session_id": "6b2e1c34-…",
  "reply": "Standard shipping takes 3-5 business days…",
  "user_message_id": 41,
  "assistant_message_id": 42,
  "latency_ms": 812,
  "model": "Qwen/Qwen2.5-0.5B-Instruct",
  "sources": [
    {
      "document_id": 2,
      "title": "Shipping and delivery",
      "source": "policies/shipping.md",
      "chunk_index": 0,
      "distance": 0.31,
      "snippet": "Standard shipping takes 3-5 business days…"
    }
  ],
  "alert_pending": true
}
```

`AlertOut` — staff-facing alert with enriched customer context:

```json
{
  "id": 7,
  "session_id": "6b2e1c34-…",
  "message_id": 41,
  "customer_id": 3,
  "customer_email": "jane@example.com",
  "customer_name": "Jane Doe",
  "customer": {
    "id": 3, "email": "jane@example.com", "full_name": "Jane Doe",
    "role": "customer", "is_active": true, "member_since": "2026-01-04T10:12:00Z",
    "total_sessions": 4, "total_messages": 22, "total_alerts": 2, "last_activity": "…"
  },
  "session_created_at": "2026-11-18T09:00:00Z",
  "category": "billing",
  "severity": 0.62,
  "confidence": 0.81,
  "scores": { "billing": 0.81, "complaint": 0.07 },
  "summary": "I was charged twice on my card…",
  "status": "open",
  "provider": "ollama",
  "created_at": "2026-11-18T09:01:12Z"
}
```

(`scores` always contains all eight label scores; `customer` is `null` for guest sessions.)

### WebSocket protocol

Endpoint: `ws(s)://<host>/api/v1/ws/{session_id}?token=<access_token>` (`backend/app/api/v1/ws.py`).

- **Auth**: browsers cannot set headers during the handshake, so the access token is passed as a
  query parameter. Missing/invalid token or deactivated account → handshake rejected
  (`close code 1008` / HTTP 403). Customers may only connect to their **own** sessions.
- On accept the server sends `{"type": "ready", "session_id": "…", "user_id": 3}`.
- Client → server: `{"type": "user_transcript", "text": "…"}`. Anything else (or malformed JSON)
  answers `{"type": "error", "detail": "…"}` without closing.
- Server → client: `{"type": "assistant_reply", …ChatReply fields}`.
- Unknown session → error frame then close `4404`; unexpected server error → close `1011`.
- Both Vite (dev) and Nginx (prod) proxy WebSocket upgrades for `/api/`.
- The shipped web console currently uses the REST chat endpoint; the socket is available for
  realtime voice clients.

### Error semantics

| Status | Raised when |
| --- | --- |
| `400` | Bad request (admin self-demotion/deactivation/deletion, wrong current password) |
| `401` | Missing/expired/invalid bearer token; wrong credentials; expired refresh token |
| `403` | Role missing (`require_agent` / `require_admin`); deactivated account; WS handshake denied |
| `404` | Unknown session/user/alert/document — **ownership violations also surface as 404** (no existence leak) |
| `409` | Duplicate email on register / user creation |
| `422` | Pydantic validation errors, empty update payloads, empty text after sanitisation |
| `429` | Rate limit exceeded (`Retry-After: 60`) |
| `500` | Unhandled errors → generic `{"detail": "Internal server error"}` |

---

## Authentication & RBAC

**Tokens** (`app/services/auth.py`): HS256 JWTs signed with `JWT_SECRET_KEY`. Claims: `sub` (user
id), `role`, `type` (`access` | `refresh`), `iat`, `exp`, `jti`. Verification is strict — signature,
expiry **and** token type are all enforced (a refresh token can never authenticate as an access
token). Passwords are bcrypt-hashed with per-user salts.

**Client behaviour**: the SPA stores both tokens and the profile in `localStorage`, attaches
`Authorization: Bearer <access>` to every request, and on any `401` silently rotates the pair via
`/auth/refresh` and retries the original request **once**; if the refresh also fails it clears the
session and emits a global "unauthorized" event that returns the app to the login screen.

**Guards** (`app/api/deps.py`): `get_current_user` (bearer → active user),
`require_agent` (`agent` | `admin`), `require_admin` (`admin`), plus reusable
`limit`/`offset` pagination parameters.

| Capability | customer | agent | admin |
| --- | :---: | :---: | :---: |
| Chat (REST + WS), own session CRUD, profile | ✅ | ✅ | ✅ |
| List / read all sessions & transcripts | — | ✅ | ✅ |
| Alerts: view, triage (acknowledge/resolve), raise | — | ✅ | ✅ |
| Alerts: delete | — | — | ✅ |
| Knowledge: list documents / stats | — | ✅ | ✅ |
| Knowledge: ingest / update / delete | — | — | ✅ |
| User management | — | — | ✅ |

## Frontend

### Structure

```
frontend/src/
├── main.jsx                    # StrictMode → BrowserRouter → ToastProvider → AuthProvider → App
├── index.css                   # Tailwind layers + slim scrollbars, sheet/modal animations
├── app/
│   ├── App.jsx                 # ErrorBoundary wrapping the route table
│   ├── routes.jsx              # Route table with <RequireAuth> / <RequireRole> guards
│   └── providers/
│       ├── AuthProvider.jsx    # user state, login/register/logout/refreshUser, isStaff/isAdmin
│       └── ToastProvider.jsx   # success / error / info toast queue (auto-dismiss)
├── components/
│   ├── layout/
│   │   ├── AppShell.jsx        # sticky header, role-filtered nav, StatusPill, sign-out, <Outlet/>
│   │   ├── BottomNav.jsx       # mobile bottom navigation (role-aware)
│   │   └── ProtectedRoute.jsx  # RequireAuth (→ /login) and RequireRole (→ home) guards
│   ├── ui/                     # Badge, Button, Card, ConfirmDialog, EmptyState, Input/Textarea,
│   │                           # InputDialog, Spinner, StatusPill (live API health dot)
│   └── feedback/               # ErrorBoundary, NotFound
├── features/
│   ├── auth/AuthScreen.jsx
│   ├── chat/                   # VoiceConsolePage, AlertBanner, MessageBubble,
│   │                           # hooks/useSpeechRecognition.js, hooks/useSpeechSynthesis.js
│   ├── dashboard/              # AgentDashboardPage, AlertCard, RaiseAlertForm
│   ├── knowledge/KnowledgePage.jsx
│   ├── profile/ProfilePage.jsx
│   └── users/UsersPage.jsx
└── lib/
    ├── api.js                  # fetch wrapper + endpoint helpers + silent token rotation
    ├── auth.js                 # localStorage token/user storage + forced-logout events
    └── format.js               # date/time formatters, severity & role badge styles, initials
```

### Routing & access control

| Route | Component | Access |
| --- | --- | --- |
| `/login` | `AuthScreen` | public — login/register toggle; registration auto-signs in |
| `/` | `VoiceConsolePage` | authenticated |
| `/profile` | `ProfilePage` | authenticated |
| `/dashboard` | `AgentDashboardPage` | `agent`, `admin` |
| `/knowledge` | `KnowledgePage` | `admin` |
| `/users` | `UsersPage` | `admin` |
| `*` | `NotFound` | public |

`RequireAuth` redirects unauthenticated visitors to `/login`; `RequireRole` redirects forbidden
roles home. Navigation (desktop header + mobile bottom bar) is filtered by role, and the backend
enforces the same rules — the UI only mirrors RBAC.

### State & data access

- **No global state library** — React context providers plus per-page hooks. `AuthProvider` holds
  the session user (hydrated from `localStorage`), exposes `login/register/logout/refreshUser` and
  the derived `isStaff` / `isAdmin` flags, and reacts to forced-logout events.
- **`lib/api.js`** — a single `request()` wrapper: JSON bodies, Bearer header, `204 → null`,
  network failures mapped to `ApiError("Backend unreachable…", 0)`, and **one silent
  refresh-and-retry** on `401` before falling back to a forced logout. Domain helpers cover auth,
  users, sessions, chat, alerts, knowledge and health.
- **`lib/auth.js`** — storage keys `securevoice:access-token`, `securevoice:refresh-token`,
  `securevoice:user`, `securevoice:session-id` (the chat session id is cleared on logout so the
  next user never inherits another user's conversation).
- **`StatusPill`** polls `GET /health` every 30 s and renders an *API online / offline* dot.

### Voice console (`/`)

- **Session bootstrap** — reuses the stored session id (validating it via `GET /sessions/{id}`) or
  creates a fresh one; the active id persists across reloads.
- **STT** — `useSpeechRecognition` wraps the browser `SpeechRecognition` API (push-to-talk, one
  utterance per start, live interim captions, permission-denied error mapping). Unsupported
  browsers degrade to text input with a hint.
- **Send** — optimistically appends the user bubble, posts to `/chat/message`, adopts the returned
  `session_id`, renders the assistant bubble (with its RAG sources) and schedules TTS playback.
- **TTS** — `useSpeechSynthesis` speaks replies as ≤ 180-char sentence chunks (280-char hard cap)
  with a language-matched voice; a toggle disables it; speaking is cancelled when the mic starts or
  the session changes.
- **Alert banner** — staff only: polls the newest open alert for the session and shows a banner
  when severity ≥ 0.7 (customers skip the call entirely).
- Session rename (inline dialog), delete-with-confirm (then a fresh session), jump-to-latest button,
  day separators and auto-scroll keep the transcript manageable.

### Agent dashboard (`/dashboard`)

- KPI cards from `/alerts/summary`: open, high-severity open, resolved, sessions, messages.
- Status filter tabs (`open` / `acknowledged` / `resolved` / `all`), auto-refresh every 15 s.
- Inline triage (acknowledge / resolve) per alert card; admin-only delete with confirm dialog.
- **Raise alert** form (manual staff ticket) — bottom sheet with FAB on mobile, inline card on
  desktop.

### Knowledge page (`/knowledge`, admin)

- Stats header (documents + indexed chunks), one-click **seed default** (9 bundled policy
  documents), add document, inline edit (triggers async re-index), delete with confirm; lists
  refresh ~2.5 s after queued operations.

### Users page (`/users`, admin)

- Create accounts with any role, change role via dropdown, deactivate/reactivate, set a new
  password (min 8 chars), delete — all self-actions on the admin's own row are disabled.

### Profile page (`/profile`)

- Display-name update and password change (current password re-verified server-side), role badge
  and member-since info.

## Getting started

### Prerequisites

- Python 3.11+, Node.js 20+, Docker (for the dev infrastructure)
- [Ollama](https://ollama.com/download) — all AI inference (chat + embeddings) runs there

### 1. Configure the environment

Create **`backend/.env`** — the single source of configuration for both the compose stack and the
app (see the [configuration table](#configuration) for every option):

```dotenv
# --- Database (must match the compose Postgres) ---
POSTGRES_USER=securevoice
POSTGRES_PASSWORD=securevoice
POSTGRES_DB=securevoice
DATABASE_URL=postgresql+psycopg2://securevoice:securevoice@localhost:5432/securevoice

# --- Redis ---
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# --- Security ---
JWT_SECRET_KEY=change-me-in-production

# --- Ollama models ---
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL_NAME=hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M
EMBEDDING_MODEL_NAME=hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
# PRELOAD_MODELS=true

# --- App ---
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:5173"]
```

### 2. Start the infrastructure

```bash
docker compose up -d        # PostgreSQL :5432 + Redis :6379, named volumes persist data
```

### 3. Pull the Ollama models (once)

```bash
ollama pull hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M
ollama pull hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
# `ollama serve` runs automatically with the desktop app; verify with `ollama list`
```

> Prefer containerised Ollama? `docker compose --profile ollama up -d` starts an `ollama/ollama`
> service on :11434 (pull the models inside it with `docker compose exec ollama ollama pull …`).

### 4. Run the backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt                       # no torch/transformers needed
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on first boot (`CREATE_TABLES_ON_STARTUP`). Swagger UI:
<http://localhost:8000/docs>.

### 5. Run the Celery worker (recommended, optional)

```bash
# from backend/ with the venv active
celery -A app.tasks.celery_app:app worker --loglevel=INFO
```

Without a worker the app still works — alert classification is skipped and knowledge operations run
synchronously.

### 6. Run the frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 — /api is proxied to :8000 (REST + WebSocket)
```

Other scripts: `npm run build` (production bundle to `dist/`), `npm run preview`, `npm run lint`.

### 7. Seed the knowledge base (admin)

- **UI/API** — sign in as an admin → Knowledge page → *Seed default knowledge base*
  (or `POST /api/v1/knowledge/ingest-default`).
- **CLI** — `python -m scripts.seed_knowledge --email admin@example.com` (password prompted;
  the script enforces the same admin RBAC rules as the API).

### 8. Bootstrap the first admin

Open registration always creates `customer` accounts, so promote the first admin manually:

```bash
docker compose exec postgres psql -U securevoice -d securevoice \
  -c "UPDATE users SET role = 'admin' WHERE email = 'you@example.com';"
```

(Or create staff accounts via `POST /api/v1/users` from an existing admin.) The admin can then
onboard agents and customers from the Users page.

## Testing

```bash
cd backend
python -m pytest -q
```

19 unit tests, none of which require PostgreSQL, Redis or the ML stack:

- `tests/test_auth_utils.py` — bcrypt roundtrips, malformed-hash tolerance, JWT access/refresh
  roundtrips, token-type enforcement, tamper rejection, TTL exposure.
- `tests/test_text_utils.py` — sanitisation, chunking (size/overlap/content), severity estimation,
  heuristic classification, prompt assembly.

## Production deployment

Both images are built **from the repository root** (their `COPY` paths assume it):

```bash
docker build -f backend/Dockerfile  -t securevoice-backend  .
docker build -f frontend/Dockerfile -t securevoice-frontend .
```

- **Backend** — `python:3.11-slim` (a thin client image — all model weights live on the Ollama
  server), non-root `appuser`, `HEALTHCHECK` on `/api/v1/health`, and
  `uvicorn app.main:app --workers 1`. Point `OLLAMA_BASE_URL` at the Ollama host
  (`http://host.docker.internal:11434` when Ollama runs on the Docker host). The same image runs
  the worker: `celery -A app.tasks.celery_app:app worker`.
- **Frontend** — Node 20 build stage → `nginx:1.27-alpine` serving the hashed `dist/` bundle.
  `nginx/nginx.conf` reverse-proxies `/api/` (REST **and** WebSocket upgrade) plus the docs routes
  to `backend:8000`, applies gzip, a 30 r/s request-limit zone, security headers, immutable asset
  caching and an SPA fallback, and health-checks `/api/v1/health`.
- Set `ENVIRONMENT=production` to disable `/docs`, `/redoc` and `/openapi.json`.
- **Checklist**: strong `JWT_SECRET_KEY`; TLS terminated at the proxy; tight `CORS_ORIGINS`;
  scale Ollama (or a GPU host) independently of the stateless API containers;
  tune `RATE_LIMIT_PER_MINUTE`; adopt Alembic migrations instead of startup `create_all`; supply
  real `POSTGRES_*` credentials.

## Observability & health

| Probe | Endpoint | Checks | Result |
| --- | --- | --- | --- |
| Liveness | `GET /api/v1/health` | none (always cheap) | `200` with service metadata |
| Readiness | `GET /api/v1/health/ready` | PostgreSQL `SELECT 1`, Redis `PING`, `knowledge_chunks` count, Ollama `list` | `200 ready` or `503 degraded` + per-component status |
| Tracing | every response | `X-Request-ID` header + structured request log line | correlation across logs |
| Frontend | `StatusPill` | polls `/health` every 30 s | online/offline indicator |

**Fail-open philosophy** — dependency outages degrade features, never the conversation:

| Outage | Behaviour |
| --- | --- |
| Redis down | Cache misses, rate limiting opens, Celery enqueue skipped (`alert_pending: false`) |
| Broker down (knowledge ops) | Synchronous fallback processing, noted in the response |
| Ollama unreachable (RAG) | Embeddings fail → RAG returns no context; the LLM answers ungrounded |
| LLM failure | Static `FALLBACK_REPLY` is returned and persisted with `model: "fallback"` |
| Ollama classification failure | Keyword `heuristic_classify` produces the alert instead |

## Security notes

- bcrypt password hashing; strict JWT verification (signature, expiry, type); deactivated accounts
  are rejected on every surface, including WebSocket handshakes.
- Ownership scoping everywhere: customers can only reach their own sessions (violations surface as
  `404`, never `403`, to avoid existence leaks); staff have wide read access by design.
- Admin self-lockout protections (cannot demote/deactivate/delete their own account).
- Input sanitisation (control characters, whitespace collapse, 2 000-char cap) on REST and WS.
- Per-IP rate limiting, gzip, CORS allow-list, non-root container user, `server_tokens off` and
  security headers in Nginx.
- Privacy posture: STT/TTS run in the browser; only the recognised text reaches the server.
  Transcripts are stored for support quality (the bundled policy docs describe a 12-month
  retention / GDPR-deletion posture) and session/document deletion endpoints are provided.

**Known limitations to address before real production use:**

- Tokens (and the profile) live in `localStorage` — an XSS would expose them; consider
  http-only cookies for high-security deployments.
- Refresh tokens are not rotated and there is no revocation/blacklist (`jti` is issued but unused).
- Embeddings and chat are served by Ollama; vectors live in PostgreSQL `knowledge_chunks` and
  document deletes cascade there, keeping the index and metadata consistent.
- Schema changes rely on `create_all` + dev-time patches locally; use Alembic in production.










