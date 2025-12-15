"""
Database client management
Singleton pattern for ChromaDB and API clients with connection pooling
"""

import logging
from functools import lru_cache
from typing import Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.utils import embedding_functions

from app.config import get_settings

logger = logging.getLogger(__name__)


class VectorDBClient:
    """Singleton wrapper for ChromaDB with cached embedding function"""

    _instance: Optional["VectorDBClient"] = None
    _client: Optional[ClientAPI] = None
    _collection = None
    _embedding_function = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if self._client is not None:
            return

        settings = get_settings()

        if settings.vector_db_dir is None or not settings.vector_db_dir.exists():
            logger.warning(
                f"Vector DB directory does not exist: {settings.vector_db_dir}"
            )
            return

        logger.info(f"Initializing ChromaDB client at {settings.vector_db_dir}")

        # Create persistent client (connection pooled internally by ChromaDB)
        self._client = chromadb.PersistentClient(path=str(settings.vector_db_dir))

        # Create embedding function once (reused for all queries)
        if settings.validate_openai():
            self._embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.openai_api_key,
                model_name=settings.embedding_model,
            )
            logger.info(f"Using OpenAI embeddings: {settings.embedding_model}")
        else:
            logger.warning("OpenAI API key not set - using default embeddings")
            self._embedding_function = embedding_functions.DefaultEmbeddingFunction()

    @property
    def client(self) -> Optional[ClientAPI]:
        """Get the ChromaDB client"""
        return self._client

    @property
    def embedding_function(self):
        """Get the cached embedding function"""
        return self._embedding_function

    def get_collection(self, name: Optional[str] = None):
        """Get or create a collection with cached embedding function"""
        if self._client is None:
            raise RuntimeError("ChromaDB client not initialized")

        settings = get_settings()
        collection_name = name or settings.vector_db_collection

        # Cache collection reference
        if self._collection is None or self._collection.name != collection_name:
            try:
                self._collection = self._client.get_collection(
                    name=collection_name,
                    embedding_function=self._embedding_function,
                )
                logger.debug(f"Loaded collection: {collection_name}")
            except Exception as e:
                logger.error(f"Failed to get collection {collection_name}: {e}")
                raise

        return self._collection

    def search(self, query: str, n_results: int = 10) -> dict:
        """Search the vector database"""
        collection = self.get_collection()
        return collection.query(query_texts=[query], n_results=n_results)

    def reset(self):
        """Reset the singleton (for testing)"""
        self._client = None
        self._collection = None
        self._embedding_function = None
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
