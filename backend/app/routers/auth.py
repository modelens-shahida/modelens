from typing import Optional
from app.config import settings
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, UTC
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets

from app.models.db import get_db, User, APIKey
from app.services.sso_service import handle_sso_login
from app.middleware.auth import (
    hash_password,
    verify_password,
    create_access_token,
    hash_api_key,
    get_current_user,
)
from app.middleware.rate_limit import RateLimiter

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Auth"],
)

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM


# --- Request Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SSOLoginRequest(BaseModel):
    email: EmailStr
    full_name: str
    provider: str


class RefreshRequest(BaseModel):
    refresh_token: str


class APIKeyRequest(BaseModel):
    name: str


# --- Endpoints ---

@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(RateLimiter(requests_limit=5, window_seconds=60))])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    Hashes password with bcrypt (cost=12), inserts User row, returns JWT.
    """
    # Check email uniqueness
    query = select(User).where(User.email == payload.email)
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password (bcrypt cost=12 configured in middleware)
    h_password = hash_password(payload.password)

    new_user = User(
        email=payload.email,
        hashed_password=h_password,
        full_name=payload.full_name,
        role="user",
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Generate JWT on registration so the user is immediately authenticated
    access_token = jwt.encode(
        {
            "sub": new_user.email,
            "exp": datetime.now(UTC) + timedelta(minutes=60),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return {
        "message": "User registered successfully",
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/login", dependencies=[Depends(RateLimiter(requests_limit=10, window_seconds=60))])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user with email + password.
    Returns access_token (60 min) + refresh_token (30 days).
    """
    query = select(User).where(User.email == payload.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not registered. Please register first.",
        )

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again.",
        )

    # Access token — 60 minutes
    access_token = jwt.encode(
        {
            "sub": user.email,
            "exp": datetime.now(UTC) + timedelta(minutes=60),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    # Refresh token — 30 days
    refresh_token = jwt.encode(
        {
            "sub": user.email,
            "exp": datetime.now(UTC) + timedelta(days=30),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    # SSO: auto-accept invitations and domain whitelist provisioning
    try:
        await handle_sso_login(user.email, db)
    except Exception as sso_err:
        print(f"[Auth] SSO provisioning error (non-fatal): {sso_err}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/sso-login")
async def sso_login(payload: SSOLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    SSO login/registration callback from the frontend.
    Verifies/creates the user in the database and returns a standard JWT session.
    """
    query = select(User).where(User.email == payload.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        # Auto-register user since they successfully authenticated via SSO (OAuth)
        h_password = hash_password(secrets.token_urlsafe(24))
        user = User(
            email=payload.email,
            hashed_password=h_password,
            full_name=payload.full_name,
            role="user",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Generate standard JWT access and refresh tokens
    access_token = jwt.encode(
        {
            "sub": user.email,
            "exp": datetime.now(UTC) + timedelta(minutes=60),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    refresh_token = jwt.encode(
        {
            "sub": user.email,
            "exp": datetime.now(UTC) + timedelta(days=30),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    # Perform domain whitelist auto-provisioning and accept pending invitations
    try:
        await handle_sso_login(user.email, db)
    except Exception as sso_err:
        print(f"[Auth] SSO provisioning error: {sso_err}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Validate refresh token, issue a new access token (60 min)."""
    try:
        decoded = jwt.decode(
            payload.refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        if not isinstance(decoded, dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        email = decoded.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify user still exists in database
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Issue new access token — 60 minutes
    access_token = jwt.encode(
        {
            "sub": email,
            "exp": datetime.now(UTC) + timedelta(minutes=60),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: APIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new API key for client/pipeline integration.
    Stores only the SHA-256 hash in DB. Returns plaintext once.
    """
    raw_key = f"ml_{secrets.token_urlsafe(32)}"
    key_hash_val = hash_api_key(raw_key)

    new_key = APIKey(
        user_id=current_user.id,
        name=payload.name,
        key_hash=key_hash_val,
        is_active=True,
    )
    db.add(new_key)
    await db.commit()

    return {
        "name": payload.name,
        "api_key": raw_key,  # Returned once — caller must store securely
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve profile information of the authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "credits": current_user.credits,
    }


class ProfileUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None


@router.patch("/me")
async def update_me(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile information."""
    if payload.email is not None and payload.email != current_user.email:
        # Check email uniqueness
        query = select(User).where(User.email == payload.email)
        result = await db.execute(query)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        current_user.email = payload.email

    if payload.full_name is not None:
        current_user.full_name = payload.full_name

    if payload.password is not None:
        current_user.hashed_password = hash_password(payload.password)

    await db.commit()
    await db.refresh(current_user)

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "credits": current_user.credits,
    }