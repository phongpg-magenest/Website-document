from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.api.v1.router import api_router
from app.services import vector_service
# Import all models to ensure they are registered with Base
from app.models import *  # noqa: F401, F403

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up MDMS API...")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")

    # Initialize pgvector
    try:
        async with AsyncSessionLocal() as db:
            await vector_service.init_pgvector(db)
        logger.info("pgvector initialized")
    except Exception as e:
        logger.warning(f"pgvector initialization skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down MDMS API...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Magenest Document Management System - API for document management, semantic search, and document generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {
        "message": "Welcome to MDMS API",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
