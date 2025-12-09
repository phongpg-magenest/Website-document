from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
import logging

from app.core.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentVersion, FileType, DocumentStatus
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentVersionResponse,
)
from app.services import vector_service, document_processing_service, s3_service
from app.api.v1.endpoints.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    status: Optional[DocumentStatus] = None,
    file_type: Optional[FileType] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents with pagination and filters"""
    query = select(Document)

    # Apply filters
    if project_id:
        query = query.where(Document.project_id == project_id)
    if category_id:
        query = query.where(Document.category_id == category_id)
    if status:
        query = query.where(Document.status == status)
    if file_type:
        query = query.where(Document.file_type == file_type)
    if search:
        query = query.where(Document.title.ilike(f"%{search}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Document.updated_at.desc())

    result = await db.execute(query)
    documents = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return DocumentListResponse(
        items=documents,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    project_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    tags: Optional[str] = None,  # comma-separated
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new document"""
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Validate file
    is_valid, message = document_processing_service.validate_file(file.filename, file_size)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # Get file type
    file_type = document_processing_service.get_file_type(file.filename)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )

    # Create document record
    document = Document(
        title=title or file.filename,
        file_type=file_type,
        file_size=file_size,
        owner_id=current_user.id,
        project_id=project_id,
        category_id=category_id,
        tags=tags.split(",") if tags else [],
        file_path="",  # Will be updated after S3 upload
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Upload to S3
    file_key = s3_service.generate_file_key(document.id, file.filename)
    upload_success = await s3_service.upload_file(
        file_content,
        file_key,
        file.content_type,
    )

    if not upload_success:
        await db.delete(document)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage",
        )

    # Update file path
    document.file_path = file_key

    # Extract text and process
    try:
        extracted_text = document_processing_service.extract_text(file_content, file_type)
        document.content_text = extracted_text

        # Chunk and index in Qdrant
        chunks = document_processing_service.chunk_text(extracted_text)
        metadata = {
            "document_title": document.title,
            "project_id": str(document.project_id) if document.project_id else None,
            "owner_id": str(document.owner_id),
            "file_type": file_type.value,
            "tags": document.tags,
        }

        await vector_service.index_document_chunks(db, document.id, chunks, metadata)

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        # Document is still created, but not indexed

    await db.commit()
    await db.refresh(document)

    return document


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document details"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    update_data: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update document metadata"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check ownership or admin
    if document.owner_id != current_user.id and current_user.role.value not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this document",
        )

    # Update fields
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(document, field, value)

    await db.commit()
    await db.refresh(document)

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check ownership or admin
    if document.owner_id != current_user.id and current_user.role.value not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this document",
        )

    # Delete from S3
    await s3_service.delete_file(document.file_path)

    # Delete from vector store
    await vector_service.delete_document(db, document_id)

    # Delete from database
    await db.delete(document)
    await db.commit()


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presigned URL for document download"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    download_url = await s3_service.get_presigned_url(document.file_path, download=True)

    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        )

    return {"download_url": download_url, "filename": document.title}


@router.get("/{document_id}/versions", response_model=List[DocumentVersionResponse])
async def get_document_versions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document version history"""
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.created_at.desc())
    )
    versions = result.scalars().all()

    return versions
