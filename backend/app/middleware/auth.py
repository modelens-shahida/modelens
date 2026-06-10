import hashlib
from typing import Optional
from app.config import settings
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import User, APIKey, Brand, BrandMember, get_db

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

# ---------------------------------------------------------------------------
# Auth schemes — auto_error=False lets both schemes coexist without
# immediately raising 401 when one header is absent.
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)

# ---------------------------------------------------------------------------
# Password hashing — bcrypt cost factor 12 (2^12 = 4096 iterations)
# ---------------------------------------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)

# ---------------------------------------------------------------------------
# RBAC role hierarchy: owner > admin > editor > viewer
# ---------------------------------------------------------------------------
ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
    "owner": 4,
}


# ========================== Utility Functions ==============================

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (cost=12)."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Encode a JWT with the given payload."""
    to_encode = data.copy()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256 for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


# ========================== Core Auth Dependency ===========================

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Production dual-auth dependency.

    Resolution order:
      1. X-API-Key header → SHA-256 lookup in api_keys table
      2. Bearer JWT        → decode and resolve email to User

    Both paths return a fully-loaded User ORM instance or raise 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # --- Path 1: X-API-Key header ---
    if api_key is not None:
        key_hash_val = hash_api_key(api_key)
        query = select(APIKey).where(
            APIKey.key_hash == key_hash_val,
            APIKey.is_active.is_(True),
        )
        result = await db.execute(query)
        api_key_record = result.scalars().first()
        if api_key_record is None:
            raise credentials_exception

        # Resolve to the owning User
        user_query = select(User).where(User.id == api_key_record.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalars().first()
        if user is None:
            raise credentials_exception
        return user

    # --- Path 2: Bearer JWT ---
    if token is not None:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if not isinstance(payload, dict):
                raise credentials_exception
            email: Optional[str] = payload.get("sub")
            if email is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        user_query = select(User).where(User.email == email)
        user_result = await db.execute(user_query)
        user = user_result.scalars().first()
        if user is None:
            raise credentials_exception
        return user

    # --- No credentials provided ---
    raise credentials_exception


# ========================== RBAC Dependency Factory ========================

def require_brand_role(minimum_role: str):
    """
    FastAPI dependency factory for per-brand RBAC enforcement.

    Returns a dependency that:
      1. Authenticates the caller via dual-auth.
      2. Verifies the brand exists (from ``brand_id`` path param).
      3. Grants instant access if the caller is the brand owner.
      4. Otherwise checks BrandMember.role against the hierarchy.

    Role hierarchy: owner (4) > admin (3) > editor (2) > viewer (1)

    Usage::

        @router.patch("/{brand_id}")
        async def update_brand(
            brand_id: int,
            _caller: User = Depends(require_brand_role("admin")),
            db: AsyncSession = Depends(get_db),
        ):
            ...
    """
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def _check_brand_role(
        brand_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Verify brand exists
        brand_query = select(Brand).where(Brand.id == brand_id)
        brand_result = await db.execute(brand_query)
        brand = brand_result.scalars().first()
        if brand is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Brand not found",
            )

        # Owner always has full access
        if brand.owner_id == current_user.id:
            return current_user

        # Lookup membership
        member_query = select(BrandMember).where(
            BrandMember.brand_id == brand_id,
            BrandMember.user_id == current_user.id,
        )
        member_result = await db.execute(member_query)
        membership = member_result.scalars().first()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this brand",
            )

        user_level = ROLE_HIERARCHY.get(membership.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Requires at least '{minimum_role}' role. "
                    f"Your role: '{membership.role}'"
                ),
            )

        return current_user

    return _check_brand_role
