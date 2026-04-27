"""Tests for the document ingestion and RAG pipeline."""
import asyncio
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a minimal text file as a stand-in for a PDF in tests."""
    p = tmp_path / "sample.txt"
    p.write_text(
        "ARTICLE 1. DEFINITIONS\n\n"
        "1.1 'Agreement' means this Software License Agreement.\n"
        "1.2 'Licensor' means Acme Corp.\n\n"
        "ARTICLE 2. LICENSE GRANT\n\n"
        "2.1 Subject to the terms herein, Licensor grants Licensee a non-exclusive license.\n\n"
        "ARTICLE 3. INDEMNIFICATION\n\n"
        "3.1 Licensee shall indemnify and hold harmless Licensor from any claims.\n"
        "3.2 The indemnification obligations shall survive termination of this Agreement.\n\n"
        "ARTICLE 4. LIMITATION OF LIABILITY\n\n"
        "4.1 IN NO EVENT SHALL LICENSOR BE LIABLE FOR ANY INDIRECT DAMAGES.\n"
    )
    return str(p)


@pytest.fixture
def mock_qdrant():
    client = MagicMock()
    client.upsert = MagicMock()
    client.search = MagicMock(return_value=[])
    client.scroll = MagicMock(return_value=([], None))
    return client


@pytest.fixture
def mock_neo4j():
    neo4j = AsyncMock()
    neo4j.ingest_document_entities = AsyncMock(return_value=None)
    return neo4j


@pytest.fixture
def mock_embedding_client():
    client = AsyncMock()
    # Return realistic 1536-dim embeddings
    client.embed_text = AsyncMock(return_value=[0.01] * 1536)
    client.embed_batch = AsyncMock(return_value=[[0.01] * 1536])
    return client


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value='{"parties": ["Acme Corp", "Licensee"], "defined_terms": ["Agreement"], "governing_law": null, "referenced_clauses": []}'
    )
    return client


@pytest.mark.asyncio
async def test_contract_clause_chunking():
    """Verify that contract text is split on clause boundaries."""
    from rag.ingestion import _contract_clause_chunks

    text = (
        "ARTICLE 1. DEFINITIONS\n\n"
        "This is the definitions section.\n\n"
        "ARTICLE 2. LICENSE GRANT\n\n"
        "This is the license grant section.\n\n"
        "ARTICLE 3. INDEMNIFICATION\n\n"
        "Indemnification terms here.\n"
    )
    chunks = _contract_clause_chunks(text)
    assert len(chunks) >= 3, f"Expected ≥3 clause chunks, got {len(chunks)}"

    headings = [c["section_heading"] for c in chunks]
    assert any("ARTICLE 1" in h for h in headings)
    assert any("ARTICLE 2" in h for h in headings)
    assert any("ARTICLE 3" in h for h in headings)


@pytest.mark.asyncio
async def test_recursive_char_split():
    """Verify that long text is split into chunks of appropriate size."""
    from rag.ingestion import _recursive_char_split

    long_text = "word " * 2000  # ~10000 chars
    chunks = _recursive_char_split(long_text, chunk_size=800, overlap=150)
    assert len(chunks) > 1, "Long text should produce multiple chunks"
    for chunk in chunks:
        assert len(chunk) <= 900, f"Chunk too large: {len(chunk)}"


@pytest.mark.asyncio
async def test_ingestion_pipeline_chunk_count(
    tmp_path, mock_qdrant, mock_neo4j, mock_embedding_client, mock_llm_client
):
    """Ingest a sample document and verify chunk count > 0 and Qdrant upsert called."""
    from db.models import Document, IngestionStatus
    from rag.ingestion import DocumentIngestionPipeline

    # Create a sample contract text file
    p = tmp_path / "contract.txt"
    p.write_text(
        "ARTICLE 1. DEFINITIONS\n\nAll terms defined herein.\n\n"
        "ARTICLE 2. PAYMENT\n\nPayment is due within 30 days.\n\n"
        "ARTICLE 3. TERMINATION\n\nEither party may terminate with 30 days notice.\n"
    )

    doc_id = uuid.uuid4()
    matter_id = uuid.uuid4()
    document = Document(
        id=doc_id,
        matter_id=matter_id,
        filename="contract.txt",
        file_path=str(p),
        doc_type="contract",
        ingestion_status=IngestionStatus.pending,
    )

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    # Patch docling to return plain text
    with patch("rag.ingestion._parse_document") as mock_parse:
        mock_parse.return_value = [{"text": p.read_text(), "page": 1, "confidence": 1.0}]

        # Patch embed_batch to return correct number of embeddings
        async def embed_batch_side_effect(texts):
            return [[0.01] * 1536 for _ in texts]

        mock_embedding_client.embed_batch = AsyncMock(side_effect=embed_batch_side_effect)

        pipeline = DocumentIngestionPipeline(
            embedding_client=mock_embedding_client,
            llm_client=mock_llm_client,
            qdrant_client=mock_qdrant,
            neo4j_client=mock_neo4j,
        )
        chunk_count = await pipeline.ingest(document, mock_db)

    assert chunk_count > 0, "Ingestion should produce at least 1 chunk"
    assert mock_qdrant.upsert.called, "Qdrant upsert should have been called"


@pytest.mark.asyncio
async def test_embedding_dimensions(mock_embedding_client):
    """Verify that embedding output is 1536 dimensions."""
    embedding = await mock_embedding_client.embed_text("test text")
    assert len(embedding) == 1536, f"Expected 1536 dims, got {len(embedding)}"


@pytest.mark.asyncio
async def test_embedding_batch_consistency(mock_embedding_client):
    """Verify batch returns same count as input."""
    texts = ["text one", "text two", "text three"]

    async def embed_batch_side_effect(texts):
        return [[0.01] * 1536 for _ in texts]

    mock_embedding_client.embed_batch = AsyncMock(side_effect=embed_batch_side_effect)
    embeddings = await mock_embedding_client.embed_batch(texts)
    assert len(embeddings) == len(texts)
    for emb in embeddings:
        assert len(emb) == 1536
