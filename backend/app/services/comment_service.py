"""
Comment Service - Quản lý comments và collaboration trên documents
"""
import re
import logging
from typing import List, Tuple, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_

from app.models.document import Comment, CommentMention
from app.models.user import User

logger = logging.getLogger(__name__)


class CommentService:
    """Service for managing document comments"""

    @staticmethod
    def extract_mentions(content: str) -> List[str]:
        """
        Extract @mentions from comment content.
        Returns list of email addresses mentioned.
        Pattern: @email@domain.com or @username
        """
        # Match @email pattern
        email_pattern = r'@([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)'
        emails = re.findall(email_pattern, content)
        return emails

    async def create_comment(
        self,
        db: AsyncSession,
        document_id: UUID,
        author_id: UUID,
        content: str,
        parent_id: Optional[UUID] = None,
        position_start: Optional[int] = None,
        position_end: Optional[int] = None,
        position_context: Optional[str] = None,
    ) -> Comment:
        """
        Create a new comment on a document.

        Args:
            db: Database session
            document_id: ID of the document
            author_id: ID of the comment author
            content: Comment content
            parent_id: Parent comment ID for replies
            position_start: Character position start (for inline comments)
            position_end: Character position end (for inline comments)
            position_context: Text context at the position

        Returns:
            Created Comment object
        """
        # Create comment
        comment = Comment(
            document_id=document_id,
            author_id=author_id,
            content=content,
            parent_id=parent_id,
            position_start=position_start,
            position_end=position_end,
            position_context=position_context,
        )

        db.add(comment)
        await db.flush()

        # Extract and create mentions
        mentioned_emails = self.extract_mentions(content)
        if mentioned_emails:
            for email in mentioned_emails:
                # Find user by email
                result = await db.execute(
                    select(User).where(User.email == email)
                )
                user = result.scalar_one_or_none()
                if user:
                    mention = CommentMention(
                        comment_id=comment.id,
                        mentioned_user_id=user.id,
                    )
                    db.add(mention)

        await db.commit()
        await db.refresh(comment)

        logger.info(f"Created comment {comment.id} on document {document_id} by user {author_id}")
        return comment

    async def update_comment(
        self,
        db: AsyncSession,
        comment: Comment,
        content: str,
        user_id: UUID,
    ) -> Comment:
        """
        Update a comment. Only author can update.
        """
        if comment.author_id != user_id:
            raise PermissionError("Only the author can edit this comment")

        # Update content
        comment.content = content

        # Re-process mentions
        # Delete existing mentions
        await db.execute(
            CommentMention.__table__.delete().where(
                CommentMention.comment_id == comment.id
            )
        )

        # Create new mentions
        mentioned_emails = self.extract_mentions(content)
        if mentioned_emails:
            for email in mentioned_emails:
                result = await db.execute(
                    select(User).where(User.email == email)
                )
                user = result.scalar_one_or_none()
                if user:
                    mention = CommentMention(
                        comment_id=comment.id,
                        mentioned_user_id=user.id,
                    )
                    db.add(mention)

        await db.commit()
        await db.refresh(comment)

        logger.info(f"Updated comment {comment.id}")
        return comment

    async def delete_comment(
        self,
        db: AsyncSession,
        comment: Comment,
        user_id: UUID,
        is_admin: bool = False,
    ) -> bool:
        """
        Delete a comment. Only author or admin can delete.
        """
        if comment.author_id != user_id and not is_admin:
            raise PermissionError("Only the author or admin can delete this comment")

        await db.delete(comment)
        await db.commit()

        logger.info(f"Deleted comment {comment.id}")
        return True

    async def resolve_comment(
        self,
        db: AsyncSession,
        comment: Comment,
        user_id: UUID,
    ) -> Comment:
        """Mark a comment as resolved."""
        comment.is_resolved = 1
        comment.resolved_by = user_id
        comment.resolved_at = datetime.utcnow()

        await db.commit()
        await db.refresh(comment)

        logger.info(f"Resolved comment {comment.id} by user {user_id}")
        return comment

    async def unresolve_comment(
        self,
        db: AsyncSession,
        comment: Comment,
    ) -> Comment:
        """Mark a comment as unresolved."""
        comment.is_resolved = 0
        comment.resolved_by = None
        comment.resolved_at = None

        await db.commit()
        await db.refresh(comment)

        logger.info(f"Unresolved comment {comment.id}")
        return comment

    async def get_comment_by_id(
        self,
        db: AsyncSession,
        comment_id: UUID,
    ) -> Optional[Comment]:
        """Get a comment by ID."""
        result = await db.execute(
            select(Comment).where(Comment.id == comment_id)
        )
        return result.scalar_one_or_none()

    async def get_document_comments(
        self,
        db: AsyncSession,
        document_id: UUID,
        include_resolved: bool = True,
        only_root: bool = True,
    ) -> Tuple[List[Comment], int, int]:
        """
        Get comments for a document.

        Args:
            db: Database session
            document_id: Document ID
            include_resolved: Whether to include resolved comments
            only_root: Only get root comments (not replies)

        Returns:
            Tuple of (comments, total_resolved, total_unresolved)
        """
        # Base query
        query = select(Comment).where(Comment.document_id == document_id)

        if only_root:
            query = query.where(Comment.parent_id.is_(None))

        if not include_resolved:
            query = query.where(Comment.is_resolved == 0)

        query = query.order_by(desc(Comment.created_at))

        result = await db.execute(query)
        comments = list(result.scalars().all())

        # Count resolved/unresolved
        count_query_resolved = select(func.count()).where(
            and_(Comment.document_id == document_id, Comment.is_resolved == 1)
        )
        if only_root:
            count_query_resolved = count_query_resolved.where(Comment.parent_id.is_(None))
        resolved_result = await db.execute(count_query_resolved)
        total_resolved = resolved_result.scalar() or 0

        count_query_unresolved = select(func.count()).where(
            and_(Comment.document_id == document_id, Comment.is_resolved == 0)
        )
        if only_root:
            count_query_unresolved = count_query_unresolved.where(Comment.parent_id.is_(None))
        unresolved_result = await db.execute(count_query_unresolved)
        total_unresolved = unresolved_result.scalar() or 0

        return comments, total_resolved, total_unresolved

    async def get_comment_replies(
        self,
        db: AsyncSession,
        parent_id: UUID,
    ) -> List[Comment]:
        """Get replies to a comment."""
        result = await db.execute(
            select(Comment)
            .where(Comment.parent_id == parent_id)
            .order_by(Comment.created_at)
        )
        return list(result.scalars().all())

    async def get_reply_count(
        self,
        db: AsyncSession,
        comment_id: UUID,
    ) -> int:
        """Get number of replies to a comment."""
        result = await db.execute(
            select(func.count()).where(Comment.parent_id == comment_id)
        )
        return result.scalar() or 0

    async def get_comment_mentions(
        self,
        db: AsyncSession,
        comment_id: UUID,
    ) -> List[CommentMention]:
        """Get mentions in a comment."""
        result = await db.execute(
            select(CommentMention).where(CommentMention.comment_id == comment_id)
        )
        return list(result.scalars().all())


# Singleton instance
comment_service = CommentService()
