"""
Analytics Schemas
"""
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel


class DocumentStatsResponse(BaseModel):
    """Document statistics"""
    total_documents: int
    by_status: Dict[str, int]
    by_file_type: Dict[str, int]
    total_size_bytes: int
    total_size_mb: float


class UserStatsResponse(BaseModel):
    """User statistics"""
    total_users: int
    active_users_30d: int
    by_role: Dict[str, int]


class ActivityStatsResponse(BaseModel):
    """Activity statistics"""
    period_days: int
    total_actions: int
    by_action: Dict[str, int]
    daily_activity: Dict[str, int]
    top_users: Dict[str, int]


class WorkflowStatsResponse(BaseModel):
    """Workflow statistics"""
    period_days: int
    workflow_actions: Dict[str, int]
    pending_reviews: int
    published_documents: int


class StorageStatsResponse(BaseModel):
    """Storage statistics"""
    by_file_type: Dict[str, Dict[str, Any]]
    total_documents: int
    total_size_bytes: int
    total_size_mb: float
    versions_size_bytes: int
    versions_size_mb: float


class SearchStatsResponse(BaseModel):
    """Search/RAG statistics"""
    period_days: int
    search_queries: int
    rag_queries: int
    total_queries: int


class DashboardSummaryResponse(BaseModel):
    """Complete dashboard summary"""
    documents: DocumentStatsResponse
    users: UserStatsResponse
    activity: ActivityStatsResponse
    workflow: WorkflowStatsResponse
    storage: StorageStatsResponse
    generated_at: str
