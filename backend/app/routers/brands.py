from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import uuid
from datetime import datetime, timedelta, UTC
from app.models.db import get_db, Brand, BrandMember, User, Invitation
from app.middleware.auth import get_current_user, require_brand_role, ROLE_HIERARCHY
from app.models.db import AuditLog
from app.services.audit import write_audit_log
from app.api_docs import error_responses, limit_query, offset_query

router = APIRouter(
    prefix="/api/v1/brands",
    tags=["Brands"],
)


# ========================== Request / Response Schemas =====================

class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class BrandUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class BrandMemberInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"viewer", "editor", "admin"}
        if v not in allowed:
            raise ValueError(
                f"Role must be one of: {', '.join(sorted(allowed))}. "
                f"'owner' role is assigned automatically to brand creators."
            )
        return v


class BrandResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    model_config = {"from_attributes": True}


class BrandMemberResponse(BaseModel):
    id: int
    brand_id: int
    user_id: int
    role: str
    user_email: Optional[str] = None

    model_config = {"from_attributes": True}


class BrandInvitationRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"viewer", "editor", "admin"}
        if v not in allowed:
            raise ValueError(
                f"Role must be one of: {', '.join(sorted(allowed))}. "
            )
        return v


class InvitationResponse(BaseModel):
    id: int
    email: str
    role: str
    brand_id: int
    token: str
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ========================== Brand CRUD =====================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BrandResponse,
    summary="Create a brand",
    description=(
        "Create a new brand. The authenticated caller becomes the owner.\n"
        "No invite needed — ownership is automatic."
    ),
    response_description="The created brand.",
    operation_id="create_brand",
    responses=error_responses(401, 422),
)
async def create_brand(
    payload: BrandCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new brand. The authenticated caller becomes the owner.
    No invite needed — ownership is automatic.
    """
    brand = Brand(
        name=payload.name,
        owner_id=current_user.id,
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.get(
    "",
    response_model=list[BrandResponse],
    summary="List brands",
    description=(
        "List all brands the caller owns or is a member of.\n"
        "Never exposes brands the caller has no relationship with."
    ),
    response_description="Brands the caller owns or belongs to.",
    operation_id="list_brands",
    responses=error_responses(401),
)
async def list_brands(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all brands the caller owns or is a member of.
    Never exposes brands the caller has no relationship with.
    """
    # Brands the user owns
    owned_query = select(Brand).where(Brand.owner_id == current_user.id)
    owned_result = await db.execute(owned_query)
    owned_brands = list(owned_result.scalars().all())

    # Brands the user is a member of (but not owner)
    member_query = (
        select(Brand)
        .join(BrandMember, BrandMember.brand_id == Brand.id)
        .where(BrandMember.user_id == current_user.id)
    )
    member_result = await db.execute(member_query)
    member_brands = list(member_result.scalars().all())

    # Combine and deduplicate by ID
    seen_ids: set[int] = set()
    brands: list[Brand] = []
    for b in owned_brands + member_brands:
        if b.id not in seen_ids:
            seen_ids.add(b.id)
            brands.append(b)

    return brands


@router.get(
    "/{brand_id}",
    response_model=BrandResponse,
    summary="Get a brand",
    description=(
        "Get a single brand by ID.\n"
        "Requires at least **viewer** role (or owner)."
    ),
    response_description="The requested brand.",
    operation_id="get_brand",
    responses=error_responses(401, 403, 404, 422),
)
async def get_brand(
    brand_id: int,
    _caller: User = Depends(require_brand_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single brand by ID.
    Requires at least **viewer** role (or owner).
    """
    query = select(Brand).where(Brand.id == brand_id)
    result = await db.execute(query)
    brand = result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    return brand


@router.patch(
    "/{brand_id}",
    response_model=BrandResponse,
    summary="Update a brand",
    description=(
        "Update brand details (currently: name).\n"
        "Requires at least **admin** role (or owner)."
    ),
    response_description="The updated brand.",
    operation_id="update_brand",
    responses=error_responses(401, 403, 404, 422),
)
async def update_brand(
    brand_id: int,
    payload: BrandUpdateRequest,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update brand details (currently: name).
    Requires at least **admin** role (or owner).
    """
    query = select(Brand).where(Brand.id == brand_id)
    result = await db.execute(query)
    brand = result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    if payload.name is not None:
        brand.name = payload.name

    await db.commit()
    await db.refresh(brand)
    return brand


# ========================== Member Management ==============================

@router.post(
    "/{brand_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=BrandMemberResponse,
    summary="Add a brand member",
    description=(
        "Invite a user to a brand by email and assign a role.\n"
        "Requires at least **admin** role (or owner).\n"
        "\n"
        "Allowed roles for invite: viewer, editor, admin.\n"
        "The 'owner' role is reserved for the brand creator."
    ),
    response_description="The created brand membership.",
    operation_id="add_brand_member",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def invite_member(
    brand_id: int,
    payload: BrandMemberInviteRequest,
    request: Request,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a user to a brand by email and assign a role.
    Requires at least **admin** role (or owner).

    Allowed roles for invite: viewer, editor, admin.
    The 'owner' role is reserved for the brand creator.
    """
    # Resolve user by email
    user_query = select(User).where(User.email == payload.email)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user found with email '{payload.email}'",
        )

    # Prevent inviting the brand owner (they already have full access)
    brand_query = select(Brand).where(Brand.id == brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    if brand and brand.owner_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user is already the brand owner",
        )

    # Check if already a member
    existing_query = select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user.id,
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this brand",
        )

    # Create membership
    member = BrandMember(
        brand_id=brand_id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    # Audit log
    await write_audit_log(db, action="brand_member_added", user_id=_caller.id, brand_id=brand_id, details={"invited_user_email": payload.email, "role": payload.role}, request=request)

    return BrandMemberResponse(
        id=member.id,
        brand_id=member.brand_id,
        user_id=member.user_id,
        role=member.role,
        user_email=payload.email,
    )


@router.get(
    "/{brand_id}/members",
    response_model=list[BrandMemberResponse],
    summary="List brand members",
    description=(
        "List all members of a brand.\n"
        "Requires at least **viewer** role (or owner)."
    ),
    response_description="Members of the brand.",
    operation_id="list_brand_members",
    responses=error_responses(401, 403, 404, 422),
)
async def list_members(
    brand_id: int,
    _caller: User = Depends(require_brand_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """
    List all members of a brand.
    Requires at least **viewer** role (or owner).
    """
    query = (
        select(BrandMember, User.email)
        .join(User, User.id == BrandMember.user_id)
        .where(BrandMember.brand_id == brand_id)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        BrandMemberResponse(
            id=member.id,
            brand_id=member.brand_id,
            user_id=member.user_id,
            role=member.role,
            user_email=email,
        )
        for member, email in rows
    ]


@router.delete(
    "/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a brand",
    description="Delete a brand. Only the owner of the brand can delete it.",
    response_description="Brand deleted; no content returned.",
    operation_id="delete_brand",
    responses=error_responses(401, 403, 404, 422),
)
async def delete_brand(
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a brand. Only the owner of the brand can delete it.
    """
    query = select(Brand).where(Brand.id == brand_id)
    result = await db.execute(query)
    brand = result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    if brand.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the brand owner can delete this brand.",
        )
    await db.delete(brand)
    await db.commit()
    return


@router.delete(
    "/{brand_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a brand member",
    description=(
        "Remove a member from a brand.\n"
        "Requires at least **admin** role on the brand.\n"
        "Cannot remove the owner of the brand."
    ),
    response_description="Member removed; no content returned.",
    operation_id="remove_brand_member",
    responses=error_responses(400, 401, 403, 404, 422),
)
async def remove_member(
    brand_id: int,
    user_id: int,
    request: Request,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a member from a brand.
    Requires at least **admin** role on the brand.
    Cannot remove the owner of the brand.
    """
    # Fetch the brand to verify owner
    brand_query = select(Brand).where(Brand.id == brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    
    if brand.owner_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the owner from their own brand",
        )

    # Find membership
    member_query = select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user_id,
    )
    member_result = await db.execute(member_query)
    member = member_result.scalars().first()
    
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this brand",
        )
    
    await db.delete(member)
    await db.commit()

    # Audit log
    await write_audit_log(db, action="brand_member_removed", user_id=_caller.id, brand_id=brand_id, details={"removed_user_id": user_id}, request=request)

    return



@router.get(
    "/{brand_id}/audit-logs",
    response_model=list[dict],
    summary="Get brand audit logs",
    description=(
        "Retrieve the audit log timeline for a brand.\n"
        "Requires at least **admin** role (or owner).\n"
        "\n"
        "Returns activity records such as asset deletions, API key changes,\n"
        "webhook subscriptions, member role updates, and billing tier changes."
    ),
    response_description="Audit log timeline for the brand.",
    operation_id="get_brand_audit_logs",
    responses=error_responses(401, 403, 404, 422),
)
async def get_brand_audit_logs(
    brand_id: int,
    limit: int = limit_query(50, le=200),
    offset: int = offset_query(),
    category: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the audit log timeline for a brand.
    Requires at least **admin** role (or owner).

    Returns activity records such as asset deletions, API key changes,
    webhook subscriptions, member role updates, and billing tier changes.
    """
    query = (
        select(AuditLog, User.email)
        .join(User, User.id == AuditLog.user_id)
        .where(AuditLog.brand_id == brand_id)
    )

    if user_email:
        query = query.where(User.email.ilike(f"%{user_email}%"))

    if category:
        category_lower = category.lower()
        if category_lower == "auth":
            query = query.where(AuditLog.action.in_(["api_key_created", "api_key_deleted"]))
        elif category_lower == "webhook":
            query = query.where(AuditLog.action.in_(["webhook_created", "webhook_deleted"]))
        elif category_lower == "asset":
            query = query.where(AuditLog.action.in_(["asset_deleted", "asset_uploaded"]))
        elif category_lower == "user":
            query = query.where(AuditLog.action.in_(["brand_member_added", "brand_member_removed"]))
        elif category_lower == "billing":
            query = query.where(AuditLog.action.ilike("%billing%"))

    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    # Map category based on action
    def get_category_by_action(action: str) -> str:
        act = action.lower()
        if "api_key" in act:
            return "auth"
        elif "webhook" in act:
            return "webhook"
        elif "asset" in act:
            return "asset"
        elif "member" in act:
            return "user"
        elif "billing" in act:
            return "billing"
        return "auth"

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "brand_id": log.brand_id,
            "action": log.action,
            "details": log.details,
            "client_ip": log.client_ip,
            "ip_address": log.client_ip,
            "created_at": log.created_at.isoformat(),
            "user_email": email,
            "category": get_category_by_action(log.action),
            "status": "success",
        }
        for log, email in rows
    ]

# ========================== Auth Settings Endpoint ===============

class AuthSettingsUpdate(BaseModel):
    domain_whitelist: Optional[list] = None

@router.patch(
    "/{brand_id}/auth-settings",
    status_code=status.HTTP_200_OK,
    summary="Update brand SSO settings",
    description=(
        "Update brand SSO auth settings including domain whitelist.\n"
        "Requires at least **admin** role (or owner)."
    ),
    response_description="The updated SSO/auth settings.",
    operation_id="update_brand_auth_settings",
    responses=error_responses(401, 403, 404, 422),
)
async def update_auth_settings(
    brand_id: int,
    payload: AuthSettingsUpdate,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update brand SSO auth settings including domain whitelist.
    Requires at least **admin** role (or owner).
    """
    brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

    if payload.domain_whitelist is not None:
        brand.domain_whitelist = payload.domain_whitelist

    await db.commit()
    await db.refresh(brand)

    return {
        "brand_id": brand_id,
        "domain_whitelist": brand.domain_whitelist,
        "message": "Auth settings updated successfully.",
    }


@router.get(
    "/{brand_id}/auth-settings",
    summary="Get brand SSO settings",
    description="Get brand SSO auth settings. Requires at least **viewer** role.",
    response_description="The brand's SSO/auth settings.",
    operation_id="get_brand_auth_settings",
    responses=error_responses(401, 403, 404, 422),
)
async def get_auth_settings(
    brand_id: int,
    _caller: User = Depends(require_brand_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Get brand SSO auth settings. Requires at least **viewer** role."""
    brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

    return {
        "brand_id": brand_id,
        "domain_whitelist": brand.domain_whitelist or [],
    }


# ========================== Brand Invitations ==============================

@router.post(
    "/{brand_id}/invites",
    status_code=status.HTTP_201_CREATED,
    response_model=InvitationResponse,
    summary="Invite a user to a brand",
    description=(
        "Invite a user to a brand by email.\n"
        "Generates a secure token and queues invitation email sending task.\n"
        "Requires at least **admin** role on the brand."
    ),
    response_description="The created invitation.",
    operation_id="create_brand_invitation",
    responses=error_responses(400, 401, 403, 404, 422),
)
async def create_brand_invitation(
    brand_id: int,
    payload: BrandInvitationRequest,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a user to a brand by email.
    Generates a secure token and queues invitation email sending task.
    Requires at least **admin** role on the brand.
    """
    # Verify if email is already the owner of the brand
    brand_query = select(Brand).where(Brand.id == brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    
    # Resolve user if exists to check if they are already owner/member
    user_query = select(User).where(User.email == payload.email)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    
    if brand and user and brand.owner_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user is already the brand owner",
        )

    # Check if already a member
    if user:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == brand_id,
            BrandMember.user_id == user.id,
        )
        member_result = await db.execute(member_query)
        if member_result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this brand",
            )

    # Revoke any previous active invitations for this email + brand to avoid duplicates
    old_invites_query = select(Invitation).where(
        Invitation.brand_id == brand_id,
        Invitation.email == payload.email,
        Invitation.accepted_at == None,
        Invitation.revoked_at == None,
        Invitation.expires_at > datetime.now(UTC),
    )
    old_invites_result = await db.execute(old_invites_query)
    old_invites = old_invites_result.scalars().all()
    for old_invite in old_invites:
        old_invite.revoked_at = datetime.now(UTC)

    # Create new invitation
    token = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=7)
    
    invitation = Invitation(
        email=payload.email,
        role=payload.role,
        brand_id=brand_id,
        token=token,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    # Queue Celery task to send invitation email
    from app.worker import send_invitation_email
    send_invitation_email.delay(invitation.id, _caller.full_name or _caller.email)

    return invitation


@router.get(
    "/{brand_id}/invites",
    response_model=list[InvitationResponse],
    summary="List pending brand invitations",
    description=(
        "List all pending invitations for a brand.\n"
        "Pending means not accepted, not revoked, and not expired.\n"
        "Requires at least **admin** role on the brand."
    ),
    response_description="Pending (not accepted, revoked or expired) invitations.",
    operation_id="list_pending_brand_invitations",
    responses=error_responses(401, 403, 404, 422),
)
async def list_pending_brand_invitations(
    brand_id: int,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    List all pending invitations for a brand.
    Pending means not accepted, not revoked, and not expired.
    Requires at least **admin** role on the brand.
    """
    query = select(Invitation).where(
        Invitation.brand_id == brand_id,
        Invitation.accepted_at == None,
        Invitation.revoked_at == None,
        Invitation.expires_at > datetime.now(UTC),
    )
    result = await db.execute(query)
    invitations = result.scalars().all()
    return invitations


@router.delete(
    "/{brand_id}/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a brand invitation",
    description=(
        "Revoke a pending brand invitation.\n"
        "Requires at least **admin** role on the brand."
    ),
    response_description="Invitation revoked; no content returned.",
    operation_id="revoke_brand_invitation",
    responses=error_responses(401, 403, 404, 422),
)
async def revoke_brand_invitation(
    brand_id: int,
    invite_id: int,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a pending brand invitation.
    Requires at least **admin** role on the brand.
    """
    query = select(Invitation).where(
        Invitation.id == invite_id,
        Invitation.brand_id == brand_id,
    )
    result = await db.execute(query)
    invitation = result.scalars().first()
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    invitation.revoked_at = datetime.now(UTC)
    await db.commit()
    return


# ========================== Update Member Role Endpoint ==========

class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(viewer|editor|admin)$")


@router.patch(
    "/{brand_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Change a brand member's role",
    description=(
        "Update a brand member's role.\n"
        "Requires Admin or Owner role.\n"
        "Cannot change the brand owner's role.\n"
        "Users cannot change their own role."
    ),
    response_description="The member with the updated role.",
    operation_id="update_brand_member_role",
    responses=error_responses(401, 403, 404, 422),
)
async def update_member_role(
    brand_id: int,
    user_id: int,
    payload: UpdateMemberRoleRequest,
    request: Request,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a brand member's role.
    Requires Admin or Owner role.
    Cannot change the brand owner's role.
    Users cannot change their own role.
    """
    # Get brand to check owner
    brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

    # Cannot change owner's role
    if user_id == brand.owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot change the brand owner's role.")

    # Cannot change own role
    if user_id == _caller.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot change your own role.")

    # Find member
    member_result = await db.execute(
        select(BrandMember).where(BrandMember.brand_id == brand_id, BrandMember.user_id == user_id)
    )
    member = member_result.scalars().first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    old_role = member.role
    member.role = payload.role
    await db.commit()

    # Audit log
    await write_audit_log(
        db,
        action="brand_member_role_updated",
        user_id=_caller.id,
        brand_id=brand_id,
        details={"target_user_id": user_id, "old_role": old_role, "new_role": payload.role},
        request=request,
    )

    return {"user_id": user_id, "brand_id": brand_id, "role": payload.role}
