"""Todo actions tests."""

import pytest
import json
from pathlib import Path
from actions.todo_actions import add_task, list_tasks, mark_task_complete, delete_task
from actions.action_router import ACTION_HANDLERS
from actions.safety import classify, SafetyLevel


def test_todo_handlers_registered():
    """Verify todo actions are registered."""
    assert "add_task" in ACTION_HANDLERS
    assert "list_tasks" in ACTION_HANDLERS
    assert "mark_task_complete" in ACTION_HANDLERS
    assert "delete_task" in ACTION_HANDLERS


def test_todo_safety_classification():
    """Verify todo actions have correct safety levels."""
    assert classify("add_task") == SafetyLevel.WARN
    assert classify("list_tasks") == SafetyLevel.SAFE
    assert classify("mark_task_complete") == SafetyLevel.WARN
    assert classify("delete_task") == SafetyLevel.WARN


def test_add_task_empty_name():
    """Test add_task rejects empty task names."""
    import asyncio

    async def run():
        result = await add_task("")
        assert result["status"] == "error"
        assert "empty" in result["result"].lower()

    asyncio.run(run())


def test_add_task_valid():
    """Test add_task accepts valid task."""
    import asyncio
    from unittest.mock import patch

    async def run():
        with patch("actions.todo_actions._add_task_sync") as mock_add:
            result = await add_task("Test task", "high")
            assert result["status"] == "ok"
            assert "Test task" in result["result"]
            assert mock_add.called

    asyncio.run(run())


def test_add_task_invalid_priority():
    """Test add_task defaults invalid priority."""
    import asyncio
    from unittest.mock import patch

    async def run():
        with patch("actions.todo_actions._add_task_sync") as mock_add:
            result = await add_task("Test", priority="invalid")
            assert result["status"] == "ok"
            # Should default to "normal"
            assert mock_add.called

    asyncio.run(run())


def test_mark_task_invalid_id():
    """Test mark_task_complete rejects invalid IDs."""
    import asyncio

    async def run():
        result = await mark_task_complete(-1)
        assert result["status"] == "error"
        assert "positive" in result["result"].lower()

    asyncio.run(run())


def test_delete_task_invalid_id():
    """Test delete_task rejects invalid IDs."""
    import asyncio

    async def run():
        result = await delete_task(0)
        assert result["status"] == "error"
        assert "positive" in result["result"].lower()

    asyncio.run(run())


def test_list_tasks_no_tasks():
    """Test list_tasks handles empty list."""
    import asyncio
    from unittest.mock import patch

    async def run():
        with patch("actions.todo_actions._list_tasks_sync", return_value="No tasks yet"):
            result = await list_tasks()
            assert result["status"] == "ok"
            assert "no tasks" in result["result"].lower()

    asyncio.run(run())
