"""
Prompt Service - Quản lý AI prompt templates
"""
import re
import logging
import asyncio
import time
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, update

from app.models.prompt import PromptTemplate, PromptTemplateVersion, PromptCategory
from app.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptVariableDefinition,
    ModelConfigSchema,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class PromptService:
    """Service for managing AI prompt templates"""

    def __init__(self):
        # Configure Gemini
        if settings.GEMINI_BASE_URL:
            genai.configure(
                api_key=settings.GEMINI_API_KEY,
                transport="rest",
                client_options={"api_endpoint": settings.GEMINI_BASE_URL}
            )
        else:
            genai.configure(api_key=settings.GEMINI_API_KEY)

    # ==================== CRUD Operations ====================

    async def create_template(
        self,
        db: AsyncSession,
        data: PromptTemplateCreate,
        user_id: UUID,
    ) -> PromptTemplate:
        """Create a new prompt template"""

        # If setting as default, unset other defaults in same category
        if data.is_default:
            await self._unset_category_defaults(db, data.category)

        # Prepare variables as dict list
        variables_list = [v.model_dump() for v in data.variables] if data.variables else []

        # Prepare model config
        model_config = data.model_config_data.model_dump() if data.model_config_data else {
            "model": "gemini-2.0-flash",
            "temperature": 0.7,
            "max_tokens": 8192,
        }

        template = PromptTemplate(
            name=data.name,
            description=data.description,
            category=data.category,
            content=data.content,
            system_prompt=data.system_prompt,
            variables=variables_list,
            model_config=model_config,
            output_format=data.output_format,
            is_default=1 if data.is_default else 0,
            created_by=user_id,
        )

        db.add(template)
        await db.flush()

        # Create initial version
        version = PromptTemplateVersion(
            template_id=template.id,
            version="1.0",
            version_number=1,
            content=data.content,
            system_prompt=data.system_prompt,
            variables=variables_list,
            model_config=model_config,
            changed_by=user_id,
            change_summary="Initial version",
        )
        db.add(version)

        await db.commit()
        await db.refresh(template)

        logger.info(f"Created prompt template: {template.name} (id={template.id})")
        return template

    async def update_template(
        self,
        db: AsyncSession,
        template: PromptTemplate,
        data: PromptTemplateUpdate,
        user_id: UUID,
    ) -> PromptTemplate:
        """Update a prompt template and create version entry"""

        # Check if content is changing (requires new version)
        content_changed = False

        if data.name is not None:
            template.name = data.name

        if data.description is not None:
            template.description = data.description

        if data.category is not None:
            template.category = data.category

        if data.content is not None and data.content != template.content:
            template.content = data.content
            content_changed = True

        if data.system_prompt is not None:
            if data.system_prompt != template.system_prompt:
                content_changed = True
            template.system_prompt = data.system_prompt

        if data.variables is not None:
            new_vars = [v.model_dump() for v in data.variables]
            if new_vars != template.variables:
                content_changed = True
            template.variables = new_vars

        if data.model_config_data is not None:
            new_config = data.model_config_data.model_dump()
            if new_config != template.model_config:
                content_changed = True
            template.model_config = new_config

        if data.output_format is not None:
            template.output_format = data.output_format

        if data.is_active is not None:
            template.is_active = 1 if data.is_active else 0

        if data.is_default is not None:
            if data.is_default:
                await self._unset_category_defaults(db, template.category)
            template.is_default = 1 if data.is_default else 0

        template.updated_by = user_id

        # Create new version if content changed
        if content_changed:
            # Get next version number
            result = await db.execute(
                select(func.max(PromptTemplateVersion.version_number))
                .where(PromptTemplateVersion.template_id == template.id)
            )
            max_version = result.scalar() or 0
            new_version_num = max_version + 1

            # Increment version string
            template.version = f"1.{new_version_num - 1}"

            version = PromptTemplateVersion(
                template_id=template.id,
                version=template.version,
                version_number=new_version_num,
                content=template.content,
                system_prompt=template.system_prompt,
                variables=template.variables,
                model_config=template.model_config,
                changed_by=user_id,
                change_summary=data.change_summary or "Updated template",
            )
            db.add(version)

        await db.commit()
        await db.refresh(template)

        logger.info(f"Updated prompt template: {template.name} (id={template.id})")
        return template

    async def delete_template(
        self,
        db: AsyncSession,
        template: PromptTemplate,
    ) -> bool:
        """Delete a prompt template"""
        template_id = template.id
        await db.delete(template)
        await db.commit()
        logger.info(f"Deleted prompt template: {template_id}")
        return True

    async def get_template_by_id(
        self,
        db: AsyncSession,
        template_id: UUID,
    ) -> Optional[PromptTemplate]:
        """Get template by ID"""
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_templates(
        self,
        db: AsyncSession,
        category: Optional[PromptCategory] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[PromptTemplate], int]:
        """Get list of templates with filtering"""
        query = select(PromptTemplate)

        if category:
            query = query.where(PromptTemplate.category == category)

        if is_active is not None:
            query = query.where(PromptTemplate.is_active == (1 if is_active else 0))

        if search:
            query = query.where(
                PromptTemplate.name.ilike(f"%{search}%") |
                PromptTemplate.description.ilike(f"%{search}%")
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get items
        query = query.order_by(desc(PromptTemplate.updated_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        templates = list(result.scalars().all())

        return templates, total

    async def get_default_template(
        self,
        db: AsyncSession,
        category: PromptCategory,
    ) -> Optional[PromptTemplate]:
        """Get default template for a category"""
        result = await db.execute(
            select(PromptTemplate).where(
                and_(
                    PromptTemplate.category == category,
                    PromptTemplate.is_default == 1,
                    PromptTemplate.is_active == 1,
                )
            )
        )
        return result.scalar_one_or_none()

    # ==================== Version Operations ====================

    async def get_template_versions(
        self,
        db: AsyncSession,
        template_id: UUID,
    ) -> List[PromptTemplateVersion]:
        """Get all versions of a template"""
        result = await db.execute(
            select(PromptTemplateVersion)
            .where(PromptTemplateVersion.template_id == template_id)
            .order_by(desc(PromptTemplateVersion.version_number))
        )
        return list(result.scalars().all())

    async def get_version_by_id(
        self,
        db: AsyncSession,
        version_id: UUID,
    ) -> Optional[PromptTemplateVersion]:
        """Get specific version"""
        result = await db.execute(
            select(PromptTemplateVersion).where(PromptTemplateVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def restore_version(
        self,
        db: AsyncSession,
        template: PromptTemplate,
        version: PromptTemplateVersion,
        user_id: UUID,
    ) -> PromptTemplate:
        """Restore template to a previous version"""
        # Get next version number
        result = await db.execute(
            select(func.max(PromptTemplateVersion.version_number))
            .where(PromptTemplateVersion.template_id == template.id)
        )
        max_version = result.scalar() or 0
        new_version_num = max_version + 1

        # Update template
        template.content = version.content
        template.system_prompt = version.system_prompt
        template.variables = version.variables
        template.model_config = version.model_config
        template.version = f"1.{new_version_num - 1}"
        template.updated_by = user_id

        # Create restore version entry
        new_version = PromptTemplateVersion(
            template_id=template.id,
            version=template.version,
            version_number=new_version_num,
            content=version.content,
            system_prompt=version.system_prompt,
            variables=version.variables,
            model_config=version.model_config,
            changed_by=user_id,
            change_summary=f"Restored from version {version.version}",
        )
        db.add(new_version)

        await db.commit()
        await db.refresh(template)

        logger.info(f"Restored template {template.id} to version {version.version}")
        return template

    # ==================== Rendering & Execution ====================

    def render_prompt(
        self,
        content: str,
        variables: Dict[str, str],
    ) -> Tuple[str, List[str]]:
        """
        Render prompt by substituting variables.

        Returns (rendered_content, missing_variables)
        """
        # Find all placeholders {{var_name}}
        pattern = r'\{\{(\w+)\}\}'
        placeholders = re.findall(pattern, content)

        rendered = content
        missing = []

        for placeholder in placeholders:
            if placeholder in variables:
                rendered = rendered.replace(f"{{{{{placeholder}}}}}", variables[placeholder])
            else:
                missing.append(placeholder)

        return rendered, missing

    async def execute_prompt(
        self,
        template: PromptTemplate,
        variables: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Execute a prompt template with Gemini.

        Returns dict with output and metadata.
        """
        start_time = time.time()

        # Render prompt
        rendered_content, missing = self.render_prompt(template.content, variables)

        if missing:
            return {
                "success": False,
                "output": None,
                "error": f"Missing required variables: {', '.join(missing)}",
                "execution_time_seconds": 0,
                "tokens_used": None,
            }

        # Render system prompt if exists
        rendered_system = None
        if template.system_prompt:
            rendered_system, _ = self.render_prompt(template.system_prompt, variables)

        # Get model config
        config = template.model_config or {}
        model_name = config.get("model", "gemini-2.0-flash")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 8192)

        try:
            # Create model with config
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            model = genai.GenerativeModel(
                model_name,
                generation_config=generation_config,
                system_instruction=rendered_system,
            )

            # Execute
            response = await asyncio.to_thread(
                model.generate_content, rendered_content
            )

            execution_time = time.time() - start_time

            return {
                "success": True,
                "output": response.text,
                "error": None,
                "execution_time_seconds": execution_time,
                "tokens_used": None,  # Gemini doesn't expose this easily
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Prompt execution failed: {e}")
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "execution_time_seconds": execution_time,
                "tokens_used": None,
            }

    async def test_prompt(
        self,
        content: str,
        variables: Dict[str, str],
        system_prompt: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Test a prompt without saving it.
        """
        # Create a temporary template-like object
        class TempTemplate:
            pass

        temp = TempTemplate()
        temp.content = content
        temp.system_prompt = system_prompt
        temp.model_config = model_config or {}

        return await self.execute_prompt(temp, variables)

    # ==================== Helper Methods ====================

    async def _unset_category_defaults(
        self,
        db: AsyncSession,
        category: PromptCategory,
    ):
        """Unset all defaults for a category"""
        await db.execute(
            update(PromptTemplate)
            .where(PromptTemplate.category == category)
            .values(is_default=0)
        )

    def extract_variables(self, content: str) -> List[str]:
        """Extract variable names from content"""
        pattern = r'\{\{(\w+)\}\}'
        return list(set(re.findall(pattern, content)))


# Singleton instance
prompt_service = PromptService()
