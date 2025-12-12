"""
Notification API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import logging

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.notification import NotificationType as NotifType, NotificationPriority
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationCreate,
    UnreadCountResponse,
)
from app.services.notification_service import notification_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def get_my_notifications(
    unread_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's notifications.
    """
    notifications, total, unread_count = await notification_service.get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )

    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                type=n.type.value if hasattr(n.type, 'value') else str(n.type),
                priority=n.priority.value if hasattr(n.priority, 'value') else str(n.priority),
                title=n.title,
                message=n.message,
                resource_type=n.resource_type,
                resource_id=n.resource_id,
                action_url=n.action_url,
                is_read=bool(n.is_read),
                read_at=n.read_at,
                sender_id=n.sender_id,
                created_at=n.created_at,
            )
            for n in notifications
        ],
        total=total,
        unread_count=unread_count,
        skip=skip,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get count of unread notifications.
    Useful for badge display.
    """
    count = await notification_service.get_unread_count(db, current_user.id)
    return UnreadCountResponse(count=count)


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a notification as read.
    """
    success = await notification_service.mark_as_read(db, notification_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return {"success": True}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark all notifications as read.
    """
    count = await notification_service.mark_all_as_read(db, current_user.id)
    return {"success": True, "marked_count": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a notification.
    """
    success = await notification_service.delete_notification(db, notification_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return {"success": True}


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    data: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a notification (admin only).
    Used for system announcements or manual notifications.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    notification = await notification_service.create(
        db=db,
        user_id=data.user_id,
        notification_type=NotifType(data.type.value),
        title=data.title,
        message=data.message,
        priority=NotificationPriority(data.priority.value),
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        action_url=data.action_url,
        sender_id=current_user.id,
    )

    await db.commit()

    return NotificationResponse(
        id=notification.id,
        type=notification.type.value,
        priority=notification.priority.value,
        title=notification.title,
        message=notification.message,
        resource_type=notification.resource_type,
        resource_id=notification.resource_id,
        action_url=notification.action_url,
        is_read=bool(notification.is_read),
        read_at=notification.read_at,
        sender_id=notification.sender_id,
        created_at=notification.created_at,
    )
