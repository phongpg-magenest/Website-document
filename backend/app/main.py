from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
import logging

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import get_password_hash
from app.api.v1.router import api_router
from app.services import vector_service
# Import all models to ensure they are registered with Base
from app.models import *  # noqa: F401, F403
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_default_admin():
    """Create or update default admin user"""
    async with AsyncSessionLocal() as db:
        # Check if admin exists
        result = await db.execute(
            select(User).where(User.email == "admin@mdms.local")
        )
        existing_user = result.scalar_one_or_none()

        if not existing_user:
            admin_user = User(
                email="admin@mdms.local",
                name="Admin",
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin_user)
            await db.commit()
            logger.info("Default admin user created: admin@mdms.local / admin123")
        else:
            # Reset password to ensure it works
            existing_user.hashed_password = get_password_hash("admin123")
            await db.commit()
            logger.info("Default admin user password reset: admin@mdms.local / admin123")


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

    # Create default admin user
    try:
        await create_default_admin()
    except Exception as e:
        logger.warning(f"Default admin creation skipped: {e}")

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
