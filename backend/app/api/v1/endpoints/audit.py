"""
Audit Trail API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import datetime
import logging

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.audit import AuditAction
from app.schemas.audit import (
    AuditLogResponse,
    AuditLogListResponse,
    ActivitySummaryResponse,
)
from app.services.audit_service import audit_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def require_admin_or_manager(user: User):
    """Require admin or manager role for audit access"""
    if user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager role required for audit access",
        )


@router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(
    action: Optional[AuditAction] = None,
    user_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[UUID] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get audit logs with filtering.
    Requires admin or manager role.
    """
    require_admin_or_manager(current_user)

    logs, total = await audit_service.get_logs(
        db=db,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                action=log.action.value if hasattr(log.action, 'value') else str(log.action),
                user_id=log.user_id,
                user_email=log.user_email,
                user_name=log.user_name,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                resource_name=log.resource_name,
                details=log.details or {},
                changes=log.changes or {},
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/document/{document_id}", response_model=AuditLogListResponse)
async def get_document_history(
    document_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get audit history for a specific document.
    """
    logs = await audit_service.get_document_history(db, document_id, limit)

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                action=log.action.value if hasattr(log.action, 'value') else str(log.action),
                user_id=log.user_id,
                user_email=log.user_email,
                user_name=log.user_name,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                resource_name=log.resource_name,
                details=log.details or {},
                changes=log.changes or {},
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=len(logs),
        skip=0,
        limit=limit,
    )


@router.get("/user/{user_id}", response_model=AuditLogListResponse)
async def get_user_activity(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent activity for a specific user.
    Users can view their own activity; admins can view anyone's.
    """
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view other users' activity",
        )

    logs = await audit_service.get_user_activity(db, user_id, days, limit)

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                action=log.action.value if hasattr(log.action, 'value') else str(log.action),
                user_id=log.user_id,
                user_email=log.user_email,
                user_name=log.user_name,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                resource_name=log.resource_name,
                details=log.details or {},
                changes=log.changes or {},
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=len(logs),
        skip=0,
        limit=limit,
    )


@router.get("/my-activity", response_model=AuditLogListResponse)
async def get_my_activity(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's recent activity.
    """
    logs = await audit_service.get_user_activity(db, current_user.id, days, limit)

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                action=log.action.value if hasattr(log.action, 'value') else str(log.action),
                user_id=log.user_id,
                user_email=log.user_email,
                user_name=log.user_name,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                resource_name=log.resource_name,
                details=log.details or {},
                changes=log.changes or {},
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=len(logs),
        skip=0,
        limit=limit,
    )


@router.get("/summary", response_model=ActivitySummaryResponse)
async def get_activity_summary(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary of recent activity.
    Requires admin or manager role.
    """
    require_admin_or_manager(current_user)

    summary = await audit_service.get_activity_summary(db, days)

    return ActivitySummaryResponse(
        period_days=summary["period_days"],
        by_action=summary["by_action"],
        by_user=summary["by_user"],
        by_resource=summary["by_resource"],
    )


@router.get("/actions")
async def list_audit_actions(
    current_user: User = Depends(get_current_user),
):
    """Get list of available audit action types"""
    return [
        {
            "value": action.value,
            "label": action.name.replace("_", " ").title(),
        }
        for action in AuditAction
    ]
