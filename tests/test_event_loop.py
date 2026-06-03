"""Focused tests for event-loop level interaction logging."""

from __future__ import annotations

import asyncio
import sys
import types
import unittest

if "loguru" not in sys.modules:
    sys.modules["loguru"] = types.SimpleNamespace(
        logger=types.SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
    )

from core.event_loop import IRISEventLoop


class _FakeState:
    def __init__(self) -> None:
        self.current = None
        self.transitions: list[str] = []

    async def transition(self, state) -> None:
        self.current = state
        self.transitions.append(getattr(state, "name", str(state)))


class _FakeWake:
    def on_wake(self, callback) -> None:
        self.callback = callback


class _FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.stop_calls = 0

    async def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        self.stop_calls += 1
        return None


class _FakeAgents:
    async def run(self, goal: str, messages: list[dict]) -> str:
        return {
            "response": f"Handled: {goal}",
            "action_summary": "browser:ok -> get_weather:ok",
            "trace": [
                {"id": 1, "action_type": "browser", "description": "browse", "result": "ok"},
                {"id": 2, "action_type": "get_weather", "description": "weather", "result": "ok"},
            ],
        }


class _FakeFailingAgents:
    async def run(self, goal: str, messages: list[dict]) -> str:
        raise RuntimeError("planner failed")


class _FakeMemory:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.stored: list[tuple[str, str]] = []

    async def inject_into_prompt(self, messages: list[dict]) -> list[dict]:
        return list(messages)

    async def store(self, role: str, content: str) -> None:
        self.stored.append((role, content))

    async def record_interaction(self, **kwargs) -> None:
        self.records.append(kwargs)


class EventLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_on_wake_transitions_to_interactive(self) -> None:
        state = _FakeState()
        loop = IRISEventLoop(
            state=state,
            asr=None,
            wake=_FakeWake(),
            interrupt=None,
            tts=_FakeTTS(),
            agent_manager=_FakeAgents(),
            memory=_FakeMemory(),
            ipc=None,
        )

        loop._on_wake("iris")
        await asyncio.sleep(0.01)

        self.assertEqual(state.current.name, "INTERACTIVE")
        self.assertIn("INTERACTIVE", state.transitions)

    async def test_handle_transcript_queues_non_interrupt_requests(self) -> None:
        state = _FakeState()
        loop = IRISEventLoop(
            state=state,
            asr=None,
            wake=_FakeWake(),
            interrupt=None,
            tts=_FakeTTS(),
            agent_manager=_FakeAgents(),
            memory=_FakeMemory(),
            ipc=None,
        )

        await loop._handle_transcript("check weather")

        self.assertEqual(loop._task_queue.qsize(), 1)
        self.assertEqual(await loop._task_queue.get(), "check weather")

    async def test_handle_transcript_interrupt_stops_active_task(self) -> None:
        state = _FakeState()
        tts = _FakeTTS()
        loop = IRISEventLoop(
            state=state,
            asr=None,
            wake=_FakeWake(),
            interrupt=None,
            tts=tts,
            agent_manager=_FakeAgents(),
            memory=_FakeMemory(),
            ipc=None,
        )

        sleeper = asyncio.create_task(asyncio.sleep(5))
        loop._current_task = sleeper

        await loop._handle_transcript("stop right there")
        await asyncio.sleep(0)

        self.assertTrue(sleeper.cancelled())
        self.assertEqual(tts.stop_calls, 1)
        self.assertEqual(state.current.name, "STOPPING")

    async def test_task_worker_records_interaction_after_success(self) -> None:
        state = _FakeState()
        tts = _FakeTTS()
        memory = _FakeMemory()
        loop = IRISEventLoop(
            state=state,
            asr=None,
            wake=_FakeWake(),
            interrupt=None,
            tts=tts,
            agent_manager=_FakeAgents(),
            memory=memory,
            ipc=None,
        )

        worker = asyncio.create_task(loop._task_worker())
        await loop._task_queue.put("check weather")

        for _ in range(20):
            if memory.records:
                break
            await asyncio.sleep(0.01)

        worker.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await worker

        self.assertEqual(len(memory.records), 1)
        self.assertEqual(memory.records[0]["user_input"], "check weather")
        self.assertEqual(memory.records[0]["status"], "success")
        self.assertEqual(memory.records[0]["response"], "Handled: check weather")
        self.assertEqual(memory.records[0]["action_summary"], "browser:ok -> get_weather:ok")
        self.assertIn("total_seconds", memory.records[0]["timing_breakdown"])
        self.assertIn("tts_seconds", memory.records[0]["timing_breakdown"])
        self.assertEqual(tts.spoken, ["Handled: check weather"])
        self.assertEqual(state.current.name, "IDLE")

    async def test_task_worker_records_planner_bias_and_resets_to_idle(self) -> None:
        state = _FakeState()
        tts = _FakeTTS()
        memory = _FakeMemory()

        class _BiasedAgents:
            async def run(self, goal: str, messages: list[dict]) -> dict:
                return {
                    "response": f"Handled: {goal}",
                    "action_summary": "browser:ok -> get_weather:ok",
                    "trace": [],
                    "metadata": {
                        "planner": {
                            "bias_applied": True,
                            "preferred_chain": "browser -> get_weather",
                            "strength": "3",
                            "domain": "browser",
                        },
                        "performance": {
                            "planning_seconds": 0.1,
                            "execution_seconds": 0.2,
                            "agent_total_seconds": 0.3,
                        },
                    },
                }

        loop = IRISEventLoop(
            state=state,
            asr=None,
            wake=_FakeWake(),
            interrupt=None,
            tts=tts,
            agent_manager=_BiasedAgents(),
            memory=memory,
            ipc=None,
        )

        worker = asyncio.create_task(loop._task_worker())
        await loop._task_queue.put("check weather")

        for _ in range(20):
            if memory.records:
                break
            await asyncio.sleep(0.01)

        worker.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await worker

        self.assertIn("planner_bias:browser -> get_weather", memory.records[0]["action_summary"])
        self.assertIn("strength=3", memory.records[0]["action_summary"])
        self.assertIn("domain=browser", memory.records[0]["action_summary"])
        self.assertEqual(memory.records[0]["timing_breakdown"]["planning_seconds"], 0.1)
        self.assertEqual(memory.records[0]["timing_breakdown"]["execution_seconds"], 0.2)
        self.assertIn("tts_seconds", memory.records[0]["timing_breakdown"])
        self.assertEqual(state.current.name, "IDLE")

    async def test_task_worker_records_error_and_apology(self) -> None:
        state = _FakeState()
        tts = _FakeTTS()
        memory = _FakeMemory()
        loop = IRISEventLoop(
            state=state,
            asr=None,
            wake=_FakeWake(),
            interrupt=None,
            tts=tts,
            agent_manager=_FakeFailingAgents(),
            memory=memory,
            ipc=None,
        )

        worker = asyncio.create_task(loop._task_worker())
        await loop._task_queue.put("do the thing")

        for _ in range(20):
            if memory.records:
                break
            await asyncio.sleep(0.01)

        worker.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await worker

        self.assertEqual(memory.records[0]["status"], "error")
        self.assertEqual(memory.records[0]["action_summary"], "agent_run:error")
        self.assertIn("planner failed", memory.records[0]["error_message"])
        self.assertIn("tts_seconds", memory.records[0]["timing_breakdown"])
        self.assertIn("total_seconds", memory.records[0]["timing_breakdown"])
        self.assertEqual(tts.spoken, ["Sorry, something went wrong."])
        self.assertEqual(state.current.name, "IDLE")
