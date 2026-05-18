"""Todo/task management — add, list, mark complete, delete."""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from loguru import logger


TODO_FILE = Path.home() / ".iris" / "tasks.json"


async def add_task(task_name: str, priority: str = "normal") -> dict:
    """
    Add a new task to the todo list.

    Args:
        task_name: Description of the task
        priority: "low", "normal", "high" (default: normal)

    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        if not task_name or not task_name.strip():
            return {"status": "error", "result": "Task name cannot be empty"}

        if priority not in ["low", "normal", "high"]:
            priority = "normal"

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _add_task_sync, task_name.strip(), priority)

        logger.info(f"Task added: {task_name} (priority: {priority})")
        return {
            "status": "ok",
            "result": f"Added task: {task_name}"
        }

    except Exception as e:
        logger.error(f"add_task error: {e}")
        return {"status": "error", "result": str(e)}


async def list_tasks() -> dict:
    """
    List all pending and completed tasks.

    Returns:
        {"status": "ok"/"error", "result": formatted task list}
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _list_tasks_sync)
        logger.debug(f"Listed tasks: {len(result.split(chr(10)))} lines")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"list_tasks error: {e}")
        return {"status": "error", "result": str(e)}


async def mark_task_complete(task_id: int) -> dict:
    """
    Mark a task as complete by ID.

    Args:
        task_id: Task number (from list output)

    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        if not isinstance(task_id, int) or task_id < 1:
            return {"status": "error", "result": "Task ID must be a positive number"}

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _mark_complete_sync, task_id)

        logger.info(f"Task {task_id} marked complete")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"mark_task_complete error: {e}")
        return {"status": "error", "result": str(e)}


async def delete_task(task_id: int) -> dict:
    """
    Delete a task by ID.

    Args:
        task_id: Task number (from list output)

    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        if not isinstance(task_id, int) or task_id < 1:
            return {"status": "error", "result": "Task ID must be a positive number"}

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _delete_task_sync, task_id)

        logger.info(f"Task {task_id} deleted")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"delete_task error: {e}")
        return {"status": "error", "result": str(e)}


def _load_tasks() -> list:
    """Load tasks from JSON file. Return empty list if file doesn't exist."""
    if not TODO_FILE.exists():
        return []
    try:
        with open(TODO_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning(f"Could not load tasks from {TODO_FILE}")
        return []


def _save_tasks(tasks: list) -> None:
    """Save tasks to JSON file."""
    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TODO_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def _add_task_sync(task_name: str, priority: str) -> None:
    """Blocking task add. Run in executor."""
    tasks = _load_tasks()
    new_task = {
        "id": len(tasks) + 1,
        "name": task_name,
        "priority": priority,
        "completed": False,
        "created": datetime.now().isoformat(),
        "completed_at": None
    }
    tasks.append(new_task)
    _save_tasks(tasks)


def _list_tasks_sync() -> str:
    """Blocking task list. Run in executor."""
    tasks = _load_tasks()

    if not tasks:
        return "No tasks yet. Say 'Add task: ...' to create one."

    pending = [t for t in tasks if not t.get("completed")]
    completed = [t for t in tasks if t.get("completed")]

    output = []
    if pending:
        output.append("PENDING TASKS:")
        for t in pending:
            status = "🔴" if t.get("priority") == "high" else "⚪" if t.get("priority") == "normal" else "🟢"
            output.append(f"  {t['id']}. {status} {t['name']} ({t['priority']})")

    if completed:
        output.append("\nCOMPLETED:")
        for t in completed:
            output.append(f"  {t['id']}. ✓ {t['name']}")

    return "\n".join(output)


def _mark_complete_sync(task_id: int) -> str:
    """Blocking mark complete. Run in executor."""
    tasks = _load_tasks()

    for t in tasks:
        if t["id"] == task_id:
            t["completed"] = True
            t["completed_at"] = datetime.now().isoformat()
            _save_tasks(tasks)
            return f"Marked task {task_id} complete: {t['name']}"

    return f"Task {task_id} not found"


def _delete_task_sync(task_id: int) -> str:
    """Blocking delete. Run in executor."""
    tasks = _load_tasks()

    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            task_name = t["name"]
            tasks.pop(i)
            _save_tasks(tasks)
            return f"Deleted task {task_id}: {task_name}"

    return f"Task {task_id} not found"
