"""
Prompt Manager API Endpoints
Admin-only endpoints for managing AI prompt templates
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import logging

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.prompt import PromptTemplate, PromptCategory
from app.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse,
    PromptVersionResponse,
    PromptVersionListResponse,
    PromptPreviewRequest,
    PromptPreviewResponse,
    PromptTestRequest,
    PromptTestResponse,
)
from app.services.prompt_service import prompt_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== Helper Functions ====================

def require_admin(user: User):
    """Require admin role for prompt management"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for prompt management",
        )


def template_to_response(template: PromptTemplate) -> PromptTemplateResponse:
    """Convert model to response schema"""
    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category.value if hasattr(template.category, 'value') else str(template.category),
        content=template.content,
        system_prompt=template.system_prompt,
        variables=template.variables or [],
        model_config=template.model_config or {},
        output_format=template.output_format,
        version=template.version,
        is_active=bool(template.is_active),
        is_default=bool(template.is_default),
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


# ==================== CRUD Endpoints ====================

@router.get("", response_model=PromptTemplateListResponse)
async def list_prompt_templates(
    category: Optional[PromptCategory] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all prompt templates.
    Non-admin users can only see active templates.
    """
    # Non-admin can only see active templates
    if current_user.role != UserRole.ADMIN:
        is_active = True

    templates, total = await prompt_service.get_templates(
        db=db,
        category=category,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
    )

    return PromptTemplateListResponse(
        items=[template_to_response(t) for t in templates],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    data: PromptTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new prompt template.
    Requires admin role.
    """
    require_admin(current_user)

    template = await prompt_service.create_template(
        db=db,
        data=data,
        user_id=current_user.id,
    )

    return template_to_response(template)


@router.get("/categories")
async def list_prompt_categories(
    current_user: User = Depends(get_current_user),
):
    """Get list of available prompt categories"""
    return [
        {
            "value": cat.value,
            "label": cat.name.replace("_", " ").title(),
        }
        for cat in PromptCategory
    ]


# ==================== Preview & Test Endpoints (MUST be before /{template_id}) ====================

@router.post("/preview", response_model=PromptPreviewResponse)
async def preview_prompt(
    data: PromptPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Preview a prompt with variables substituted.
    Does not execute the prompt.
    """
    rendered, missing = prompt_service.render_prompt(data.content, data.variables)

    return PromptPreviewResponse(
        rendered_content=rendered,
        missing_variables=missing,
    )


@router.post("/extract-variables")
async def extract_variables(
    content: str = Query(..., description="Prompt content to extract variables from"),
    current_user: User = Depends(get_current_user),
):
    """Extract variable names from prompt content"""
    variables = prompt_service.extract_variables(content)

    return {
        "variables": variables,
        "count": len(variables),
    }


@router.post("/test", response_model=PromptTestResponse)
async def test_prompt(
    data: PromptTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Test a prompt template with actual LLM execution.
    Can test saved template by ID or unsaved content directly.
    Requires admin role.
    """
    require_admin(current_user)

    if data.template_id:
        # Test saved template
        template = await prompt_service.get_template_by_id(db, data.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt template not found",
            )

        result = await prompt_service.execute_prompt(template, data.variables)
    elif data.content:
        # Test unsaved content
        model_config = data.model_config_data.model_dump() if data.model_config_data else None
        result = await prompt_service.test_prompt(
            content=data.content,
            variables=data.variables,
            system_prompt=data.system_prompt,
            model_config=model_config,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either template_id or content is required",
        )

    return PromptTestResponse(
        success=result["success"],
        output=result["output"],
        error=result["error"],
        execution_time_seconds=result["execution_time_seconds"],
        tokens_used=result["tokens_used"],
    )


# ==================== Default Template Endpoints (MUST be before /{template_id}) ====================

@router.get("/category/{category}/default", response_model=PromptTemplateResponse)
async def get_default_template_for_category(
    category: PromptCategory,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the default template for a specific category"""
    template = await prompt_service.get_default_template(db, category)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No default template found for category: {category.value}",
        )

    return template_to_response(template)


# ==================== Single Template CRUD (with {template_id}) ====================

@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific prompt template"""
    template = await prompt_service.get_template_by_id(db, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt template not found",
        )

    # Non-admin can only see active templates
    if current_user.role != UserRole.ADMIN and not template.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt template not found",
        )

    return template_to_response(template)


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: UUID,
    data: PromptTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a prompt template.
    Creates new version if content changes.
    Requires admin role.
    """
    require_admin(current_user)

    template = await prompt_service.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt template not found",
        )

    template = await prompt_service.update_template(
        db=db,
        template=template,
        data=data,
        user_id=current_user.id,
    )

    return template_to_response(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a prompt template.
    Requires admin role.
    """
    require_admin(current_user)

    template = await prompt_service.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt template not found",
        )

    await prompt_service.delete_template(db, template)
    return None


# ==================== Version Endpoints ====================

@router.get("/{template_id}/versions", response_model=PromptVersionListResponse)
async def get_prompt_versions(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a prompt template"""
    template = await prompt_service.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt template not found",
        )

    versions = await prompt_service.get_template_versions(db, template_id)

    return PromptVersionListResponse(
        items=[
            PromptVersionResponse(
                id=v.id,
                template_id=v.template_id,
                version=v.version,
                version_number=v.version_number,
                content=v.content,
                system_prompt=v.system_prompt,
                variables=v.variables or [],
                model_config=v.model_config or {},
                changed_by=v.changed_by,
                change_summary=v.change_summary,
                created_at=v.created_at,
            )
            for v in versions
        ],
        total=len(versions),
    )


@router.post("/{template_id}/versions/{version_id}/restore", response_model=PromptTemplateResponse)
async def restore_prompt_version(
    template_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore template to a previous version.
    Requires admin role.
    """
    require_admin(current_user)

    template = await prompt_service.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt template not found",
        )

    version = await prompt_service.get_version_by_id(db, version_id)
    if not version or version.template_id != template_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    template = await prompt_service.restore_version(
        db=db,
        template=template,
        version=version,
        user_id=current_user.id,
    )

    return template_to_response(template)


@router.post("/{template_id}/execute", response_model=PromptTestResponse)
async def execute_prompt_template(
    template_id: UUID,
    variables: dict = {},
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a saved prompt template with provided variables.
    Returns the LLM response.
    """
    template = await prompt_service.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt template not found",
        )

    if not template.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template is not active",
        )

    result = await prompt_service.execute_prompt(template, variables)

    return PromptTestResponse(
        success=result["success"],
        output=result["output"],
        error=result["error"],
        execution_time_seconds=result["execution_time_seconds"],
        tokens_used=result["tokens_used"],
    )
