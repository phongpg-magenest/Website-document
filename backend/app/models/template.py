import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class CustomTemplate(Base):
    """Custom document templates uploaded by admin"""
    __tablename__ = "custom_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)  # e.g., "SRS Template - IEEE 830"
    document_type = Column(String(50), nullable=False)  # e.g., "srs", "prd"
    description = Column(Text, nullable=True)

    # Template content - the actual template structure/format
    template_content = Column(Text, nullable=False)

    # Optional: file path if uploaded as file
    file_path = Column(String(1000), nullable=True)

    # Metadata
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default template for this type

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
