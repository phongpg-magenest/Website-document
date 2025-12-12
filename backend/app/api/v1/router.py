from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, documents, search, generate, projects, users,
    templates, review, prompts, audit, notifications, analytics
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(generate.router, prefix="/generate", tags=["Generate"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["Prompt Manager"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(review.router, tags=["Review"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit Trail"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
