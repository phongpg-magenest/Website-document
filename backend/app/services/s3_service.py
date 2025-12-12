"""
Storage Service - Lưu file local thay vì AWS S3
"""
import os
from pathlib import Path
from typing import Optional
from uuid import UUID
import logging
import aiofiles

from app.core.config import settings

logger = logging.getLogger(__name__)

# Thư mục lưu file local
UPLOAD_DIR = Path("/app/uploads")


class S3Service:
    """Local file storage (thay thế S3)"""

    def __init__(self):
        # Tạo thư mục uploads nếu chưa có
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"StorageService: Using LOCAL storage at {UPLOAD_DIR}")

    async def upload_file(
        self,
        file_content: bytes,
        file_key: str,
        content_type: Optional[str] = None,
    ) -> bool:
        """Upload file to local storage"""
        try:
            file_path = UPLOAD_DIR / file_key
            file_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)

            logger.info(f"Uploaded file to local: {file_key}")
            return True
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False

    async def download_file(self, file_key: str) -> Optional[bytes]:
        """Download file from local storage"""
        try:
            file_path = UPLOAD_DIR / file_key
            if not file_path.exists():
                logger.error(f"File not found: {file_key}")
                return None

            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None

    async def delete_file(self, file_key: str) -> bool:
        """Delete file from local storage"""
        try:
            file_path = UPLOAD_DIR / file_key
            if file_path.exists():
                os.remove(file_path)
                # Xóa thư mục rỗng
                try:
                    file_path.parent.rmdir()
                except OSError:
                    pass  # Thư mục không rỗng, bỏ qua
            logger.info(f"Deleted file: {file_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    async def get_presigned_url(
        self,
        file_key: str,
        expiration: int = 3600,
        download: bool = False,
    ) -> Optional[str]:
        """Generate URL for file access (local endpoint)"""
        try:
            # Trả về URL tới API download
            return f"/api/v1/documents/download/{file_key}"
        except Exception as e:
            logger.error(f"Error generating URL: {e}")
            return None

    def generate_file_key(self, document_id: UUID, filename: str) -> str:
        """Generate key for document"""
        return f"documents/{document_id}/{filename}"

    def generate_version_key(
        self,
        document_id: UUID,
        version: str,
        filename: str,
    ) -> str:
        """Generate key for document version"""
        return f"documents/{document_id}/versions/{version}/{filename}"


# Singleton instance
s3_service = S3Service()
