"""
Audit Service - Log all system activities
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from fastapi import Request

from app.models.audit import AuditLog, AuditAction
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditService:
    """Service for audit logging"""

    async def log(
        self,
        db: AsyncSession,
        action: AuditAction,
        user: Optional[User],
        resource_type: str,
        resource_id: Optional[UUID] = None,
        resource_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log an audit event.

        Args:
            db: Database session
            action: Type of action performed
            user: User who performed the action (None for system actions)
            resource_type: Type of resource affected (document, comment, etc.)
            resource_id: ID of the affected resource
            resource_name: Human-readable name of the resource
            details: Additional action-specific details
            changes: Before/after values for updates
            request: FastAPI request object for IP/user-agent
        """
        # Extract request info
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]

        log_entry = AuditLog(
            action=action,
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            user_name=user.name if user else None,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details or {},
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(log_entry)
        await db.flush()

        logger.info(
            f"Audit: {action.value} by {user.email if user else 'system'} "
            f"on {resource_type}/{resource_id}"
        )

        return log_entry

    async def log_document_action(
        self,
        db: AsyncSession,
        action: AuditAction,
        user: User,
        document_id: UUID,
        document_title: str,
        details: Optional[Dict] = None,
        changes: Optional[Dict] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """Convenience method for document-related actions"""
        return await self.log(
            db=db,
            action=action,
            user=user,
            resource_type="document",
            resource_id=document_id,
            resource_name=document_title,
            details=details,
            changes=changes,
            request=request,
        )

    async def get_logs(
        self,
        db: AsyncSession,
        action: Optional[AuditAction] = None,
        user_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[AuditLog], int]:
        """
        Get audit logs with filtering.
        """
        query = select(AuditLog)

        if action:
            query = query.where(AuditLog.action == action)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if from_date:
            query = query.where(AuditLog.created_at >= from_date)
        if to_date:
            query = query.where(AuditLog.created_at <= to_date)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get items
        query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        logs = list(result.scalars().all())

        return logs, total

    async def get_document_history(
        self,
        db: AsyncSession,
        document_id: UUID,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get all audit logs for a specific document"""
        result = await db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.resource_type == "document",
                    AuditLog.resource_id == document_id,
                )
            )
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        db: AsyncSession,
        user_id: UUID,
        days: int = 30,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get recent activity for a specific user"""
        from_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.created_at >= from_date,
                )
            )
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_activity_summary(
        self,
        db: AsyncSession,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get summary of recent activity"""
        from_date = datetime.utcnow() - timedelta(days=days)

        # Count by action type
        action_counts = await db.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .where(AuditLog.created_at >= from_date)
            .group_by(AuditLog.action)
        )

        # Count by user
        user_counts = await db.execute(
            select(AuditLog.user_email, func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.user_email.isnot(None),
                )
            )
            .group_by(AuditLog.user_email)
            .order_by(desc(func.count(AuditLog.id)))
            .limit(10)
        )

        # Count by resource type
        resource_counts = await db.execute(
            select(AuditLog.resource_type, func.count(AuditLog.id))
            .where(AuditLog.created_at >= from_date)
            .group_by(AuditLog.resource_type)
        )

        return {
            "period_days": days,
            "by_action": {row[0].value: row[1] for row in action_counts},
            "by_user": {row[0]: row[1] for row in user_counts},
            "by_resource": {row[0]: row[1] for row in resource_counts},
        }


# Singleton instance
audit_service = AuditService()
