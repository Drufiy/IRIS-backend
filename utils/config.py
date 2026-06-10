"""Load settings.yaml and overlay API keys from the environment.

Two operating modes (set via settings.yaml `mode`):
  - remote:  All services route through the shared backend proxy.
  - local:   Each service uses its own API keys and endpoints.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


MODE_REMOTE = "remote"
MODE_LOCAL = "local"

_DEFAULT_PROXY_PORT = 8000


def load_config(settings_path: str = "configs/settings.yaml") -> dict:
    """Load YAML config and overlay API keys from the environment."""
    settings_file = Path(settings_path)
    if not settings_file.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    with settings_file.open("r", encoding="utf-8") as f:
        config: dict = yaml.safe_load(f)

    # Load .env file if present
    keys_file = Path("configs/keys.env")
    if keys_file.exists():
        load_dotenv(dotenv_path=keys_file)

    # Ensure required top-level keys exist
    config.setdefault("llm", {})
    config.setdefault("voice", {})
    config.setdefault("asr", {})

    mode = config.get("mode", MODE_LOCAL).lower().strip()

    if mode == MODE_REMOTE:
        _apply_remote_mode(config)
    else:
        _apply_local_mode(config)

    return config


def _apply_remote_mode(config: dict) -> None:
    """Remote mode: all three services route through the shared backend proxy."""
    remote_cfg = config.get("remote", {})
    backend_url = (remote_cfg.get("backend_url", f"http://localhost:{_DEFAULT_PROXY_PORT}")).rstrip("/")

    # Resolve auth token
    auth_token_env = remote_cfg.get("auth_token_env", "")
    auth_token = os.getenv(auth_token_env, "") if auth_token_env else ""
    if not auth_token:
        auth_token = remote_cfg.get("auth_token", "")  # fallback to inline value
    api_key = auth_token or "shared-default"

    # ── LLM ────────────────────────────────────────────────────────────────
    config["llm"]["mode"] = MODE_REMOTE
    config["llm"]["api_key"] = api_key
    config["llm"]["base_url"] = backend_url

    # ── TTS ─────────────────────────────────────────────────────────────────
    config["voice"]["mode"] = MODE_REMOTE
    config["voice"]["elevenlabs_api_key"] = api_key
    config["voice"]["elevenlabs_base_url"] = f"{backend_url}/v1"

    # ── ASR ─────────────────────────────────────────────────────────────────
    config["asr"]["mode"] = MODE_REMOTE
    config["asr"]["groq_api_key"] = api_key
    config["asr"]["groq_base_url"] = f"{backend_url}/v1"


def _apply_local_mode(config: dict) -> None:
    """Local mode: each service uses independently configured API keys and endpoints."""
    # ── LLM ─────────────────────────────────────────────────────────────────
    llm_cfg = config.get("llm", {})
    llm_provider = llm_cfg.get("provider", "")
    default_llm_key_env = "AGENTIC_API_KEY" if llm_provider == "agentrouter" else "DEEPSEEK_API_KEY"
    llm_key_env = llm_cfg.get("api_key_env", default_llm_key_env)
    llm_key = os.getenv(llm_key_env, "")
    if llm_provider == "agentrouter" and not llm_key:
        llm_key = os.getenv("AGENT_ROUTER_TOKEN", "")
    if not llm_key:
        llm_key = os.getenv("DEEPSEEK_API_KEY", "") or llm_cfg.get("api_key", "")

    env_llm_base_url = os.getenv("AGENTIC_API_BASE_URL", "").strip() if llm_provider == "agentrouter" else ""
    default_llm_base_url = (
        env_llm_base_url
        if env_llm_base_url
        else (
            "https://api.agentrouter.to/api/agentic-api"
            if llm_provider == "agentrouter"
            else "https://api.deepseek.com"
        )
    )
    config["llm"]["mode"] = MODE_LOCAL
    config["llm"]["api_key"] = llm_key
    config["llm"]["deepseek_api_key"] = llm_key
    config["llm"]["base_url"] = llm_cfg.get("base_url", default_llm_base_url)

    # ── TTS ─────────────────────────────────────────────────────────────────
    voice_cfg = config.get("voice", {})
    tts_key_env = voice_cfg.get("api_key_env", "ELEVENLABS_API_KEY")
    tts_key = os.getenv(tts_key_env, "") or voice_cfg.get("api_key", "")
    config["voice"]["mode"] = MODE_LOCAL
    config["voice"]["elevenlabs_api_key"] = tts_key
    # Remove any stale proxy base_url in local mode
    config["voice"].pop("elevenlabs_base_url", None)

    # ── ASR ─────────────────────────────────────────────────────────────────
    asr_cfg = config.get("asr", {})
    asr_key_env = asr_cfg.get("api_key_env", "GROQ_API_KEY")
    asr_key = os.getenv(asr_key_env, "") or asr_cfg.get("api_key", "")
    config["asr"]["mode"] = MODE_LOCAL
    config["asr"]["groq_api_key"] = asr_key
    # Remove any stale proxy base_url in local mode
    config["asr"].pop("groq_base_url", None)
