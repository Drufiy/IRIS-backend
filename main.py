"""IRIS single entrypoint. Boots all modules and starts the event loop."""

import asyncio
import argparse

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

    ipc = IPCBridge(port=config["ui"]["ipc_port"])
    state = StateManager(ipc)
    tts = TTSRouter(config["voice"])
    actions = ActionRouter(ipc)

    if not config["llm"].get("deepseek_api_key"):
        log.warning("No DeepSeek API key found — LLM calls will fail")

    llm = LLMRouter(config["llm"])
    asr = ASREngine(GroqWhisperBackend(config["audio"]["groq_api_key"]))
    loop = IRISEventLoop(state=state, tts=tts, asr=asr, llm=llm, actions=actions, ipc=ipc)
    await loop.run()


if __name__ == "__main__":
    asyncio.run(main())
