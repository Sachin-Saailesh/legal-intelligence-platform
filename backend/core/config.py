from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Azure OpenAI — Chat (GPT-5)
    azure_chat_endpoint: str = Field(..., env="AZURE_CHAT_ENDPOINT")
    azure_chat_api_key: str = Field(..., env="AZURE_CHAT_API_KEY")
    azure_chat_deployment: str = Field("gpt-5-chat", env="AZURE_CHAT_DEPLOYMENT")
    azure_chat_api_version: str = Field("2024-12-01-preview", env="AZURE_CHAT_API_VERSION")

    # Azure OpenAI — Embeddings (text-embedding-3-large)
    azure_embedding_endpoint: str = Field(..., env="AZURE_EMBEDDING_ENDPOINT")
    azure_embedding_api_key: str = Field(..., env="AZURE_EMBEDDING_API_KEY")
    azure_embedding_deployment: str = Field("text-embedding-3-large", env="AZURE_EMBEDDING_DEPLOYMENT")
    azure_embedding_api_version: str = Field("2024-02-01", env="AZURE_EMBEDDING_API_VERSION")

    # Postgres
    database_url: str = Field(..., env="DATABASE_URL")
    database_sync_url: str = Field("", env="DATABASE_SYNC_URL")

    # Qdrant
    qdrant_url: str = Field("http://qdrant:6333", env="QDRANT_URL")
    qdrant_api_key: str = Field("", env="QDRANT_API_KEY")
    qdrant_collection: str = Field("lexmind_documents", env="QDRANT_COLLECTION")

    # Neo4j
    neo4j_uri: str = Field("bolt://neo4j:7687", env="NEO4J_URI")
    neo4j_user: str = Field("neo4j", env="NEO4J_USER")
    neo4j_password: str = Field("lexmind_password", env="NEO4J_PASSWORD")

    # Redis / Celery
    redis_url: str = Field("redis://redis:6379/0", env="REDIS_URL")
    celery_broker_url: str = Field("redis://redis:6379/0", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://redis:6379/1", env="CELERY_RESULT_BACKEND")

    # Langfuse
    langfuse_public_key: str = Field("", env="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field("", env="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field("http://langfuse:3001", env="LANGFUSE_HOST")

    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(60, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # CORS — stored as a comma-separated string so pydantic-settings doesn't
    # attempt json.loads() on "http://...,http://..." which is not valid JSON
    allowed_origins: str = Field(
        default="http://localhost:3100,http://localhost:8080", env="ALLOWED_ORIGINS"
    )

    # File upload
    upload_dir: str = Field("/app/uploads", env="UPLOAD_DIR")
    max_upload_size_mb: int = Field(50, env="MAX_UPLOAD_SIZE_MB")

    # Feature flags — set to "false" to disable optional services in cloud deployment
    neo4j_enabled: bool = Field(True, env="NEO4J_ENABLED")
    redis_enabled: bool = Field(True, env="REDIS_ENABLED")

    # Application
    app_env: str = Field("development", env="APP_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # Embedding dimensions
    embedding_dimensions: int = 3072

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def allowed_origins_list(self) -> list[str]:
        if isinstance(self.allowed_origins, str):
            return [o.strip() for o in self.allowed_origins.split(",")]
        return self.allowed_origins


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
