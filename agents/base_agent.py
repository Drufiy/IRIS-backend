"""Abstract base class for all IRIS agents."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """All agents (Planner, Executor, Coding) extend this."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.is_running = False

    @abstractmethod
    async def run(self, goal: str, context: list[dict]) -> Any:
        """Execute the agent's primary function."""
        ...

    async def cancel(self) -> None:
        """Cancel the agent gracefully."""
        self.is_running = False
