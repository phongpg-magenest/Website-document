"""
API Endpoints cho tính năng Review tài liệu bằng AI
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
import logging
import io

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.template import CustomTemplate
from app.services.review_service import review_service
from app.services.document_service import document_processing_service
from app.schemas.review import (
    ReviewResult,
    ReviewResponse,
    ExportRequest,
    ExportFormat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["Review"])


@router.post("", response_model=ReviewResponse)
async def review_document(
    file: UploadFile = File(..., description="Tài liệu cần review (PDF, DOCX, MD)"),
    document_type: Optional[str] = Form(None, description="Loại tài liệu (srs, prd, contract...)"),
    template_id: Optional[UUID] = Form(None, description="ID template để so sánh (optional)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Review tài liệu bằng AI (Gemini)

    - **file**: File tài liệu (PDF, DOCX, MD, TXT)
    - **document_type**: Loại tài liệu để lấy template phù hợp
    - **template_id**: ID template cụ thể (nếu muốn so sánh với template khác)

    Trả về báo cáo review chi tiết với điểm số và danh sách vấn đề.
    """
    # Validate file extension
    filename = file.filename or "document"
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    allowed_extensions = ["pdf", "docx", "doc", "md", "txt"]
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type .{ext} không được hỗ trợ. Allowed: {', '.join(allowed_extensions)}"
        )

    # Read file content
    try:
        file_content = await file.read()
        file_size = len(file_content)

        # Check file size (max 50MB for review)
        max_size = 50 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File quá lớn. Tối đa {max_size // (1024*1024)}MB"
            )

    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể đọc file"
        )

    # Extract text from document
    try:
        from app.models.document import FileType

        # Map extension to FileType
        ext_map = {
            "pdf": FileType.PDF,
            "docx": FileType.DOCX,
            "doc": FileType.DOC,
            "md": FileType.MD,
            "txt": FileType.MD,  # Treat txt as markdown
        }

        file_type = ext_map.get(ext)
        if not file_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể xử lý file type: {ext}"
            )

        document_text = document_processing_service.extract_text(file_content, file_type)

        if not document_text or len(document_text.strip()) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể trích xuất nội dung từ tài liệu hoặc tài liệu quá ngắn"
            )

        logger.info(f"Extracted {len(document_text)} characters from {filename}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi trích xuất nội dung: {str(e)}"
        )

    # Get template for comparison (if available)
    template_content = None
    template_name = None
    template_id_str = None

    try:
        if template_id:
            # User specified a template
            result = await db.execute(
                select(CustomTemplate).where(
                    CustomTemplate.id == template_id,
                    CustomTemplate.is_active == True
                )
            )
            template = result.scalar_one_or_none()
            if template:
                template_content = template.template_content
                template_name = template.name
                template_id_str = str(template.id)

        elif document_type:
            # Find default template for this document type
            result = await db.execute(
                select(CustomTemplate).where(
                    CustomTemplate.document_type == document_type,
                    CustomTemplate.is_default == True,
                    CustomTemplate.is_active == True
                )
            )
            template = result.scalar_one_or_none()
            if template:
                template_content = template.template_content
                template_name = template.name
                template_id_str = str(template.id)

            # If no default, try any active template for this type
            if not template_content:
                result = await db.execute(
                    select(CustomTemplate).where(
                        CustomTemplate.document_type == document_type,
                        CustomTemplate.is_active == True
                    ).limit(1)
                )
                template = result.scalar_one_or_none()
                if template:
                    template_content = template.template_content
                    template_name = template.name
                    template_id_str = str(template.id)

    except Exception as e:
        logger.warning(f"Error fetching template: {e}")
        # Continue without template

    # Call review service
    try:
        review_result = await review_service.review_document(
            document_content=document_text,
            document_name=filename,
            document_type=document_type,
            template_content=template_content,
            template_name=template_name,
            template_id=template_id_str,
        )

        return ReviewResponse(
            success=True,
            data=review_result,
            message="Review hoàn tất"
        )

    except Exception as e:
        logger.error(f"Review error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi review tài liệu: {str(e)}"
        )


@router.post("/export")
async def export_review_report(
    request: ExportRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Export báo cáo review ra PDF hoặc Word

    - **review_result**: Kết quả review từ API /review
    - **format**: "pdf" hoặc "docx"
    - **document_name**: Tên file output (optional)
    """
    from app.services.review_export_service import review_export_service

    try:
        if request.format == ExportFormat.PDF:
            file_bytes = review_export_service.export_to_pdf(request.review_result)
            media_type = "application/pdf"
            extension = "pdf"
        else:
            file_bytes = review_export_service.export_to_docx(request.review_result)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            extension = "docx"

        # Generate filename
        doc_name = request.document_name or request.review_result.document_name or "document"
        # Remove extension if present
        if "." in doc_name:
            doc_name = doc_name.rsplit(".", 1)[0]
        filename = f"Review_{doc_name}.{extension}"

        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi export báo cáo: {str(e)}"
        )


@router.get("/templates")
async def get_available_templates(
    document_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách templates có sẵn để review

    - **document_type**: Filter theo loại tài liệu (optional)
    """
    try:
        query = select(CustomTemplate).where(CustomTemplate.is_active == True)

        if document_type:
            query = query.where(CustomTemplate.document_type == document_type)

        query = query.order_by(CustomTemplate.document_type, CustomTemplate.is_default.desc())

        result = await db.execute(query)
        templates = result.scalars().all()

        return {
            "templates": [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "document_type": t.document_type,
                    "is_default": t.is_default,
                    "description": t.description,
                }
                for t in templates
            ],
            "total": len(templates)
        }

    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi khi lấy danh sách templates"
        )
