"""
Routers package for FastAPI application
"""

from app.routers.code import router as code_router
from app.routers.ask import router as ask_router
from app.routers.founding_docs import router as founding_docs_router

__all__ = [
    "code_router",
    "ask_router",
    "founding_docs_router",
]
