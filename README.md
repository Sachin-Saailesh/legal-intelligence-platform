# LexMind — Multi-Agent Legal Intelligence Platform

Production-grade AI platform for law firms. Five specialist agents coordinated by a LangGraph
master orchestrator, four-stage hybrid RAG, human-in-the-loop review, and real-time compliance
monitoring.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NGINX (port 80)                             │
│              /api/* → backend:8000  |  /* → frontend:3000           │
└─────────────────────────┬───────────────────┬───────────────────────┘
                          │                   │
               ┌──────────▼──────┐  ┌─────────▼──────────┐
               │  FastAPI (8000) │  │  Next.js 14 (3000) │
               │  + WebSocket    │  │  Dashboard, Query, │
               │  streaming      │  │  Review, Alerts    │
               └──────────┬──────┘  └────────────────────┘
                          │
            ┌─────────────▼──────────────────────────┐
            │         LangGraph Orchestrator          │
            │  classify_intent → route → [agents] →  │
            │  synthesize → guard → review_gate       │
            └──┬──────┬──────┬──────┬──────┬─────────┘
               │      │      │      │      │
     ┌─────────▼─┐ ┌──▼──┐ ┌▼────┐ ┌▼────┐ └────────┐
     │ Contract  │ │Case │ │Comp │ │Legal│  Litig.  │
     │ Analyst   │ │Rsrch│ │Mon. │ │Draft│  Risk    │
     └─────┬─────┘ └──┬──┘ └──┬──┘ └──┬──┘ └───┬────┘
           └──────────┴───────┴───────┴─────────┘
                          │
         ┌────────────────▼────────────────────────┐
         │           Hybrid RAG Pipeline            │
         │  Qdrant (dense) + BM25 (sparse) → RRF   │
         │  → FlashRank reranker → Hallucination    │
         │    Guard (GPT-4o, temp=0) → output       │
         └──────┬──────────┬──────────┬─────────────┘
                │          │          │
        ┌───────▼──┐ ┌─────▼───┐ ┌───▼────┐
        │  Qdrant  │ │  Neo4j  │ │Postgres│
        │ (vectors)│ │ (graph) │ │  (ORM) │
        └──────────┘ └─────────┘ └────────┘
                          │
        ┌─────────────────▼─────────────────────┐
        │  Celery Beat (every 6h)               │
        │  compliance_monitor → alerts →        │
        │  Redis pub/sub → WebSocket push       │
        └───────────────────────────────────────┘
```

**LLM & Embeddings:** Azure OpenAI — GPT-4o (generation), text-embedding-3-large (1536-dim).
All infrastructure is self-hosted via Docker (zero additional cost).

---

## Prerequisites

- Docker Desktop 4.x+ with Compose V2
- Azure OpenAI resource with:
  - GPT-4o deployment
  - text-embedding-3-large deployment
- 8 GB RAM minimum (16 GB recommended for all services)

---

## Quick Start

```bash
# 1. Clone and enter the repo
cd lexmind

# 2. Configure environment
cp infra/.env.example infra/.env
# Edit infra/.env — fill in your Azure OpenAI keys:
#   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
#   AZURE_OPENAI_API_KEY=your_key_here
#   SECRET_KEY=$(openssl rand -hex 32)

# 3. Build and start all services
cd infra
docker compose up --build

# Services will be available at:
#   http://localhost       — Main app (nginx)
#   http://localhost:3000  — Frontend direct
#   http://localhost:8000  — Backend API
#   http://localhost:3001  — Langfuse observability
#   http://localhost:7474  — Neo4j Browser
#   http://localhost:6333  — Qdrant Dashboard
```

---

## First Document Ingestion

```bash
# 1. Register an account
curl -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"attorney@yourfirm.com","password":"yourpassword","firm_name":"Your Firm LLP"}'

# 2. Get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"attorney@yourfirm.com","password":"yourpassword"}' \
  | jq -r '.data.access_token')

# 3. Create a matter
MATTER_ID=$(curl -s -X POST http://localhost:8000/api/matters \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"My Contract Review","matter_type":"contract","jurisdiction":"Delaware"}' \
  | jq -r '.data.id')

# 4. Upload a document (triggers background ingestion)
curl -X POST http://localhost:8000/api/matters/$MATTER_ID/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/your/contract.pdf"

# Check ingestion status
curl http://localhost:8000/api/matters/$MATTER_ID/documents \
  -H "Authorization: Bearer $TOKEN" | jq '.data[].ingestion_status'
```

---

## Running a Query

```bash
# POST a query — returns session_id immediately
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/queries \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"query\":\"Analyze the indemnification clause for risks\",\"matter_id\":\"$MATTER_ID\"}" \
  | jq -r '.data.session_id')

echo "Session: $SESSION_ID"

# Stream the response via WebSocket (use wscat or websocat)
# npm install -g wscat
wscat -c "ws://localhost:8000/api/queries/$SESSION_ID/stream"

# Or poll for the final result
curl http://localhost:8000/api/queries/$SESSION_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.data.final_output'
```

---

## Running Tests

```bash
# Run full test suite inside the backend container
docker compose exec backend pytest tests/ -v

# Run individual test modules
docker compose exec backend pytest tests/test_hallucination_guard.py -v
docker compose exec backend pytest tests/test_agents.py -v
docker compose exec backend pytest tests/test_rag_pipeline.py -v
docker compose exec backend pytest tests/test_api.py -v

# Run retrieval benchmark (requires ingested documents)
docker compose exec backend python scripts/test_retrieval.py <matter_id>

# Seed sample data
docker compose exec backend python scripts/seed_data.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_CHAT_ENDPOINT` | ✓ | Chat resource URL (`aifoundry2212.cognitiveservices.azure.com`) |
| `AZURE_CHAT_API_KEY` | ✓ | API key for the chat resource |
| `AZURE_CHAT_DEPLOYMENT` | ✓ | Deployment name (e.g. `gpt-5-chat`) |
| `AZURE_CHAT_API_VERSION` | ✓ | API version (e.g. `2024-12-01-preview`) |
| `AZURE_EMBEDDING_ENDPOINT` | ✓ | Embedding resource URL (`directors-8066-resource.cognitiveservices.azure.com`) |
| `AZURE_EMBEDDING_API_KEY` | ✓ | API key for the embedding resource |
| `AZURE_EMBEDDING_DEPLOYMENT` | ✓ | Deployment name (`text-embedding-3-large`) |
| `AZURE_EMBEDDING_API_VERSION` | ✓ | API version (e.g. `2024-02-01`) |
| `DATABASE_URL` | ✓ | PostgreSQL async connection URL |
| `SECRET_KEY` | ✓ | 64-char random string for JWT signing |
| `QDRANT_URL` | | Qdrant base URL (default: http://qdrant:6333) |
| `QDRANT_COLLECTION` | | Collection name (default: lexmind_documents) |
| `NEO4J_URI` | | Neo4j bolt URI |
| `NEO4J_PASSWORD` | | Neo4j password |
| `REDIS_URL` | | Redis connection URL |
| `LANGFUSE_PUBLIC_KEY` | | Langfuse observability (optional) |
| `LANGFUSE_SECRET_KEY` | | Langfuse secret key (optional) |

---

## Scaling Notes (Docker Compose → ECS Fargate)

1. **Backend API**: Deploy as Fargate task. Set `min_capacity=2` for HA. Use an ALB target group
   for the `/api/*` path. WebSocket sessions need sticky routing (`stickiness.enabled = true`).

2. **Celery Workers**: Separate Fargate task definition. Scale on `celery_queue_length` CloudWatch
   metric using Application Auto Scaling.

3. **Postgres**: Migrate to Amazon RDS PostgreSQL with Multi-AZ. Update `DATABASE_URL`.

4. **Qdrant**: Use Qdrant Cloud or deploy to ECS with an EBS volume. For production, use Qdrant's
   distributed mode with 3 nodes.

5. **Neo4j**: Use Neo4j Aura (managed) or AuraDB Enterprise for production.

6. **Redis**: Migrate to Amazon ElastiCache (Redis OSS). Use cluster mode for high throughput.

7. **File uploads**: Replace local `/app/uploads` volume with S3. Update `DocumentIngestionPipeline`
   to read from S3 using `aioboto3`.

8. **Langfuse**: Self-hosted on ECS or use Langfuse Cloud. Set `LANGFUSE_HOST` accordingly.

---

## Key Design Decisions

- **Hallucination guard is mandatory**: Every final generation passes through `HallucinationGuard`
  before delivery. Confidence < 0.70 forces human review regardless of agent.

- **Human-in-the-loop via LangGraph checkpointing**: Sessions with `requires_human_review=True`
  halt at the `human_review_gate` node. Attorneys approve/reject via the review queue.
  Corrections are re-ingested as high-weight chunks to improve future retrievals.

- **Hybrid retrieval**: Dense (Qdrant cosine) + Sparse (BM25) merged via RRF ensures both
  semantic similarity and keyword precision. BM25 corpus is cached in Redis with 1-hour TTL.

- **Azure-only paid services**: GPT-4o and text-embedding-3-large are the sole paid dependencies.
  All infrastructure (Qdrant, Neo4j, Redis, Postgres, Langfuse) runs free/self-hosted.

---

## File Structure

```
lexmind/
├── backend/                    Python/FastAPI backend
│   ├── agents/                 LangGraph + specialist agents
│   ├── rag/                    Ingestion, retrieval, reranking, guard
│   ├── graph/                  Neo4j client
│   ├── tasks/                  Celery beat compliance scheduler
│   ├── api/                    FastAPI app + routers
│   ├── db/                     SQLAlchemy models + Alembic migrations
│   └── core/                   Config + logging
├── frontend/                   Next.js 14 frontend
│   ├── app/                    App Router pages
│   ├── components/             Reusable UI components
│   └── lib/                    API client + WebSocket hook
├── infra/                      Docker Compose + nginx
├── scripts/                    Seed data + benchmarks
└── tests/                      Pytest test suite
```
