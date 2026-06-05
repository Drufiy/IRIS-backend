"""Backward-compatible alias for the HTTP provider.

DeepSeekProvider now delegates to HttpProvider which makes direct
HTTP calls to the configured API (DeepSeek, AgentRouter, or shared backend)
instead of spawning a Claude CLI subprocess.
"""

from __future__ import annotations

from llm.providers.http_provider import HttpProvider

DeepSeekProvider = HttpProvider
