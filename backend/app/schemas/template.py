from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    document_type: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    template_content: str = Field(..., min_length=1)
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    template_content: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    document_type: str
    description: Optional[str]
    template_content: str
    is_active: bool
    is_default: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]
    total: int


class TemplateUploadResponse(BaseModel):
    id: UUID
    name: str
    document_type: str
    message: str
