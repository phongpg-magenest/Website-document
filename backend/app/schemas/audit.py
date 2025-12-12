"""
Audit Trail Schemas
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from enum import Enum


class AuditAction(str, Enum):
    DOCUMENT_CREATE = "document_create"
    DOCUMENT_VIEW = "document_view"
    DOCUMENT_UPDATE = "document_update"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_DOWNLOAD = "document_download"
    VERSION_CREATE = "version_create"
    VERSION_RESTORE = "version_restore"
    WORKFLOW_SUBMIT = "workflow_submit"
    WORKFLOW_APPROVE = "workflow_approve"
    WORKFLOW_REJECT = "workflow_reject"
    WORKFLOW_PUBLISH = "workflow_publish"
    WORKFLOW_UNPUBLISH = "workflow_unpublish"
    COMMENT_CREATE = "comment_create"
    COMMENT_UPDATE = "comment_update"
    COMMENT_DELETE = "comment_delete"
    COMMENT_RESOLVE = "comment_resolve"
    SEARCH_QUERY = "search_query"
    RAG_QUERY = "rag_query"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PROMPT_CREATE = "prompt_create"
    PROMPT_UPDATE = "prompt_update"
    PROMPT_DELETE = "prompt_delete"
    TEMPLATE_CREATE = "template_create"
    TEMPLATE_UPDATE = "template_update"


class AuditLogResponse(BaseModel):
    """Response schema for audit log entry"""
    id: UUID
    action: str
    user_id: Optional[UUID]
    user_email: Optional[str]
    user_name: Optional[str]
    resource_type: str
    resource_id: Optional[UUID]
    resource_name: Optional[str]
    details: Dict[str, Any]
    changes: Dict[str, Any]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """List response with pagination"""
    items: List[AuditLogResponse]
    total: int
    skip: int
    limit: int


class ActivitySummaryResponse(BaseModel):
    """Summary of recent activity"""
    period_days: int
    by_action: Dict[str, int]
    by_user: Dict[str, int]
    by_resource: Dict[str, int]
