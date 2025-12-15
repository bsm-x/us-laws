"""
Routers package for FastAPI application
"""

from app.routers.laws import router as laws_router
from app.routers.code import router as code_router
from app.routers.ask import router as ask_router

__all__ = [
    "laws_router",
    "code_router",
    "ask_router",
]
