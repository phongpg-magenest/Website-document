from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
import logging
import io

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
    DocumentVersionDetail,
    UploadNewVersionRequest,
    RestoreVersionRequest,
    VersionCompareResponse,
    ApprovalRequest,
    ApprovalHistoryResponse,
    WorkflowStatusResponse,
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentThreadResponse,
    CommentListResponse,
    MentionResponse,
)
from app.services import vector_service, document_processing_service, s3_service
from app.services.version_service import version_service
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

    # Extract text
    extracted_text = None
    try:
        extracted_text = document_processing_service.extract_text(file_content, file_type)
        document.content_text = extracted_text
    except Exception as e:
        logger.error(f"Error extracting text: {e}")

    # Create initial version (version 1.0) - do this before indexing
    from app.models.document import DocumentVersion, ChangeType
    initial_version = DocumentVersion(
        document_id=document.id,
        version="1.0",
        version_number=1,
        content_snapshot=extracted_text,
        file_path=document.file_path,
        file_size=document.file_size,
        file_type=document.file_type,
        changed_by=current_user.id,
        change_type=ChangeType.CREATED,
        change_summary="Tạo tài liệu mới",
        new_status=document.status,
        is_major_version=1,
    )
    db.add(initial_version)

    # Commit document and version first
    await db.commit()
    await db.refresh(document)

    # Now index in vector store (separate operation, can fail without affecting doc creation)
    try:
        if extracted_text:
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
        logger.error(f"Error indexing document: {e}")
        # Document and version are still created, just not indexed

    # Refresh document to ensure it's attached to session before return
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
    """Update document metadata - auto tracks changes in version history"""
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

    # Capture old data for version tracking
    old_data = {
        "title": document.title,
        "status": document.status,
        "visibility": document.visibility,
        "project_id": document.project_id,
        "category_id": document.category_id,
        "tags": document.tags,
    }

    # Get new data
    new_data = update_data.model_dump(exclude_unset=True)

    # Update fields
    for field, value in new_data.items():
        setattr(document, field, value)

    # Create version record for tracking changes
    try:
        await version_service.create_version_on_update(
            db=db,
            document=document,
            user_id=current_user.id,
            old_data=old_data,
            new_data=new_data,
        )
    except Exception as e:
        logger.error(f"Error creating version on update: {e}")

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
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get document version history with pagination

    Returns list of all versions with change details, who made changes, and when.
    """
    # Check document exists
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    versions, total = await version_service.get_version_history(
        db=db,
        document_id=document_id,
        page=page,
        page_size=page_size,
    )

    # Enrich with user names
    result_list = []
    for v in versions:
        user_result = await db.execute(select(User).where(User.id == v.changed_by))
        user = user_result.scalar_one_or_none()

        version_dict = {
            "id": v.id,
            "document_id": v.document_id,
            "version": v.version,
            "version_number": v.version_number,
            "change_type": v.change_type,
            "change_summary": v.change_summary,
            "changes_detail": v.changes_detail,
            "previous_status": v.previous_status,
            "new_status": v.new_status,
            "file_path": v.file_path,
            "file_size": v.file_size,
            "file_type": v.file_type,
            "is_major_version": v.is_major_version,
            "changed_by": v.changed_by,
            "changed_by_name": user.name if user else None,
            "created_at": v.created_at,
        }
        result_list.append(DocumentVersionResponse(**version_dict))

    return result_list


@router.get("/{document_id}/versions/compare", response_model=VersionCompareResponse)
async def compare_versions(
    document_id: UUID,
    version_old_id: UUID,
    version_new_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two versions of a document.

    Returns a diff showing additions, deletions, and unchanged content.

    Query Parameters:
    - version_old_id: UUID of the older version to compare
    - version_new_id: UUID of the newer version to compare
    """
    from app.services.diff_service import diff_service

    # Get both versions
    version_old = await version_service.get_version_by_id(db, version_old_id)
    version_new = await version_service.get_version_by_id(db, version_new_id)

    if not version_old or version_old.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Old version not found",
        )

    if not version_new or version_new.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New version not found",
        )

    # Compute diff
    result = diff_service.compute_diff(
        old_text=version_old.content_snapshot,
        new_text=version_new.content_snapshot,
        document_id=document_id,
        version_old=version_old.version,
        version_new=version_new.version,
        version_old_id=version_old_id,
        version_new_id=version_new_id,
    )

    return result


@router.get("/{document_id}/versions/{version_id}", response_model=DocumentVersionDetail)
async def get_version_detail(
    document_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific version including content snapshot
    """
    version = await version_service.get_version_by_id(db, version_id)

    if not version or version.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Get user name
    user_result = await db.execute(select(User).where(User.id == version.changed_by))
    user = user_result.scalar_one_or_none()

    return DocumentVersionDetail(
        id=version.id,
        document_id=version.document_id,
        version=version.version,
        version_number=version.version_number,
        change_type=version.change_type,
        change_summary=version.change_summary,
        changes_detail=version.changes_detail,
        previous_status=version.previous_status,
        new_status=version.new_status,
        file_path=version.file_path,
        file_size=version.file_size,
        file_type=version.file_type,
        is_major_version=version.is_major_version,
        changed_by=version.changed_by,
        changed_by_name=user.name if user else None,
        created_at=version.created_at,
        content_snapshot=version.content_snapshot,
    )


@router.post("/{document_id}/versions", response_model=DocumentVersionResponse)
async def upload_new_version(
    document_id: UUID,
    file: UploadFile = File(...),
    change_summary: Optional[str] = Form(None),
    is_major_version: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a new version of the document with a new file

    - **file**: New file to replace current version
    - **change_summary**: Description of what changed
    - **is_major_version**: True for major version bump (1.0 -> 2.0), False for minor (1.0 -> 1.1)
    """
    # Get document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check permission
    if document.owner_id != current_user.id and current_user.role.value not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this document",
        )

    # Read and validate file
    file_content = await file.read()
    file_size = len(file_content)

    is_valid, message = document_processing_service.validate_file(file.filename, file_size)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    file_type = document_processing_service.get_file_type(file.filename)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )

    # Upload new file to storage
    file_key = s3_service.generate_file_key(document.id, file.filename)
    upload_success = await s3_service.upload_file(
        file_content,
        file_key,
        file.content_type,
    )

    if not upload_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage",
        )

    # Extract text
    extracted_text = None
    try:
        extracted_text = document_processing_service.extract_text(file_content, file_type)
    except Exception as e:
        logger.error(f"Error extracting text: {e}")

    # Create new version
    new_version = await version_service.create_version_on_file_upload(
        db=db,
        document=document,
        user_id=current_user.id,
        new_file_path=file_key,
        new_file_size=file_size,
        new_file_type=file_type,
        new_content_text=extracted_text,
        change_summary=change_summary,
        is_major=is_major_version,
    )

    # Re-index document
    try:
        if extracted_text:
            chunks = document_processing_service.chunk_text(extracted_text)
            metadata = {
                "document_title": document.title,
                "project_id": str(document.project_id) if document.project_id else None,
                "owner_id": str(document.owner_id),
                "file_type": file_type.value,
                "tags": document.tags,
            }
            # Delete old vectors and index new ones
            await vector_service.delete_document(db, document.id)
            await vector_service.index_document_chunks(db, document.id, chunks, metadata)
    except Exception as e:
        logger.error(f"Error re-indexing document: {e}")

    await db.commit()

    # Get user name
    user_result = await db.execute(select(User).where(User.id == new_version.changed_by))
    user = user_result.scalar_one_or_none()

    return DocumentVersionResponse(
        id=new_version.id,
        document_id=new_version.document_id,
        version=new_version.version,
        version_number=new_version.version_number,
        change_type=new_version.change_type,
        change_summary=new_version.change_summary,
        changes_detail=new_version.changes_detail,
        previous_status=new_version.previous_status,
        new_status=new_version.new_status,
        file_path=new_version.file_path,
        file_size=new_version.file_size,
        file_type=new_version.file_type,
        is_major_version=new_version.is_major_version,
        changed_by=new_version.changed_by,
        changed_by_name=user.name if user else None,
        created_at=new_version.created_at,
    )


@router.post("/{document_id}/versions/restore", response_model=DocumentVersionResponse)
async def restore_version(
    document_id: UUID,
    request: RestoreVersionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore document to a previous version

    Creates a new version with content from the specified old version.
    Does not delete any version history.
    """
    # Get document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check permission
    if document.owner_id != current_user.id and current_user.role.value not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to restore this document",
        )

    # Get version to restore
    version_to_restore = await version_service.get_version_by_id(db, request.version_id)

    if not version_to_restore or version_to_restore.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Restore
    new_version = await version_service.restore_version(
        db=db,
        document=document,
        version_to_restore=version_to_restore,
        user_id=current_user.id,
        change_summary=request.change_summary,
    )

    # Re-index if content exists
    try:
        if version_to_restore.content_snapshot:
            chunks = document_processing_service.chunk_text(version_to_restore.content_snapshot)
            metadata = {
                "document_title": document.title,
                "project_id": str(document.project_id) if document.project_id else None,
                "owner_id": str(document.owner_id),
                "file_type": document.file_type.value if document.file_type else None,
                "tags": document.tags,
            }
            await vector_service.delete_document(db, document.id)
            await vector_service.index_document_chunks(db, document.id, chunks, metadata)
    except Exception as e:
        logger.error(f"Error re-indexing after restore: {e}")

    await db.commit()

    # Get user name
    user_result = await db.execute(select(User).where(User.id == new_version.changed_by))
    user = user_result.scalar_one_or_none()

    return DocumentVersionResponse(
        id=new_version.id,
        document_id=new_version.document_id,
        version=new_version.version,
        version_number=new_version.version_number,
        change_type=new_version.change_type,
        change_summary=new_version.change_summary,
        changes_detail=new_version.changes_detail,
        previous_status=new_version.previous_status,
        new_status=new_version.new_status,
        file_path=new_version.file_path,
        file_size=new_version.file_size,
        file_type=new_version.file_type,
        is_major_version=new_version.is_major_version,
        changed_by=new_version.changed_by,
        changed_by_name=user.name if user else None,
        created_at=new_version.created_at,
    )


@router.get("/{document_id}/versions/{version_id}/download")
async def download_version(
    document_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a specific version of the document
    """
    # Get version
    version = await version_service.get_version_by_id(db, version_id)

    if not version or version.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    if not version.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No file associated with this version",
        )

    # Get download URL
    download_url = await s3_service.get_presigned_url(version.file_path, download=True)

    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        )

    # Get document for filename
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()

    filename = f"{document.title}_v{version.version}" if document else f"document_v{version.version}"

    return {
        "download_url": download_url,
        "filename": filename,
        "version": version.version,
    }


# ===== APPROVAL WORKFLOW ENDPOINTS =====

@router.get("/{document_id}/workflow", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get document's current workflow status and available actions.

    Returns:
    - Current status
    - Available actions for the current user
    - Approval history
    - Whether current user can edit/approve
    """
    from app.services.approval_service import approval_service

    # Get document
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Get available actions
    available_actions = approval_service.get_available_actions(document, current_user)

    # Get approval history
    history = await approval_service.get_approval_history(db, document_id)

    # Build history response with user names
    history_response = []
    for h in history:
        user_result = await db.execute(select(User).where(User.id == h.performed_by))
        user = user_result.scalar_one_or_none()

        history_response.append(ApprovalHistoryResponse(
            id=h.id,
            document_id=h.document_id,
            action=h.action,
            from_status=h.from_status,
            to_status=h.to_status,
            performed_by=h.performed_by,
            performed_by_name=user.name if user else None,
            comment=h.comment,
            created_at=h.created_at,
        ))

    return WorkflowStatusResponse(
        document_id=document_id,
        current_status=document.status,
        available_actions=available_actions,
        approval_history=history_response,
        can_edit=approval_service.can_edit_document(document, current_user),
        can_approve=approval_service.can_approve_document(document, current_user),
    )


@router.post("/{document_id}/workflow", response_model=ApprovalHistoryResponse)
async def perform_workflow_action(
    document_id: UUID,
    request: ApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform an approval workflow action on a document.

    Available actions depend on document status and user role:
    - SUBMIT_FOR_REVIEW: Draft -> Review (owner or admin)
    - APPROVE: Review -> Approved (admin/manager, not owner)
    - REJECT: Review -> Draft (admin/manager, requires comment)
    - REQUEST_CHANGES: Review -> Draft (admin/manager, requires comment)
    - PUBLISH: Approved -> Published (admin/manager)
    - UNPUBLISH: Published -> Approved (admin/manager)
    """
    from app.services.approval_service import approval_service
    from app.services.version_service import version_service as vs

    # Get document
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Store previous status for version tracking
    previous_status = document.status

    # Perform action
    success, message, approval_entry = await approval_service.perform_action(
        db=db,
        document=document,
        user=current_user,
        action=request.action,
        comment=request.comment,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # Create version entry for status change
    await vs.create_version_on_status_change(
        db=db,
        document=document,
        user_id=current_user.id,
        previous_status=previous_status,
        new_status=document.status,
        change_summary=f"{request.action.value}: {request.comment}" if request.comment else None,
    )

    # Commit all changes (approval entry + version entry)
    await db.commit()
    await db.refresh(approval_entry)
    await db.refresh(document)

    # Build response
    user_result = await db.execute(select(User).where(User.id == approval_entry.performed_by))
    user = user_result.scalar_one_or_none()

    return ApprovalHistoryResponse(
        id=approval_entry.id,
        document_id=approval_entry.document_id,
        action=approval_entry.action,
        from_status=approval_entry.from_status,
        to_status=approval_entry.to_status,
        performed_by=approval_entry.performed_by,
        performed_by_name=user.name if user else None,
        comment=approval_entry.comment,
        created_at=approval_entry.created_at,
    )


@router.get("/workflow/pending", response_model=DocumentListResponse)
async def get_pending_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get documents pending approval (in REVIEW status).

    Only accessible by ADMIN or MANAGER users.
    Managers cannot see their own documents in this list.
    """
    from app.services.approval_service import approval_service
    from app.models.user import UserRole

    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or manager can view pending approvals",
        )

    documents, total = await approval_service.get_pending_approvals(
        db=db,
        user=current_user,
        page=page,
        page_size=page_size,
    )

    # Convert to response
    items = []
    for doc in documents:
        items.append(DocumentResponse(
            id=doc.id,
            title=doc.title,
            file_path=doc.file_path,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            visibility=doc.visibility,
            owner_id=doc.owner_id,
            project_id=doc.project_id,
            category_id=doc.category_id,
            tags=doc.tags or [],
            version=doc.version,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ))

    total_pages = (total + page_size - 1) // page_size

    return DocumentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ===== COMMENT ENDPOINTS =====

@router.get("/{document_id}/comments", response_model=CommentListResponse)
async def get_document_comments(
    document_id: UUID,
    include_resolved: bool = Query(True, description="Include resolved comments"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all comments on a document (with replies nested).
    """
    from app.services.comment_service import comment_service

    # Check document exists
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Get root comments
    comments, total_resolved, total_unresolved = await comment_service.get_document_comments(
        db=db,
        document_id=document_id,
        include_resolved=include_resolved,
        only_root=True,
    )

    # Build response with nested replies
    items = []
    for comment in comments:
        # Get author info
        author_result = await db.execute(select(User).where(User.id == comment.author_id))
        author = author_result.scalar_one_or_none()

        # Get resolved_by info
        resolved_by_name = None
        if comment.resolved_by:
            resolved_result = await db.execute(select(User).where(User.id == comment.resolved_by))
            resolver = resolved_result.scalar_one_or_none()
            if resolver:
                resolved_by_name = resolver.name

        # Get mentions
        mentions = await comment_service.get_comment_mentions(db, comment.id)
        mention_responses = []
        for m in mentions:
            user_result = await db.execute(select(User).where(User.id == m.mentioned_user_id))
            user = user_result.scalar_one_or_none()
            if user:
                mention_responses.append(MentionResponse(
                    user_id=user.id,
                    user_name=user.name,
                    user_email=user.email,
                ))

        # Get replies
        replies_list = await comment_service.get_comment_replies(db, comment.id)
        replies_responses = []
        for reply in replies_list:
            reply_author_result = await db.execute(select(User).where(User.id == reply.author_id))
            reply_author = reply_author_result.scalar_one_or_none()

            # Get reply mentions
            reply_mentions = await comment_service.get_comment_mentions(db, reply.id)
            reply_mention_responses = []
            for m in reply_mentions:
                user_result = await db.execute(select(User).where(User.id == m.mentioned_user_id))
                user = user_result.scalar_one_or_none()
                if user:
                    reply_mention_responses.append(MentionResponse(
                        user_id=user.id,
                        user_name=user.name,
                        user_email=user.email,
                    ))

            replies_responses.append(CommentResponse(
                id=reply.id,
                document_id=reply.document_id,
                parent_id=reply.parent_id,
                author_id=reply.author_id,
                author_name=reply_author.name if reply_author else None,
                author_email=reply_author.email if reply_author else None,
                content=reply.content,
                is_resolved=bool(reply.is_resolved),
                resolved_by=reply.resolved_by,
                resolved_at=reply.resolved_at,
                position_start=reply.position_start,
                position_end=reply.position_end,
                position_context=reply.position_context,
                mentions=reply_mention_responses,
                reply_count=0,
                created_at=reply.created_at,
                updated_at=reply.updated_at,
            ))

        items.append(CommentThreadResponse(
            id=comment.id,
            document_id=comment.document_id,
            parent_id=comment.parent_id,
            author_id=comment.author_id,
            author_name=author.name if author else None,
            author_email=author.email if author else None,
            content=comment.content,
            is_resolved=bool(comment.is_resolved),
            resolved_by=comment.resolved_by,
            resolved_by_name=resolved_by_name,
            resolved_at=comment.resolved_at,
            position_start=comment.position_start,
            position_end=comment.position_end,
            position_context=comment.position_context,
            mentions=mention_responses,
            reply_count=len(replies_responses),
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            replies=replies_responses,
        ))

    return CommentListResponse(
        items=items,
        total=len(items),
        total_resolved=total_resolved,
        total_unresolved=total_unresolved,
    )


@router.post("/{document_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    document_id: UUID,
    request: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new comment on a document.

    Supports @mentions using @email@domain.com format.
    """
    from app.services.comment_service import comment_service

    # Check document exists
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # If parent_id provided, check it exists and belongs to same document
    if request.parent_id:
        parent = await comment_service.get_comment_by_id(db, request.parent_id)
        if not parent or parent.document_id != document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parent comment",
            )

    # Create comment
    comment = await comment_service.create_comment(
        db=db,
        document_id=document_id,
        author_id=current_user.id,
        content=request.content,
        parent_id=request.parent_id,
        position_start=request.position_start,
        position_end=request.position_end,
        position_context=request.position_context,
    )

    # Get mentions
    mentions = await comment_service.get_comment_mentions(db, comment.id)
    mention_responses = []
    for m in mentions:
        user_result = await db.execute(select(User).where(User.id == m.mentioned_user_id))
        user = user_result.scalar_one_or_none()
        if user:
            mention_responses.append(MentionResponse(
                user_id=user.id,
                user_name=user.name,
                user_email=user.email,
            ))

    return CommentResponse(
        id=comment.id,
        document_id=comment.document_id,
        parent_id=comment.parent_id,
        author_id=comment.author_id,
        author_name=current_user.name,
        author_email=current_user.email,
        content=comment.content,
        is_resolved=bool(comment.is_resolved),
        resolved_by=comment.resolved_by,
        resolved_at=comment.resolved_at,
        position_start=comment.position_start,
        position_end=comment.position_end,
        position_context=comment.position_context,
        mentions=mention_responses,
        reply_count=0,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.put("/{document_id}/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    document_id: UUID,
    comment_id: UUID,
    request: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a comment. Only the author can edit.
    """
    from app.services.comment_service import comment_service

    comment = await comment_service.get_comment_by_id(db, comment_id)

    if not comment or comment.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    try:
        comment = await comment_service.update_comment(
            db=db,
            comment=comment,
            content=request.content,
            user_id=current_user.id,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    # Get mentions
    mentions = await comment_service.get_comment_mentions(db, comment.id)
    mention_responses = []
    for m in mentions:
        user_result = await db.execute(select(User).where(User.id == m.mentioned_user_id))
        user = user_result.scalar_one_or_none()
        if user:
            mention_responses.append(MentionResponse(
                user_id=user.id,
                user_name=user.name,
                user_email=user.email,
            ))

    author_result = await db.execute(select(User).where(User.id == comment.author_id))
    author = author_result.scalar_one_or_none()

    return CommentResponse(
        id=comment.id,
        document_id=comment.document_id,
        parent_id=comment.parent_id,
        author_id=comment.author_id,
        author_name=author.name if author else None,
        author_email=author.email if author else None,
        content=comment.content,
        is_resolved=bool(comment.is_resolved),
        resolved_by=comment.resolved_by,
        resolved_at=comment.resolved_at,
        position_start=comment.position_start,
        position_end=comment.position_end,
        position_context=comment.position_context,
        mentions=mention_responses,
        reply_count=await comment_service.get_reply_count(db, comment.id),
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.delete("/{document_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    document_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a comment. Only the author or admin can delete.
    """
    from app.services.comment_service import comment_service
    from app.models.user import UserRole

    comment = await comment_service.get_comment_by_id(db, comment_id)

    if not comment or comment.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    try:
        await comment_service.delete_comment(
            db=db,
            comment=comment,
            user_id=current_user.id,
            is_admin=current_user.role == UserRole.ADMIN,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post("/{document_id}/comments/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    document_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a comment as resolved.
    """
    from app.services.comment_service import comment_service

    comment = await comment_service.get_comment_by_id(db, comment_id)

    if not comment or comment.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    comment = await comment_service.resolve_comment(db, comment, current_user.id)

    # Get author
    author_result = await db.execute(select(User).where(User.id == comment.author_id))
    author = author_result.scalar_one_or_none()

    return CommentResponse(
        id=comment.id,
        document_id=comment.document_id,
        parent_id=comment.parent_id,
        author_id=comment.author_id,
        author_name=author.name if author else None,
        author_email=author.email if author else None,
        content=comment.content,
        is_resolved=True,
        resolved_by=comment.resolved_by,
        resolved_by_name=current_user.name,
        resolved_at=comment.resolved_at,
        position_start=comment.position_start,
        position_end=comment.position_end,
        position_context=comment.position_context,
        mentions=[],
        reply_count=await comment_service.get_reply_count(db, comment.id),
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.post("/{document_id}/comments/{comment_id}/unresolve", response_model=CommentResponse)
async def unresolve_comment(
    document_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a comment as unresolved.
    """
    from app.services.comment_service import comment_service

    comment = await comment_service.get_comment_by_id(db, comment_id)

    if not comment or comment.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    comment = await comment_service.unresolve_comment(db, comment)

    # Get author
    author_result = await db.execute(select(User).where(User.id == comment.author_id))
    author = author_result.scalar_one_or_none()

    return CommentResponse(
        id=comment.id,
        document_id=comment.document_id,
        parent_id=comment.parent_id,
        author_id=comment.author_id,
        author_name=author.name if author else None,
        author_email=author.email if author else None,
        content=comment.content,
        is_resolved=False,
        resolved_by=None,
        resolved_at=None,
        position_start=comment.position_start,
        position_end=comment.position_end,
        position_context=comment.position_context,
        mentions=[],
        reply_count=await comment_service.get_reply_count(db, comment.id),
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )
