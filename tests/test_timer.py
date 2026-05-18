"""Timer and reminder actions tests."""

import pytest
from actions.timer_actions import set_timer, set_reminder, list_reminders, cancel_reminder
from actions.action_router import ACTION_HANDLERS
from actions.safety import classify, SafetyLevel


def test_timer_handlers_registered():
    """Verify timer actions are registered."""
    assert "set_timer" in ACTION_HANDLERS
    assert "set_reminder" in ACTION_HANDLERS
    assert "list_reminders" in ACTION_HANDLERS
    assert "cancel_reminder" in ACTION_HANDLERS


def test_timer_safety_classification():
    """Verify timer actions have correct safety levels."""
    assert classify("set_timer") == SafetyLevel.WARN
    assert classify("set_reminder") == SafetyLevel.WARN
    assert classify("list_reminders") == SafetyLevel.SAFE
    assert classify("cancel_reminder") == SafetyLevel.WARN


def test_set_timer_invalid_duration():
    """Test set_timer rejects invalid durations."""
    import asyncio

    async def run():
        # Too short
        result = await set_timer(0)
        assert result["status"] == "error"
        assert "between" in result["result"].lower()

        # Too long
        result = await set_timer(3601)
        assert result["status"] == "error"
        assert "between" in result["result"].lower()

    asyncio.run(run())


def test_set_timer_valid():
    """Test set_timer accepts valid duration."""
    import asyncio

    async def run():
        result = await set_timer(300, label="Cooking")
        assert result["status"] == "ok"
        assert "300" in result["result"]
        assert "Cooking" in result["result"]

    asyncio.run(run())


def test_set_reminder_invalid_minutes():
    """Test set_reminder rejects invalid minutes."""
    import asyncio

    async def run():
        # Too short
        result = await set_reminder("Test", 0)
        assert result["status"] == "error"
        assert "between" in result["result"].lower()

        # Too long (>24 hours)
        result = await set_reminder("Test", 1441)
        assert result["status"] == "error"
        assert "between" in result["result"].lower()

    asyncio.run(run())


def test_set_reminder_valid():
    """Test set_reminder accepts valid input."""
    import asyncio
    from unittest.mock import patch

    async def run():
        with patch("actions.timer_actions._add_reminder_sync"):
            result = await set_reminder("Check email", 30)
            assert result["status"] == "ok"
            assert "Check email" in result["result"]
            assert "30" in result["result"]

    asyncio.run(run())


def test_cancel_reminder_invalid_id():
    """Test cancel_reminder rejects invalid IDs."""
    import asyncio

    async def run():
        result = await cancel_reminder(-1)
        assert result["status"] == "error"
        assert "positive" in result["result"].lower()

        result = await cancel_reminder(0)
        assert result["status"] == "error"
        assert "positive" in result["result"].lower()

    asyncio.run(run())


def test_list_reminders_no_reminders():
    """Test list_reminders handles empty list."""
    import asyncio
    from unittest.mock import patch

    async def run():
        with patch("actions.timer_actions._list_reminders_sync", return_value="No active reminders."):
            result = await list_reminders()
            assert result["status"] == "ok"
            assert "no" in result["result"].lower()

    asyncio.run(run())
