from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID, uuid4
from io import BytesIO
import logging

from app.core.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.template import CustomTemplate
from app.schemas.generate import (
    DocumentType,
    OutputLanguage,
    GenerateRequest,
    GenerateJobStatus,
    GenerateJobResponse,
    GenerateTemplatesResponse,
    GenerateTemplateInfo,
)
from app.services import gemini_service, document_processing_service, s3_service
from app.services.export_service import export_service, ExportFormat
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job storage (in production, use Redis or database)
generate_jobs = {}


async def get_custom_template(db: AsyncSession, document_type: str, template_id: Optional[UUID] = None):
    """Get custom template for document type"""
    if template_id:
        # Get specific template
        result = await db.execute(
            select(CustomTemplate)
            .where(CustomTemplate.id == template_id)
            .where(CustomTemplate.is_active == True)
        )
        return result.scalar_one_or_none()

    # Get default template for document type
    result = await db.execute(
        select(CustomTemplate)
        .where(CustomTemplate.document_type == document_type.lower())
        .where(CustomTemplate.is_default == True)
        .where(CustomTemplate.is_active == True)
    )
    return result.scalar_one_or_none()


async def process_generation_job(
    job_id: UUID,
    document_type: DocumentType,
    language: OutputLanguage,
    reference_content: str,
    context: Optional[str],
    user_id: UUID,
    custom_template_content: Optional[str],
):
    """Background task to process document generation"""
    try:
        generate_jobs[str(job_id)]["status"] = GenerateJobStatus.PROCESSING

        # Generate document using Gemini
        result = await gemini_service.generate_document(
            document_type=document_type,
            reference_content=reference_content,
            context=context,
            language=language,
            custom_template=custom_template_content,
        )

        # Create a new document with generated content
        # In real implementation, you would save this to database and S3

        generate_jobs[str(job_id)].update({
            "status": GenerateJobStatus.COMPLETED,
            "result": result,
        })

    except Exception as e:
        logger.error(f"Generation job {job_id} failed: {e}")
        generate_jobs[str(job_id)].update({
            "status": GenerateJobStatus.FAILED,
            "error_message": str(e),
        })


@router.post("", response_model=GenerateJobResponse)
async def generate_document(
    background_tasks: BackgroundTasks,
    document_type: DocumentType = Form(...),
    language: OutputLanguage = Form(default=OutputLanguage.VIETNAMESE),
    context: Optional[str] = Form(default=None),
    template_id: Optional[str] = Form(default=None),  # Custom template ID
    text_input: Optional[str] = Form(default=None),  # Direct text input for requirements
    reference_files: List[UploadFile] = File(default=[]),
    reference_document_ids: Optional[str] = Form(default=None),  # comma-separated UUIDs
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start document generation job"""
    reference_content_parts = []

    # Add direct text input if provided
    if text_input and text_input.strip():
        reference_content_parts.append(f"## User Requirements:\n{text_input.strip()}")

    # Process uploaded reference files
    for file in reference_files:
        try:
            content = await file.read()
            file_type = document_processing_service.get_file_type(file.filename)
            if file_type:
                text = document_processing_service.extract_text(content, file_type)
                reference_content_parts.append(f"## File: {file.filename}\n{text}")
        except Exception as e:
            logger.error(f"Error processing reference file {file.filename}: {e}")

    # Get content from existing documents
    if reference_document_ids:
        doc_ids = [UUID(id.strip()) for id in reference_document_ids.split(",") if id.strip()]
        result = await db.execute(
            select(Document).where(Document.id.in_(doc_ids))
        )
        for doc in result.scalars().all():
            if doc.content_text:
                reference_content_parts.append(f"## Document: {doc.title}\n{doc.content_text}")

    if not reference_content_parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide text input, upload files, or select existing documents",
        )

    reference_content = "\n\n".join(reference_content_parts)

    # Get custom template if available
    custom_template_content = None
    template_uuid = UUID(template_id) if template_id else None
    custom_template = await get_custom_template(db, document_type.value, template_uuid)
    if custom_template:
        custom_template_content = custom_template.template_content
        logger.info(f"Using custom template: {custom_template.name}")

    # Create job
    job_id = uuid4()
    from datetime import datetime
    generate_jobs[str(job_id)] = {
        "job_id": job_id,
        "status": GenerateJobStatus.PENDING,
        "document_type": document_type,
        "created_at": datetime.utcnow(),
    }

    # Start background processing
    background_tasks.add_task(
        process_generation_job,
        job_id,
        document_type,
        language,
        reference_content,
        context,
        current_user.id,
        custom_template_content,
    )

    return GenerateJobResponse(
        job_id=job_id,
        status=GenerateJobStatus.PENDING,
        document_type=document_type,
        created_at=generate_jobs[str(job_id)]["created_at"],
    )


@router.get("/templates", response_model=GenerateTemplatesResponse)
async def get_templates(
    current_user: User = Depends(get_current_user),
):
    """Get available document templates"""
    templates = gemini_service.get_available_templates()

    return GenerateTemplatesResponse(
        templates=[
            GenerateTemplateInfo(
                document_type=t["document_type"],
                name=t["name"],
                description=f"Generate {t['name']} document",
                template_standard=t["standard"],
            )
            for t in templates
        ]
    )


@router.get("/{job_id}", response_model=GenerateJobResponse)
async def get_generation_status(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """Get document generation job status"""
    job = generate_jobs.get(str(job_id))

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation job not found",
        )

    return GenerateJobResponse(
        job_id=job["job_id"],
        status=job["status"],
        document_type=job["document_type"],
        created_at=job["created_at"],
        error_message=job.get("error_message"),
    )


@router.get("/{job_id}/result")
async def get_generation_result(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """Get generated document content"""
    job = generate_jobs.get(str(job_id))

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation job not found",
        )

    if job["status"] != GenerateJobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {job['status']}",
        )

    return job.get("result", {})


@router.get("/{job_id}/download")
async def download_generated_document(
    job_id: UUID,
    format: str = Query(default="docx", description="Export format: docx, pdf, md, html"),
    current_user: User = Depends(get_current_user),
):
    """Download generated document in specified format"""
    job = generate_jobs.get(str(job_id))

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation job not found",
        )

    if job["status"] != GenerateJobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {job['status']}",
        )

    result = job.get("result", {})
    content = result.get("content", "")

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content available for download",
        )

    # Validate format
    try:
        export_format = ExportFormat(format.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format: {format}. Supported formats: docx, pdf, md, html",
        )

    # Get document type for filename
    document_type = job.get("document_type", DocumentType.SRS)
    title = result.get("title", f"Generated_{document_type.value}")

    try:
        file_bytes, filename, content_type = await export_service.export_document(
            content=content,
            format=export_format,
            title=title,
            document_type=document_type.value,
        )

        return StreamingResponse(
            BytesIO(file_bytes),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"Error exporting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export document: {str(e)}",
        )


@router.get("/{job_id}/export-formats")
async def get_export_formats(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """Get available export formats for a generated document"""
    job = generate_jobs.get(str(job_id))

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation job not found",
        )

    return {
        "formats": [
            {"value": "docx", "label": "Microsoft Word (.docx)", "icon": "document"},
            {"value": "pdf", "label": "PDF Document (.pdf)", "icon": "document-text"},
            {"value": "md", "label": "Markdown (.md)", "icon": "code"},
            {"value": "html", "label": "HTML Page (.html)", "icon": "globe"},
        ]
    }
