"""
Prompt Template Model - Quản lý AI prompt templates
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class PromptCategory(str, enum.Enum):
    """Categories for organizing prompts"""
    DOCUMENT_GENERATION = "document_generation"
    DOCUMENT_REVIEW = "document_review"
    RAG_QUERY = "rag_query"
    SUMMARIZATION = "summarization"
    KEYWORD_EXTRACTION = "keyword_extraction"
    CUSTOM = "custom"


class PromptTemplate(Base):
    """
    AI Prompt Template - Cho phép Admin quản lý prompts mà không cần thay đổi code

    Tương đương ai.prompt.template trong Odoo:
    - Name: Tên template
    - Content: Nội dung prompt với variables
    - Variables: Danh sách biến có thể thay thế
    - Model Config: Cấu hình cho LLM model
    """
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic info
    name = Column(String(200), nullable=False)  # e.g., "SRS Generation Prompt"
    description = Column(Text, nullable=True)
    category = Column(
        SQLEnum(PromptCategory, values_callable=lambda x: [e.value for e in x]),
        default=PromptCategory.CUSTOM
    )

    # Prompt content with placeholders
    # Placeholders use format: {{variable_name}}
    # Example: "Generate a {{document_type}} based on: {{reference_content}}"
    content = Column(Text, nullable=False)

    # System prompt (optional, for chat-based models)
    system_prompt = Column(Text, nullable=True)

    # Variables definition - JSON array of variable definitions
    # Example: [{"name": "document_type", "description": "Type of document", "required": true, "default": null}]
    variables = Column(JSON, default=list)

    # Model configuration - JSON object
    # Example: {"model": "gemini-2.0-flash", "temperature": 0.7, "max_tokens": 8192}
    model_config = Column(JSON, default=dict)

    # Output format instructions (optional)
    # Example: "json", "markdown", "plain_text"
    output_format = Column(String(50), default="plain_text")

    # Versioning
    version = Column(String(20), default="1.0")
    is_active = Column(Integer, default=1)  # 1 = active, 0 = inactive
    is_default = Column(Integer, default=0)  # 1 = default for this category

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    versions = relationship(
        "PromptTemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan"
    )


class PromptTemplateVersion(Base):
    """
    Version history for prompt templates
    Track changes to prompts over time
    """
    __tablename__ = "prompt_template_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"), nullable=False)

    # Snapshot of the template at this version
    version = Column(String(20), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)

    content = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=True)
    variables = Column(JSON, default=list)
    model_config = Column(JSON, default=dict)

    # Change tracking
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    change_summary = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    template = relationship("PromptTemplate", back_populates="versions")
    user = relationship("User")
