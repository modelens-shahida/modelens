from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, CreditTransaction, User
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/credits",
    tags=["Credits"],
)

# ========================== Schemas ==============================

class CreditTransactionResponse(BaseModel):
    id: int
    amount: int
    transaction_type: str
    reference_type: Optional[str]
    reference_id: Optional[int]
    balance_after: int
    description: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class MockPurchaseRequest(BaseModel):
    package: str = Field(..., description="starter (100 credits) or pro (500 credits)")

class AdminAdjustRequest(BaseModel):
    target_user_id: int
    amount: int = Field(..., description="Positive to add, negative to deduct")
    description: Optional[str] = None

CREDIT_PACKAGES = {
    "starter": 100,
    "pro": 500,
    "enterprise": 2000,
}

LOW_CREDIT_THRESHOLD = 20

# ========================== Helper ===============================

async def log_credit_transaction(
    db: AsyncSession,
    user_id: int,
    amount: int,
    transaction_type: str,
    balance_after: int,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    description: Optional[str] = None,
):
    """Insert a credit ledger entry."""
    txn = CreditTransaction(
        user_id=user_id,
        amount=amount,
        transaction_type=transaction_type,
        reference_type=reference_type,
        reference_id=reference_id,
        balance_after=balance_after,
        description=description,
    )
    db.add(txn)
    await db.flush()
    return txn

# ========================== Endpoints ============================

@router.get("/balance")
async def get_credit_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns current credit balance and low credit warning flag."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalars().first()
    return {
        "user_id": user.id,
        "balance": user.credits,
        "low_credits": user.credits < LOW_CREDIT_THRESHOLD,
        "low_credit_threshold": LOW_CREDIT_THRESHOLD,
    }


@router.get("/history", response_model=List[CreditTransactionResponse])
async def get_credit_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of the user's credit transactions."""
    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post("/mock-purchase", status_code=status.HTTP_201_CREATED)
async def mock_purchase(
    payload: MockPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate a credit package purchase (Stripe mock)."""
    package = payload.package.lower()
    if package not in CREDIT_PACKAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid package. Choose from: {list(CREDIT_PACKAGES.keys())}"
        )

    credits_to_add = CREDIT_PACKAGES[package]

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalars().first()
    user.credits += credits_to_add
    new_balance = user.credits

    await log_credit_transaction(
        db,
        user_id=user.id,
        amount=credits_to_add,
        transaction_type="top_up",
        balance_after=new_balance,
        reference_type="purchase_invoice",
        description=f"Mock purchase: {package} package ({credits_to_add} credits)",
    )

    await db.commit()

    return {
        "message": f"Successfully purchased {package} package",
        "credits_added": credits_to_add,
        "new_balance": new_balance,
    }


@router.post("/admin-adjust", status_code=status.HTTP_200_OK)
async def admin_adjust(
    payload: AdminAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Grant or deduct credits from a user."""
    # Only owner or admin role users can adjust credits
    from app.middleware.auth import ROLE_HIERARCHY
    if ROLE_HIERARCHY.get(current_user.role, 0) < ROLE_HIERARCHY.get("admin", 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Owner role required."
        )

    result = await db.execute(select(User).where(User.id == payload.target_user_id))
    target_user = result.scalars().first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    target_user.credits += payload.amount
    new_balance = target_user.credits

    txn_type = "top_up" if payload.amount > 0 else "spend"
    await log_credit_transaction(
        db,
        user_id=target_user.id,
        amount=payload.amount,
        transaction_type=txn_type,
        balance_after=new_balance,
        reference_type="admin_action",
        description=payload.description or f"Admin adjustment by user {current_user.id}",
    )

    await db.commit()

    return {
        "message": "Credits adjusted successfully",
        "target_user_id": target_user.id,
        "amount": payload.amount,
        "new_balance": new_balance,
    }
