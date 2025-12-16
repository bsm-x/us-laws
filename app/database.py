"""
Database client management
Singleton pattern for LanceDB and API clients with connection pooling
"""

import logging
from functools import lru_cache
from typing import Optional, List, Dict, Any

import lancedb
import openai

from app.config import get_settings

logger = logging.getLogger(__name__)


class VectorDBClient:
    """Singleton wrapper for LanceDB with OpenAI embeddings"""

    _instance: Optional["VectorDBClient"] = None
    _db = None
    _table = None
    _scotus_table = None
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

    def get_scotus_table(self):
        """Get the SCOTUS opinions table"""
        if self._db is None:
            raise RuntimeError("LanceDB client not initialized")

        if self._scotus_table is None:
            try:
                self._scotus_table = self._db.open_table("scotus_opinions")
                logger.debug("Loaded SCOTUS opinions table")
            except Exception as e:
                logger.debug(f"SCOTUS table not available: {e}")
                return None

        return self._scotus_table

    def has_scotus_table(self) -> bool:
        """Check if SCOTUS opinions table exists"""
        if self._db is None:
            return False
        return "scotus_opinions" in self._db.table_names()

    def search(
        self, query: str, n_results: int = 10, where: Optional[str] = None
    ) -> dict:
        """Search the vector database - returns ChromaDB-compatible format

        Args:
            query: Natural language query.
            n_results: Number of results to return.
            where: Optional LanceDB filter expression, e.g. "title = 'Founding Documents'".
        """
        table = self.get_table()

        # Get query embedding
        query_embedding = self._get_embedding(query)

        # Search LanceDB
        search_query = table.search(query_embedding)
        if where:
            search_query = search_query.where(where)

        results = search_query.limit(n_results).to_list()

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

    def search_scotus(self, query: str, n_results: int = 5) -> dict:
        """Search the SCOTUS opinions table - returns ChromaDB-compatible format"""
        table = self.get_scotus_table()

        if table is None:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Get query embedding
        query_embedding = self._get_embedding(query)

        # Search LanceDB
        results = table.search(query_embedding).limit(n_results).to_list()

        # Convert to ChromaDB-compatible format
        documents = []
        metadatas = []
        distances = []

        for r in results:
            documents.append(r.get("text", ""))
            metadatas.append(
                {
                    "identifier": r.get("identifier", ""),
                    "heading": r.get("heading", ""),
                    "title": "SCOTUS",
                    "source_type": "scotus",
                    "cluster_id": r.get("cluster_id", ""),
                    "case_name": r.get("case_name", ""),
                    "citation": r.get("citation", ""),
                    "date_filed": r.get("date_filed", ""),
                    "text_length": r.get("text_length", len(r.get("text", ""))),
                }
            )
            distances.append(r.get("_distance", 0))

        return {
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    def search_all(
        self, query: str, n_results: int = 10, include_scotus: bool = True
    ) -> dict:
        """Search both US Code and SCOTUS tables, merging results by relevance.

        Args:
            query: Natural language query
            n_results: Total number of results to return
            include_scotus: Whether to include SCOTUS opinions in search

        Returns:
            Combined results sorted by distance (relevance)
        """
        # Search US Code
        usc_results = self.search(query, n_results=n_results)

        # Search SCOTUS if available and requested
        if include_scotus and self.has_scotus_table():
            scotus_results = self.search_scotus(query, n_results=n_results)
        else:
            scotus_results = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Combine results
        combined = []

        # Add US Code results
        for doc, meta, dist in zip(
            usc_results["documents"][0],
            usc_results["metadatas"][0],
            usc_results["distances"][0],
        ):
            combined.append({"document": doc, "metadata": meta, "distance": dist})

        # Add SCOTUS results
        for doc, meta, dist in zip(
            scotus_results["documents"][0],
            scotus_results["metadatas"][0],
            scotus_results["distances"][0],
        ):
            combined.append({"document": doc, "metadata": meta, "distance": dist})

        # Sort by distance (lower is better) and take top n_results
        combined.sort(key=lambda x: x["distance"])
        combined = combined[:n_results]

        # Convert back to ChromaDB-compatible format
        documents = [r["document"] for r in combined]
        metadatas = [r["metadata"] for r in combined]
        distances = [r["distance"] for r in combined]

        return {
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    def reset(self):
        """Reset the singleton (for testing)"""
        self._db = None
        self._table = None
        self._scotus_table = None
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
