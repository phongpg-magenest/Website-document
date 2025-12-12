import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum as SQLEnum, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"


class DocumentVisibility(str, enum.Enum):
    PUBLIC = "public"
    PROJECT = "project"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


class FileType(str, enum.Enum):
    DOCX = "docx"
    DOC = "doc"
    XLSX = "xlsx"
    XLS = "xls"
    PDF = "pdf"
    MD = "md"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)  # S3 key
    file_type = Column(SQLEnum(FileType), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    content_text = Column(Text, nullable=True)  # extracted text
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.DRAFT)
    visibility = Column(SQLEnum(DocumentVisibility), default=DocumentVisibility.PRIVATE)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    tags = Column(ARRAY(String), default=[])
    version = Column(String(20), default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="documents", foreign_keys=[owner_id])
    project = relationship("Project", back_populates="documents")
    category = relationship("Category", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    approvals = relationship("ApprovalHistory", back_populates="document", cascade="all, delete-orphan")


class ApprovalAction(str, enum.Enum):
    """Actions in the approval workflow"""
    SUBMIT_FOR_REVIEW = "submit_for_review"  # Draft -> Review
    APPROVE = "approve"                       # Review -> Approved
    REJECT = "reject"                         # Review -> Draft (with reason)
    PUBLISH = "publish"                       # Approved -> Published
    UNPUBLISH = "unpublish"                   # Published -> Approved
    REQUEST_CHANGES = "request_changes"       # Review -> Draft (similar to reject)


class ApprovalHistory(Base):
    """Track approval workflow history for documents"""
    __tablename__ = "approval_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    action = Column(SQLEnum(ApprovalAction, values_callable=lambda x: [e.value for e in x]), nullable=False)
    from_status = Column(SQLEnum(DocumentStatus), nullable=False)
    to_status = Column(SQLEnum(DocumentStatus), nullable=False)
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=True)  # Required for reject/request_changes
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="approvals")
    user = relationship("User")


class ChangeType(str, enum.Enum):
    # Enum values must match PostgreSQL enum values exactly (lowercase)
    CREATED = "created"
    CONTENT_UPDATED = "content_updated"
    METADATA_UPDATED = "metadata_updated"
    STATUS_CHANGED = "status_changed"
    FILE_REPLACED = "file_replaced"
    RESTORED = "restored"

    def __str__(self):
        return self.value


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    version = Column(String(20), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)  # Auto-increment version number
    content_snapshot = Column(Text, nullable=True)  # Full text content at this version
    file_path = Column(String(1000), nullable=True)  # Storage key for this version's file
    file_size = Column(Integer, nullable=True)  # File size in bytes
    file_type = Column(SQLEnum(FileType), nullable=True)  # File type at this version
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    change_type = Column(SQLEnum(ChangeType, values_callable=lambda x: [e.value for e in x]), default=ChangeType.CONTENT_UPDATED)
    change_summary = Column(String(500), nullable=True)  # User-provided summary
    changes_detail = Column(Text, nullable=True)  # JSON: detailed field changes
    previous_status = Column(SQLEnum(DocumentStatus), nullable=True)
    new_status = Column(SQLEnum(DocumentStatus), nullable=True)
    is_major_version = Column(Integer, default=0)  # 1 for major (1.0, 2.0), 0 for minor (1.1, 1.2)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="versions")
    user = relationship("User")


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    odoo_project_id = Column(String, unique=True, nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="project")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="members")
    user = relationship("User")


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="category")
    children = relationship("Category", backref="parent", remote_side=[id])


class Comment(Base):
    """Comments on documents - supports threading and @mentions"""
    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True)  # For replies
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_resolved = Column(Integer, default=0)  # 0 = open, 1 = resolved
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    # Position in document (optional, for inline comments)
    position_start = Column(Integer, nullable=True)  # Character position start
    position_end = Column(Integer, nullable=True)    # Character position end
    position_context = Column(String(500), nullable=True)  # Text context for position
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", backref="comments")
    author = relationship("User", foreign_keys=[author_id])
    resolved_by_user = relationship("User", foreign_keys=[resolved_by])
    # Self-referential: parent has many replies
    replies = relationship(
        "Comment",
        backref="parent",
        remote_side=[id],
        cascade="all, delete-orphan",
        single_parent=True,
    )
    mentions = relationship("CommentMention", back_populates="comment", cascade="all, delete-orphan")


class CommentMention(Base):
    """Track @mentions in comments"""
    __tablename__ = "comment_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=False)
    mentioned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    comment = relationship("Comment", back_populates="mentions")
    mentioned_user = relationship("User")
