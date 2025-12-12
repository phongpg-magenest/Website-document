"""
Approval Workflow Service - Quản lý quy trình phê duyệt tài liệu
"""
from typing import List, Tuple, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import logging

from app.models.document import (
    Document,
    DocumentStatus,
    ApprovalHistory,
    ApprovalAction,
)
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


class ApprovalService:
    """Service for document approval workflow management"""

    # Define valid status transitions
    VALID_TRANSITIONS = {
        ApprovalAction.SUBMIT_FOR_REVIEW: (DocumentStatus.DRAFT, DocumentStatus.REVIEW),
        ApprovalAction.APPROVE: (DocumentStatus.REVIEW, DocumentStatus.APPROVED),
        ApprovalAction.REJECT: (DocumentStatus.REVIEW, DocumentStatus.DRAFT),
        ApprovalAction.REQUEST_CHANGES: (DocumentStatus.REVIEW, DocumentStatus.DRAFT),
        ApprovalAction.PUBLISH: (DocumentStatus.APPROVED, DocumentStatus.PUBLISHED),
        ApprovalAction.UNPUBLISH: (DocumentStatus.PUBLISHED, DocumentStatus.APPROVED),
    }

    # Actions that require a comment
    COMMENT_REQUIRED_ACTIONS = {
        ApprovalAction.REJECT,
        ApprovalAction.REQUEST_CHANGES,
    }

    def get_available_actions(
        self,
        document: Document,
        user: User,
    ) -> List[ApprovalAction]:
        """
        Get available approval actions for a document based on current status and user role.

        Args:
            document: The document to check
            user: The current user

        Returns:
            List of available ApprovalAction values
        """
        available = []
        current_status = document.status

        for action, (from_status, _) in self.VALID_TRANSITIONS.items():
            if current_status == from_status:
                # Check user permissions
                if self._can_perform_action(document, user, action):
                    available.append(action)

        return available

    def _can_perform_action(
        self,
        document: Document,
        user: User,
        action: ApprovalAction,
    ) -> bool:
        """
        Check if a user can perform a specific action.

        Rules:
        - Document owner can: SUBMIT_FOR_REVIEW
        - ADMIN/MANAGER can: APPROVE, REJECT, REQUEST_CHANGES, PUBLISH, UNPUBLISH
        - Cannot approve own document (unless ADMIN)
        """
        is_owner = document.owner_id == user.id
        is_admin = user.role == UserRole.ADMIN
        is_manager = user.role == UserRole.MANAGER

        if action == ApprovalAction.SUBMIT_FOR_REVIEW:
            # Owner or admin can submit for review
            return is_owner or is_admin

        if action in [ApprovalAction.APPROVE, ApprovalAction.REJECT, ApprovalAction.REQUEST_CHANGES]:
            # Only admin/manager can approve/reject
            # Cannot approve own document (unless admin)
            if is_admin:
                return True
            if is_manager and not is_owner:
                return True
            return False

        if action in [ApprovalAction.PUBLISH, ApprovalAction.UNPUBLISH]:
            # Only admin/manager can publish/unpublish
            return is_admin or is_manager

        return False

    def can_edit_document(self, document: Document, user: User) -> bool:
        """
        Check if user can edit the document.

        Rules:
        - Can edit in DRAFT status (owner or admin)
        - Cannot edit in REVIEW, APPROVED, PUBLISHED status (except admin)
        """
        is_owner = document.owner_id == user.id
        is_admin = user.role == UserRole.ADMIN

        if is_admin:
            return True

        if document.status == DocumentStatus.DRAFT:
            return is_owner

        return False

    def can_approve_document(self, document: Document, user: User) -> bool:
        """Check if user can approve/reject the document."""
        is_admin = user.role == UserRole.ADMIN
        is_manager = user.role == UserRole.MANAGER
        is_owner = document.owner_id == user.id

        # Document must be in REVIEW status
        if document.status != DocumentStatus.REVIEW:
            return False

        # Admin can always approve
        if is_admin:
            return True

        # Manager can approve if not owner
        if is_manager and not is_owner:
            return True

        return False

    async def perform_action(
        self,
        db: AsyncSession,
        document: Document,
        user: User,
        action: ApprovalAction,
        comment: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[ApprovalHistory]]:
        """
        Perform an approval action on a document.

        Args:
            db: Database session
            document: The document
            user: The user performing the action
            action: The action to perform
            comment: Optional comment (required for some actions)

        Returns:
            Tuple of (success, message, approval_history)
        """
        # Validate action is available
        available_actions = self.get_available_actions(document, user)
        if action not in available_actions:
            return False, f"Action '{action.value}' is not available for this document", None

        # Check comment requirement
        if action in self.COMMENT_REQUIRED_ACTIONS and not comment:
            return False, f"Comment is required for action '{action.value}'", None

        # Get transition
        from_status, to_status = self.VALID_TRANSITIONS[action]

        # Create approval history entry
        approval_entry = ApprovalHistory(
            document_id=document.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            performed_by=user.id,
            comment=comment,
        )

        # Update document status
        document.status = to_status

        db.add(approval_entry)
        await db.flush()  # Use flush instead of commit - let endpoint handle commit

        logger.info(
            f"Document {document.id} status changed: {from_status.value} -> {to_status.value} "
            f"by user {user.id} ({action.value})"
        )

        return True, f"Document status changed to {to_status.value}", approval_entry

    async def get_approval_history(
        self,
        db: AsyncSession,
        document_id: UUID,
        limit: int = 50,
    ) -> List[ApprovalHistory]:
        """
        Get approval history for a document.

        Args:
            db: Database session
            document_id: The document ID
            limit: Maximum number of entries to return

        Returns:
            List of ApprovalHistory entries, newest first
        """
        result = await db.execute(
            select(ApprovalHistory)
            .where(ApprovalHistory.document_id == document_id)
            .order_by(desc(ApprovalHistory.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_approvals(
        self,
        db: AsyncSession,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Document], int]:
        """
        Get documents pending approval that the user can approve.

        Args:
            db: Database session
            user: The current user
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (documents, total_count)
        """
        # Only admin/manager can see pending approvals
        if user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            return [], 0

        # Base query: documents in REVIEW status
        base_query = select(Document).where(Document.status == DocumentStatus.REVIEW)

        # If manager, exclude own documents
        if user.role == UserRole.MANAGER:
            base_query = base_query.where(Document.owner_id != user.id)

        # Get total count
        from sqlalchemy import func
        count_result = await db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await db.execute(
            base_query
            .order_by(desc(Document.updated_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        documents = list(result.scalars().all())

        return documents, total


# Singleton instance
approval_service = ApprovalService()
