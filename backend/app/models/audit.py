"""
Audit Trail Model - Track all document actions and system activities
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class AuditAction(str, enum.Enum):
    """Types of auditable actions"""
    # Document actions
    DOCUMENT_CREATE = "document_create"
    DOCUMENT_VIEW = "document_view"
    DOCUMENT_UPDATE = "document_update"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_DOWNLOAD = "document_download"

    # Version actions
    VERSION_CREATE = "version_create"
    VERSION_RESTORE = "version_restore"

    # Workflow actions
    WORKFLOW_SUBMIT = "workflow_submit"
    WORKFLOW_APPROVE = "workflow_approve"
    WORKFLOW_REJECT = "workflow_reject"
    WORKFLOW_PUBLISH = "workflow_publish"
    WORKFLOW_UNPUBLISH = "workflow_unpublish"

    # Comment actions
    COMMENT_CREATE = "comment_create"
    COMMENT_UPDATE = "comment_update"
    COMMENT_DELETE = "comment_delete"
    COMMENT_RESOLVE = "comment_resolve"

    # Search/RAG actions
    SEARCH_QUERY = "search_query"
    RAG_QUERY = "rag_query"

    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"

    # Admin actions
    PROMPT_CREATE = "prompt_create"
    PROMPT_UPDATE = "prompt_update"
    PROMPT_DELETE = "prompt_delete"
    TEMPLATE_CREATE = "template_create"
    TEMPLATE_UPDATE = "template_update"


class AuditLog(Base):
    """
    Audit Trail - Log all system activities
    Tương đương ir.logging / mail.tracking trong Odoo
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Action info
    action = Column(
        SQLEnum(AuditAction, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # Who performed the action
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    user_email = Column(String(255), nullable=True)  # Store email for historical reference
    user_name = Column(String(255), nullable=True)   # Store name for historical reference

    # What was affected
    resource_type = Column(String(50), nullable=False)  # document, comment, user, prompt, etc.
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    resource_name = Column(String(500), nullable=True)  # Human readable name

    # Additional context
    details = Column(JSON, default=dict)  # Action-specific details
    changes = Column(JSON, default=dict)  # Before/after values for updates

    # Request info
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
