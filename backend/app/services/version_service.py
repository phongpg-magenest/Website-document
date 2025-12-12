"""
Version Control Service - Quản lý lịch sử phiên bản tài liệu

Theo SOW mục 6.1.2:
- Track lịch sử thay đổi: ai thay đổi, vào lúc nào
- Rollback được version cũ nếu cần
- Lưu trữ đầy đủ metadata của mỗi version
"""
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.document import (
    Document,
    DocumentVersion,
    DocumentStatus,
    FileType,
    ChangeType
)
from app.models.user import User

logger = logging.getLogger(__name__)


class VersionService:
    """Service xử lý version control cho documents"""

    @staticmethod
    def _calculate_next_version(current_version: str, is_major: bool = False) -> str:
        """
        Tính version tiếp theo
        - Major: 1.0 -> 2.0
        - Minor: 1.0 -> 1.1
        """
        try:
            parts = current_version.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0

            if is_major:
                return f"{major + 1}.0"
            else:
                return f"{major}.{minor + 1}"
        except (ValueError, IndexError):
            return "1.1"

    @staticmethod
    def _detect_changes(old_doc: Document, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect what fields changed"""
        changes = {}

        for field, new_value in new_data.items():
            if hasattr(old_doc, field):
                old_value = getattr(old_doc, field)

                # Convert enums to string for comparison
                if hasattr(old_value, 'value'):
                    old_value = old_value.value
                if hasattr(new_value, 'value'):
                    new_value = new_value.value

                if old_value != new_value:
                    changes[field] = {
                        "old": str(old_value) if old_value is not None else None,
                        "new": str(new_value) if new_value is not None else None
                    }

        return changes

    async def create_initial_version(
        self,
        db: AsyncSession,
        document: Document,
        user_id: UUID,
        content_text: Optional[str] = None,
    ) -> DocumentVersion:
        """
        Tạo version đầu tiên khi document được tạo mới
        """
        version = DocumentVersion(
            document_id=document.id,
            version="1.0",
            version_number=1,
            content_snapshot=content_text or document.content_text,
            file_path=document.file_path,
            file_size=document.file_size,
            file_type=document.file_type,
            changed_by=user_id,
            change_type=ChangeType.CREATED,
            change_summary="Tạo tài liệu mới",
            new_status=document.status,
            is_major_version=1,  # First version is always major
        )

        db.add(version)
        await db.flush()

        logger.info(f"Created initial version for document {document.id}")
        return version

    async def create_version_on_update(
        self,
        db: AsyncSession,
        document: Document,
        user_id: UUID,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        change_summary: Optional[str] = None,
        is_major: bool = False,
    ) -> Optional[DocumentVersion]:
        """
        Tạo version mới khi document được update metadata
        Chỉ tạo version nếu có thay đổi thực sự
        """
        changes = self._detect_changes(document, new_data)

        if not changes:
            return None

        # Determine change type
        change_type = ChangeType.METADATA_UPDATED
        if "status" in changes:
            change_type = ChangeType.STATUS_CHANGED

        # Get latest version number
        result = await db.execute(
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.document_id == document.id)
        )
        latest_version_num = result.scalar() or 0

        new_version_str = self._calculate_next_version(document.version, is_major)

        version = DocumentVersion(
            document_id=document.id,
            version=new_version_str,
            version_number=latest_version_num + 1,
            content_snapshot=document.content_text,
            file_path=document.file_path,
            file_size=document.file_size,
            file_type=document.file_type,
            changed_by=user_id,
            change_type=change_type,
            change_summary=change_summary or f"Cập nhật: {', '.join(changes.keys())}",
            changes_detail=json.dumps(changes, ensure_ascii=False),
            previous_status=old_data.get("status"),
            new_status=new_data.get("status", document.status),
            is_major_version=1 if is_major else 0,
        )

        db.add(version)

        # Update document version string
        document.version = new_version_str

        await db.flush()

        logger.info(f"Created version {new_version_str} for document {document.id}")
        return version

    async def create_version_on_file_upload(
        self,
        db: AsyncSession,
        document: Document,
        user_id: UUID,
        new_file_path: str,
        new_file_size: int,
        new_file_type: FileType,
        new_content_text: Optional[str] = None,
        change_summary: Optional[str] = None,
        is_major: bool = False,
    ) -> DocumentVersion:
        """
        Tạo version mới khi upload file mới thay thế
        """
        # Get latest version number
        result = await db.execute(
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.document_id == document.id)
        )
        latest_version_num = result.scalar() or 0

        new_version_str = self._calculate_next_version(document.version, is_major)

        version = DocumentVersion(
            document_id=document.id,
            version=new_version_str,
            version_number=latest_version_num + 1,
            content_snapshot=new_content_text,
            file_path=new_file_path,
            file_size=new_file_size,
            file_type=new_file_type,
            changed_by=user_id,
            change_type=ChangeType.FILE_REPLACED,
            change_summary=change_summary or "Upload phiên bản file mới",
            is_major_version=1 if is_major else 0,
        )

        db.add(version)

        # Update document
        document.version = new_version_str
        document.file_path = new_file_path
        document.file_size = new_file_size
        document.file_type = new_file_type
        if new_content_text:
            document.content_text = new_content_text

        await db.flush()

        logger.info(f"Created file version {new_version_str} for document {document.id}")
        return version

    async def restore_version(
        self,
        db: AsyncSession,
        document: Document,
        version_to_restore: DocumentVersion,
        user_id: UUID,
        change_summary: Optional[str] = None,
    ) -> DocumentVersion:
        """
        Restore về một version cũ
        Tạo một version mới với nội dung từ version cũ
        """
        # Get latest version number
        result = await db.execute(
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.document_id == document.id)
        )
        latest_version_num = result.scalar() or 0

        # Always create as minor version when restoring
        new_version_str = self._calculate_next_version(document.version, is_major=False)

        version = DocumentVersion(
            document_id=document.id,
            version=new_version_str,
            version_number=latest_version_num + 1,
            content_snapshot=version_to_restore.content_snapshot,
            file_path=version_to_restore.file_path,
            file_size=version_to_restore.file_size,
            file_type=version_to_restore.file_type,
            changed_by=user_id,
            change_type=ChangeType.RESTORED,
            change_summary=change_summary or f"Khôi phục từ phiên bản {version_to_restore.version}",
            changes_detail=json.dumps({
                "restored_from_version": version_to_restore.version,
                "restored_from_version_id": str(version_to_restore.id)
            }, ensure_ascii=False),
            is_major_version=0,
        )

        db.add(version)

        # Update document to restored state
        document.version = new_version_str
        if version_to_restore.file_path:
            document.file_path = version_to_restore.file_path
        if version_to_restore.file_size:
            document.file_size = version_to_restore.file_size
        if version_to_restore.file_type:
            document.file_type = version_to_restore.file_type
        if version_to_restore.content_snapshot:
            document.content_text = version_to_restore.content_snapshot

        await db.flush()

        logger.info(f"Restored document {document.id} to version {version_to_restore.version}")
        return version

    async def get_version_history(
        self,
        db: AsyncSession,
        document_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[DocumentVersion], int]:
        """
        Lấy lịch sử version của document với pagination
        """
        # Count total
        count_result = await db.execute(
            select(func.count())
            .where(DocumentVersion.document_id == document_id)
        )
        total = count_result.scalar()

        # Get versions with user info
        offset = (page - 1) * page_size
        result = await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(desc(DocumentVersion.created_at))
            .offset(offset)
            .limit(page_size)
        )
        versions = result.scalars().all()

        return versions, total

    async def get_version_by_id(
        self,
        db: AsyncSession,
        version_id: UUID,
    ) -> Optional[DocumentVersion]:
        """Lấy version theo ID"""
        result = await db.execute(
            select(DocumentVersion).where(DocumentVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def get_version_by_number(
        self,
        db: AsyncSession,
        document_id: UUID,
        version_number: int,
    ) -> Optional[DocumentVersion]:
        """Lấy version theo số version"""
        result = await db.execute(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version_number == version_number
            )
        )
        return result.scalar_one_or_none()

    async def create_version_on_status_change(
        self,
        db: AsyncSession,
        document: Document,
        user_id: UUID,
        previous_status: DocumentStatus,
        new_status: DocumentStatus,
        change_summary: Optional[str] = None,
    ) -> DocumentVersion:
        """
        Tạo version mới khi status document thay đổi (workflow transition)
        """
        # Get latest version number
        result = await db.execute(
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.document_id == document.id)
        )
        latest_version_num = result.scalar() or 0

        # Status change is always minor version
        new_version_str = self._calculate_next_version(document.version, is_major=False)

        version = DocumentVersion(
            document_id=document.id,
            version=new_version_str,
            version_number=latest_version_num + 1,
            content_snapshot=document.content_text,
            file_path=document.file_path,
            file_size=document.file_size,
            file_type=document.file_type,
            changed_by=user_id,
            change_type=ChangeType.STATUS_CHANGED,
            change_summary=change_summary or f"Chuyển trạng thái từ {previous_status.value} sang {new_status.value}",
            changes_detail=json.dumps({
                "previous_status": previous_status.value,
                "new_status": new_status.value
            }, ensure_ascii=False),
            previous_status=previous_status,
            new_status=new_status,
            is_major_version=0,
        )

        db.add(version)

        # Update document version string
        document.version = new_version_str

        await db.flush()

        logger.info(f"Created status change version {new_version_str} for document {document.id}: {previous_status.value} -> {new_status.value}")
        return version

    async def get_latest_version(
        self,
        db: AsyncSession,
        document_id: UUID,
    ) -> Optional[DocumentVersion]:
        """Lấy version mới nhất"""
        result = await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(desc(DocumentVersion.version_number))
            .limit(1)
        )
        return result.scalar_one_or_none()


# Singleton instance
version_service = VersionService()
