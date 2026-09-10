from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List
from app.models.db import get_db, User
from app.middleware.auth import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/assets", tags=["Presigned Upload"])

# ========================== Schemas ==============================

class PresignedUploadRequest(BaseModel):
    filename: str
    content_type: str = "image/png"
    asset_type: str = "reference"
    brand_id: int
    file_size_bytes: Optional[int] = None


class PresignedUploadResponse(BaseModel):
    upload_url: str
    asset_key: str
    expires_in_seconds: int
    fields: dict


# ========================== Endpoints ============================

@router.post("/presigned-upload", status_code=status.HTTP_200_OK)
async def generate_presigned_upload(
    payload: PresignedUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate direct S3 presigned upload URL bypassing API gateway."""
    import os

    storage_backend = os.getenv("STORAGE_BACKEND", "local")
    asset_key = f"{payload.asset_type}/{payload.brand_id}/{uuid.uuid4()}_{payload.filename}"

    if storage_backend == "s3":
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3_client = boto3.client(
                "s3",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_S3_REGION", "us-east-1"),
            )
            bucket = os.getenv("AWS_S3_BUCKET", "modelens-assets")

            presigned = s3_client.generate_presigned_post(
                Bucket=bucket,
                Key=asset_key,
                Fields={"Content-Type": payload.content_type},
                Conditions=[
                    {"Content-Type": payload.content_type},
                    ["content-length-range", 1, 100 * 1024 * 1024],  # 100MB max
                ],
                ExpiresIn=3600,
            )

            return {
                "upload_url": presigned["url"],
                "asset_key": asset_key,
                "expires_in_seconds": 3600,
                "fields": presigned["fields"],
                "storage_backend": "s3",
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 presigned URL generation failed: {e}")

    else:
        # Local/mock mode
        return {
            "upload_url": f"/api/v1/assets/upload-local/{asset_key}",
            "asset_key": asset_key,
            "expires_in_seconds": 3600,
            "fields": {"Content-Type": payload.content_type},
            "storage_backend": "local",
        }


@router.post("/confirm-upload")
async def confirm_upload(
    asset_key: str,
    brand_id: int,
    filename: str,
    asset_type: str = "reference",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm successful S3 upload and register asset in database."""
    from app.models.db import Asset
    import os

    cdn_base = os.getenv("CDN_BASE_URL", "")
    storage_path = f"{cdn_base}/{asset_key}" if cdn_base else asset_key

    asset = Asset(
        brand_id=brand_id,
        name=filename,
        filename=filename,
        storage_path=storage_path,
        asset_type=asset_type,
        status="active",
        meta={
            "asset_key": asset_key,
            "upload_method": "presigned_s3",
            "uploaded_by": current_user.id,
            "uploaded_at": datetime.utcnow().isoformat(),
        }
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return {
        "asset_id": asset.id,
        "asset_key": asset_key,
        "storage_path": storage_path,
        "status": "registered",
    }
