# Memoire

A living-memory system. Ingests documents, builds a knowledge graph backed by evidence, evolves facts over time through consolidation and inference, and answers questions with citations traced to source text.

The graph maintains fact lifecycle (active / deprecated / disputed), runs declarative inference rules, and grounds every claim -- including inferred ones -- in real document quotes.

---

## Architecture

```
                     +-----------+
                     |  React UI |   Vite + React 19 + Tailwind v4
                     +-----+-----+
                           |
               +-----------+-----------+
               |                       |
        +------+------+       +-------+-------+
        |  Auth API   |       |  Memory API   |
        |  :8001      |       |  :8000        |
        +------+------+       +---+-----------+
               |                  |
               +--------+---------+
                        |
              +---------+---------+
              |   PostgreSQL 16   |
              |  + pgvector       |
              |  + Apache AGE     |
              +---------+---------+
                        |
              +---------+---------+
              |      Worker       |
              | (background jobs) |
              +-------------------+
```

| Service | Path | Port | Role |
|---------|------|------|------|
| Frontend | `apps/web/` | 5173 | React 19, Vite 7, Tailwind v4 |
| Auth API | `apps/services/auth/` | 8001 | Signup, login, JWT, spaces |
| Memory API | `apps/services/memory/` | 8000 | Chat, search, notes, documents, profiles, inference rules |
| Worker | `apps/worker/` | -- | Ingestion, graph extraction, consolidation, inference |
| Database | `docker/postgresql/` | 5433 | PostgreSQL 16 + pgvector 0.7.4 + Apache AGE 1.5.0 |

---

## Pipeline

### Ingestion

Document uploaded or chat saved -> `ingestion_jobs` queue -> worker picks it up:

1. Extract text (URL / PDF / raw text)
2. Chunk with paragraph/sentence-aware splitting + overlap (800 chars, 120 overlap)
3. Embed via OpenAI `text-embedding-3-small` (1536d)
4. Store chunks with character offsets

### Graph Extraction

Per chunk, a hybrid NER + LLM pipeline:

1. SpaCy NER (regex fallback) extracts candidate entities
2. LLM verifier accepts/rejects, extracts relations with quote offsets
3. Entities -> AGE vertices; relations -> typed edges with stable keys (`src_key|relation|dst_key`)
4. Evidence stored in `graph_evidence` with exact quote, char offsets, and confidence

### Consolidation

After ingestion, `memory_consolidation` job fires:

- No competing edges -> `active`
- Additive relations (likes, has_skill) -> always `active`
- Higher confidence wins -> new `active`, old `deprecated`
- Conflicting at similar confidence -> both `disputed`
- All transitions logged in `memory_events`

### Inference

After consolidation, `memory_inference` job fires:

- Loads enabled rules from `inference_rules` table
- Each rule is a Cypher pattern (e.g. "A works_at B, B located_in C -> A works_in C")
- Only uses `explicit` + `active` edges as support
- Creates `inferred` edges with `support_edges` provenance
- Deduplicates via `graph_edge_map`

The inference step also runs rule discovery: scans existing relation types and asks the LLM to suggest new rules, which are stored for future runs.

### Query

1. **Vector recall** -- pgvector HNSW finds top-k chunks
2. **Seed building** -- chunks -> evidence -> edge keys -> entity keys
3. **Graph expansion** (2-pass) -- explicit+active edges first; if < 12 results, second pass includes inferred
4. **Evidence pack** -- explicit edges cite their own evidence; inferred edges cite their support_edges' evidence
5. **LLM answer** -- system prompt enforces `[citation_id]` references; response includes `MemoryCitation[]` with score, snippet, timestamp

Inferred facts are still backed by real document text.

---

## Project Structure

```
memoire/
├── docker-compose.yml
├── docker/postgresql/Dockerfile
│
├── apps/
│   ├── services/
│   │   ├── auth/
│   │   │   ├── main.py                  # FastAPI app + routes
│   │   │   ├── auth.py                  # Password hashing, JWT creation
│   │   │   ├── auth_deps.py             # JWT dependency
│   │   │   ├── models.py
│   │   │   ├── database.py
│   │   │   ├── deps.py
│   │   │   └── schema/schemas.py
│   │   │
│   │   ├── memory/app/
│   │   │   ├── main.py                  # FastAPI app + router registration
│   │   │   ├── auth_deps.py, database.py, deps.py, models.py, schema.py
│   │   │   │
│   │   │   ├── routers/
│   │   │   │   ├── chats.py             # POST /chats (query + citations)
│   │   │   │   ├── chat_save.py         # POST /chat_save
│   │   │   │   ├── documents.py         # Document upload / list
│   │   │   │   ├── notes.py             # Notes CRUD
│   │   │   │   ├── search.py            # Vector search
│   │   │   │   ├── profile.py           # User profile
│   │   │   │   ├── inference_rules.py   # Rules CRUD + toggle
│   │   │   │   └── cursor.py            # Keyset pagination encoding
│   │   │   │
│   │   │   └── utils/
│   │   │       ├── retrieval/
│   │   │       │   ├── vector.py         # pgvector semantic recall
│   │   │       │   ├── graph_expand.py   # Multi-hop graph traversal (2-pass)
│   │   │       │   ├── graph_edges.py    # Read edge metadata from AGE
│   │   │       │   ├── seeds.py          # Chunk -> edge -> entity seed building
│   │   │       │   └── evidence.py       # Grounded evidence builder
│   │   │       ├── graph/
│   │   │       │   └── age.py            # GRAPH_NAME, AGE setup SQL
│   │   │       ├── llm/
│   │   │       │   ├── gateway.py        # OpenAI / Groq with retries + backoff
│   │   │       │   └── embeddings.py     # text-embedding-3-small
│   │   │       └── infra/
│   │   │           ├── limits.py         # Sliding-window rate + concurrency limiters
│   │   │           └── metrics.py        # Counter-based observability
│   │   │
│   │   └── schemas/                       # SQL migrations (run in order)
│   │       ├── 001_core.sql
│   │       ├── 002_graph.sql
│   │       ├── 003_evolution.sql
│   │       ├── 004_profiles.sql
│   │       ├── 005_inference.sql
│   │       ├── 006_metrics.sql
│   │       └── seed.sql
│   │
│   ├── worker/
│   │   ├── worker.py                     # Main loop (claim -> process -> done/fail)
│   │   ├── db.py, models.py, llm_client.py
│   │   ├── metrics.py
│   │   ├── ingestion/
│   │   │   ├── extractors.py             # Text extraction (URL, PDF)
│   │   │   ├── chunking.py              # Paragraph/sentence chunking
│   │   │   └── embeddings.py            # OpenAI embeddings
│   │   ├── graph/
│   │   │   ├── age.py                    # AGE vertex/edge upsert
│   │   │   ├── key.py                    # Stable key generation
│   │   │   ├── extract_hybrid.py         # NER + LLM extraction
│   │   │   └── persist.py               # Persist extraction -> graph + evidence
│   │   ├── evolution/
│   │   │   ├── consolidate.py            # Update / deprecate / dispute
│   │   │   └── infer_engine.py           # Generic inference rule executor
│   │   └── rules/
│   │       ├── discovery.py              # Discover existing relation types
│   │       ├── generator.py              # LLM-based rule suggestion
│   │       └── storage.py               # Store rules to DB
│   │
│   └── web/                               # Frontend
│       ├── src/
│       │   ├── App.jsx
│       │   ├── api/client.js             # API client (proxy to :8000 / :8001)
│       │   ├── app/routes.jsx            # /, /login, /app (protected)
│       │   ├── components/
│       │   │   ├── layout/               # AppShell, LeftRail, TopSpaceChips,
│       │   │   │                         # CenterCanvas, RightContext
│       │   │   └── chat/BottomComposer.jsx
│       │   ├── hooks/useLoadSpaces.js
│       │   ├── pages/                    # LoginPage, AppPage
│       │   ├── store/                    # Zustand (auth, space)
│       │   └── styles/
│       └── package.json
```

---

## Database

### Core (`001_core.sql`)
- `users`, `user_passwords`, `user_oauth_identities`
- `spaces`, `user_spaces` (roles: owner / admin / viewer)
- `documents` (status: pending / processing / ready / failed)
- `chunks` -- embeddings as VECTOR(1536), character offsets for grounding
- `memory_items` -- notes, decisions
- `ingestion_jobs` -- job queue (document_ingest / memory_consolidation / memory_inference)
- `api_tokens`

### Graph (`002_graph.sql`)
- `memory_graph` -- Apache AGE graph (Entity vertices, typed relation edges)
- `graph_vertex_map` -- entity_key -> AGE vertex ID
- `graph_edge_map` -- edge_key -> AGE edge ID
- `graph_evidence` -- edge/entity -> document quote, char offsets, confidence

### Evolution (`003_evolution.sql`)
- `memory_events` -- audit log (update / deprecate / contradict / merge)

### Profiles (`004_profiles.sql`)
- `profiles` -- static + dynamic profile per user per space
- `profile_facts` -- individual facts with confidence and state

### Inference (`005_inference.sql`)
- `inference_rules` -- declarative patterns (JSON), toggleable

### Metrics (`006_metrics.sql`)
- `metrics_counters` -- simple counters per space

---

## API

### Auth (:8001)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | -- | Health check |
| POST | `/auth/signup` | -- | Create account + default space, returns JWT |
| POST | `/auth/login` | -- | Returns JWT |
| GET | `/me` | JWT | Current user + spaces |
| GET | `/spaces` | JWT | List spaces |

### Memory (:8000)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | -- | Health check |
| POST | `/chats` | JWT | Ask a question, get answer + grounded citations |
| POST | `/chat_save` | JWT | Save conversation to memory |
| POST | `/notes` | JWT | Create a note |
| POST | `/search` | JWT | Vector similarity search |
| POST | `/documents` | JWT | Upload document for ingestion |
| GET | `/profile/about` | JWT | Get profile text |
| POST | `/profile/about` | JWT | Set profile text |
| GET | `/inference-rules` | JWT | List rules for a space |
| POST | `/inference-rules` | JWT | Create / update a rule |
| POST | `/inference-rules/toggle` | JWT | Enable / disable a rule |

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker

### 1. Database

```bash
docker compose up -d
```

Builds PostgreSQL 16 with pgvector 0.7.4 and Apache AGE 1.5.0. Exposed on port 5433.

### 2. Schema

```bash
psql -h localhost -p 5433 -U memoire -d memoire
```

Run migrations in order:

```sql
\i apps/services/schemas/001_core.sql
\i apps/services/schemas/002_graph.sql
\i apps/services/schemas/003_evolution.sql
\i apps/services/schemas/004_profiles.sql
\i apps/services/schemas/005_inference.sql
\i apps/services/schemas/006_metrics.sql

-- optional dev seed data:
\i apps/services/schemas/seed.sql
```

### 3. Python

```bash
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r apps/services/auth/requirements.txt
pip install -r apps/services/memory/requirements.txt
pip install -r apps/worker/requirements.txt
```

### 4. Environment

Create `.env` in each service directory:

**`apps/services/auth/.env`**
```
DATABASE_URL=postgresql://memoire:memoire@localhost:5433/memoire
JWT_SECRET=<your-secret>
```

**`apps/services/memory/app/.env`**
```
DATABASE_URL=postgresql://memoire:memoire@localhost:5433/memoire
JWT_SECRET=<your-secret>
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...          # optional, for Groq provider
```

**`apps/worker/.env`**
```
DATABASE_URL=postgresql://memoire:memoire@localhost:5433/memoire
OPENAI_API_KEY=sk-...
GRAPH_ENABLED=1
```

### 5. Run

```bash
# Auth API
cd apps/services
python -m uvicorn auth.main:app --reload --port 8001

# Memory API
cd apps/services/memory
python -m uvicorn app.main:app --reload --port 8000

# Worker
cd apps/worker
python -m worker

# Frontend
cd apps/web
npm install && npm run dev
```

---

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | yes | -- | PostgreSQL connection string |
| `JWT_SECRET` | yes | -- | Shared between auth + memory services |
| `JWT_ALG` | no | `HS256` | |
| `OPENAI_API_KEY` | yes* | -- | Required for memory service and worker |
| `GROQ_API_KEY` | no | -- | Alternative chat provider |
| `OPENAI_CHAT_MODEL` | no | `gpt-4o-mini` | |
| `GROQ_CHAT_MODEL` | no | `llama-3.1-8b-instant` | |
| `GRAPH_ENABLED` | no | `1` | Set to `0` to skip graph extraction |
| `LLM_PROVIDER` | no | `stub` | Worker LLM provider (`stub` returns empty extractions) |
| `WORKER_POLL_SECONDS` | no | `2` | |
| `WORKER_MAX_ATTEMPTS` | no | `5` | |
| `WORKER_LOCK_STALE_MINUTES` | no | `15` | Auto-recover stale worker locks |

---

## Status

### Done
- Document ingestion (URL, PDF, text)
- Paragraph/sentence-aware chunking with character offsets
- OpenAI embeddings (1536d) + pgvector HNSW search
- Apache AGE knowledge graph with evidence grounding
- Hybrid NER + LLM graph extraction
- Memory consolidation (active / deprecated / disputed lifecycle)
- Declarative inference rules with generic executor
- Inferred edge citations grounded via support_edges
- 2-pass retrieval (explicit-first, inferred-fallback)
- Chat with grounded citations
- Sliding-window rate limiting + concurrency control
- LLM gateway (OpenAI + Groq) with retry/backoff
- Inference rule management API
- User profiles per space
- Metrics counters
- Automated rule discovery + suggestion

### Planned
- MCP server layer -- expose memory to external tools (Cursor, Claude Desktop, etc.)
- Wire metrics instrumentation into worker + API
- Admin dashboard for memory events, rules, metrics
- Retention / archiving -- drop raw text after N days, keep graph
- Importance scoring -- rank edges by access frequency + recency
- AWS deployment (ECS/Fargate, RDS, S3)
- Bedrock integration for embeddings + chat

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `OPENAI_API_KEY is not set` | Add to `.env` in memory service and/or worker directory |
| `JWT_SECRET is not set` | Add to `.env` in both auth and memory services |
| `DATABASE_URL is not set` | Add to `.env` or make sure `docker compose up -d` ran |
| 403 on endpoints | Login first to get a valid JWT |
| 429 on chat | Rate limit (10 req/min per user, 50 req/min per space) |
| Worker stuck | Check `ingestion_jobs` table; stale locks auto-recover after 15 min |
| Graph queries empty | Confirm `GRAPH_ENABLED=1` and AGE extension is loaded |

---

## License

MIT
