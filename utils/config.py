"""Load settings.yaml and keys.env into a unified config dict."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def load_config(settings_path: str = "configs/settings.yaml") -> dict:
    """Load YAML config and overlay API keys from keys.env."""
    settings_file = Path(settings_path)
    if not settings_file.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    with settings_file.open("r") as f:
        config: dict = yaml.safe_load(f)

    keys_file = Path("configs/keys.env")
    if keys_file.exists():
        load_dotenv(dotenv_path=keys_file)

    # Inject API keys from environment into config
    config.setdefault("llm", {})
    config.setdefault("voice", {})
    config.setdefault("asr", {})

    provider = config["llm"].get("provider", "deepseek").lower()

    if provider == "shared":
        # Shared backend: no user API key needed
        shared_url = config["llm"].get("shared_backend_url", "http://localhost:8000")
        config["llm"]["api_key"] = config["llm"].get("shared_backend_key", "") or "shared-default"
        config["llm"]["deepseek_api_key"] = config["llm"]["api_key"]
        config["llm"]["base_url"] = shared_url
        config["llm"]["provider"] = "shared"
    elif provider == "agentrouter":
        # AgentRouter: read AGENT_ROUTER_TOKEN
        llm_api_key = os.getenv("AGENT_ROUTER_TOKEN", "")
        config["llm"]["api_key"] = llm_api_key
        config["llm"]["deepseek_api_key"] = llm_api_key
        config["llm"]["base_url"] = config["llm"].get("base_url", "https://agentrouter.org")
        config["llm"]["provider"] = "agentrouter"
    else:
        # DeepSeek (default) or custom: read from DEEPSEEK_API_KEY or custom env var
        llm_api_key_env = config["llm"].get("api_key_env", "DEEPSEEK_API_KEY")
        llm_api_key = os.getenv(llm_api_key_env, "")
        if not llm_api_key:
            llm_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not llm_api_key:
            llm_api_key = config["llm"].get("deepseek_api_key", "")
        config["llm"]["api_key"] = llm_api_key
        config["llm"]["deepseek_api_key"] = llm_api_key

        if provider != "custom":
            config["llm"]["provider"] = "deepseek"
        config["llm"]["base_url"] = config["llm"].get("base_url", "https://api.deepseek.com")

    # ── Inject service keys ────────────────────────────────────────────────
    config.setdefault("voice", {})
    config.setdefault("asr", {})

    provider = config["llm"].get("provider", "deepseek").lower()

    if provider == "shared":
        # Shared backend mode: route all services through the shared proxy
        shared_url = config["llm"].get("shared_backend_url", "http://localhost:8000").rstrip("/")

        # LLM: already handled above
        # TTS: point to shared backend instead of api.elevenlabs.io
        # Note: /v1 suffix so ElevenLabsTTS constructs the correct path
        config["voice"]["elevenlabs_api_key"] = config["llm"].get("shared_backend_key", "") or "shared-default"
        config["voice"]["elevenlabs_base_url"] = f"{shared_url}/v1"

        # ASR: point to shared backend instead of api.groq.com
        # Note: /v1 suffix so Groq SDK constructs correct paths like /v1/audio/transcriptions
        config["asr"]["groq_api_key"] = config["llm"].get("shared_backend_key", "") or "shared-default"
        config["asr"]["groq_base_url"] = f"{shared_url}/v1"
    else:
        # Normal mode: use user's own API keys
        config["voice"]["elevenlabs_api_key"] = os.getenv("ELEVENLABS_API_KEY", "")
        # No custom base_url — use default ElevenLabs URL
        config["voice"].pop("elevenlabs_base_url", None)

        config["asr"]["groq_api_key"] = os.getenv("GROQ_API_KEY", "")
        # No custom base_url — use default Groq URL
        config["asr"].pop("groq_base_url", None)

    return config
