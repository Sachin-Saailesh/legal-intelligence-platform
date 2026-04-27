import os
import sys

# Ensure backend package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Set minimal env vars required by config
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test_key_for_testing_only")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://lexmind:lexmind@localhost:5432/lexmind_test")
os.environ.setdefault("DATABASE_SYNC_URL", "postgresql+psycopg2://lexmind:lexmind@localhost:5432/lexmind_test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_at_least_32_chars_long_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
