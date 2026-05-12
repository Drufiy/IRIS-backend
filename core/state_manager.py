"""IRIS state machine + UI sync via IPC bridge."""

from enum import Enum
from loguru import logger


class IRISState(Enum):
    IDLE        = "IDLE"
    INTERACTIVE = "INTERACTIVE"
    ACTING      = "ACTING"
    STOPPING    = "STOPPING"


class StateManager:
    """Owns the current IRIS state and broadcasts transitions to the Tauri UI."""

    def __init__(self, ipc_bridge) -> None:
        self.current = IRISState.IDLE
        self.ipc = ipc_bridge

    async def transition(self, new_state: IRISState) -> None:
        """Transition to new_state and broadcast to UI. No-op if already in that state."""
        if new_state == self.current:
            return
        logger.info(f"State: {self.current.value} → {new_state.value}")
        self.current = new_state
        await self.ipc.broadcast(new_state.value)
