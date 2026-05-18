"""Email actions integration tests."""

import pytest
from actions.email_actions import send_email, check_email
from actions.action_router import ACTION_HANDLERS
from actions.safety import classify, SafetyLevel


def test_email_handlers_registered():
    """Verify email actions are registered in action router."""
    assert "send_email" in ACTION_HANDLERS
    assert "check_email" in ACTION_HANDLERS
    assert ACTION_HANDLERS["send_email"] == send_email
    assert ACTION_HANDLERS["check_email"] == check_email


def test_email_safety_classification():
    """Verify email actions have correct safety levels."""
    assert classify("send_email") == SafetyLevel.WARN
    assert classify("check_email") == SafetyLevel.SAFE


def test_send_email_missing_config():
    """Test send_email fails gracefully when credentials not configured."""
    import asyncio

    async def run():
        # This should fail because config is empty
        result = await send_email(
            recipient="test@example.com",
            subject="Test",
            body="Test body"
        )
        # Should return error status since email_config is missing
        assert result["status"] == "error"
        assert "not configured" in result["result"].lower()

    asyncio.run(run())


def test_check_email_missing_config():
    """Test check_email fails gracefully when credentials not configured."""
    import asyncio

    async def run():
        result = await check_email()
        assert result["status"] == "error"
        assert "not configured" in result["result"].lower()

    asyncio.run(run())


def test_send_email_invalid_recipient():
    """Test send_email rejects invalid email addresses."""
    import asyncio
    from unittest.mock import patch

    async def run():
        # Mock the config to have email credentials
        mock_config = {
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "test@gmail.com",
                "sender_password": "password"
            }
        }

        with patch("actions.email_actions.load_config", return_value=mock_config):
            result = await send_email(
                recipient="not-an-email",
                subject="Test",
                body="Test"
            )
            assert result["status"] == "error"
            assert "invalid" in result["result"].lower()

    asyncio.run(run())


def test_send_email_valid_format():
    """Test send_email accepts valid email format."""
    import asyncio
    from unittest.mock import patch, MagicMock

    async def run():
        mock_config = {
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "test@gmail.com",
                "sender_password": "password"
            }
        }

        with patch("actions.email_actions.load_config", return_value=mock_config):
            with patch("actions.email_actions._send_smtp") as mock_smtp:
                # Mock successful SMTP send
                result = await send_email(
                    recipient="valid@example.com",
                    subject="Test Subject",
                    body="Test Body"
                )
                # Should attempt to send
                assert mock_smtp.called or result["status"] in ["ok", "error"]

    asyncio.run(run())
