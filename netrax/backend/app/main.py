"""
NETRA-X — AI-Powered Criminal Network Analysis System
Phase 1: Data Ingestion, Document Processing & Entity Extraction

Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"  Phase 1: Data Ingestion & Entity Extraction")
    logger.info("=" * 60)

    # Initialize database tables (dev mode — use Alembic in production)
    await init_db()
    logger.info("Database initialized")

    # Log service availability
    from app.services.processing.pipeline import get_pipeline
    pipeline = get_pipeline()
    logger.info(f"NER available: {pipeline.ner_extractor.is_available()}")
    logger.info(f"OCR available: {pipeline.ocr_service.is_available()}")
    logger.info(f"LLM available: {pipeline.llm_extractor.is_available()}")

    yield

    logger.info("NETRA-X shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-Powered Criminal Network Analysis System — Phase 1\n\n"
        "**Data Ingestion, Document Processing & Entity Extraction**\n\n"
        "⚠️ All AI/NLP results are extraction results requiring human verification. "
        "They do not represent proof of criminal activity.\n\n"
        "⚠️ This system uses synthetic demo data only."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "phase": "1",
    }
