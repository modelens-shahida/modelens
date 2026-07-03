import pytest
from unittest.mock import patch, MagicMock


class TestSendGridEmailIntegration:
    """Tests for SendGrid email sending in the low credit warning task."""

    def test_sendgrid_email_sent_on_low_credit(self):
        """SendGridAPIClient.send should be called with the correct payload."""
        from app.worker import _send_email

        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client_instance = MagicMock()
        mock_client_instance.send.return_value = mock_response

        with patch("app.config.settings") as mock_settings, \
             patch("sendgrid.SendGridAPIClient", return_value=mock_client_instance) as mock_sg:
            mock_settings.EMAIL_PROVIDER = "sendgrid"
            mock_settings.SENDGRID_API_KEY = "SG.test_key"
            mock_settings.FROM_EMAIL = "no-reply@modelens.com"

            _send_email(
                to_email="user@example.com",
                subject="Low Credit Balance Warning - ModeLens",
                html_content="<html><body>Test</body></html>",
            )

            mock_sg.assert_called_once_with("SG.test_key")
            mock_client_instance.send.assert_called_once()

            # Verify the Mail object was passed
            sent_message = mock_client_instance.send.call_args[0][0]
            assert sent_message is not None

    def test_ses_email_sent_on_low_credit(self):
        """boto3 send_email should be called with correct destination."""
        from app.worker import _send_email

        mock_ses_client = MagicMock()

        with patch("app.config.settings") as mock_settings, \
             patch("boto3.client", return_value=mock_ses_client) as mock_boto:
            mock_settings.EMAIL_PROVIDER = "ses"
            mock_settings.SES_REGION = "us-east-1"
            mock_settings.FROM_EMAIL = "no-reply@modelens.com"

            _send_email(
                to_email="user@example.com",
                subject="Low Credit Balance Warning - ModeLens",
                html_content="<html><body>Test</body></html>",
            )

            mock_boto.assert_called_once_with("ses", region_name="us-east-1")
            mock_ses_client.send_email.assert_called_once()

            call_kwargs = mock_ses_client.send_email.call_args[1]
            assert call_kwargs["Source"] == "no-reply@modelens.com"
            assert call_kwargs["Destination"] == {"ToAddresses": ["user@example.com"]}
            assert call_kwargs["Message"]["Subject"]["Data"] == "Low Credit Balance Warning - ModeLens"


class TestEmailTemplateRendering:
    """Tests for the HTML email template rendering."""

    def test_email_template_renders_correctly(self):
        """Template should contain user name, balance, threshold, and credits URL."""
        from app.worker import _render_low_credit_template

        html = _render_low_credit_template(
            user_name="testuser",
            current_balance=12,
            threshold=20,
            credits_url="https://modelens.com/credits",
        )

        assert "testuser" in html
        assert "12 credits" in html
        assert "20 credits" in html
        assert "https://modelens.com/credits" in html
        assert "ModeLens" in html

    def test_email_template_default_user_name(self):
        """Template should use 'User' when user_name is None."""
        from app.worker import _render_low_credit_template

        html = _render_low_credit_template(
            user_name=None,
            current_balance=5,
        )

        assert "Hi User" in html


class TestEmailSendRetry:
    """Tests for email send failure behavior."""

    def test_email_send_failure_triggers_retry(self):
        """SendGrid failure should raise an exception to trigger retry."""
        from app.worker import _send_email

        with patch("app.config.settings") as mock_settings, \
             patch("sendgrid.SendGridAPIClient") as mock_sg:
            mock_settings.EMAIL_PROVIDER = "sendgrid"
            mock_settings.SENDGRID_API_KEY = "SG.test_key"
            mock_settings.FROM_EMAIL = "no-reply@modelens.com"

            mock_sg.return_value.send.side_effect = Exception("SendGrid API error")

            with pytest.raises(Exception, match="SendGrid API error"):
                _send_email(
                    to_email="user@example.com",
                    subject="Test",
                    html_content="<html></html>",
                )
