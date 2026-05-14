"""IRIS single entrypoint. Boots all modules and starts the event loop."""

import asyncio

from actions.action_router import ActionRouter
from audio.asr import ASREngine
from audio.groq_whisper_backend import GroqWhisperBackend
from core.event_loop import IRISEventLoop
from core.state_manager import StateManager
from llm.router import LLMRouter
from ui.ipc_bridge import IPCBridge
from utils.config import load_config
from utils.logger import setup_logger
from voice.tts_router import TTSRouter


async def main() -> None:
    config = load_config("configs/settings.yaml")
    log = setup_logger(
        log_level=config.get("logging", {}).get("level", "DEBUG"),
        log_file=config.get("logging", {}).get("log_file", "logs/iris.log"),
    )
    log.info("IRIS booting...")

    ipc = IPCBridge(port=config["ui"]["ipc_port"])
    state = StateManager(ipc)
    tts = TTSRouter(config["voice"])
    actions = ActionRouter(ipc)

    if not config["llm"].get("deepseek_api_key"):
        raise RuntimeError("DeepSeek API key is not configured.")
    llm = LLMRouter(config["llm"])

    try:
        from memory.memory_manager import MemoryManager

        memory = MemoryManager(config["memory"])
    except Exception as exc:
        log.warning(f"Memory manager failed to init: {exc} - using stub")
        memory = _StubMemory()

    if not config["asr"].get("groq_api_key"):
        raise RuntimeError("Groq API key is not configured.")
    asr = ASREngine(
        backend=GroqWhisperBackend(
            api_key=config["asr"]["groq_api_key"],
            model=config["asr"].get("model", "whisper-large-v3-turbo"),
        )
    )
    log.info("ASR: Groq Whisper cloud loaded")

    try:
        from audio.wake_word import WakeWordDetector

        wake = WakeWordDetector()
    except Exception as exc:
        log.warning(f"Wake word detector failed to init: {exc} - using stub")
        wake = _StubWake()

    try:
        from audio.interrupt_handler import InterruptHandler

        interrupt = InterruptHandler()
    except Exception as exc:
        log.warning(f"Interrupt handler failed to init: {exc} - using stub")
        interrupt = None

    try:
        from browser.browser_agent import BrowserAgent

        browser = BrowserAgent()
    except Exception as exc:
        log.warning(f"Browser agent failed to init: {exc} - using stub")
        browser = _StubBrowser()

    try:
        from agents.coding_agent import CodingAgent

        coding = CodingAgent(llm, state_manager=state, action_router=actions)
    except Exception as exc:
        log.warning(f"Coding agent failed to init: {exc} - using stub")
        coding = _StubCoding()

    from agents.agent_manager import AgentManager

    agents = AgentManager(llm, memory, actions, browser, coding, tts)
    loop = IRISEventLoop(state, asr, wake, interrupt, tts, agents, memory, ipc)

    log.info("IRIS ready. Say 'Jarvis' or 'Iris' to begin.")
    await asyncio.gather(
        ipc.start(),
        loop.run(),
    )


class _StubMemory:
    async def inject_into_prompt(self, base_messages):
        return base_messages

    async def store(self, role, content, tags=None):
        pass

    async def retrieve_context(self, query, top_k=5):
        return []


class _StubWake:
    def on_wake(self, callback):
        pass

    def process_chunk(self, chunk):
        return False

    async def process_text(self, text):
        return None


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
