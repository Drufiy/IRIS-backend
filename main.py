"""IRIS single entrypoint. Boots all modules and starts the event loop."""

import asyncio
import argparse
from time import perf_counter

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
from ui.runtime_snapshot import build_shell_snapshot
from utils.config import load_config
from utils.logger import setup_logger
from voice.tts_router import TTSRouter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IRIS voice assistant")
    parser.add_argument("--headless", action="store_true", help="Run without UI")
    parser.add_argument("--config", default="configs/settings.yaml", help="Path to config file")
    return parser.parse_args()


async def main() -> None:
    started_at = perf_counter()
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
    ipc = IPCBridge(
        port=config["ui"]["ipc_port"],
        http_port=config.get("ui", {}).get("http_port", 7790),
    )
    state = StateManager(ipc)
    tts = TTSRouter(config["voice"])
    actions = ActionRouter(ipc)

    mode = config.get("mode", "local")
    if mode == "remote":
        remote_cfg = config.get("remote", {})
        backend_url = remote_cfg.get("backend_url", "http://localhost:8000")
        log.info(f"Remote mode: routing all services through shared backend at {backend_url}")
    else:
        llm_base_url = config["llm"].get("base_url", "https://api.deepseek.com")
        has_api_key = bool(config["llm"].get("api_key"))
        log.info(f"Local mode: LLM at {llm_base_url} (key configured: {has_api_key})")
        if not has_api_key:
            log.warning("No API key configured — LLM calls will fail")

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

    ipc.set_snapshot_provider(
        lambda: build_shell_snapshot(
            config=config,
            state_manager=state,
            llm_router=llm,
            ipc_bridge=ipc,
            started_at=started_at,
            headless=args.headless,
        )
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
