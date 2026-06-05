"""IRIS single entrypoint. Boots all modules and starts the event loop."""

import asyncio
import argparse

from actions.action_router import ActionRouter
from agents.agent_manager import AgentManager
from agents.coding_agent import CodingAgent
from audio.asr import ASREngine
from audio.groq_whisper_backend import GroqWhisperBackend
from audio.interrupt_handler import InterruptHandler
from audio.wake_word import WakeWordDetector
from browser.browser_agent import BrowserAgent
from core.event_loop import IRISEventLoop
from core.state_manager import StateManager
from llm.router import LLMRouter
from memory.memory_manager import MemoryManager
from ui.ipc_bridge import IPCBridge
from utils.config import load_config
from utils.logger import setup_logger
from voice.tts_router import TTSRouter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IRIS voice assistant")
    parser.add_argument("--headless", action="store_true", help="Run without UI")
    parser.add_argument("--config", default="configs/settings.yaml", help="Path to config file")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    log = setup_logger(
        log_level=config.get("logging", {}).get("level", "DEBUG"),
        log_file=config.get("logging", {}).get("log_file", "logs/iris.log"),
    )
    log.info("IRIS booting...")
    if args.headless:
        log.info("Running in headless mode — UI disabled")

    # ── Core infrastructure ─────────────────────────────────────────────────
    ipc = IPCBridge(port=config["ui"]["ipc_port"])
    state = StateManager(ipc)
    tts = TTSRouter(config["voice"])
    actions = ActionRouter(ipc)

    provider = config["llm"].get("provider", "deepseek")
    if provider == "shared":
        shared_url = config["llm"].get("shared_backend_url", "")
        log.info(f"Using shared backend mode: {shared_url}")
    elif provider == "agentrouter":
        if not config["llm"].get("api_key"):
            log.warning("AgentRouter mode selected but no AGENT_ROUTER_TOKEN found")
    elif provider == "deepseek":
        if not config["llm"].get("deepseek_api_key"):
            log.warning("DeepSeek mode selected but no DEEPSEEK_API_KEY found — LLM calls will fail")
    else:
        log.warning(f"Unknown LLM provider '{provider}'")

    llm = LLMRouter(config["llm"])
    asr = ASREngine(GroqWhisperBackend(
        api_key=config["asr"]["groq_api_key"],
        base_url=config["asr"].get("groq_base_url"),
    ))

    # ── Memory layer ────────────────────────────────────────────────────────
    memory = MemoryManager(config.get("memory", {}))

    # ── Agent pipeline (Planner → Executor) ─────────────────────────────────
    browser = BrowserAgent()
    coding_agent = CodingAgent(llm, state_manager=state, action_router=actions)
    agent_manager = AgentManager(
        llm=llm,
        memory=memory,
        action_router=actions,
        browser_agent=browser,
        coding_agent=coding_agent,
        tts=tts,
    )

    # ── Audio pipeline ──────────────────────────────────────────────────────
    wake_words = config.get("audio", {}).get("wake_words", ["jarvis", "iris"])
    wake = WakeWordDetector(wake_words=wake_words)
    interrupt = InterruptHandler()

    # ── Start IPC bridge and event loop ─────────────────────────────────────
    loop = IRISEventLoop(
        state=state,
        asr=asr,
        wake=wake,
        interrupt=interrupt,
        tts=tts,
        agent_manager=agent_manager,
        memory=memory,
        ipc=ipc,
    )

    await asyncio.gather(
        ipc.start(),
        loop.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
