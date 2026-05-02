# LexMind: Architecture & Technology Reference

> A multi-agent AI platform for legal intelligence — built for law firms to query, analyze, and review legal documents with structured human oversight.

---

## 1. Product Overview

LexMind is a full-stack legal AI platform designed to reduce the time attorneys spend on document review, compliance monitoring, and case research. It accepts uploaded legal documents (contracts, briefs, filings), ingests them into a hybrid search pipeline, and routes attorney queries through a multi-agent orchestration system. Every AI-generated answer is graded for factual confidence before it reaches the attorney — responses below configurable thresholds are held for mandatory human review rather than surfaced directly.

The platform covers five core legal workflows:

| Workflow | Description |
|----------|-------------|
| Contract review | Clause-level analysis of risk, obligations, and terms |
| Case research | Retrieval of relevant precedents and legal authority |
| Compliance check | Monitoring regulatory changes against active matters |
| Legal drafting | Generation and revision of contract clauses |
| Litigation risk | Evidence-based case outcome assessment |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│         (dashboard, matters, review queue, alerts)       │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP / WebSocket
┌───────────────────────▼─────────────────────────────────┐
│                   FastAPI Backend                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   REST API   │  │  WebSocket   │  │  Background   │  │
│  │   Routers    │  │  Streaming   │  │    Tasks      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘  │
│         └─────────────────┼─────────────────┘           │
│                    ┌──────▼───────┐                      │
│                    │ LangGraph    │                       │
│                    │ Orchestrator │                       │
│                    └──────┬───────┘                      │
│          ┌────────────────┼────────────────┐             │
│    ┌─────▼──────┐  ┌──────▼─────┐  ┌──────▼──────┐      │
│    │  Contract  │  │    Case    │  │ Compliance  │      │
│    │  Analyst   │  │ Researcher │  │  Monitor   │      │
│    └─────┬──────┘  └──────┬─────┘  └──────┬──────┘      │
│          └────────────────┼────────────────┘             │
│                    ┌──────▼───────┐                      │
│                    │   Hybrid     │                      │
│                    │  Retriever   │                      │
│                    └──────┬───────┘                      │
└───────────────────────────┼─────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
    ┌─────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │ PostgreSQL │   │   Qdrant    │   │   Neo4j*    │
    │  (primary) │   │  (vectors)  │   │   (graph)   │
    └────────────┘   └─────────────┘   └─────────────┘

* Neo4j disabled in cloud deployment, active in local/full stack
```

---

## 3. Technology Stack

### 3.1 FastAPI

**Role:** Primary backend web framework and API server.

FastAPI serves all REST endpoints (`/api/matters`, `/api/queries`, `/api/review`, etc.) and WebSocket connections for real-time query streaming. It was chosen over Flask or Django for its native `async/await` support — critical for a system that simultaneously manages LLM API calls, database queries, and vector search without blocking.

Its automatic OpenAPI schema generation and Pydantic-based request validation ensure that all incoming data is type-checked before reaching business logic. The `lifespan` context manager handles ordered startup and shutdown of all external connections (Qdrant, Neo4j, Redis, Postgres).

**Why essential:** Every user interaction — uploading documents, submitting queries, reviewing responses — passes through FastAPI. It is the integration point for every other service in the stack.

---

### 3.2 PostgreSQL + SQLAlchemy (async)

**Role:** Primary relational database — stores all persistent application state.

PostgreSQL holds the core data model:

| Table | Purpose |
|-------|---------|
| `firms` | Law firm accounts |
| `users` | Attorney and admin accounts |
| `matters` | Legal matters/cases |
| `documents` | Uploaded document metadata and ingestion status |
| `agent_sessions` | Every query, its intent, confidence score, and AI output |
| `timeline_events` | Court dates, deadlines, hearings (AI-extracted + manual) |
| `discovery_items` | Evidence requests and document production tracking |
| `compliance_alerts` | AI-generated regulatory change notifications |

SQLAlchemy's async engine (`asyncpg` driver) allows all DB operations to be non-blocking. Alembic manages schema migrations with a versioned migration chain.

**Why essential:** The relational model is the authoritative source of truth for every matter, session, and document in the system. Qdrant holds vector representations; Postgres holds everything else.

---

### 3.3 Qdrant

**Role:** Vector database — powers semantic document search.

After a document is uploaded, the ingestion pipeline chunks it, generates embeddings via Azure OpenAI `text-embedding-3-large` (3072 dimensions), and upserts the vectors into a Qdrant collection. Each vector point carries a full metadata payload (matter ID, document ID, page number, clause type, section heading, raw text).

At query time, the `HybridRetriever` executes two parallel searches against Qdrant:
1. **Dense search** — cosine similarity against the query embedding (semantic matching)
2. **BM25 sparse search** — term frequency scoring over the matter's corpus (keyword matching)

Results are merged using Reciprocal Rank Fusion (RRF), then passed to `FlashRank` for a final cross-encoder reranking pass. This three-stage pipeline significantly outperforms single-method retrieval on legal text, where exact clause terminology (dense fails) and semantic context (sparse fails) are both required.

**Why essential:** Without Qdrant there is no document search. The entire RAG pipeline depends on it. Removing it would reduce the system to a pure LLM chatbot with no grounding in uploaded documents.

---

### 3.4 LangGraph

**Role:** Multi-agent orchestration framework — routes queries through specialist agents.

LangGraph implements the query-processing pipeline as a directed acyclic graph (DAG). Each node is an async function; edges are conditionally traversed based on the classified intent of the query.

The DAG structure:

```
classify_intent → retrieve_context → [specialist agent] → synthesize → hallucination_guard → persist
```

**Intent classification** uses GPT to categorize each query into one of five legal intents and decompose it into 2–4 sub-tasks. The intent determines which specialist agent node is activated and what confidence threshold applies.

**Specialist agents** (one per intent):
- `ContractAnalyst` — clause extraction, obligation mapping, risk flagging
- `CaseResearcher` — precedent retrieval and legal authority synthesis
- `ComplianceMonitor` — regulatory change detection against matter context
- `LegalDrafter` — clause generation with source-grounded suggestions
- `LitigationRiskAssessor` — evidence-based outcome probability

**Confidence thresholds** are calibrated per intent. High-stakes intents (contract drafting, litigation risk) require ≥87% confidence before auto-approval. Lower-stakes intents (case research) allow ≥72%. Any response below threshold is routed to the human review queue with a structured explanation of why review was triggered.

LangGraph's `AsyncPostgresSaver` checkpointer persists graph execution state to Postgres, enabling full audit trails and resumable sessions.

**Why essential:** LangGraph is the execution backbone of the AI system. Without it, queries cannot be classified, routed to specialists, or graded before delivery to the attorney.

---

### 3.5 Azure OpenAI

**Role:** LLM provider — powers classification, specialist agents, synthesis, and embeddings.

Two Azure OpenAI deployments are used:
- **GPT (chat)** — all language generation: intent classification, specialist analysis, synthesis, timeline extraction, entity extraction
- **text-embedding-3-large** — document and query embeddings for Qdrant (3072 dimensions, highest accuracy tier)

The `AzureLLMClient` and `AzureEmbeddingClient` wrappers handle retry logic, Langfuse tracing hooks, and structured output parsing. Temperature is set to 0 for all classification and extraction tasks to ensure deterministic outputs.

**Why essential:** Every AI capability in LexMind — document understanding, query answering, compliance monitoring — runs on these two models. There is no in-house model.

---

### 3.6 Hallucination Guard

**Role:** Confidence scoring and human review routing.

The `HallucinationGuard` is a dedicated verification step at the end of every agent pipeline. It takes the specialist agent's output alongside the retrieved source chunks and asks the LLM to grade how well the answer is grounded in the sources — producing a confidence score between 0 and 1 and a structured reasoning chain.

If the score falls below the intent-specific threshold, the session is flagged `pending_review` and placed in the attorney review queue. The review reason — formatted as a human-readable string explaining which agent failed and by how much — is stored on the session and surfaced in the UI.

This design ensures attorneys are never presented with a low-confidence AI output as if it were authoritative. The system fails safe: uncertain = human reviews it.

**Why essential:** This is the trust and safety layer of the product. Removing it would mean auto-approving all AI outputs regardless of quality, which is unacceptable in a legal context.

---

### 3.7 Next.js 14 (App Router)

**Role:** Frontend — the attorney-facing dashboard.

The frontend is a Next.js 14 application using the App Router and Tailwind CSS. It provides:

- **Dashboard** — live stats: open matters, pending reviews, overdue deadlines, upcoming events
- **Matters** — create, manage, and close legal matters
- **Chat** — per-matter query interface with streaming responses and session history
- **Review queue** — flagged sessions awaiting attorney sign-off, with confidence scores and review reason banners
- **Timeline** — court dates and deadlines with AI-extracted and manual events
- **Discovery** — evidence tracking and production deadlines
- **Alerts** — compliance notifications from the scheduled monitoring agent

Queries stream back token-by-token over WebSocket, giving attorneys a real-time view of the AI reasoning process. The frontend was built with `standalone` output mode, making it deployable as a single `server.js` process.

**Why essential:** This is the user interface. Without it, the system has no front-end and is unusable outside of raw API calls.

---

### 3.8 Docling + Tesseract + pdf2image

**Role:** Document parsing pipeline — converts uploaded files to structured text.

The ingestion pipeline uses a layered parsing approach:
1. **Docling** — primary parser for PDFs and DOCX; extracts structured text, tables, and section headings with layout awareness
2. **pdf2image + Tesseract OCR** — fallback for scanned PDFs where Docling finds no extractable text; converts pages to images and runs OCR

This two-layer approach handles both digitally created documents (contracts, filings exported as PDF) and scanned documents (older court records, physical discovery materials).

**Why essential:** Without robust document parsing, the ingestion pipeline produces empty or garbled text, making vector search useless. Legal documents frequently include scanned exhibits — OCR fallback is not optional in practice.

---

### 3.9 FlashRank

**Role:** Cross-encoder reranker — second-pass relevance scoring.

After the `HybridRetriever` produces a merged list of ~20 candidate chunks via RRF, `FlashRank` applies a lightweight cross-encoder model to re-score chunks against the specific query. This reranking step is the difference between returning "chunks that mention the same topic" and "chunks that directly answer this question."

FlashRank was chosen over heavier rerankers (Cohere, BGE) for its sub-100ms latency — it runs as a local model with no external API call.

**Why essential:** In testing, reranking consistently elevated the most relevant clauses into the top-3 context slots, directly improving synthesis quality. Without it, the LLM receives noisier context and produces lower-confidence outputs.

---

### 3.10 Neo4j *(local/full stack only)*

**Role:** Knowledge graph — stores entity relationships extracted from documents.

During ingestion, an LLM pass extracts named legal entities (parties, courts, dates, statutes, clauses) and their relationships from each document chunk. These are stored as nodes and edges in Neo4j, building a per-matter knowledge graph.

This graph is intended to power cross-document relationship queries ("which matters reference the same statute?", "what contracts involve party X?") and is the foundation for future graph-augmented retrieval.

**Current status:** Neo4j entity ingestion runs during document processing but graph queries are not yet exposed in the query pipeline — the knowledge graph is write-only in the current version. It is disabled in cloud deployment (`NEO4J_ENABLED=false`) without any loss of query functionality.

**Why kept for local:** The graph data is being accumulated for a planned graph-augmented RAG upgrade. Disabling it in production avoids the resource cost while preserving local data collection.

---

### 3.11 Redis + Celery *(local/full stack only)*

**Role:** Message broker and task queue — powers the scheduled compliance monitoring agent.

Redis serves as both the Celery task broker and the BM25 corpus cache. The `celery_beat` service runs a cron schedule every 6 hours: for each active matter, it runs the `ComplianceMonitor` agent to detect regulatory changes and publishes alerts via Redis pub/sub to connected WebSocket clients.

Redis also caches the BM25 sparse search corpus per matter (1-hour TTL), avoiding a full Qdrant scroll on every query. When Redis is disabled (`REDIS_ENABLED=false`), the retriever fetches the corpus directly from Qdrant on each request — slower but functionally identical.

**Why disabled in cloud deployment:** The free tier of Render provides a single web service process. Running Celery worker and beat as separate persistent processes requires additional compute. The compliance monitoring feature is non-critical for initial deployment — alerts can be triggered manually via the API until Celery is reintroduced.

---

### 3.12 Langfuse *(optional)*

**Role:** LLM observability — traces every model call with latency, token counts, and inputs/outputs.

Every `llm_client.complete()` call in the system emits a trace to Langfuse when keys are configured. This provides a full audit log of every AI decision: what prompt was sent, what the model returned, how long it took, and what it cost.

Langfuse is entirely opt-in — the client only initializes if `LANGFUSE_PUBLIC_KEY` is set. Leaving it blank silently disables tracing with no impact on functionality.

**Why kept:** For a legal AI product, LLM observability is not optional in production — it is essential for debugging, cost monitoring, and demonstrating compliance with attorney supervision requirements. Langfuse Cloud has a free hobby tier that covers development and early production use.

---

## 4. Data Flow: Query Lifecycle

```
1. Attorney submits query via frontend chat
2. WebSocket connection opened → backend creates AgentSession (status: processing)
3. LangGraph DAG starts:
   a. classify_intent → determines intent + sub-tasks
   b. retrieve_context → HybridRetriever fetches top-20 chunks (dense + sparse + rerank)
   c. specialist agent → runs intent-specific analysis against retrieved chunks
   d. synthesize → merges sub-task outputs into a coherent response
   e. hallucination_guard → scores response against sources
4. If confidence ≥ threshold:
   - Session marked complete, response streamed to attorney
5. If confidence < threshold:
   - Session marked pending_review, placed in review queue
   - Attorney notified in dashboard
6. Session persisted to Postgres (query, intent, confidence, output, review_reason)
```

---

## 5. Document Ingestion Pipeline

```
Upload → validate (type + size) → save to disk
→ parse (Docling → OCR fallback)
→ chunk (sliding window, clause-aware)
→ embed (text-embedding-3-large, batch)
→ upsert to Qdrant (with metadata payload)
→ extract entities → write to Neo4j* (* if enabled)
→ extract timeline events → write to Postgres
→ mark document complete
```

---

## 6. Deployment Configurations

### 6.1 Local / Full Stack
All services via `docker-compose.yml`. Includes Neo4j, Redis, Celery, Langfuse.

### 6.2 Cloud (Free Tier)
| Service | Provider |
|---------|----------|
| Frontend | Vercel |
| Backend | Render |
| PostgreSQL | Neon |
| Qdrant | Qdrant Cloud |

Disabled: `NEO4J_ENABLED=false`, `REDIS_ENABLED=false`. Celery and Langfuse containers not deployed.

---

## 7. Security Model

- **Authentication:** JWT tokens signed with `SECRET_KEY`, 60-minute expiry
- **Multi-tenancy:** Every query is scoped to `firm_id` — attorneys can only access matters belonging to their firm
- **File validation:** Upload endpoint validates extension and content before writing to disk
- **Human oversight:** The hallucination guard and review queue enforce that no AI output auto-approves below confidence thresholds — a deliberate architectural constraint, not a feature

---

*Last updated: May 2026*
