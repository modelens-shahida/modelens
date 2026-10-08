from typing import Literal, Optional
from app.config import settings
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from datetime import datetime, timedelta, UTC
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets

from app.models.db import get_db, User, APIKey
from app.services.sso_service import handle_sso_login
from app.services.sso_verification import SSOVerificationError, verify_sso_identity
from app.middleware.auth import (
    hash_password,
    verify_password,
    create_access_token,
    hash_api_key,
    get_current_user,
)
from app.middleware.rate_limit import RateLimiter
from app.middleware.sso_rate_limit import LIMITED_DETAIL, limit_sso_account, limit_sso_ip
from app.api_docs import ERROR_RESPONSES, error_responses

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
    """Provider credential only; the email always comes from the provider, never the client."""
    model_config = ConfigDict(extra="forbid")

    provider: Literal["google", "github"]
    id_token: Optional[str] = Field(default=None, min_length=1, max_length=8192)      # Google
    access_token: Optional[str] = Field(default=None, min_length=1, max_length=1024)  # GitHub
    code: Optional[str] = Field(default=None, min_length=1, max_length=1024)          # GitHub

    @model_validator(mode="after")
    def check_credentials(self):
        if self.provider == "google":
            if not self.id_token or self.access_token or self.code:
                raise ValueError("google requires id_token only")
        elif bool(self.access_token) == bool(self.code) or self.id_token:
            raise ValueError("github requires exactly one of access_token or code")
        return self


class RefreshRequest(BaseModel):
    refresh_token: str


class APIKeyRequest(BaseModel):
    name: str


# --- Endpoints ---

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(requests_limit=5, window_seconds=60))],
    summary="Register a user",
    description=(
        "Register a new user.\n"
        "Hashes password with bcrypt (cost=12), inserts User row, returns JWT.\n"
        "\n"
        "No authentication required.\n"
        "\n"
        "Rate limited; see the 429 response for the rate-limit headers."
    ),
    response_description="The created user and a JWT access token.",
    operation_id="register",
    responses=error_responses(400, 422, 429),
)
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


@router.post(
    "/login",
    dependencies=[Depends(RateLimiter(requests_limit=10, window_seconds=60))],
    summary="Log in with email and password",
    description=(
        "Authenticate user with email + password.\n"
        "Returns access_token (60 min) + refresh_token (30 days).\n"
        "\n"
        "No authentication required.\n"
        "\n"
        "Rate limited; see the 429 response for the rate-limit headers."
    ),
    response_description="Access token (60 min) and refresh token (30 days).",
    operation_id="login",
    responses=error_responses(401, 422, 429),
)
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


@router.post(
    "/sso-login",
    dependencies=[Depends(limit_sso_ip)],
    summary="Log in with SSO",
    description=(
        "SSO login/registration. Verifies the provider credential server-side, then\n"
        "finds or creates the user for the provider-verified email and returns a JWT session.\n"
        "\n"
        "No authentication required.\n"
        "\n"
        "Rate limited per client IP (`SSO_RATE_LIMIT_REQUESTS` per `SSO_RATE_LIMIT_WINDOW_SECONDS`,\n"
        "default 10 per 60 s) and per provider-verified account (`SSO_RATE_LIMIT_ACCOUNT_REQUESTS` per\n"
        "`SSO_RATE_LIMIT_ACCOUNT_WINDOW_SECONDS`, default 5 per 300 s). Both answer 429 with the same\n"
        "body and a `Retry-After` header."
    ),
    response_description="A JWT session for the provider-verified user.",
    operation_id="sso_login",
    responses={**error_responses(401, 422), 429: {
        **ERROR_RESPONSES[429],
        "description": "Too many SSO sign-in attempts from this IP or for this account. Wait `Retry-After` seconds.",
        "content": {"application/json": {"example": {"detail": LIMITED_DETAIL}}},
    }},
)
async def sso_login(payload: SSOLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    SSO login/registration. Verifies the provider credential server-side, then
    finds or creates the user for the provider-verified email and returns a JWT session.
    """
    try:
        identity = await verify_sso_identity(
            payload.provider,
            id_token=payload.id_token,
            access_token=payload.access_token,
            code=payload.code,
        )
    except SSOVerificationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SSO verification failed",
        )

    # Before the user lookup, so a 429 never tells whether the account exists.
    await limit_sso_account(identity.email)

    query = select(User).where(User.email == identity.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        # Auto-register: the provider has verified ownership of this email
        h_password = hash_password(secrets.token_urlsafe(24))
        user = User(
            email=identity.email,
            hashed_password=h_password,
            full_name=identity.full_name,
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


@router.post(
    "/refresh",
    summary="Refresh an access token",
    description=(
        "Validate refresh token, issue a new access token (60 min).\n"
        "\n"
        "No authentication required."
    ),
    response_description="A new access token.",
    operation_id="refresh_access_token",
    responses=error_responses(401, 422),
)
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


@router.post(
    "/api-keys",
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key (legacy auth path)",
    description=(
        "Generate a new API key for client/pipeline integration.\n"
        "Stores only the SHA-256 hash in DB. Returns plaintext once."
    ),
    response_description="The new API key. The plaintext key is shown only in this response.",
    operation_id="auth_create_api_key",
    responses=error_responses(401, 422),
)
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


@router.get(
    "/me",
    summary="Get the current user",
    description="Retrieve profile information of the authenticated user.",
    response_description="Profile of the authenticated user.",
    operation_id="get_current_user_profile",
    responses=error_responses(401),
)
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


@router.patch(
    "/me",
    summary="Update the current user",
    description="Update user profile information.",
    response_description="The updated user profile.",
    operation_id="update_current_user_profile",
    responses=error_responses(400, 401, 422),
)
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