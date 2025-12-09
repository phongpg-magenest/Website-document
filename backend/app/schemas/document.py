from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.models.document import DocumentStatus, DocumentVisibility, FileType


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
    change_summary: Optional[str]
    changed_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


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
