from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID
import logging

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.template import CustomTemplate
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
    TemplateUploadResponse,
)
from app.services import document_processing_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def require_admin(user: User):
    """Check if user is admin"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


@router.post("/upload", response_model=TemplateUploadResponse)
async def upload_template(
    name: str = Form(...),
    document_type: str = Form(...),
    description: Optional[str] = Form(default=None),
    is_default: bool = Form(default=False),
    template_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a template file (DOCX, PDF, MD, TXT) as a custom template.
    The content will be extracted and used as the template structure.
    """
    require_admin(current_user)

    # Extract content from uploaded file
    try:
        content = await template_file.read()
        file_type = document_processing_service.get_file_type(template_file.filename)

        if not file_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Supported: DOCX, PDF, MD, TXT",
            )

        template_content = document_processing_service.extract_text(content, file_type)

        if not template_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract content from file",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing template file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}",
        )

    # If setting as default, unset other defaults for this document type
    if is_default:
        await db.execute(
            update(CustomTemplate)
            .where(CustomTemplate.document_type == document_type)
            .where(CustomTemplate.is_default == True)
            .values(is_default=False)
        )

    # Create template
    template = CustomTemplate(
        name=name,
        document_type=document_type.lower(),
        description=description,
        template_content=template_content,
        is_default=is_default,
        created_by=current_user.id,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return TemplateUploadResponse(
        id=template.id,
        name=template.name,
        document_type=template.document_type,
        message="Template uploaded successfully",
    )


@router.post("", response_model=TemplateResponse)
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new custom template by providing content directly"""
    require_admin(current_user)

    # If setting as default, unset other defaults for this document type
    if template_data.is_default:
        await db.execute(
            update(CustomTemplate)
            .where(CustomTemplate.document_type == template_data.document_type.lower())
            .where(CustomTemplate.is_default == True)
            .values(is_default=False)
        )

    template = CustomTemplate(
        name=template_data.name,
        document_type=template_data.document_type.lower(),
        description=template_data.description,
        template_content=template_data.template_content,
        is_default=template_data.is_default,
        created_by=current_user.id,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return TemplateResponse.model_validate(template)


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    document_type: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all custom templates"""
    query = select(CustomTemplate)

    if document_type:
        query = query.where(CustomTemplate.document_type == document_type.lower())

    if active_only:
        query = query.where(CustomTemplate.is_active == True)

    query = query.order_by(CustomTemplate.document_type, CustomTemplate.is_default.desc())

    result = await db.execute(query)
    templates = result.scalars().all()

    return TemplateListResponse(
        templates=[TemplateResponse.model_validate(t) for t in templates],
        total=len(templates),
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific template by ID"""
    result = await db.execute(
        select(CustomTemplate).where(CustomTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return TemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    template_data: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a custom template"""
    require_admin(current_user)

    result = await db.execute(
        select(CustomTemplate).where(CustomTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Update fields
    update_data = template_data.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        await db.execute(
            update(CustomTemplate)
            .where(CustomTemplate.document_type == template.document_type)
            .where(CustomTemplate.id != template_id)
            .where(CustomTemplate.is_default == True)
            .values(is_default=False)
        )

    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)

    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom template"""
    require_admin(current_user)

    result = await db.execute(
        select(CustomTemplate).where(CustomTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    await db.delete(template)
    await db.commit()

    return {"message": "Template deleted successfully"}


@router.post("/{template_id}/set-default")
async def set_default_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a template as default for its document type"""
    require_admin(current_user)

    result = await db.execute(
        select(CustomTemplate).where(CustomTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Unset other defaults for this document type
    await db.execute(
        update(CustomTemplate)
        .where(CustomTemplate.document_type == template.document_type)
        .where(CustomTemplate.is_default == True)
        .values(is_default=False)
    )

    # Set this one as default
    template.is_default = True
    await db.commit()

    return {"message": f"Template '{template.name}' set as default for {template.document_type}"}
