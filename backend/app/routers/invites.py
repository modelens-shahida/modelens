from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, Brand, BrandMember, User, Invitation
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/invites",
    tags=["Invitations"],
)


class AcceptInvitationRequest(BaseModel):
    token: str


class AcceptInvitationResponse(BaseModel):
    status: str
    brand_id: int
    role: str


@router.post("/accept", status_code=status.HTTP_200_OK, response_model=AcceptInvitationResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a pending invitation.
    Verifies that the invitation token is valid, has not expired, is not revoked, and is not already accepted.
    Enforces that the logged-in user's email matches the invitation email.
    Provisions the user into the brand with the invited role.
    """
    query = select(Invitation).where(Invitation.token == payload.token)
    result = await db.execute(query)
    invitation = result.scalars().first()
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has already been accepted",
        )

    if invitation.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has been revoked",
        )

    if invitation.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired",
        )

    # Enforce email check
    if current_user.email.lower() != invitation.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation was sent to a different email address.",
        )

    # Check if they are already a member or owner of the brand
    brand_query = select(Brand).where(Brand.id == invitation.brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    
    if brand and brand.owner_id == current_user.id:
        # User is owner, just mark accepted
        invitation.accepted_at = datetime.utcnow()
        await db.commit()
        return AcceptInvitationResponse(
            status="success",
            brand_id=invitation.brand_id,
            role="owner",
        )

    member_query = select(BrandMember).where(
        BrandMember.brand_id == invitation.brand_id,
        BrandMember.user_id == current_user.id,
    )
    member_result = await db.execute(member_query)
    existing_member = member_result.scalars().first()
    
    if existing_member:
        # Already a member, just update the role if it's different and mark invitation accepted
        existing_member.role = invitation.role
        invitation.accepted_at = datetime.utcnow()
        await db.commit()
        return AcceptInvitationResponse(
            status="success",
            brand_id=invitation.brand_id,
            role=invitation.role,
        )

    # Create new BrandMember
    new_member = BrandMember(
        brand_id=invitation.brand_id,
        user_id=current_user.id,
        role=invitation.role,
    )
    db.add(new_member)
    invitation.accepted_at = datetime.utcnow()
    await db.commit()

    return AcceptInvitationResponse(
        status="success",
        brand_id=invitation.brand_id,
        role=invitation.role,
    )
