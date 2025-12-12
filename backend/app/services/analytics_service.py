"""
Analytics Service - Dashboard statistics and metrics
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, case

from app.models.document import Document, DocumentStatus, DocumentVersion, FileType
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.models.notification import Notification

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for dashboard analytics and metrics"""

    async def get_document_stats(
        self,
        db: AsyncSession,
        project_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Get document statistics"""
        query = select(Document)
        if project_id:
            query = query.where(Document.project_id == project_id)

        # Total documents
        total_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar() or 0

        # By status
        status_query = select(Document.status, func.count(Document.id)).group_by(Document.status)
        if project_id:
            status_query = status_query.where(Document.project_id == project_id)
        status_result = await db.execute(status_query)
        by_status = {row[0].value: row[1] for row in status_result}

        # By file type
        type_query = select(Document.file_type, func.count(Document.id)).group_by(Document.file_type)
        if project_id:
            type_query = type_query.where(Document.project_id == project_id)
        type_result = await db.execute(type_query)
        by_type = {row[0].value: row[1] for row in type_result}

        # Total file size
        size_query = select(func.sum(Document.file_size))
        if project_id:
            size_query = size_query.where(Document.project_id == project_id)
        size_result = await db.execute(size_query)
        total_size = size_result.scalar() or 0

        return {
            "total_documents": total,
            "by_status": by_status,
            "by_file_type": by_type,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    async def get_user_stats(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get user statistics"""
        # Total users
        total_result = await db.execute(select(func.count(User.id)))
        total = total_result.scalar() or 0

        # Active users (logged in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_result = await db.execute(
            select(func.count(func.distinct(AuditLog.user_id))).where(
                and_(
                    AuditLog.created_at >= thirty_days_ago,
                    AuditLog.user_id.isnot(None),
                )
            )
        )
        active = active_result.scalar() or 0

        # By role
        role_result = await db.execute(
            select(User.role, func.count(User.id)).group_by(User.role)
        )
        by_role = {row[0].value: row[1] for row in role_result}

        return {
            "total_users": total,
            "active_users_30d": active,
            "by_role": by_role,
        }

    async def get_activity_stats(
        self,
        db: AsyncSession,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get activity statistics for recent period"""
        from_date = datetime.utcnow() - timedelta(days=days)

        # Total actions
        total_result = await db.execute(
            select(func.count(AuditLog.id)).where(AuditLog.created_at >= from_date)
        )
        total = total_result.scalar() or 0

        # By action type
        action_result = await db.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .where(AuditLog.created_at >= from_date)
            .group_by(AuditLog.action)
            .order_by(desc(func.count(AuditLog.id)))
        )
        by_action = {row[0].value: row[1] for row in action_result}

        # Daily activity
        daily_result = await db.execute(
            select(
                func.date(AuditLog.created_at).label('date'),
                func.count(AuditLog.id).label('count')
            )
            .where(AuditLog.created_at >= from_date)
            .group_by(func.date(AuditLog.created_at))
            .order_by(func.date(AuditLog.created_at))
        )
        daily = {str(row[0]): row[1] for row in daily_result}

        # Most active users
        user_result = await db.execute(
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
        top_users = {row[0]: row[1] for row in user_result}

        return {
            "period_days": days,
            "total_actions": total,
            "by_action": by_action,
            "daily_activity": daily,
            "top_users": top_users,
        }

    async def get_workflow_stats(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get workflow/approval statistics"""
        from_date = datetime.utcnow() - timedelta(days=days)

        # Documents by workflow status
        workflow_actions = [
            AuditAction.WORKFLOW_SUBMIT,
            AuditAction.WORKFLOW_APPROVE,
            AuditAction.WORKFLOW_REJECT,
            AuditAction.WORKFLOW_PUBLISH,
        ]

        workflow_result = await db.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.action.in_(workflow_actions),
                )
            )
            .group_by(AuditLog.action)
        )
        workflow_counts = {row[0].value: row[1] for row in workflow_result}

        # Pending reviews (documents in Review status)
        pending_result = await db.execute(
            select(func.count(Document.id)).where(Document.status == DocumentStatus.REVIEW)
        )
        pending_reviews = pending_result.scalar() or 0

        # Published documents
        published_result = await db.execute(
            select(func.count(Document.id)).where(Document.status == DocumentStatus.PUBLISHED)
        )
        published = published_result.scalar() or 0

        return {
            "period_days": days,
            "workflow_actions": workflow_counts,
            "pending_reviews": pending_reviews,
            "published_documents": published,
        }

    async def get_storage_stats(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get storage usage statistics"""
        # Total storage by file type
        type_result = await db.execute(
            select(
                Document.file_type,
                func.count(Document.id).label('count'),
                func.sum(Document.file_size).label('total_size')
            )
            .group_by(Document.file_type)
        )
        by_type = {
            row[0].value: {
                "count": row[1],
                "size_bytes": row[2] or 0,
                "size_mb": round((row[2] or 0) / (1024 * 1024), 2),
            }
            for row in type_result
        }

        # Total
        total_result = await db.execute(
            select(
                func.count(Document.id),
                func.sum(Document.file_size)
            )
        )
        row = total_result.first()
        total_count = row[0] or 0
        total_size = row[1] or 0

        # Versions storage
        version_result = await db.execute(
            select(func.sum(DocumentVersion.file_size))
        )
        version_size = version_result.scalar() or 0

        return {
            "by_file_type": by_type,
            "total_documents": total_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "versions_size_bytes": version_size,
            "versions_size_mb": round(version_size / (1024 * 1024), 2),
        }

    async def get_search_stats(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get search/RAG usage statistics"""
        from_date = datetime.utcnow() - timedelta(days=days)

        # Search queries count
        search_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.action == AuditAction.SEARCH_QUERY,
                )
            )
        )
        search_count = search_result.scalar() or 0

        # RAG queries count
        rag_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.action == AuditAction.RAG_QUERY,
                )
            )
        )
        rag_count = rag_result.scalar() or 0

        return {
            "period_days": days,
            "search_queries": search_count,
            "rag_queries": rag_count,
            "total_queries": search_count + rag_count,
        }

    async def get_dashboard_summary(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get complete dashboard summary"""
        document_stats = await self.get_document_stats(db)
        user_stats = await self.get_user_stats(db)
        activity_stats = await self.get_activity_stats(db, days=7)
        workflow_stats = await self.get_workflow_stats(db, days=30)
        storage_stats = await self.get_storage_stats(db)

        return {
            "documents": document_stats,
            "users": user_stats,
            "activity": activity_stats,
            "workflow": workflow_stats,
            "storage": storage_stats,
            "generated_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
analytics_service = AnalyticsService()
