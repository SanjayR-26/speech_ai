"""
S3 client for file storage
"""
import boto3
from botocore.exceptions import ClientError
import logging
from typing import Optional, Dict, Any
import os
from uuid import UUID

from ..core.config import settings
from ..core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class S3Client:
    """Client for AWS S3 storage"""
    
    def __init__(self):
        self.bucket_name = settings.aws_s3_bucket
        self.region = settings.aws_region
        
        if settings.storage_type == "s3" and settings.aws_access_key_id:
            self.client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=self.region
            )
        else:
            self.client = None
    
    async def upload_file(
        self,
        file_data: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Upload file to S3"""
        if not self.client:
            raise ExternalServiceError("S3", "S3 client not configured")
        
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Upload file
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_data,
                **extra_args
            )
            
            # Return S3 URL
            return f"s3://{self.bucket_name}/{key}"
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise ExternalServiceError(
                "S3",
                f"Upload failed: {e.response['Error']['Message']}",
                {"error_code": e.response['Error']['Code']}
            )
    
    async def download_file(self, key: str) -> bytes:
        """Download file from S3"""
        if not self.client:
            raise ExternalServiceError("S3", "S3 client not configured")
        
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response['Body'].read()
            
        except ClientError as e:
            logger.error(f"S3 download error: {e}")
            raise ExternalServiceError(
                "S3",
                f"Download failed: {e.response['Error']['Message']}",
                {"error_code": e.response['Error']['Code']}
            )
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from S3"""
        if not self.client:
            raise ExternalServiceError("S3", "S3 client not configured")
        
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
            
        except ClientError as e:
            logger.error(f"S3 delete error: {e}")
            return False
    
    async def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        http_method: str = "GET"
    ) -> str:
        """Generate presigned URL for direct access"""
        if not self.client:
            raise ExternalServiceError("S3", "S3 client not configured")
        
        try:
            url = self.client.generate_presigned_url(
                'get_object' if http_method == "GET" else 'put_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            logger.error(f"S3 presigned URL error: {e}")
            raise ExternalServiceError(
                "S3",
                f"Presigned URL generation failed: {e.response['Error']['Message']}",
                {"error_code": e.response['Error']['Code']}
            )
    
    def get_file_key(self, call_id: UUID, file_name: str) -> str:
        """Generate S3 key for file"""
        # Organize by date and call ID
        from datetime import datetime
        date_path = datetime.utcnow().strftime("%Y/%m/%d")
        return f"calls/{date_path}/{call_id}/{file_name}"
    
    async def check_file_exists(self, key: str) -> bool:
        """Check if file exists in S3"""
        if not self.client:
            return False
        
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except ClientError:
            return False
