from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.models.db import get_db, User, Brand, CreditTransaction
from app.middleware.auth import get_current_user
from app.services.credits_sync_service import credits_sync_service

router = APIRouter(prefix="/api/v1/credits/alerts", tags=["Low Credit Alerts"])


# ========================== Thresholds ===========================

DEFAULT_LOW_CREDIT_THRESHOLD = 20
DEFAULT_CRITICAL_THRESHOLD = 5
DEFAULT_WARNING_COOLDOWN_DAYS = 7

ALERT_LEVELS = {
    "critical": {"threshold": 5, "label": "Critical", "color": "red"},
    "low": {"threshold": 20, "label": "Low", "color": "orange"},
    "warning": {"threshold": 50, "label": "Warning", "color": "yellow"},
}


# ========================== Schemas ==============================

class AlertThresholdConfig(BaseModel):
    low_threshold: int = Field(20, ge=1)
    critical_threshold: int = Field(5, ge=1)
    warning_threshold: int = Field(50, ge=1)
    cooldown_days: int = Field(7, ge=1)
    email_alerts_enabled: bool = True
    webhook_alerts_enabled: bool = True


class LowCreditAlertResponse(BaseModel):
    brand_id: int
    current_balance: int
    alert_level: Optional[str]
    threshold_breached: Optional[int]
    email_sent: bool = False
    webhook_triggered: bool = False


# ========================== Alert Service ========================

async def check_and_trigger_alerts(
    brand_id: int,
    current_balance: int,
    user_id: int,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Check balance and trigger alerts if needed."""
    alert_level = None
    threshold_breached = None

    if current_balance <= DEFAULT_CRITICAL_THRESHOLD:
        alert_level = "critical"
        threshold_breached = DEFAULT_CRITICAL_THRESHOLD
    elif current_balance <= DEFAULT_LOW_CREDIT_THRESHOLD:
        alert_level = "low"
        threshold_breached = DEFAULT_LOW_CREDIT_THRESHOLD
    elif current_balance <= 50:
        alert_level = "warning"
        threshold_breached = 50

    email_sent = False
    webhook_triggered = False

    if alert_level:
        # Try sending email alert
        try:
            from app.worker import send_low_credit_warning_email
            send_low_credit_warning_email.delay(user_id)
            email_sent = True
        except Exception:
            pass

        # Trigger generation event
        try:
            from app.services.generation_events import generation_events, GenerationEvent
            await generation_events.publish(
                brand_id=brand_id,
                job_id=f"credit_alert_{brand_id}",
                event=GenerationEvent.FAILED,
                data={
                    "alert_type": "low_credits",
                    "alert_level": alert_level,
                    "current_balance": current_balance,
                    "threshold": threshold_breached,
                    "message": f"Credit balance is {alert_level}: {current_balance} credits remaining",
                }
            )
            webhook_triggered = True
        except Exception:
            pass

    return {
        "brand_id": brand_id,
        "current_balance": current_balance,
        "alert_level": alert_level,
        "threshold_breached": threshold_breached,
        "email_sent": email_sent,
        "webhook_triggered": webhook_triggered,
    }


# ========================== Endpoints ============================

async def _resolve_brand_id(current_user: User, db: AsyncSession) -> int:
    """Resolve brand_id from user attribute, brand ownership, or fallback."""
    brand_id = getattr(current_user, 'brand_id', None)
    if brand_id:
        return brand_id
    res = await db.execute(select(Brand.id).where(Brand.owner_id == current_user.id))
    b_id = res.scalars().first()
    if b_id:
        return b_id
    res = await db.execute(select(Brand.id))
    b_id = res.scalars().first()
    return b_id or 1


@router.get("/status")
async def get_credit_alert_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current credit alert status for the brand."""
    brand_id = await _resolve_brand_id(current_user, db)

    balance = await credits_sync_service.get_brand_credits(brand_id, db)

    alert_level = None
    if balance <= DEFAULT_CRITICAL_THRESHOLD:
        alert_level = "critical"
    elif balance <= DEFAULT_LOW_CREDIT_THRESHOLD:
        alert_level = "low"
    elif balance <= 50:
        alert_level = "warning"

    return {
        "brand_id": brand_id,
        "current_balance": balance,
        "alert_level": alert_level,
        "thresholds": ALERT_LEVELS,
        "is_critical": balance <= DEFAULT_CRITICAL_THRESHOLD,
        "is_low": balance <= DEFAULT_LOW_CREDIT_THRESHOLD,
        "is_warning": balance <= 50,
        "can_generate": balance > 0,
    }


@router.post("/check")
async def check_and_send_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger credit alert check."""
    brand_id = await _resolve_brand_id(current_user, db)

    balance = await credits_sync_service.get_brand_credits(brand_id, db)
    result = await check_and_trigger_alerts(brand_id, balance, current_user.id, db)
    return result


@router.get("/history")
async def get_alert_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent credit transactions that triggered low balance."""
    brand_id = await _resolve_brand_id(current_user, db)

    result = await db.execute(
        select(CreditTransaction)
        .where(
            CreditTransaction.brand_id == brand_id,
            CreditTransaction.amount < 0,
        )
        .order_by(CreditTransaction.id.desc())
        .limit(limit)
    )
    transactions = result.scalars().all()

    # Check which transactions dropped below threshold
    history = []
    for t in transactions:
        balance_after = getattr(t, 'balance_after', None)
        alert_level = None
        if balance_after is not None:
            if balance_after <= DEFAULT_CRITICAL_THRESHOLD:
                alert_level = "critical"
            elif balance_after <= DEFAULT_LOW_CREDIT_THRESHOLD:
                alert_level = "low"

        history.append({
            "transaction_id": t.id,
            "amount": t.amount,
            "balance_after": balance_after,
            "alert_level": alert_level,
            "description": t.description,
            "created_at": str(t.created_at),
        })

    return {
        "brand_id": brand_id,
        "history": history,
        "total": len(history),
    }


@router.get("/thresholds")
async def get_alert_thresholds(
    current_user: User = Depends(get_current_user),
):
    """Get current alert threshold configuration."""
    return {
        "thresholds": ALERT_LEVELS,
        "defaults": {
            "critical": DEFAULT_CRITICAL_THRESHOLD,
            "low": DEFAULT_LOW_CREDIT_THRESHOLD,
            "warning": 50,
            "cooldown_days": DEFAULT_WARNING_COOLDOWN_DAYS,
        }
    }
