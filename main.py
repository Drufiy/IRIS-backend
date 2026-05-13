"""IRIS — single entrypoint. Boots all modules and starts the event loop."""

import asyncio
import httpx
from utils.config import load_config
from utils.logger import setup_logger
from ui.ipc_bridge import IPCBridge
from core.state_manager import StateManager
from core.event_loop import IRISEventLoop
from voice.tts_router import TTSRouter
from actions.action_router import ActionRouter


async def _check_ollama(host: str) -> bool:
    """Health check: verify Ollama is running before boot."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{host}/api/tags", timeout=5)
            return r.status_code == 200
    except Exception:
        return False


async def main() -> None:
    config = load_config("configs/settings.yaml")
    log = setup_logger(
        log_level=config.get("logging", {}).get("level", "DEBUG"),
        log_file=config.get("logging", {}).get("log_file", "logs/iris.log"),
    )
    log.info("IRIS booting...")

    # Ollama health check
    ollama_host = config.get("ollama", {}).get("host", "http://localhost:11434")
    if not await _check_ollama(ollama_host):
        log.warning(f"Ollama not reachable at {ollama_host} — local model will be unavailable")

    # ── Init modules ──────────────────────────────────────────────────────────

    ipc = IPCBridge(port=config["ui"]["ipc_port"])
    state = StateManager(ipc)
    tts = TTSRouter(config["voice"])
    actions = ActionRouter(ipc)

    # Aryan's modules — import with graceful fallback stubs for solo testing
    try:
        from llm.router import LLMRouter
        llm = LLMRouter(config["llm"])
    except Exception as e:
        log.warning(f"LLM router failed to init: {e} — using stub")
        llm = _StubLLM()

    try:
        from memory.memory_manager import MemoryManager
        memory = MemoryManager(config["memory"])
    except Exception as e:
        log.warning(f"Memory manager failed to init: {e} — using stub")
        memory = _StubMemory()

    try:
        from audio.asr import ASREngine
        asr = ASREngine()
    except Exception as e:
        log.warning(f"ASR failed to init: {e} — using stub")
        asr = _StubASR()

    try:
        from audio.wake_word import WakeWordDetector
        wake = WakeWordDetector()
    except Exception as e:
        log.warning(f"Wake word detector failed to init: {e} — using stub")
        wake = _StubWake()

    try:
        from audio.interrupt_handler import InterruptHandler
        interrupt = InterruptHandler()
    except Exception as e:
        log.warning(f"Interrupt handler failed to init: {e} — using stub")
        interrupt = None

    try:
        from browser.browser_agent import BrowserAgent
        browser = BrowserAgent()
    except Exception as e:
        log.warning(f"Browser agent failed to init: {e} — using stub")
        browser = _StubBrowser()

    try:
        from agents.coding_agent import CodingAgent
        coding = CodingAgent(llm, state_manager=state, action_router=actions)
    except Exception as e:
        log.warning(f"Coding agent failed to init: {e} — using stub")
        coding = _StubCoding()

    from agents.agent_manager import AgentManager
    agents = AgentManager(llm, memory, actions, browser, coding, tts)

    loop = IRISEventLoop(state, asr, wake, interrupt, tts, agents, memory, ipc)

    log.info("IRIS ready. Say 'Jarvis' or 'Iris' to begin.")
    await asyncio.gather(
        ipc.start(),
        loop.run(),
    )


# ── Stubs for Aryan's modules (allow Aradhya to test independently) ──────────

class _StubLLM:
    async def complete(self, messages, system="", task_type="chat"):
        return '[{"id":1,"action_type":"voice","description":"LLM not available yet","params":{"question":"LLM module not connected."}}]'
    async def stream(self, messages, system="", task_type="chat"):
        yield "LLM not available"

class _StubMemory:
    async def inject_into_prompt(self, base_messages):
        return base_messages
    async def store(self, role, content, tags=None):
        pass
    async def retrieve_context(self, query, top_k=5):
        return []

class _StubASR:
    async def transcribe(self, audio):
        return {"transcript": "", "language": "en", "confidence": 0.0}

class _StubWake:
    def on_wake(self, callback):
        pass
    def process_chunk(self, chunk):
        return False

class _StubBrowser:
    async def start(self, headless=False):
        pass
    async def navigate(self, url):
        return url
    async def extract_text(self, selector="body"):
        return ""
    async def close(self):
        pass

class _StubCoding:
    async def run(self, goal, repo_path):
        return {"status": "stub", "message": "Coding agent not connected yet"}


if __name__ == "__main__":
    asyncio.run(main())
