"""
Generation Credits Sync Service
Handles atomic credit deductions, reservations, refunds for generation jobs.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.db import Brand, CreditTransaction


# ========================== Credit Rates =========================

CREDIT_RATES = {
    "FAST_DRAFT": {
        "1K": 1,
        "2K": 2,
        "4K": 3,
        "8K": 5,
        "default": 2,
    },
    "STUDIO_QUALITY": {
        "1K": 2,
        "2K": 4,
        "4K": 7,
        "8K": 10,
        "default": 5,
    },
}

GHOST_CREDIT_RATES = {
    "1K": 2,
    "2K": 4,
    "4K": 7,
    "default": 4,
}


def estimate_credits(params: Dict[str, Any]) -> int:
    """Estimate credits for a generation job."""
    quality_mode = params.get("quality_mode", "FAST_DRAFT").upper()
    resolution = params.get("resolution", "2K").upper()
    output_count = params.get("outputCount", 1)

    rates = CREDIT_RATES.get(quality_mode, CREDIT_RATES["FAST_DRAFT"])
    per_output = rates.get(resolution, rates["default"])
    return per_output * output_count


def estimate_batch_credits(
    angle_count: int,
    quality_mode: str = "STUDIO_QUALITY",
    resolution: str = "2K",
) -> int:
    """Estimate credits for a batch generation job."""
    rates = CREDIT_RATES.get(quality_mode.upper(), CREDIT_RATES["STUDIO_QUALITY"])
    per_angle = rates.get(resolution.upper(), rates["default"])
    return per_angle * angle_count


class CreditsSyncService:
    """Atomic credit sync for generation jobs."""

    async def get_brand_credits(
        self,
        brand_id: int,
        db: AsyncSession,
    ) -> int:
        """Get current credit balance for a brand."""
        result = await db.execute(
            select(Brand).where(Brand.id == brand_id)
        )
        brand = result.scalars().first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found.")
        return brand.credits or 0

    async def check_sufficient_credits(
        self,
        brand_id: int,
        required_credits: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Check if brand has sufficient credits."""
        balance = await self.get_brand_credits(brand_id, db)
        sufficient = balance >= required_credits
        return {
            "sufficient": sufficient,
            "balance": balance,
            "required": required_credits,
            "shortfall": max(0, required_credits - balance),
        }

    async def reserve_credits(
        self,
        brand_id: int,
        user_id: int,
        amount: int,
        generation_id: str,
        description: str,
        db: AsyncSession,
    ) -> CreditTransaction:
        """Reserve credits atomically before generation starts."""
        # Check balance
        check = await self.check_sufficient_credits(brand_id, amount, db)
        if not check["sufficient"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "message": f"Insufficient credits. Required: {amount}, Available: {check['balance']}",
                    "balance": check["balance"],
                    "required": amount,
                    "shortfall": check["shortfall"],
                }
            )

        # Deduct from brand
        result = await db.execute(
            select(Brand).where(Brand.id == brand_id)
        )
        brand = result.scalars().first()
        brand.credits = (brand.credits or 0) - amount

        # Create pending transaction
        txn = CreditTransaction(
            user_id=user_id,
            brand_id=brand_id,
            transaction_type="reserved",
            amount=-amount,
            description=description,
            reference_id=generation_id,
            status="pending",
        )
        db.add(txn)
        await db.commit()
        await db.refresh(txn)

        # Add hash chaining
        from app.services.credit_ledger_service import credit_ledger_service
        txn.chain_hash = credit_ledger_service.compute_transaction_hash(
            transaction_id=txn.id,
            user_id=user_id,
            brand_id=brand_id,
            transaction_type="reserved",
            amount=-amount,
            balance_after=brand.credits,
            previous_hash="GENESIS",
            created_at=str(txn.created_at),
        )
        txn.balance_after = brand.credits
        await db.commit()

        return txn

    async def finalize_credits(
        self,
        generation_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Finalize pending reservation on generation success."""
        result = await db.execute(
            select(CreditTransaction).where(
                CreditTransaction.reference_id == generation_id,
                CreditTransaction.status == "pending",
            )
        )
        txn = result.scalars().first()
        if not txn:
            raise HTTPException(status_code=404, detail="Pending transaction not found.")

        txn.status = "completed"
        await db.commit()

        return {
            "status": "completed",
            "generation_id": generation_id,
            "transaction_id": txn.id,
            "amount": txn.amount,
        }

    async def refund_credits(
        self,
        generation_id: str,
        reason: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Refund credits on generation failure."""
        result = await db.execute(
            select(CreditTransaction).where(
                CreditTransaction.reference_id == generation_id,
                CreditTransaction.status == "pending",
            )
        )
        txn = result.scalars().first()
        if not txn:
            raise HTTPException(status_code=404, detail="Pending transaction not found.")

        refund_amount = abs(txn.amount)

        # Restore brand credits
        brand_result = await db.execute(
            select(Brand).where(Brand.id == txn.brand_id)
        )
        brand = brand_result.scalars().first()
        if brand:
            brand.credits = (brand.credits or 0) + refund_amount

        # Mark original as refunded
        txn.status = "refunded"

        # Create refund transaction
        refund_txn = CreditTransaction(
            user_id=txn.user_id,
            brand_id=txn.brand_id,
            transaction_type="refund",
            amount=refund_amount,
            description=f"Auto refund: {reason}",
            reference_id=f"refund_{generation_id}",
            status="completed",
        )
        db.add(refund_txn)
        await db.commit()

        return {
            "status": "refunded",
            "generation_id": generation_id,
            "credits_refunded": refund_amount,
            "reason": reason,
            "new_balance": brand.credits if brand else None,
        }


# Singleton
credits_sync_service = CreditsSyncService()
