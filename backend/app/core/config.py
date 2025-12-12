from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "MDMS"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-here"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/mdms"
    DATABASE_POOL_SIZE: int = 10

    @property
    def async_database_url(self) -> str:
        """Convert DATABASE_URL to async format for SQLAlchemy"""
        url = self.DATABASE_URL
        # Railway provides postgresql:// but we need postgresql+asyncpg://
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        # Also handle case where it might already have +psycopg2 or similar
        elif "postgresql+psycopg2://" in url:
            url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        # If already asyncpg, keep as is
        print(f"[DEBUG] Original DATABASE_URL: {self.DATABASE_URL[:50]}...")
        print(f"[DEBUG] Converted async_database_url: {url[:50]}...")
        return url

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-southeast-1"
    S3_BUCKET_NAME: str = "mdms-documents"

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = ""  # Custom base URL for proxy (e.g., https://gemini-proxy.izysync.com)

    # Embedding Model (legacy - không dùng nữa)
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Local RAG Services (Vietnamese models)
    TEI_URL: str = "http://localhost:8080"  # Vietnamese Embedding
    RERANKER_URL: str = "http://localhost:8081"  # Vietnamese Reranker
    OLLAMA_URL: str = "http://localhost:11434"  # Local LLM
    OLLAMA_MODEL: str = "qwen2.5:1.5b-instruct"

    # RAG Settings
    EMBEDDING_DIMENSION: int = 1024  # AITeamVN/Vietnamese_Embedding dimension
    RAG_TOP_K_SEARCH: int = 20  # Số chunks lấy từ vector search
    RAG_TOP_K_RERANK: int = 10  # Số chunks sau rerank để đưa vào LLM
    RAG_MAX_TOKENS: int = 2048  # Số tokens tối đa cho câu trả lời
    USE_LOCAL_RAG: bool = True  # True = dùng local models, False = dùng Gemini

    # JWT
    JWT_SECRET_KEY: str = "your-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Odoo Integration
    ODOO_URL: str = ""
    ODOO_DB: str = ""
    ODOO_USERNAME: str = ""
    ODOO_PASSWORD: str = ""

    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = ".doc,.docx,.xls,.xlsx,.pdf,.md"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
