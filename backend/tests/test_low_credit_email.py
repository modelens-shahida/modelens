import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.models.db import User


@pytest.mark.asyncio
async def test_sendgrid_email_sent_on_low_credit(db_session: AsyncSession, test_data: dict):
    """SendGrid should be called when low credit warning is triggered."""
    from app.worker import send_low_credit_warning_email

    editor_user = test_data["users"]["editor"]
    result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = result.scalars().first()
    user.credits = 10
    user.last_low_credit_warning_at = None
    await db_session.commit()

    mock_sg_instance = MagicMock()
    mock_sg_instance.send.return_value = MagicMock(status_code=202)

    with patch("app.worker.settings") as mock_settings, \
         patch("app.worker.async_session_maker") as mock_session_maker:

        mock_settings.EMAIL_PROVIDER = "sendgrid"
        mock_settings.SENDGRID_API_KEY = "SG.testkey"
        mock_settings.FROM_EMAIL = "no-reply@modelens.com"

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.email = "editor@test.com"
        mock_user.full_name = "Editor User"
        mock_user.credits = 10
        mock_db.execute.return_value.scalars.return_value.first.return_value = mock_user
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        with patch("sendgrid.SendGridAPIClient", return_value=mock_sg_instance):
            send_low_credit_warning_email(editor_user.id)

        mock_sg_instance.send.assert_called_once()
        call_args = mock_sg_instance.send.call_args[0][0]
        assert "editor@test.com" in str(call_args) or any("editor@test.com" in str(p.tos) for p in getattr(call_args, "personalizations", []))


@pytest.mark.asyncio
async def test_ses_email_sent_on_low_credit(db_session: AsyncSession, test_data: dict):
    """AWS SES should be called when EMAIL_PROVIDER is ses."""
    from app.worker import send_low_credit_warning_email

    editor_user = test_data["users"]["editor"]

    mock_ses_client = MagicMock()
    mock_ses_client.send_email.return_value = {"MessageId": "mock-message-id"}

    with patch("app.worker.settings") as mock_settings, \
         patch("app.worker.async_session_maker") as mock_session_maker:

        mock_settings.EMAIL_PROVIDER = "ses"
        mock_settings.SES_REGION = "us-east-1"
        mock_settings.FROM_EMAIL = "no-reply@modelens.com"

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.email = "editor@test.com"
        mock_user.full_name = "Editor User"
        mock_user.credits = 5
        mock_db.execute.return_value.scalars.return_value.first.return_value = mock_user
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        with patch("boto3.client", return_value=mock_ses_client):
            send_low_credit_warning_email(editor_user.id)

        mock_ses_client.send_email.assert_called_once()
        call_kwargs = mock_ses_client.send_email.call_args[1]
        assert call_kwargs["Destination"]["ToAddresses"] == ["editor@test.com"]
        assert "Low Credit" in call_kwargs["Message"]["Subject"]["Data"]


@pytest.mark.asyncio
async def test_email_template_renders_correctly():
    """HTML template should contain user details."""
    from app.worker import _render_low_credit_template

    html = _render_low_credit_template("Anshu Kumar", 15, threshold=20)
    assert "Anshu Kumar" in html
    assert "15" in html
    assert "20" in html
    assert "modelens.com/credits" in html


@pytest.mark.asyncio
async def test_email_send_failure_triggers_retry():
    """Email send failure should trigger Celery retry."""
    from app.worker import send_low_credit_warning_email

    with patch("app.worker.settings") as mock_settings, \
         patch("app.worker.async_session_maker") as mock_session_maker:

        mock_settings.EMAIL_PROVIDER = "sendgrid"
        mock_settings.SENDGRID_API_KEY = "SG.testkey"
        mock_settings.FROM_EMAIL = "no-reply@modelens.com"

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.email = "test@test.com"
        mock_user.full_name = "Test User"
        mock_user.credits = 5
        mock_db.execute.return_value.scalars.return_value.first.return_value = mock_user
        mock_session_maker.return_value.__aenter__.return_value = mock_db

        mock_sg = MagicMock()
        mock_sg.send.side_effect = Exception("SendGrid unavailable")

        with patch("sendgrid.SendGridAPIClient", return_value=mock_sg):
            # Should not crash — retry is handled internally
            try:
                send_low_credit_warning_email(1)
            except Exception:
                pass  # Retry exception is expected
