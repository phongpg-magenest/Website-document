"""
Notification Schemas
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from enum import Enum


class NotificationType(str, Enum):
    DOCUMENT_SHARED = "document_shared"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_COMMENTED = "document_commented"
    REVIEW_REQUESTED = "review_requested"
    DOCUMENT_APPROVED = "document_approved"
    DOCUMENT_REJECTED = "document_rejected"
    DOCUMENT_PUBLISHED = "document_published"
    COMMENT_REPLY = "comment_reply"
    COMMENT_MENTION = "comment_mention"
    COMMENT_RESOLVED = "comment_resolved"
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    TASK_REMINDER = "task_reminder"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationResponse(BaseModel):
    """Response schema for notification"""
    id: UUID
    type: str
    priority: str
    title: str
    message: str
    resource_type: Optional[str]
    resource_id: Optional[UUID]
    action_url: Optional[str]
    is_read: bool
    read_at: Optional[datetime]
    sender_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """List response with counts"""
    items: List[NotificationResponse]
    total: int
    unread_count: int
    skip: int
    limit: int


class NotificationCreate(BaseModel):
    """Schema for creating a notification (admin/system use)"""
    user_id: UUID
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    title: str
    message: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    action_url: Optional[str] = None


class UnreadCountResponse(BaseModel):
    """Response for unread count"""
    count: int
