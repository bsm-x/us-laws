"""
Database client management
Singleton pattern for LanceDB and API clients with connection pooling
"""

import logging
from functools import lru_cache
from typing import Optional, List

import lancedb
import openai

from app.config import get_settings

logger = logging.getLogger(__name__)


class VectorDBClient:
    """Singleton wrapper for LanceDB with OpenAI embeddings"""

    _instance: Optional["VectorDBClient"] = None
    _db = None
    _table = None
    _openai_client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if self._db is not None:
            return

        settings = get_settings()

        if settings.vector_db_dir is None or not settings.vector_db_dir.exists():
            logger.warning(
                f"Vector DB directory does not exist: {settings.vector_db_dir}"
            )
            return

        logger.info(f"Initializing LanceDB client at {settings.vector_db_dir}")

        # Create LanceDB connection
        self._db = lancedb.connect(str(settings.vector_db_dir))

        # Create OpenAI client for embeddings
        if settings.validate_openai():
            self._openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            logger.info(f"Using OpenAI embeddings: {settings.embedding_model}")
        else:
            logger.warning("OpenAI API key not set - embeddings will fail")

    @property
    def db(self):
        """Get the LanceDB connection"""
        return self._db

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for a query using OpenAI"""
        settings = get_settings()
        response = self._openai_client.embeddings.create(
            input=[text], model=settings.embedding_model
        )
        return response.data[0].embedding

    def get_table(self, name: Optional[str] = None):
        """Get a LanceDB table"""
        if self._db is None:
            raise RuntimeError("LanceDB client not initialized")

        settings = get_settings()
        table_name = name or settings.vector_db_collection

        # Cache table reference
        if self._table is None:
            try:
                self._table = self._db.open_table(table_name)
                logger.debug(f"Loaded table: {table_name}")
            except Exception as e:
                logger.error(f"Failed to open table {table_name}: {e}")
                raise

        return self._table

    def search(self, query: str, n_results: int = 10) -> dict:
        """Search the vector database - returns ChromaDB-compatible format"""
        table = self.get_table()

        # Get query embedding
        query_embedding = self._get_embedding(query)

        # Search LanceDB
        results = table.search(query_embedding).limit(n_results).to_list()

        # Convert to ChromaDB-compatible format for backwards compatibility
        documents = []
        metadatas = []
        distances = []

        for r in results:
            documents.append(r.get("text", ""))
            metadatas.append(
                {
                    "identifier": r.get("identifier", ""),
                    "heading": r.get("heading", ""),
                    "title": r.get("title", ""),
                    "text_length": r.get("text_length", 0),
                }
            )
            distances.append(r.get("_distance", 0))

        return {
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    def reset(self):
        """Reset the singleton (for testing)"""
        self._db = None
        self._table = None
        self._openai_client = None
        VectorDBClient._instance = None


@lru_cache()
def get_vector_db() -> VectorDBClient:
    """Get cached VectorDB client instance"""
    return VectorDBClient()


class LLMClientPool:
    """Connection pool for LLM API clients"""

    _openai_client = None
    _anthropic_client = None

    @classmethod
    def get_openai(cls):
        """Get cached OpenAI client"""
        if cls._openai_client is None:
            settings = get_settings()
            if not settings.validate_openai():
                raise ValueError("OPENAI_API_KEY not configured")

            from openai import OpenAI

            cls._openai_client = OpenAI(api_key=settings.openai_api_key)
            logger.info("Initialized OpenAI client")

        return cls._openai_client

    @classmethod
    def get_anthropic(cls):
        """Get cached Anthropic client"""
        if cls._anthropic_client is None:
            settings = get_settings()
            if not settings.validate_anthropic():
                raise ValueError("ANTHROPIC_API_KEY not configured")

            from anthropic import Anthropic

            cls._anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
            logger.info("Initialized Anthropic client")

        return cls._anthropic_client

    @classmethod
    def reset(cls):
        """Reset all clients (for testing)"""
        cls._openai_client = None
        cls._anthropic_client = None


def get_openai_client():
    """Convenience function for OpenAI client"""
    return LLMClientPool.get_openai()


def get_anthropic_client():
    """Convenience function for Anthropic client"""
    return LLMClientPool.get_anthropic()
