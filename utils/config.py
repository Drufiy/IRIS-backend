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

    llm_api_key_env = config["llm"].get("api_key_env", "AGENT_ROUTER_TOKEN")
    llm_api_key = os.getenv(llm_api_key_env, "")
    if not llm_api_key:
        llm_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    config["llm"]["api_key"] = llm_api_key
    config["llm"]["deepseek_api_key"] = llm_api_key
    default_llm_base_url = "https://api.anthropic.com/" if config["llm"].get("provider") == "agentrouter" else "https://api.deepseek.com"
    config["llm"]["base_url"] = config["llm"].get("base_url", default_llm_base_url)
    config["voice"]["elevenlabs_api_key"] = os.getenv("ELEVENLABS_API_KEY", "")
    config["asr"]["groq_api_key"] = os.getenv("GROQ_API_KEY", "")

    return config
