"""
Dashboard Analytics API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import logging

from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.analytics import (
    DocumentStatsResponse,
    UserStatsResponse,
    ActivityStatsResponse,
    WorkflowStatsResponse,
    StorageStatsResponse,
    SearchStatsResponse,
    DashboardSummaryResponse,
)
from app.services.analytics_service import analytics_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def require_manager_or_admin(user: User):
    """Require manager or admin role for analytics access"""
    if user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or Admin role required for analytics access",
        )


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get complete dashboard summary with all metrics.
    Requires manager or admin role.
    """
    require_manager_or_admin(current_user)

    summary = await analytics_service.get_dashboard_summary(db)

    return DashboardSummaryResponse(
        documents=DocumentStatsResponse(**summary["documents"]),
        users=UserStatsResponse(**summary["users"]),
        activity=ActivityStatsResponse(**summary["activity"]),
        workflow=WorkflowStatsResponse(**summary["workflow"]),
        storage=StorageStatsResponse(**summary["storage"]),
        generated_at=summary["generated_at"],
    )


@router.get("/documents", response_model=DocumentStatsResponse)
async def get_document_stats(
    project_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get document statistics.
    """
    stats = await analytics_service.get_document_stats(db, project_id)
    return DocumentStatsResponse(**stats)


@router.get("/users", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user statistics.
    Requires manager or admin role.
    """
    require_manager_or_admin(current_user)

    stats = await analytics_service.get_user_stats(db)
    return UserStatsResponse(**stats)


@router.get("/activity", response_model=ActivityStatsResponse)
async def get_activity_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get activity statistics for specified period.
    Requires manager or admin role.
    """
    require_manager_or_admin(current_user)

    stats = await analytics_service.get_activity_stats(db, days)
    return ActivityStatsResponse(**stats)


@router.get("/workflow", response_model=WorkflowStatsResponse)
async def get_workflow_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get workflow/approval statistics.
    """
    stats = await analytics_service.get_workflow_stats(db, days)
    return WorkflowStatsResponse(**stats)


@router.get("/storage", response_model=StorageStatsResponse)
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get storage usage statistics.
    Requires manager or admin role.
    """
    require_manager_or_admin(current_user)

    stats = await analytics_service.get_storage_stats(db)
    return StorageStatsResponse(**stats)


@router.get("/search", response_model=SearchStatsResponse)
async def get_search_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get search/RAG usage statistics.
    """
    stats = await analytics_service.get_search_stats(db, days)
    return SearchStatsResponse(**stats)
