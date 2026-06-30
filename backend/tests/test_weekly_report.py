import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import CreditTransaction, AuditLog


@pytest.mark.asyncio
async def test_weekly_report_records_audit_log(db_session: AsyncSession, test_data: dict):
    """Weekly report should create AuditLog entries for brands with spend activity."""
    from app.worker import _weekly_usage_report_async

    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    txn = CreditTransaction(
        user_id=owner_user.id,
        amount=-5,
        transaction_type="spend",
        reference_type="job",
        balance_after=95,
        description="Test spend for weekly report",
    )
    db_session.add(txn)
    await db_session.commit()

    with patch("app.worker._send_weekly_report_email", new=AsyncMock()) as mock_email:
        await _weekly_usage_report_async()

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.brand_id == brand.id,
            AuditLog.action == "weekly_usage_report_generated"
        )
    )
    audit_entry = result.scalars().first()
    assert audit_entry is not None
    assert audit_entry.details["total_spent"] >= 5

    mock_email.assert_called()


@pytest.mark.asyncio
async def test_weekly_report_no_spend_no_audit_log(db_session: AsyncSession, test_data: dict):
    """If no spend occurred, no email should be triggered."""
    from app.worker import _weekly_usage_report_async

    with patch("app.worker._send_weekly_report_email", new=AsyncMock()) as mock_email:
        await _weekly_usage_report_async()

    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_send_weekly_report_email_format():
    """Email simulation should print expected mock email format."""
    from app.worker import _send_weekly_report_email
    import io
    import sys

    captured_output = io.StringIO()
    sys.stdout = captured_output

    await _send_weekly_report_email("owner@test.com", "Test Brand", 50, 10)

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    assert "owner@test.com" in output
    assert "Test Brand" in output
    assert "50" in output
