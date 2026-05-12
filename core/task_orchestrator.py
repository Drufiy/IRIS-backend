"""Async priority task queue for IRIS."""

import asyncio
from dataclasses import dataclass, field
from typing import Any
from loguru import logger


@dataclass(order=True)
class Task:
    """A queued task with priority. Lower number = higher priority."""
    priority: int
    goal: str = field(compare=False)
    context: list[dict] = field(default_factory=list, compare=False)
    metadata: dict = field(default_factory=dict, compare=False)


class TaskOrchestrator:
    """Priority queue that feeds goals into the event loop worker."""

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_count: int = 0

    async def enqueue(self, goal: str, priority: int = 5, context: list[dict] = None, metadata: dict = None) -> None:
        """Add a task to the queue. Priority 1 = highest, 10 = lowest."""
        task = Task(
            priority=priority,
            goal=goal,
            context=context or [],
            metadata=metadata or {},
        )
        await self._queue.put(task)
        logger.debug(f"Enqueued task (priority={priority}): {goal[:60]}")

    async def get(self) -> Task:
        """Block until a task is available, then return it."""
        task = await self._queue.get()
        self._active_count += 1
        return task

    def done(self) -> None:
        """Mark the current task complete."""
        self._queue.task_done()
        self._active_count = max(0, self._active_count - 1)

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def active(self) -> int:
        return self._active_count
