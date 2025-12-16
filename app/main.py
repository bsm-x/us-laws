"""
US Laws Viewer - FastAPI Application

A web interface for browsing and searching US federal law.

Run with: python -m app.main
Then visit: http://localhost:8000

Architecture:
- main.py: App setup, lifespan, health endpoint
- templates.py: HTML/CSS rendering (dark mode)
- data_loaders.py: CSV loading with caching
- config.py: Centralized settings
- database.py: Vector DB client singleton
- models.py: Pydantic models
- rag.py: RAG pipeline
- routers/: Route handlers
    - ask.py: Home page - AI Search
    - code.py: US Code browser
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from app.config import get_settings, setup_logging
from app.models import HealthResponse
from app.routers import (
    code_router,
    ask_router,
    founding_docs_router,
    citations_router,
    scotus_router,
)

# Setup logging
logger = setup_logging()

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - runs on startup/shutdown"""
    # Startup
    logger.info("Starting US Laws Viewer...")
    logger.info(f"Data directory: {settings.data_dir}")

    status = settings.get_status()
    logger.info(f"OpenAI configured: {status['openai_configured']}")
    logger.info(f"Vector DB exists: {status['vector_db_exists']}")

    # Initialize database on startup (instead of first request)
    if status["vector_db_exists"]:
        from app.database import get_vector_db

        try:
            db = get_vector_db()
            table = db.get_table()
            count = table.count_rows()
            logger.info(f"Vector DB initialized: {count:,} sections indexed")
        except Exception as e:
            logger.warning(f"Failed to initialize vector DB: {e}")

    # Initialize LLM clients on startup
    from app.database import LLMClientPool

    if status["openai_configured"]:
        try:
            LLMClientPool.get_openai()
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")

    if settings.validate_anthropic():
        try:
            LLMClientPool.get_anthropic()
        except Exception as e:
            logger.warning(f"Failed to initialize Anthropic client: {e}")

    yield

    # Shutdown
    logger.info("Shutting down US Laws Viewer...")


# Create FastAPI app
app = FastAPI(
    title="US Laws Viewer",
    description="Browse and search US federal law",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(ask_router)  # Home page (AI Search at /)
app.include_router(code_router)
app.include_router(founding_docs_router)
app.include_router(citations_router)
app.include_router(scotus_router)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        from app.database import get_vector_db

        db = get_vector_db()
        table = db.get_table()
        sections_count = table.count_rows()
    except Exception:
        sections_count = 0

    return HealthResponse(
        status="ok",
        vector_db_available=settings.validate_vector_db(),
        openai_configured=settings.validate_openai(),
        anthropic_configured=settings.validate_anthropic(),
        sections_indexed=sections_count,
    )


if __name__ == "__main__":
    logger.info("Starting US Laws Viewer...")
    logger.info(f"Visit: http://localhost:{settings.port}")
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info" if settings.debug else "warning",
    )
