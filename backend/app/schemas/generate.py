from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class DocumentType(str, Enum):
    SRS = "srs"  # Software Requirements Specification
    PRD = "prd"  # Product Requirements Document
    TECHNICAL_DESIGN = "technical_design"
    TEST_CASES = "test_cases"
    API_DOCUMENTATION = "api_documentation"
    RELEASE_NOTES = "release_notes"
    USER_GUIDE = "user_guide"


class OutputLanguage(str, Enum):
    VIETNAMESE = "vi"
    ENGLISH = "en"


class GenerateRequest(BaseModel):
    document_type: DocumentType
    language: OutputLanguage = OutputLanguage.VIETNAMESE
    context: Optional[str] = Field(None, max_length=5000)
    reference_document_ids: Optional[List[UUID]] = None


class GenerateJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerateJobResponse(BaseModel):
    job_id: UUID
    status: GenerateJobStatus
    document_type: DocumentType
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_document_id: Optional[UUID] = None
    error_message: Optional[str] = None


class GenerateTemplateInfo(BaseModel):
    document_type: DocumentType
    name: str
    description: str
    template_standard: Optional[str] = None


class GenerateTemplatesResponse(BaseModel):
    templates: List[GenerateTemplateInfo]


class GeneratedContent(BaseModel):
    title: str
    content: str
    sections: List[dict]
