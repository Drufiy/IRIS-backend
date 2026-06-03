from datetime import datetime
from pathlib import Path


class EventHistoryLogger:
    """Appends accepted command history to a local file."""

    def __init__(self, log_path: str = "logs/event_history.log"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: str, action: str) -> None:
        """Writes a single accepted command entry to the history log."""
        timestamp = datetime.now().isoformat(timespec="seconds")
        entry = f"{timestamp} {event} {action}\n"

        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(entry)
