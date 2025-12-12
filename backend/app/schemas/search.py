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
    # RAG options
    use_rerank: bool = Field(default=True, description="Sử dụng Reranker để cải thiện kết quả")
    generate_answer: bool = Field(default=False, description="Sinh câu trả lời từ LLM")


class SearchResult(BaseModel):
    document_id: UUID
    title: str
    snippet: str
    highlights: List[str]
    score: float
    rerank_score: Optional[float] = None  # Score từ Reranker
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
    # RAG response
    answer: Optional[str] = None  # Câu trả lời từ LLM
    used_rerank: bool = False  # Có dùng Reranker không


class SearchSuggestion(BaseModel):
    suggestions: List[str]
