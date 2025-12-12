"""
Notification Service - Manage in-app notifications
"""
import logging
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, update

from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications"""

    async def create(
        self,
        db: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        action_url: Optional[str] = None,
        sender_id: Optional[UUID] = None,
    ) -> Notification:
        """Create a new notification"""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
            action_url=action_url,
            sender_id=sender_id,
        )

        db.add(notification)
        await db.flush()

        logger.info(f"Created notification {notification.id} for user {user_id}")
        return notification

    async def notify_document_shared(
        self,
        db: AsyncSession,
        document_id: UUID,
        document_title: str,
        shared_by: User,
        shared_with_user_ids: List[UUID],
    ):
        """Notify users when a document is shared with them"""
        for user_id in shared_with_user_ids:
            await self.create(
                db=db,
                user_id=user_id,
                notification_type=NotificationType.DOCUMENT_SHARED,
                title="Document Shared",
                message=f"{shared_by.name} shared '{document_title}' with you",
                resource_type="document",
                resource_id=document_id,
                action_url=f"/documents/{document_id}",
                sender_id=shared_by.id,
            )

    async def notify_review_requested(
        self,
        db: AsyncSession,
        document_id: UUID,
        document_title: str,
        requester: User,
        reviewer_ids: List[UUID],
    ):
        """Notify reviewers when a document needs review"""
        for user_id in reviewer_ids:
            await self.create(
                db=db,
                user_id=user_id,
                notification_type=NotificationType.REVIEW_REQUESTED,
                priority=NotificationPriority.HIGH,
                title="Review Requested",
                message=f"{requester.name} requested your review on '{document_title}'",
                resource_type="document",
                resource_id=document_id,
                action_url=f"/documents/{document_id}",
                sender_id=requester.id,
            )

    async def notify_document_approved(
        self,
        db: AsyncSession,
        document_id: UUID,
        document_title: str,
        approver: User,
        owner_id: UUID,
    ):
        """Notify document owner when their document is approved"""
        await self.create(
            db=db,
            user_id=owner_id,
            notification_type=NotificationType.DOCUMENT_APPROVED,
            title="Document Approved",
            message=f"Your document '{document_title}' was approved by {approver.name}",
            resource_type="document",
            resource_id=document_id,
            action_url=f"/documents/{document_id}",
            sender_id=approver.id,
        )

    async def notify_document_rejected(
        self,
        db: AsyncSession,
        document_id: UUID,
        document_title: str,
        rejector: User,
        owner_id: UUID,
        reason: Optional[str] = None,
    ):
        """Notify document owner when their document is rejected"""
        message = f"Your document '{document_title}' was rejected by {rejector.name}"
        if reason:
            message += f". Reason: {reason}"

        await self.create(
            db=db,
            user_id=owner_id,
            notification_type=NotificationType.DOCUMENT_REJECTED,
            priority=NotificationPriority.HIGH,
            title="Document Rejected",
            message=message,
            resource_type="document",
            resource_id=document_id,
            action_url=f"/documents/{document_id}",
            sender_id=rejector.id,
        )

    async def notify_comment_mention(
        self,
        db: AsyncSession,
        document_id: UUID,
        document_title: str,
        comment_id: UUID,
        commenter: User,
        mentioned_user_ids: List[UUID],
    ):
        """Notify users when they are mentioned in a comment"""
        for user_id in mentioned_user_ids:
            await self.create(
                db=db,
                user_id=user_id,
                notification_type=NotificationType.COMMENT_MENTION,
                title="You were mentioned",
                message=f"{commenter.name} mentioned you in a comment on '{document_title}'",
                resource_type="comment",
                resource_id=comment_id,
                action_url=f"/documents/{document_id}#comment-{comment_id}",
                sender_id=commenter.id,
            )

    async def notify_comment_reply(
        self,
        db: AsyncSession,
        document_id: UUID,
        document_title: str,
        comment_id: UUID,
        replier: User,
        original_author_id: UUID,
    ):
        """Notify user when someone replies to their comment"""
        if replier.id == original_author_id:
            return  # Don't notify self

        await self.create(
            db=db,
            user_id=original_author_id,
            notification_type=NotificationType.COMMENT_REPLY,
            title="New Reply",
            message=f"{replier.name} replied to your comment on '{document_title}'",
            resource_type="comment",
            resource_id=comment_id,
            action_url=f"/documents/{document_id}#comment-{comment_id}",
            sender_id=replier.id,
        )

    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Notification], int, int]:
        """
        Get notifications for a user.
        Returns (notifications, total, unread_count)
        """
        query = select(Notification).where(Notification.user_id == user_id)

        if unread_only:
            query = query.where(Notification.is_read == 0)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Count unread
        unread_query = select(func.count()).where(
            and_(Notification.user_id == user_id, Notification.is_read == 0)
        )
        unread_result = await db.execute(unread_query)
        unread_count = unread_result.scalar() or 0

        # Get items
        query = query.order_by(desc(Notification.created_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        notifications = list(result.scalars().all())

        return notifications, total, unread_count

    async def mark_as_read(
        self,
        db: AsyncSession,
        notification_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Mark a notification as read"""
        result = await db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
            .values(is_read=1, read_at=datetime.utcnow())
        )
        await db.commit()
        return result.rowcount > 0

    async def mark_all_as_read(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """Mark all notifications as read for a user"""
        result = await db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == 0,
                )
            )
            .values(is_read=1, read_at=datetime.utcnow())
        )
        await db.commit()
        return result.rowcount

    async def delete_notification(
        self,
        db: AsyncSession,
        notification_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Delete a notification"""
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
        )
        notification = result.scalar_one_or_none()

        if notification:
            await db.delete(notification)
            await db.commit()
            return True
        return False

    async def get_unread_count(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """Get count of unread notifications"""
        result = await db.execute(
            select(func.count()).where(
                and_(Notification.user_id == user_id, Notification.is_read == 0)
            )
        )
        return result.scalar() or 0


# Singleton instance
notification_service = NotificationService()
