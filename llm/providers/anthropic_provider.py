"""Claude Code CLI provider routed through AgentRouter."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider

ANTHROPIC_MODELS = {
    "deepseek-chat": "deepseek-v4-pro",
    "deepseek-reasoner": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-v4-pro",
    "deepseek-v4-pro": "deepseek-v4-pro",
}


class AnthropicProvider(BaseLLMProvider):
    """Async wrapper around the Claude Code CLI."""

    def __init__(self, model: str, config: dict, client=None):
        self.model = ANTHROPIC_MODELS.get(model, model)
        self.api_key = config.get("api_key") or config.get("anthropic_api_key", "")
        self.base_url = config.get("base_url", "https://agentrouter.org/").rstrip("/")
        self.timeout = config.get("request_timeout_seconds", 60)
        self.executable = config.get("claude_executable", "claude")

    def _build_command(self, prompt: str, system: str = "") -> list[str]:
        command = [
            self.executable,
            "--bare",
            "--verbose",
            "--print",
            "--output-format",
            "stream-json",
            "--model",
            self.model,
        ]
        if system:
            command.extend(["--system-prompt", system])
        command.append(prompt)
        return command

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = self.base_url
        env["ANTHROPIC_API_KEY"] = self.api_key
        env["ANTHROPIC_AUTH_TOKEN"] = self.api_key
        return env

    def _serialize_prompt(self, messages: list[dict]) -> str:
        chunks: list[str] = []
        for message in messages:
            content = message.get("content", "")
            if content is None:
                content = ""
            if content:
                chunks.append(str(content))
        return "\n\n".join(chunks).strip()

    def _extract_text_from_events(self, stdout: str) -> str:
        final_result = ""
        result_text = ""
        for raw_line in stdout.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                candidate = event.get("result", "")
                if candidate:
                    final_result = str(candidate)
                continue
            if event.get("type") != "assistant":
                continue
            message = event.get("message") or {}
            content = message.get("content") or []
            pieces: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        pieces.append(text)
            if pieces:
                result_text = "".join(pieces)
        return (final_result or result_text).strip()

    def _run_sync(self, prompt: str, system: str = "") -> tuple[int, str, str]:
        proc = subprocess.run(
            self._build_command(prompt, system),
            cwd=os.getcwd(),
            env=self._build_env(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr

    async def complete(self, messages: list[dict], system: str = "") -> str:
        """Calls AgentRouter through the Claude Code CLI and extracts the final text."""
        if not self.api_key:
            raise RuntimeError("Anthropic/AgentRouter API key is not configured.")

        prompt = self._serialize_prompt(messages)
        try:
            returncode, stdout, stderr = await asyncio.to_thread(self._run_sync, prompt, system)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Claude Code CLI timed out while contacting AgentRouter.") from exc

        if returncode != 0:
            tail = (stderr or stdout).strip()
            raise RuntimeError(f"Claude Code CLI failed: {tail[:500]}")

        text = self._extract_text_from_events(stdout)
        if text:
            return text

        raise RuntimeError("Claude Code CLI returned no assistant text.")

    async def stream(self, messages: list[dict], system: str = "") -> AsyncGenerator[str, None]:
        """Fallback streaming implementation that yields the final completion as one chunk."""
        text = await self.complete(messages, system)
        if text:
            yield text

    async def healthcheck(self) -> bool:
        """Healthy when an API key is configured."""
        return bool(self.api_key)
