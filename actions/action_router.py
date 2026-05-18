"""Routes subtasks to the correct action handler. Enforces safety classification."""

import uuid
from loguru import logger
from actions.safety import classify, SafetyLevel
from actions import (
    os_actions, shell_actions, file_actions, screen_actions, clipboard_actions,
    email_actions, todo_actions, weather_actions, timer_actions
)


ACTION_HANDLERS = {
    "open_app":         os_actions.open_app,
    "focus_window":     os_actions.focus_window,
    "run_shell":        shell_actions.run_shell,
    "run_shell_sudo":   shell_actions.run_shell,
    "read_file":        file_actions.read_file,
    "write_file":       file_actions.write_file,
    "move_file":        file_actions.move_file,
    "delete_file":      file_actions.delete_file,
    "screenshot":       screen_actions.take_screenshot,
    "ocr":              screen_actions.ocr_screenshot,
    "get_clipboard":    clipboard_actions.get_clipboard,
    "set_clipboard":    clipboard_actions.set_clipboard,
    "send_email":       email_actions.send_email,
    "check_email":      email_actions.check_email,
    "add_task":         todo_actions.add_task,
    "list_tasks":       todo_actions.list_tasks,
    "mark_task_complete": todo_actions.mark_task_complete,
    "delete_task":      todo_actions.delete_task,
    "get_weather":      weather_actions.get_weather,
    "get_forecast":     weather_actions.get_forecast,
    "set_timer":        timer_actions.set_timer,
    "set_reminder":     timer_actions.set_reminder,
    "list_reminders":   timer_actions.list_reminders,
    "cancel_reminder":  timer_actions.cancel_reminder,
}


class ActionRouter:
    """
    Central dispatcher for all IRIS actions.
    Checks safety classification, requests approval if DANGEROUS, then executes.

    Interface contract (consumed by Aryan's modules):
        result = await action_router.execute(subtask)
        -> {"status": str, "result": str, "requires_approval": bool}
    """

    def __init__(self, ipc_bridge) -> None:
        self.ipc = ipc_bridge

    async def execute(self, subtask: dict) -> dict:
        """Route and execute a subtask dict with keys: action_type, params."""
        action_type = subtask.get("action_type", "")
        params = subtask.get("params", {})
        description = subtask.get("description", action_type)

        safety = classify(action_type)
        logger.info(f"Action: {action_type} [{safety.value}] — {description}")

        # Safety gate
        if safety == SafetyLevel.DANGEROUS:
            req_id = str(uuid.uuid4())
            approved = await self.ipc.request_approval(action_type, params, req_id)
            if not approved:
                logger.warning(f"Action denied by user: {action_type}")
                return {"status": "denied", "result": "User denied action", "requires_approval": True}

        if safety == SafetyLevel.WARN:
            logger.warning(f"WARN action executing: {action_type}")

        # Dispatch
        handler = ACTION_HANDLERS.get(action_type)
        if not handler:
            logger.error(f"No handler for action_type: {action_type}")
            return {"status": "error", "result": f"Unknown action: {action_type}", "requires_approval": False}

        try:
            result = await self._call_handler(handler, params)
            result["requires_approval"] = safety == SafetyLevel.DANGEROUS
            return result
        except Exception as e:
            logger.error(f"Action handler error ({action_type}): {e}")
            return {"status": "error", "result": str(e), "requires_approval": False}

    async def _call_handler(self, handler, params: dict) -> dict:
        """Call the action handler with the correct arguments from params."""
        # All handlers accept keyword args matching their function signature
        return await handler(**params)
