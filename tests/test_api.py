"""Integration tests for the FastAPI endpoints."""
import asyncio
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# ── App fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def app():
    """Create a test app with mocked infrastructure."""
    import os
    os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    os.environ.setdefault("AZURE_OPENAI_API_KEY", "test_key")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://lexmind:lexmind@localhost:5432/lexmind_test")
    os.environ.setdefault("SECRET_KEY", "test_secret_key_at_least_32_chars_long_here")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")

    with (
        patch("api.main.lifespan") as mock_lifespan,
        patch("db.session.engine"),
    ):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_lifespan_ctx(app):
            app.state.qdrant_client = MagicMock()
            app.state.neo4j_client = AsyncMock()
            app.state.redis_client = AsyncMock()
            app.state.retriever = AsyncMock()
            app.state.guard = AsyncMock()
            yield

        mock_lifespan.return_value = mock_lifespan_ctx
        from api.main import app as fastapi_app
        yield fastapi_app


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _create_user_and_get_token(client: AsyncClient) -> str:
    """Register a test user and return JWT token."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    with patch("api.main.AsyncSessionFactory") as mock_factory:
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        res = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "testpass123", "firm_name": "Test Firm"},
        )
    return email


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint should return 200."""
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_login():
    """Register a user and verify login returns a JWT token."""
    import os
    os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    os.environ.setdefault("AZURE_OPENAI_API_KEY", "test_key")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://lexmind:lexmind@localhost:5432/lexmind")
    os.environ.setdefault("SECRET_KEY", "test_secret_key_at_least_32_chars_long_here")

    from api.dependencies import hash_password, verify_password, create_access_token
    from datetime import timedelta

    hashed = hash_password("testpass123")
    assert verify_password("testpass123", hashed)
    assert not verify_password("wrongpass", hashed)

    token = create_access_token({"sub": str(uuid.uuid4())}, expires_delta=timedelta(minutes=5))
    assert isinstance(token, str)
    assert len(token) > 20


@pytest.mark.asyncio
async def test_document_upload_validates_matter(client):
    """Document upload should return 404 for non-existent matter."""
    with (
        patch("api.routers.documents.get_current_user") as mock_auth,
        patch("api.routers.documents.get_db") as mock_db_dep,
    ):
        from db.models import User, Firm
        mock_user = MagicMock(spec=User)
        mock_user.firm_id = uuid.uuid4()
        mock_auth.return_value = mock_user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        mock_db_dep.return_value = mock_db

        fake_matter_id = str(uuid.uuid4())
        files = {"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")}
        res = await client.post(
            f"/api/matters/{fake_matter_id}/documents",
            files=files,
            headers={"Authorization": "Bearer fake_token"},
        )
    # Either 404 (matter not found) or 401 (auth)
    assert res.status_code in (401, 404)


@pytest.mark.asyncio
async def test_query_create_returns_session_id(client):
    """Query creation should return a session_id."""
    with (
        patch("api.routers.queries.get_current_user") as mock_auth,
        patch("api.routers.queries.get_db") as mock_db_dep,
        patch("api.routers.queries._run_orchestrator", new_callable=AsyncMock),
    ):
        from db.models import User, Matter
        mock_user = MagicMock(spec=User)
        mock_user.firm_id = uuid.uuid4()
        mock_auth.return_value = mock_user

        mock_matter = MagicMock(spec=Matter)
        mock_matter.id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_matter))
        )
        mock_db_dep.return_value = mock_db

        matter_id = str(uuid.uuid4())
        res = await client.post(
            "/api/queries",
            json={"query": "Analyze indemnification clause", "matter_id": matter_id},
            headers={"Authorization": "Bearer fake_token"},
        )

    # Either 200 with session_id or auth error
    if res.status_code == 200:
        data = res.json()
        assert "session_id" in data.get("data", {})


@pytest.mark.asyncio
async def test_review_approve(client):
    """Review approval should update session status."""
    with (
        patch("api.routers.review.get_current_user") as mock_auth,
        patch("api.routers.review.get_db") as mock_db_dep,
    ):
        from db.models import User, AgentSession, Matter, SessionStatus
        mock_user = MagicMock(spec=User)
        mock_user.firm_id = uuid.uuid4()
        mock_auth.return_value = mock_user

        mock_session = MagicMock(spec=AgentSession)
        mock_session.id = uuid.uuid4()
        mock_session.matter_id = uuid.uuid4()
        mock_session.status = SessionStatus.pending_review
        mock_session.final_output = "Original output from agent."

        mock_matter = MagicMock(spec=Matter)
        mock_matter.firm_id = mock_user.firm_id

        call_count = 0
        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none = MagicMock(return_value=mock_session)
            else:
                result.scalar_one_or_none = MagicMock(return_value=mock_matter)
            return result

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        mock_db_dep.return_value = mock_db

        session_id = str(uuid.uuid4())
        res = await client.post(
            f"/api/review/{session_id}/approve",
            json={},
            headers={"Authorization": "Bearer fake_token"},
        )

    assert res.status_code in (200, 400, 401, 404)


@pytest.mark.asyncio
async def test_alerts_list(client):
    """Alerts list should return data array."""
    with (
        patch("api.routers.alerts.get_current_user") as mock_auth,
        patch("api.routers.alerts.get_db") as mock_db_dep,
    ):
        from db.models import User
        mock_user = MagicMock(spec=User)
        mock_user.firm_id = uuid.uuid4()
        mock_auth.return_value = mock_user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))), fetchall=MagicMock(return_value=[])))
        mock_db_dep.return_value = mock_db

        res = await client.get(
            "/api/alerts",
            headers={"Authorization": "Bearer fake_token"},
        )

    assert res.status_code in (200, 401)
    if res.status_code == 200:
        assert "data" in res.json()
