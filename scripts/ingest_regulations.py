#!/usr/bin/env python3
"""Bootstrap regulatory document feeds into Qdrant for compliance monitoring."""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

SEED_REGULATIONS = [
    {
        "title": "SEC Cybersecurity Risk Management Rules",
        "url": "https://www.sec.gov/rules/final/2023/33-11216.pdf",
        "text": """The Securities and Exchange Commission has adopted rules requiring registrants
to disclose material cybersecurity incidents and to disclose on an annual basis material
information regarding their cybersecurity risk management, strategy, and governance.
Registrants must now disclose any cybersecurity incident determined to be material within 4 business days.
The rules require Board oversight of cybersecurity risk management and management's role in such oversight.
Effective dates: December 2023 for large accelerated filers, June 2024 for smaller reporting companies.""",
        "jurisdiction": "US Federal",
        "practice_area": "Securities",
    },
    {
        "title": "FTC Rule on Non-Compete Clauses",
        "url": "https://www.federalregister.gov/documents/2024/05/07/2024-09171/non-compete-clause-rule",
        "text": """The Federal Trade Commission has issued a final rule banning most non-compete agreements
for workers in the United States. The rule declares non-compete clauses an unfair method of competition
under Section 5 of the FTC Act. Existing non-competes for senior executives remain enforceable.
Employers must provide notice to workers subject to non-competes that such agreements will not be enforced.
The rule was stayed pending litigation as of August 2024.""",
        "jurisdiction": "US Federal",
        "practice_area": "Employment",
    },
    {
        "title": "EU AI Act Compliance Requirements",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
        "text": """The EU Artificial Intelligence Act establishes a comprehensive regulatory framework for AI.
High-risk AI systems must undergo conformity assessments before market placement.
General-purpose AI models with systemic risk face enhanced obligations including adversarial testing.
Prohibited AI practices include real-time remote biometric identification in public spaces.
Penalties for non-compliance can reach €35 million or 7% of global annual turnover.
Timeline: Most provisions apply from August 2026; GPAI model provisions from August 2025.""",
        "jurisdiction": "EU",
        "practice_area": "Technology / AI",
    },
]


async def ingest_regulations():
    from rag.embeddings import AzureEmbeddingClient
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance
    from core.config import settings

    print("Bootstrapping regulatory document collection...")

    embedder = AzureEmbeddingClient()
    qdrant = QdrantClient(url=settings.qdrant_url)

    # Create regulations collection if needed
    reg_collection = "lexmind_regulations"
    existing = [c.name for c in qdrant.get_collections().collections]
    if reg_collection not in existing:
        qdrant.create_collection(
            collection_name=reg_collection,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        print(f"  Created collection: {reg_collection}")

    texts = [r["text"] for r in SEED_REGULATIONS]
    print(f"  Embedding {len(texts)} regulatory documents...")
    embeddings = await embedder.embed_batch(texts)

    points = []
    for reg, emb in zip(SEED_REGULATIONS, embeddings):
        chunk_id = f"reg_{uuid.uuid5(uuid.NAMESPACE_DNS, reg['title'])}"
        points.append(
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id)),
                vector=emb,
                payload={
                    "chunk_id": chunk_id,
                    "doc_id": chunk_id,
                    "matter_id": "regulations",
                    "text": reg["text"],
                    "title": reg["title"],
                    "url": reg["url"],
                    "jurisdiction": reg["jurisdiction"],
                    "practice_area": reg["practice_area"],
                    "is_regulation": True,
                },
            )
        )

    qdrant.upsert(collection_name=reg_collection, points=points, wait=True)
    print(f"  ✓ Ingested {len(points)} regulations")
    print("\nRegulatory collection ready. The compliance monitor will use this as a baseline.")


if __name__ == "__main__":
    asyncio.run(ingest_regulations())
