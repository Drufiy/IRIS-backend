import logging
import time


class SystemState:
    """Manages camera state and shared timing helpers."""

    def __init__(self, debounce_seconds: float, command_cooldown_seconds: float = 0.5):
        self.camera_active = False
        self.clap_debounce_seconds = debounce_seconds
        self.command_cooldown_seconds = command_cooldown_seconds
        self.last_command_time = None

    def toggle_camera_state(self) -> bool:
        """Toggles the desired camera state and returns the new state."""
        self.camera_active = not self.camera_active
        logging.info("Clap accepted. Camera target state is now %s.", self.camera_active)
        return self.camera_active

    def current_time(self) -> float:
        """Returns a monotonic timestamp for clap sequencing logic."""
        return time.monotonic()

    def is_command_on_cooldown(self) -> bool:
        """Returns True when accepted commands are still inside the cooldown window."""
        if self.last_command_time is None:
            return False

        elapsed = self.current_time() - self.last_command_time
        return elapsed < self.command_cooldown_seconds

    def mark_command_executed(self) -> None:
        """Marks the current time as the last accepted command timestamp."""
        self.last_command_time = self.current_time()

    def set_camera_state(self, active: bool) -> None:
        """Sets the camera's operational state."""
        self.camera_active = active

    def reset_state(self) -> None:
        """Resets all tracked state variables."""
        self.camera_active = False
        self.last_command_time = None
