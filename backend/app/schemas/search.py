from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.models.document import DocumentStatus, FileType


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    project_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    file_types: Optional[List[FileType]] = None
    status: Optional[DocumentStatus] = None
    tags: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    top_k: int = Field(default=10, ge=1, le=100)


class SearchResult(BaseModel):
    document_id: UUID
    title: str
    snippet: str
    highlights: List[str]
    score: float
    file_type: FileType
    owner_name: str
    project_name: Optional[str]
    tags: List[str]
    created_at: datetime


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int
    processing_time_ms: float


class SearchSuggestion(BaseModel):
    suggestions: List[str]
