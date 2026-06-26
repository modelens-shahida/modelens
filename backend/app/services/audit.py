from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from fastapi import Request
from app.models.db import AuditLog


async def write_audit_log(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """
    Write an audit log entry to the database.

    Actions include:
    - api_key_created, api_key_deleted
    - webhook_created, webhook_deleted
    - asset_deleted, asset_restored
    - brand_member_added, brand_member_removed, brand_member_role_updated
    """
    client_ip = None
    if request:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host

    log = AuditLog(
        user_id=user_id,
        brand_id=brand_id,
        action=action,
        details=details or {},
        client_ip=client_ip,
    )
    db.add(log)
    await db.flush()  # Write immediately without committing (caller commits)
