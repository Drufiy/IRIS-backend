"""Prompt loading and memory-aware composition helpers."""

from __future__ import annotations

from pathlib import Path


class PromptManager:
    """Loads prompt templates and appends compact context safely."""

    def __init__(self, prompt_root: str = "configs/prompts", max_messages: int = 20):
        self.prompt_root = Path(prompt_root)
        self.max_messages = max_messages

    def load_prompt(self, name: str) -> str:
        """Loads a prompt file by logical name."""
        path = self.prompt_root / f"{name}.txt"
        return path.read_text(encoding="utf-8").strip()

    def build_messages(
        self,
        base_messages: list[dict],
        memory_context: list[dict] | None = None,
    ) -> list[dict]:
        """Builds a bounded message list with injected memory context."""
        built = list(base_messages[-self.max_messages :])
        if not memory_context:
            return built

        context_lines = []
        for item in memory_context:
            text = item.get("text", "").strip()
            if text:
                context_lines.append(f"- {text}")

        if context_lines:
            built.insert(
                0,
                {
                    "role": "system",
                    "content": "Relevant memory context:\n" + "\n".join(context_lines),
                },
            )
        return built
