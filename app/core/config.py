"""Application configuration"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://dbuser:dbpass@localhost:5432/release_notes_db",
        alias="DATABASE_URL"
    )
    
    # Vector Store
    vector_db: Literal["faiss", "qdrant"] = Field(default="faiss", alias="VECTOR_DB")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    
    # LLM Configuration
    llm_provider: Literal["grok", "openai", "mock"] = Field(default="grok", alias="LLM_PROVIDER")
    
    # Grok Configuration
    grok_api_key: str = Field(default="", alias="GROK_API_KEY")
    grok_api_url: str = Field(default="https://api.x.ai/v1", alias="GROK_API_URL")
    grok_model: str = Field(default="grok-beta", alias="GROK_MODEL")
    
    # OpenAI Configuration
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_api_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_API_URL")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    
    # Legacy field for backward compatibility
    llm_model: str = Field(default="grok-beta", alias="LLM_MODEL")
    
    # Embedding Configuration
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")
    
    # API Security
    api_key: str = Field(default="dev_api_key_change_in_production", alias="API_KEY")
    
    # Application
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Paths
    assets_path: str = Field(default="assets", alias="ASSETS_PATH")
    faiss_index_path: str = Field(default="faiss_index", alias="FAISS_INDEX_PATH")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
