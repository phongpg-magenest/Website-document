"""
Prompt Template Schemas
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class PromptCategory(str, Enum):
    DOCUMENT_GENERATION = "document_generation"
    DOCUMENT_REVIEW = "document_review"
    RAG_QUERY = "rag_query"
    SUMMARIZATION = "summarization"
    KEYWORD_EXTRACTION = "keyword_extraction"
    CUSTOM = "custom"


class PromptVariableDefinition(BaseModel):
    """Definition of a variable in prompt template"""
    name: str = Field(..., description="Variable name (used as {{name}} in template)")
    description: str = Field(..., description="Description of what this variable is for")
    required: bool = Field(default=True, description="Whether this variable is required")
    default: Optional[str] = Field(default=None, description="Default value if not provided")


class ModelConfigSchema(BaseModel):
    """LLM Model configuration"""
    model: str = Field(default="gemini-2.0-flash", description="Model name")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Creativity level")
    max_tokens: int = Field(default=8192, ge=1, le=100000, description="Max output tokens")
    top_p: Optional[float] = Field(default=None, ge=0, le=1, description="Top-p sampling")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-k sampling")


# ==================== CREATE ====================

class PromptTemplateCreate(BaseModel):
    """Schema for creating a new prompt template"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: PromptCategory = PromptCategory.CUSTOM

    content: str = Field(..., min_length=1, description="Prompt content with {{variables}}")
    system_prompt: Optional[str] = Field(default=None, description="System prompt for chat models")

    variables: List[PromptVariableDefinition] = Field(default_factory=list)
    model_config_data: Optional[ModelConfigSchema] = Field(default=None, alias="model_config")

    output_format: str = Field(default="plain_text", description="Expected output format")
    is_default: bool = Field(default=False, description="Set as default for this category")

    class Config:
        populate_by_name = True


# ==================== UPDATE ====================

class PromptTemplateUpdate(BaseModel):
    """Schema for updating a prompt template"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[PromptCategory] = None

    content: Optional[str] = Field(default=None, min_length=1)
    system_prompt: Optional[str] = None

    variables: Optional[List[PromptVariableDefinition]] = None
    model_config_data: Optional[ModelConfigSchema] = Field(default=None, alias="model_config")

    output_format: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None

    change_summary: Optional[str] = Field(default=None, max_length=500, description="Summary of changes")

    class Config:
        populate_by_name = True


# ==================== RESPONSE ====================

class PromptTemplateResponse(BaseModel):
    """Response schema for prompt template"""
    id: UUID
    name: str
    description: Optional[str]
    category: str

    content: str
    system_prompt: Optional[str]

    variables: List[Dict[str, Any]]
    model_config_data: Dict[str, Any] = Field(alias="model_config")

    output_format: str
    version: str
    is_active: bool
    is_default: bool

    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class PromptTemplateListResponse(BaseModel):
    """List response with pagination"""
    items: List[PromptTemplateResponse]
    total: int
    skip: int
    limit: int


# ==================== VERSION ====================

class PromptVersionResponse(BaseModel):
    """Response schema for prompt template version"""
    id: UUID
    template_id: UUID
    version: str
    version_number: int

    content: str
    system_prompt: Optional[str]
    variables: List[Dict[str, Any]]
    model_config_data: Dict[str, Any] = Field(alias="model_config")

    changed_by: UUID
    change_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class PromptVersionListResponse(BaseModel):
    """List of versions for a template"""
    items: List[PromptVersionResponse]
    total: int


# ==================== EXECUTION ====================

class PromptExecuteRequest(BaseModel):
    """Request to execute a prompt template with variables"""
    template_id: UUID
    variables: Dict[str, str] = Field(default_factory=dict, description="Variable values to substitute")


class PromptPreviewRequest(BaseModel):
    """Request to preview a prompt with variables substituted"""
    content: str = Field(..., description="Prompt content with {{variables}}")
    variables: Dict[str, str] = Field(default_factory=dict)


class PromptPreviewResponse(BaseModel):
    """Response with rendered prompt"""
    rendered_content: str
    missing_variables: List[str] = Field(default_factory=list)


# ==================== TEST ====================

class PromptTestRequest(BaseModel):
    """Request to test a prompt template"""
    template_id: Optional[UUID] = None
    content: Optional[str] = None  # For testing without saving
    system_prompt: Optional[str] = None
    variables: Dict[str, str] = Field(default_factory=dict)
    model_config_data: Optional[ModelConfigSchema] = Field(default=None, alias="model_config")

    class Config:
        populate_by_name = True


class PromptTestResponse(BaseModel):
    """Response from testing a prompt"""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time_seconds: float
    tokens_used: Optional[int] = None
