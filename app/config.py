"""
Configuration management with validation
Centralizes all settings and validates on startup
"""

import os
import logging
from pathlib import Path
from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with validation"""

    # API Keys
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    congress_api_key: Optional[str] = Field(default=None, alias="CONGRESS_API_KEY")

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    data_dir: Optional[Path] = None
    uscode_dir: Optional[Path] = None
    vector_db_dir: Optional[Path] = None

    # Vector DB settings
    # Embedding model options:
    #   - "text-embedding-3-small": Good quality, 1536 dims, $0.02/1M tokens
    #   - "text-embedding-3-large": Best quality, 3072 dims, $0.13/1M tokens
    # NOTE: Must match the model used when creating the database!
    embedding_model: str = "text-embedding-3-small"
    vector_db_collection: str = "uscode"
    vector_batch_size: int = 100  # Reduced to avoid OpenAI rate limits

    # RAG settings
    default_llm_provider: str = "openai"
    default_openai_model: str = "gpt-4o"
    default_anthropic_model: str = "claude-sonnet-4-20250514"
    rag_temperature: float = 0.3
    rag_max_tokens: int = 2000
    rag_n_sections: int = 5

    # Server settings
    # Safer default: bind to localhost unless explicitly overridden
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def model_post_init(self, __context) -> None:
        """Set derived paths after initialization"""
        if self.data_dir is None:
            self.data_dir = self.project_root / "data"
        if self.uscode_dir is None:
            self.uscode_dir = self.data_dir / "uscode"
        if self.vector_db_dir is None:
            self.vector_db_dir = self.data_dir / "vector_db"

    def validate_openai(self) -> bool:
        """Check if OpenAI is configured"""
        return bool(self.openai_api_key)

    def validate_anthropic(self) -> bool:
        """Check if Anthropic is configured"""
        return bool(self.anthropic_api_key)

    def validate_congress(self) -> bool:
        """Check if Congress API is configured"""
        return bool(self.congress_api_key)

    def validate_vector_db(self) -> bool:
        """Check if vector database exists (LanceDB format)"""
        if self.vector_db_dir is None:
            return False
        # LanceDB stores tables as .lance directories
        return (
            self.vector_db_dir.exists()
            and (self.vector_db_dir / "uscode.lance").exists()
        )

    def get_status(self) -> dict:
        """Get configuration status for debugging"""
        return {
            "openai_configured": self.validate_openai(),
            "anthropic_configured": self.validate_anthropic(),
            "congress_configured": self.validate_congress(),
            "vector_db_exists": self.validate_vector_db(),
            "data_dir": str(self.data_dir) if self.data_dir else None,
            "uscode_dir_exists": self.uscode_dir.exists() if self.uscode_dir else False,
        }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (singleton)"""
    return Settings()


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """Configure application logging"""
    settings = get_settings()
    log_level = level or settings.log_level

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    return logging.getLogger("us_laws")


def validate_startup(
    require_openai: bool = False, require_vector_db: bool = False
) -> None:
    """
    Validate configuration at startup
    Raises exceptions for missing required configuration
    """
    settings = get_settings()
    logger = setup_logging()

    logger.info("Validating configuration...")

    status = settings.get_status()
    for key, value in status.items():
        logger.debug(f"  {key}: {value}")

    if require_openai and not settings.validate_openai():
        raise ValueError(
            "OPENAI_API_KEY is required but not set. "
            "Add it to .env file or set environment variable."
        )

    if require_vector_db and not settings.validate_vector_db():
        raise ValueError(
            f"Vector database not found at {settings.vector_db_dir}. "
            "Run: python scripts/processing/create_vector_db.py"
        )

    logger.info("Configuration validated successfully")


if __name__ == "__main__":
    # Test configuration
    settings = get_settings()
    print("\nConfiguration Status:")
    print("-" * 40)
    for key, value in settings.get_status().items():
        status = "✓" if value else "✗"
        print(f"  {status} {key}: {value}")
