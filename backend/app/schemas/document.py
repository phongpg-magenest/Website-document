from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from uuid import UUID

from app.models.document import DocumentStatus, DocumentVisibility, FileType, ChangeType, ApprovalAction


class DocumentBase(BaseModel):
    title: str = Field(..., max_length=500)
    visibility: DocumentVisibility = DocumentVisibility.PRIVATE
    project_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    tags: List[str] = []


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    status: Optional[DocumentStatus] = None
    visibility: Optional[DocumentVisibility] = None
    project_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    tags: Optional[List[str]] = None


class DocumentResponse(DocumentBase):
    id: UUID
    file_path: str
    file_type: FileType
    file_size: int
    status: DocumentStatus
    owner_id: UUID
    version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentDetail(DocumentResponse):
    content_text: Optional[str] = None
    owner_name: Optional[str] = None
    project_name: Optional[str] = None
    category_name: Optional[str] = None


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version: str
    version_number: int
    change_type: ChangeType
    change_summary: Optional[str]
    changes_detail: Optional[str]  # JSON string
    previous_status: Optional[DocumentStatus]
    new_status: Optional[DocumentStatus]
    file_path: Optional[str]
    file_size: Optional[int]
    file_type: Optional[FileType]
    is_major_version: int
    changed_by: UUID
    changed_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentVersionDetail(DocumentVersionResponse):
    """Version with full content snapshot"""
    content_snapshot: Optional[str] = None


class UploadNewVersionRequest(BaseModel):
    """Request body for uploading new version"""
    change_summary: Optional[str] = Field(None, max_length=500, description="Summary of changes")
    is_major_version: bool = Field(False, description="True for major version bump (1.0 -> 2.0)")


class RestoreVersionRequest(BaseModel):
    """Request body for restoring a version"""
    version_id: UUID = Field(..., description="ID of the version to restore")
    change_summary: Optional[str] = Field(None, max_length=500, description="Reason for restoring")


class DiffLine(BaseModel):
    """A single line in the diff output"""
    line_number_old: Optional[int] = None
    line_number_new: Optional[int] = None
    content: str
    change_type: str  # "unchanged", "added", "removed", "modified"


class DiffHunk(BaseModel):
    """A hunk/block of changes in the diff"""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[DiffLine]


class VersionCompareResponse(BaseModel):
    """Response for version comparison"""
    document_id: UUID
    version_old: str
    version_new: str
    version_old_id: UUID
    version_new_id: UUID
    total_additions: int
    total_deletions: int
    total_changes: int
    diff_hunks: List[DiffHunk]
    # Summary statistics
    old_line_count: int
    new_line_count: int
    similarity_percentage: float  # How similar are the two versions (0-100)


# Approval workflow schemas
class ApprovalRequest(BaseModel):
    """Request for approval workflow action"""
    action: ApprovalAction
    comment: Optional[str] = Field(None, max_length=1000, description="Required for reject/request_changes")


class ApprovalHistoryResponse(BaseModel):
    """Response for approval history entry"""
    id: UUID
    document_id: UUID
    action: ApprovalAction
    from_status: DocumentStatus
    to_status: DocumentStatus
    performed_by: UUID
    performed_by_name: Optional[str] = None
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowStatusResponse(BaseModel):
    """Response showing document's current workflow status and available actions"""
    document_id: UUID
    current_status: DocumentStatus
    available_actions: List[ApprovalAction]
    approval_history: List[ApprovalHistoryResponse]
    can_edit: bool  # Whether current user can edit the document
    can_approve: bool  # Whether current user can approve/reject


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Comment schemas
class CommentCreate(BaseModel):
    """Create a new comment on a document"""
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[UUID] = Field(None, description="Parent comment ID for replies")
    # Optional position for inline comments
    position_start: Optional[int] = Field(None, ge=0, description="Character position start")
    position_end: Optional[int] = Field(None, ge=0, description="Character position end")
    position_context: Optional[str] = Field(None, max_length=500, description="Text context")


class CommentUpdate(BaseModel):
    """Update a comment"""
    content: str = Field(..., min_length=1, max_length=5000)


class MentionResponse(BaseModel):
    """User mention in a comment"""
    user_id: UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None


class CommentResponse(BaseModel):
    """Response for a single comment"""
    id: UUID
    document_id: UUID
    parent_id: Optional[UUID]
    author_id: UUID
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    content: str
    is_resolved: bool
    resolved_by: Optional[UUID]
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime]
    position_start: Optional[int]
    position_end: Optional[int]
    position_context: Optional[str]
    mentions: List[MentionResponse] = []
    reply_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommentThreadResponse(CommentResponse):
    """Comment with its replies"""
    replies: List[CommentResponse] = []


class CommentListResponse(BaseModel):
    """Paginated list of comments"""
    items: List[CommentThreadResponse]
    total: int
    total_resolved: int
    total_unresolved: int


# Project schemas
class ProjectBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: UUID
    odoo_project_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Category schemas
class CategoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    parent_id: Optional[UUID] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[UUID] = None


class CategoryResponse(CategoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
