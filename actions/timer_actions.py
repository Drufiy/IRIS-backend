"""Timers, alarms, and reminders — set, list, cancel."""

import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger


REMINDERS_FILE = Path.home() / ".iris" / "reminders.json"
_active_timers = {}  # In-memory tracking of active timers


async def set_timer(duration_seconds: int, label: str = "Timer") -> dict:
    """
    Set a countdown timer.

    Args:
        duration_seconds: How long the timer runs (in seconds)
        label: Label for the timer (e.g., "Cooking", "Break")

    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        if duration_seconds < 1 or duration_seconds > 3600:
            return {
                "status": "error",
                "result": "Timer must be between 1 second and 1 hour"
            }

        timer_id = f"timer_{datetime.now().timestamp()}"
        _active_timers[timer_id] = {
            "label": label,
            "duration": duration_seconds,
            "start": datetime.now().isoformat()
        }

        logger.info(f"Timer started: {label} for {duration_seconds}s")

        # Start background countdown
        asyncio.create_task(_timer_countdown(timer_id, duration_seconds, label))

        return {
            "status": "ok",
            "result": f"Timer set: {label} for {duration_seconds} seconds"
        }

    except Exception as e:
        logger.error(f"set_timer error: {e}")
        return {"status": "error", "result": str(e)}


async def set_reminder(text: str, minutes: int) -> dict:
    """
    Set a reminder for a future time.

    Args:
        text: What to remind about (e.g., "Check email")
        minutes: How many minutes from now

    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        if minutes < 1 or minutes > 1440:  # 1 min to 1 day
            return {
                "status": "error",
                "result": "Reminder must be between 1 minute and 24 hours"
            }

        reminder_time = datetime.now() + timedelta(minutes=minutes)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _add_reminder_sync,
            text,
            reminder_time.isoformat()
        )

        logger.info(f"Reminder set: {text} in {minutes} minutes")

        return {
            "status": "ok",
            "result": f"Reminder set: {text} in {minutes} minutes"
        }

    except Exception as e:
        logger.error(f"set_reminder error: {e}")
        return {"status": "error", "result": str(e)}


async def list_reminders() -> dict:
    """
    List all active reminders.

    Returns:
        {"status": "ok"/"error", "result": formatted reminders}
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _list_reminders_sync)

        logger.debug("Listed reminders")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"list_reminders error: {e}")
        return {"status": "error", "result": str(e)}


async def cancel_reminder(reminder_id: int) -> dict:
    """
    Cancel a reminder by ID.

    Args:
        reminder_id: ID from list output

    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        if not isinstance(reminder_id, int) or reminder_id < 1:
            return {"status": "error", "result": "Reminder ID must be a positive number"}

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _cancel_reminder_sync, reminder_id)

        logger.info(f"Reminder {reminder_id} cancelled")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"cancel_reminder error: {e}")
        return {"status": "error", "result": str(e)}


async def _timer_countdown(timer_id: str, duration: int, label: str) -> None:
    """Async timer countdown. When done, trigger alert."""
    try:
        await asyncio.sleep(duration)

        if timer_id in _active_timers:
            del _active_timers[timer_id]

        # TODO: Integrate with TTS to say alert
        logger.warning(f"Timer finished: {label}")
        print(f"\n🔔 TIMER ALERT: {label} is done!\n")

    except asyncio.CancelledError:
        logger.debug(f"Timer cancelled: {label}")
    except Exception as e:
        logger.error(f"Timer countdown error: {e}")


def _load_reminders() -> list:
    """Load reminders from JSON file."""
    if not REMINDERS_FILE.exists():
        return []
    try:
        with open(REMINDERS_FILE, "r") as f:
            reminders = json.load(f)
            # Filter out expired reminders
            now = datetime.now()
            return [r for r in reminders if datetime.fromisoformat(r["time"]) > now]
    except (json.JSONDecodeError, IOError, ValueError):
        logger.warning(f"Could not load reminders from {REMINDERS_FILE}")
        return []


def _save_reminders(reminders: list) -> None:
    """Save reminders to JSON file."""
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REMINDERS_FILE, "w") as f:
        json.dump(reminders, f, indent=2)


def _add_reminder_sync(text: str, time_iso: str) -> None:
    """Blocking reminder add. Run in executor."""
    reminders = _load_reminders()
    new_reminder = {
        "id": len(reminders) + 1,
        "text": text,
        "time": time_iso,
        "created": datetime.now().isoformat()
    }
    reminders.append(new_reminder)
    _save_reminders(reminders)


def _list_reminders_sync() -> str:
    """Blocking reminder list. Run in executor."""
    reminders = _load_reminders()

    if not reminders:
        return "No active reminders."

    output = ["UPCOMING REMINDERS:"]
    now = datetime.now()

    for r in sorted(reminders, key=lambda x: x["time"]):
        reminder_time = datetime.fromisoformat(r["time"])
        delta = reminder_time - now
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)

        time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        output.append(f"  {r['id']}. {r['text']} (in {time_str})")

    return "\n".join(output)


def _cancel_reminder_sync(reminder_id: int) -> str:
    """Blocking reminder cancel. Run in executor."""
    reminders = _load_reminders()

    for i, r in enumerate(reminders):
        if r["id"] == reminder_id:
            text = r["text"]
            reminders.pop(i)
            _save_reminders(reminders)
            return f"Cancelled reminder: {text}"

    return f"Reminder {reminder_id} not found"
