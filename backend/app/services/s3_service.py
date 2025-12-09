import boto3
from botocore.exceptions import ClientError
from typing import Optional
from uuid import UUID
import logging
from io import BytesIO

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    async def upload_file(
        self,
        file_content: bytes,
        file_key: str,
        content_type: Optional[str] = None,
    ) -> bool:
        """Upload file to S3"""
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            self.s3_client.upload_fileobj(
                BytesIO(file_content),
                self.bucket_name,
                file_key,
                ExtraArgs=extra_args if extra_args else None,
            )
            logger.info(f"Uploaded file to S3: {file_key}")
            return True
        except ClientError as e:
            logger.error(f"Error uploading to S3: {e}")
            return False

    async def download_file(self, file_key: str) -> Optional[bytes]:
        """Download file from S3"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_key,
            )
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Error downloading from S3: {e}")
            return None

    async def delete_file(self, file_key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key,
            )
            logger.info(f"Deleted file from S3: {file_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting from S3: {e}")
            return False

    async def get_presigned_url(
        self,
        file_key: str,
        expiration: int = 3600,
        download: bool = False,
    ) -> Optional[str]:
        """Generate presigned URL for file access"""
        try:
            params = {
                "Bucket": self.bucket_name,
                "Key": file_key,
            }
            if download:
                params["ResponseContentDisposition"] = "attachment"

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None

    def generate_file_key(self, document_id: UUID, filename: str) -> str:
        """Generate S3 key for document"""
        return f"documents/{document_id}/{filename}"

    def generate_version_key(
        self,
        document_id: UUID,
        version: str,
        filename: str,
    ) -> str:
        """Generate S3 key for document version"""
        return f"documents/{document_id}/versions/{version}/{filename}"


# Singleton instance
s3_service = S3Service()
