import logging
from core.detector import SoundEvent, detect_sound_event
from core.history import EventHistoryLogger
from core.state import SystemState
from modules.camera import CameraModule
from modules.screenshot import ScreenshotModule


class EventRouter:
    """Coordinates events (like clap detection) to update system state and modules."""

    def __init__(
        self,
        state: SystemState,
        camera_module: CameraModule,
        screenshot_module: ScreenshotModule,
        single_clap_guard_seconds: float = 0.15,
        double_clap_window_seconds: float = 0.45,
    ):
        self.state = state
        self.camera_module = camera_module
        self.screenshot_module = screenshot_module
        self.single_clap_guard_seconds = single_clap_guard_seconds
        self.double_clap_window_seconds = double_clap_window_seconds
        self.last_detected_clap_time = None
        self.pending_clap_time = None
        self.history_logger = EventHistoryLogger()
        self.event_handlers = {
            SoundEvent.CLAP: self._handle_clap_event,
            SoundEvent.DOUBLE_CLAP: self._handle_double_clap_event,
        }
        self.event_actions = {
            SoundEvent.CLAP: "camera_toggle",
            SoundEvent.DOUBLE_CLAP: "screenshot",
        }

    def _handle_clap_event(self) -> None:
        """Handles the current clap event behavior."""
        should_enable_camera = self.state.toggle_camera_state()

        if should_enable_camera:
            logging.info("Clap received and camera is OFF. Attempting to open camera.")
            if not self.camera_module.open_camera():
                logging.error("Camera failed to open. Reverting toggle state.")
                self.state.set_camera_state(False)
        else:
            logging.info("Clap received and camera is ON. Closing camera.")
            self.camera_module.close_camera()
            self.state.set_camera_state(False)

    def _handle_double_clap_event(self) -> None:
        """Handles the current double clap event behavior."""
        logging.info("Double clap received. Capturing desktop screenshot.")
        self.screenshot_module.capture_screenshot()

    def _dispatch_event(self, event: SoundEvent) -> None:
        """Routes a resolved sound event to its registered handler."""
        if self.state.is_command_on_cooldown():
            logging.info("Sound command ignored during cooldown window.")
            return

        handler = self.event_handlers.get(event)
        if handler is None:
            logging.info("No handler registered for sound event: %s", event)
            return

        handler()
        action = self.event_actions.get(event, "unknown_action")
        self.history_logger.log_event(event.value, action)
        self.state.mark_command_executed()

    def _resolve_pending_clap(self) -> None:
        """Emits a single clap if the double-clap window has expired."""
        if self.pending_clap_time is None:
            return

        if self.state.current_time() - self.pending_clap_time < self.double_clap_window_seconds:
            return

        self.pending_clap_time = None
        self._dispatch_event(SoundEvent.CLAP)

    def process_sound_event(self, data: bytes) -> None:
        """Detects a sound event and routes it to the matching handler."""
        event = detect_sound_event(data)
        if event is None:
            return

        if self.state.is_command_on_cooldown():
            logging.info("Detected sound ignored during command cooldown.")
            return

        if event is not SoundEvent.CLAP:
            self._dispatch_event(event)
            return

        current_time = self.state.current_time()

        if self.last_detected_clap_time is not None:
            elapsed_since_last_clap = current_time - self.last_detected_clap_time
            if elapsed_since_last_clap < self.single_clap_guard_seconds:
                logging.info("Clap ignored inside raw guard window.")
                return

        self.last_detected_clap_time = current_time

        if self.pending_clap_time is None:
            self.pending_clap_time = current_time
            logging.info("Clap queued while waiting for double-clap window.")
            return

        elapsed_since_pending = current_time - self.pending_clap_time
        if elapsed_since_pending <= self.double_clap_window_seconds:
            self.pending_clap_time = None
            self._dispatch_event(SoundEvent.DOUBLE_CLAP)
            return

        self.pending_clap_time = None
        self._dispatch_event(SoundEvent.CLAP)
        self.pending_clap_time = current_time
        logging.info("Previous pending clap expired; queued new clap window.")

    def process_loop_cycle(self, audio_data: bytes) -> None:
        """The main event processing routine for one cycle."""
        # 1. Handle Audio Input / Sound Events (Event Trigger)
        self.process_sound_event(audio_data)

        # 2. Resolve a single clap once the double-clap window has passed.
        self._resolve_pending_clap()

        # 3. Read and Display Camera Frame (Module Operation)
        if self.camera_module.is_active:
            self.camera_module.read_frame()
