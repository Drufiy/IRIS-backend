"""Main async event brain for IRIS."""

import asyncio
from time import perf_counter

from loguru import logger

from core.state_manager import IRISState

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised only in dependency-light environments
    np = None

INTERRUPT_PHRASES = ["stop", "cancel", "enough", "shut up", "pause"]
STOP_STATES = {"IDLE", "STOPPING", "ERROR"}


class IRISEventLoop:
    """
    Orchestrates the mic -> wake word -> ASR -> LLM -> TTS -> UI pipeline.

    Dependencies injected at construction so each can be tested independently.
    Aryan's modules (asr, wake, memory) are consumed via their interface contract.
    """

    def __init__(
        self,
        state,
        asr,
        wake,
        interrupt,
        tts,
        agent_manager,
        memory,
        ipc,
    ) -> None:
        self.state = state
        self.asr = asr
        self.wake = wake
        self.interrupt = interrupt
        self.tts = tts
        self.agents = agent_manager
        self.memory = memory
        self.ipc = ipc
        self._task_queue = asyncio.Queue()
        self._current_task = None

    async def run(self) -> None:
        """Boot the event loop. Runs until cancelled."""
        self.wake.on_wake(self._on_wake)
        await self.state.transition(IRISState.IDLE)
        logger.info("IRIS event loop running")
        await asyncio.gather(
            self._mic_loop(),
            self._task_worker(),
        )

    async def _mic_loop(self) -> None:
        """
        Continuously pull audio and run ASR-based wake word / command detection.

        Pipeline:
          IDLE -> buffer 3 s of audio, run ASR, check for 'iris'/'jarvis'
          INTERACTIVE -> buffer up to 4 s (or until 0.8 s of silence), then transcribe
        """
        from audio.listener import MicListener

        if np is None:
            raise RuntimeError("numpy is required for microphone buffering.")

        listener = MicListener()
        await asyncio.to_thread(listener.start)
        logger.info("Mic listener started")

        IDLE_CHUNKS = 30
        MAX_CMD_CHUNKS = 40
        SILENCE_ENERGY_THRESH = 5e-4
        SILENCE_CHUNKS_NEEDED = 8

        buffer = []
        silence_run = 0

        try:
            while True:
                chunk = await asyncio.to_thread(listener.get_chunk)
                if chunk is None:
                    await asyncio.sleep(0.02)
                    continue

                chunk_np = np.asarray(chunk, dtype=np.float32)
                buffer.append(chunk_np)

                if self.state.current == IRISState.IDLE:
                    if len(buffer) >= IDLE_CHUNKS:
                        audio = np.concatenate(buffer)
                        buffer = []
                        rms = float(np.sqrt(np.mean(audio ** 2)))
                        if rms < 1e-3:
                            continue

                        try:
                            result = await self.asr.transcribe(audio)
                        except Exception as exc:
                            logger.error(f"IDLE ASR failed: {exc}")
                            buffer = []
                            continue
                        text = result.get("transcript", "").strip()
                        if text:
                            logger.info(f"[IDLE ASR] '{text}'")
                            await self.wake.process_text(text)

                elif self.state.current == IRISState.INTERACTIVE:
                    rms = float(np.sqrt(np.mean(chunk_np ** 2)))
                    if rms < SILENCE_ENERGY_THRESH:
                        silence_run += 1
                    else:
                        silence_run = 0

                    utterance_done = (
                        silence_run >= SILENCE_CHUNKS_NEEDED
                        or len(buffer) >= MAX_CMD_CHUNKS
                    )
                    if utterance_done and len(buffer) > SILENCE_CHUNKS_NEEDED:
                        audio = np.concatenate(buffer)
                        buffer = []
                        silence_run = 0
                        try:
                            result = await self.asr.transcribe(audio)
                        except Exception as exc:
                            logger.error(f"INTERACTIVE ASR failed: {exc}")
                            continue
                        text = result.get("transcript", "").strip()
                        if text:
                            logger.info(f"[INTERACTIVE ASR] '{text}'")
                            await self._handle_transcript(text)
                else:
                    buffer = []
                    silence_run = 0

        finally:
            await asyncio.to_thread(listener.stop)

    def _on_wake(self, word: str) -> None:
        """Callback fired by WakeWordDetector on detection."""
        logger.info(f"Wake word detected: {word}")
        asyncio.create_task(self.state.transition(IRISState.INTERACTIVE))

    async def _handle_transcript(self, text: str) -> None:
        """Route transcript: interrupts take priority, rest go to task queue."""
        normalized = text.strip()
        if not normalized or not any(ch.isalnum() for ch in normalized):
            logger.info(f"Ignoring empty/punctuation-only transcript: '{text}'")
            return
        if any(phrase in normalized.lower() for phrase in INTERRUPT_PHRASES):
            logger.info(f"Interrupt detected: '{text}'")
            await self._stop()
            return
        logger.info(f"Transcript queued: '{normalized}'")
        await self._task_queue.put(normalized)

    async def _task_worker(self) -> None:
        """Pull goals from the queue, run agents, speak response."""
        while True:
            goal = await self._task_queue.get()
            logger.info(f"Processing goal: '{goal}'")
            await self.state.transition(IRISState.ACTING)
            started_at = perf_counter()
            response = ""
            status = "success"
            error_message = ""
            action_summary = "agent_run:success"
            bias_summary = ""
            timing_breakdown: dict[str, float] = {}

            try:
                messages = await self.memory.inject_into_prompt(
                    [{"role": "user", "content": goal}]
                )
                self._current_task = asyncio.current_task()
                agent_result = await self.agents.run(goal, messages)
                if isinstance(agent_result, dict):
                    response = agent_result.get("response", "")
                    action_summary = agent_result.get("action_summary", action_summary)
                    metadata = agent_result.get("metadata", {})
                    planner_meta = metadata.get("planner", {})
                    timing_breakdown.update(metadata.get("performance", {}))
                    if planner_meta.get("bias_applied"):
                        bias_summary = (
                            f" planner_bias:{planner_meta.get('preferred_chain', '')}"
                            f" strength={planner_meta.get('strength', '')}"
                            f" domain={planner_meta.get('domain', '')}"
                        )
                else:
                    response = str(agent_result)
                await self.memory.store("user", goal)
                await self.memory.store("iris", response)
                tts_started_at = perf_counter()
                await self.tts.speak(response)
                timing_breakdown["tts_seconds"] = perf_counter() - tts_started_at
            except asyncio.CancelledError:
                status = "cancelled"
                error_message = "Task cancelled mid-execution"
                action_summary = "agent_run:cancelled"
                logger.info("Task cancelled mid-execution")
            except Exception as exc:
                status = "error"
                error_message = str(exc)
                action_summary = "agent_run:error"
                logger.error(f"Task worker error: {exc}")
                tts_started_at = perf_counter()
                await self.tts.speak("Sorry, something went wrong.")
                timing_breakdown["tts_seconds"] = perf_counter() - tts_started_at
            finally:
                self._current_task = None
                total_seconds = perf_counter() - started_at
                timing_breakdown["total_seconds"] = total_seconds
                if timing_breakdown:
                    logger.info(
                        "Task timings: "
                        + ", ".join(
                            f"{key}={value:.3f}s" for key, value in sorted(timing_breakdown.items())
                        )
                    )
                if hasattr(self.memory, "record_interaction"):
                    try:
                        await self.memory.record_interaction(
                            user_input=goal,
                            response=response,
                            status=status,
                            latency_seconds=total_seconds,
                            action_summary=f"{action_summary}{bias_summary}",
                            error_message=error_message,
                            timing_breakdown=timing_breakdown,
                        )
                    except Exception as exc:  # pragma: no cover - logging only
                        logger.warning(f"Failed to record interaction: {exc}")
                await self.state.transition(IRISState.IDLE)

    async def _stop(self) -> None:
        """Stop TTS, cancel running task, transition to STOPPING."""
        self.tts.stop()
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        target_state = IRISState.STOPPING if getattr(self.state, "current", None) not in STOP_STATES else IRISState.IDLE
        await self.state.transition(target_state)
        logger.info("IRIS stopped")
