import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any

from app.config import settings

class StorageService:
    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
        self._s3_client = None

    @property
    def s3_client(self):
        if self._s3_client is None and self.backend == "s3":
            self._s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            try:
                self.configure_lifecycle_rules()
            except Exception:
                pass
        return self._s3_client

    def generate_upload_params(self, unique_filename: str, file_type: str = "image") -> Dict[str, Any]:
        """
        Generates upload details. 
        If S3 backend is active, returns a presigned PUT URL.
        If local backend is active, returns a URL pointing to our local API.
        """
        if self.backend == "s3":
            try:
                # Generate a presigned PUT URL
                url = self.s3_client.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={
                        "Bucket": self.bucket,
                        "Key": unique_filename,
                        "ContentType": "application/octet-stream" if file_type != "image" else "image/png"
                    },
                    ExpiresIn=3600
                )
                return {
                    "upload_url": url,
                    "storage_path": f"s3://{self.bucket}/{unique_filename}",
                    "method": "PUT",
                    "headers": {
                        "Content-Type": "application/octet-stream" if file_type != "image" else "image/png"
                    }
                }
            except ClientError as e:
                # Fallback on configuration or connection error
                raise RuntimeError(f"Failed to generate S3 pre-signed URL: {str(e)}")
        else:
            # Local fallback: Point the frontend to our mock PUT route
            # Host name can be resolved dynamically or relative to current origin on frontend
            # For simplicity, we return a relative path that the frontend can call directly.
            # Example: /api/v1/assets/upload-mock/{unique_filename}
            return {
                "upload_url": f"/api/v1/assets/upload-mock/{unique_filename}",
                "storage_path": f"/uploads/{unique_filename}",
                "method": "PUT",
                "headers": {
                    "Content-Type": "application/octet-stream"
                }
            }

    def verify_file_exists(self, unique_filename: str) -> bool:
        """Checks if the file actually exists in S3 or local directory."""
        if self.backend == "s3":
            try:
                self.s3_client.head_object(Bucket=self.bucket, Key=unique_filename)
                return True
            except Exception:
                return False
        else:
            local_path = os.path.join("uploads", unique_filename)
            return os.path.exists(local_path)

    def configure_lifecycle_rules(self):
        """Sets a lifecycle rule on the S3 bucket to delete files with prefix 'temp/' after 24 hours."""
        if self.backend != "s3" or not self.bucket:
            return
        try:
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket,
                LifecycleConfiguration={
                    'Rules': [
                        {
                            'ID': 'DeleteTemporaryFilesAfter24Hours',
                            'Status': 'Enabled',
                            'Prefix': 'temp/',
                            'Expiration': {
                                'Days': 1
                            }
                        }
                    ]
                }
            )
        except Exception:
            pass

    def read_file_bytes(self, unique_filename: str) -> bytes:
        """Reads and returns file bytes from either S3 or local uploads directory."""
        if self.backend == "s3":
            try:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=unique_filename)
                return response['Body'].read()
            except Exception as e:
                raise RuntimeError(f"Failed to read file from S3 '{unique_filename}': {str(e)}")
        else:
            local_path = os.path.join("uploads", unique_filename)
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found: {local_path}")
            with open(local_path, "rb") as f:
                return f.read()

    def save_file_bytes(self, unique_filename: str, file_bytes: bytes, file_type: str = "image") -> str:
        """Saves file bytes to either S3 or local uploads directory, returning the public storage path."""
        if self.backend == "s3":
            try:
                content_type = "application/octet-stream" if file_type != "image" else "image/png"
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=unique_filename,
                    Body=file_bytes,
                    ContentType=content_type
                )
                return f"s3://{self.bucket}/{unique_filename}"
            except Exception as e:
                raise RuntimeError(f"Failed to upload file to S3 '{unique_filename}': {str(e)}")
        else:
            local_dir = "uploads"
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, unique_filename)
            with open(local_path, "wb") as f:
                f.write(file_bytes)
            return f"/uploads/{unique_filename}"


    def delete_file(self, filename: str) -> bool:
        """
        Deletes a file from either S3 or local uploads directory.
        Returns True if the deletion was successful or the file didn't exist.
        """
        if self.backend == "s3":
            try:
                self.s3_client.delete_object(Bucket=self.bucket, Key=filename)
                return True
            except Exception as e:
                raise RuntimeError(f"Failed to delete file from S3 '{filename}': {str(e)}")
        else:
            local_path = os.path.join("uploads", filename)
            if os.path.exists(local_path):
                os.remove(local_path)
            return True

storage_service = StorageService()
