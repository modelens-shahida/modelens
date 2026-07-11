from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime, UTC

from app.models.db import Brand, BrandMember, User, Invitation


def extract_email_domain(email: str) -> str:
    """Extract domain from email address."""
    return email.split("@")[-1].lower() if "@" in email else ""


async def find_whitelisted_brand(email: str, db: AsyncSession) -> Optional[Brand]:
    """
    Find a brand whose domain_whitelist contains the user's email domain.
    Returns the first matching brand or None.
    """
    domain = extract_email_domain(email)
    if not domain:
        return None

    result = await db.execute(
        select(Brand).where(Brand.domain_whitelist != None)
    )
    brands = result.scalars().all()

    for brand in brands:
        whitelist = brand.domain_whitelist or []
        if domain in [d.lower() for d in whitelist]:
            return brand

    return None


async def auto_provision_member(user: User, brand: Brand, role: str = "viewer", db: AsyncSession = None) -> bool:
    """
    Automatically provision a user into a brand workspace.
    Returns True if provisioned, False if already a member.
    """
    # Check if already a member
    existing = await db.execute(
        select(BrandMember).where(
            BrandMember.brand_id == brand.id,
            BrandMember.user_id == user.id,
        )
    )
    if existing.scalars().first():
        return False

    # Check if user is the brand owner
    if brand.owner_id == user.id:
        return False

    member = BrandMember(
        brand_id=brand.id,
        user_id=user.id,
        role=role,
    )
    db.add(member)
    await db.flush()
    print(f"[SSO] Auto-provisioned user {user.email} as {role} in brand {brand.name}")
    return True


async def accept_pending_invitation(user: User, db: AsyncSession) -> Optional[BrandMember]:
    """
    Check if there is a pending invitation for the user's email and auto-accept it.
    Returns the BrandMember if accepted, None otherwise.
    """
    result = await db.execute(
        select(Invitation).where(
            Invitation.email == user.email,
            Invitation.accepted_at == None,
            Invitation.revoked_at == None,
            Invitation.expires_at > datetime.now(UTC),
        )
    )
    invite = result.scalars().first()
    if not invite:
        return None

    # Check if already a member
    existing = await db.execute(
        select(BrandMember).where(
            BrandMember.brand_id == invite.brand_id,
            BrandMember.user_id == user.id,
        )
    )
    if existing.scalars().first():
        invite.accepted_at = datetime.now(UTC)
        await db.flush()
        return None

    member = BrandMember(
        brand_id=invite.brand_id,
        user_id=user.id,
        role=invite.role,
    )
    db.add(member)
    invite.accepted_at = datetime.now(UTC)
    await db.flush()
    print(f"[SSO] Auto-accepted invitation for {user.email} into brand {invite.brand_id} as {invite.role}")
    return member


async def handle_sso_login(email: str, db: AsyncSession) -> dict:
    """
    Handle SSO login/registration flow:
    1. Check for pending invitations and auto-accept
    2. Check domain whitelist and auto-provision
    3. Return provisioning result
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
        return {"provisioned": False, "reason": "User not found"}

    # 1. Check pending invitations
    member = await accept_pending_invitation(user, db)
    if member:
        await db.commit()
        return {
            "provisioned": True,
            "method": "invitation",
            "brand_id": member.brand_id,
            "role": member.role,
        }

    # 2. Check domain whitelist
    brand = await find_whitelisted_brand(email, db)
    if brand:
        provisioned = await auto_provision_member(user, brand, role="viewer", db=db)
        if provisioned:
            await db.commit()
            return {
                "provisioned": True,
                "method": "domain_whitelist",
                "brand_id": brand.id,
                "role": "viewer",
            }

    return {"provisioned": False, "reason": "No matching invitation or whitelisted domain"}
