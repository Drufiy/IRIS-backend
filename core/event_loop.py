"""Main async event brain for IRIS."""

import asyncio
from loguru import logger
from core.state_manager import IRISState

INTERRUPT_PHRASES = ["stop", "cancel", "enough", "shut up", "pause"]


class IRISEventLoop:
    """
    Orchestrates the mic → wake word → ASR → LLM → TTS → UI pipeline.

    Dependencies injected at construction so each can be tested independently.
    Aryan's modules (asr, wake, memory) are consumed via their interface contract.
    """

    def __init__(
        self,
        state,        # StateManager
        asr,          # ASREngine  (Aryan)
        wake,         # WakeWordDetector  (Aryan)
        interrupt,    # InterruptHandler  (Aryan)
        tts,          # TTSRouter  (Aradhya)
        agent_manager,# AgentManager  (Aradhya)
        memory,       # MemoryManager  (Aryan)
        ipc,          # IPCBridge  (Aradhya)
    ) -> None:
        self.state         = state
        self.asr           = asr
        self.wake          = wake
        self.interrupt     = interrupt
        self.tts           = tts
        self.agents        = agent_manager
        self.memory        = memory
        self.ipc           = ipc
        self._task_queue   = asyncio.Queue()
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

    # ── Mic pipeline ──────────────────────────────────────────────────────────

    async def _mic_loop(self) -> None:
        """Continuously pull chunks from the mic listener and process them."""
        from audio.listener import MicListener
        listener = MicListener()
        listener.start()
        logger.info("Mic listener started")

        try:
            while True:
                chunk = listener.get_chunk()
                if chunk is not None:
                    self.wake.process_chunk(chunk)

                    if self.state.current == IRISState.INTERACTIVE:
                        result = await self.asr.transcribe(chunk)
                        if result.get("transcript"):
                            await self._handle_transcript(result["transcript"])

                await asyncio.sleep(0.01)
        finally:
            listener.stop()

    def _on_wake(self, word: str) -> None:
        """Callback fired by WakeWordDetector on detection."""
        logger.info(f"Wake word detected: {word}")
        asyncio.create_task(self.state.transition(IRISState.INTERACTIVE))

    async def _handle_transcript(self, text: str) -> None:
        """Route transcript: interrupts take priority, rest go to task queue."""
        if any(p in text.lower() for p in INTERRUPT_PHRASES):
            logger.info(f"Interrupt detected: '{text}'")
            await self._stop()
            return
        logger.info(f"Transcript queued: '{text}'")
        await self._task_queue.put(text)

    # ── Task worker ───────────────────────────────────────────────────────────

    async def _task_worker(self) -> None:
        """Pull goals from the queue, run agents, speak response."""
        while True:
            goal = await self._task_queue.get()
            logger.info(f"Processing goal: '{goal}'")
            await self.state.transition(IRISState.ACTING)

            try:
                messages = await self.memory.inject_into_prompt(
                    [{"role": "user", "content": goal}]
                )
                self._current_task = asyncio.current_task()
                response = await self.agents.run(goal, messages)
                await self.memory.store("user", goal)
                await self.memory.store("iris", response)
                await self.tts.speak(response)
            except asyncio.CancelledError:
                logger.info("Task cancelled mid-execution")
            except Exception as e:
                logger.error(f"Task worker error: {e}")
                await self.tts.speak("Sorry, something went wrong.")
            finally:
                self._current_task = None
                await self.state.transition(IRISState.INTERACTIVE)

    # ── Interrupt ─────────────────────────────────────────────────────────────

    async def _stop(self) -> None:
        """Stop TTS, cancel running task, transition to STOPPING."""
        self.tts.stop()
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        await self.state.transition(IRISState.STOPPING)
        logger.info("IRIS stopped")
