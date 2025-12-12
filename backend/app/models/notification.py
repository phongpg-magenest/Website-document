"""
Notification Model - In-app notifications for users
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class NotificationType(str, enum.Enum):
    """Types of notifications"""
    # Document notifications
    DOCUMENT_SHARED = "document_shared"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_COMMENTED = "document_commented"

    # Workflow notifications
    REVIEW_REQUESTED = "review_requested"
    DOCUMENT_APPROVED = "document_approved"
    DOCUMENT_REJECTED = "document_rejected"
    DOCUMENT_PUBLISHED = "document_published"

    # Comment notifications
    COMMENT_REPLY = "comment_reply"
    COMMENT_MENTION = "comment_mention"
    COMMENT_RESOLVED = "comment_resolved"

    # System notifications
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    TASK_REMINDER = "task_reminder"


class NotificationPriority(str, enum.Enum):
    """Priority levels for notifications"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Notification(Base):
    """
    In-app Notification
    Tương đương mail.message / bus.bus trong Odoo
    """
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Recipient
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Notification content
    type = Column(
        SQLEnum(NotificationType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    priority = Column(
        SQLEnum(NotificationPriority, values_callable=lambda x: [e.value for e in x]),
        default=NotificationPriority.NORMAL
    )
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=False)

    # Related resource
    resource_type = Column(String(50), nullable=True)  # document, comment, etc.
    resource_id = Column(UUID(as_uuid=True), nullable=True)

    # Action URL (for frontend routing)
    action_url = Column(String(500), nullable=True)

    # Status
    is_read = Column(Integer, default=0)  # 0 = unread, 1 = read
    read_at = Column(DateTime, nullable=True)

    # Sender (optional)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    sender = relationship("User", foreign_keys=[sender_id])
