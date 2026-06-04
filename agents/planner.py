"""Planner agent — decomposes a user goal into ordered JSON subtasks."""

import json
import re
from datetime import datetime
from loguru import logger
from agents.base_agent import BaseAgent
from llm.router import LLMRouter

PLANNER_SYSTEM = ""
try:
    with open("configs/prompts/planner.txt", "r") as f:
        PLANNER_SYSTEM = f.read()
except FileNotFoundError:
    logger.warning("planner.txt prompt not found — using empty system prompt")


class PlannerAgent(BaseAgent):
    """Takes a goal string and returns a list of subtask dicts."""

    def __init__(self, llm: LLMRouter) -> None:
        super().__init__(name="Planner")
        self.llm = llm
        self.last_plan_metadata: dict = {}

    async def run(self, goal: str, context: list[dict], hints: list[dict] | None = None) -> list[dict]:
        """Returns ordered list of subtasks as JSON."""
        self.is_running = True
        self.last_plan_metadata = {"bias_applied": False}
        logger.info(f"Planner: decomposing goal — '{goal[:80]}'")

        try:
            planning_messages = list(context)
            if hints:
                planning_messages.append(
                    {
                        "role": "system",
                        "content": self._hint_message(hints),
                    }
                )
            response = await self.llm.complete(
                messages=planning_messages + [{"role": "user", "content": f"Goal: {goal}"}],
                system=PLANNER_SYSTEM,
                task_type="plan",
            )
            plan = self._parse_plan(response)
            if plan:
                return self._apply_preferred_chain(plan, hints or [])
            logger.warning("Planner produced an empty or invalid plan; using local fallback.")
            return self._fallback_plan(goal)
        except Exception as e:
            logger.error(f"Planner error: {e}")
            fallback = self._fallback_plan(goal)
            if fallback:
                logger.info("Planner fallback activated after LLM failure.")
                return fallback
            return [{"id": 1, "action_type": "voice", "description": str(e), "params": {}}]
        finally:
            self.is_running = False

    def _parse_plan(self, response: str) -> list[dict]:
        """Parse LLM response into a list of subtask dicts."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            clean = response.strip().strip("```json").strip("```").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                logger.error(f"Planner returned unparseable response: {response[:200]}")
                return []

    def _fallback_plan(self, goal: str) -> list[dict]:
        """Heuristic local planner for common user-facing commands."""
        normalized = goal.strip().lower()
        if not normalized:
            return [
                {
                    "id": 1,
                    "action_type": "voice",
                    "description": "Ask for clarification",
                    "params": {"question": "Could you repeat that?"},
                }
            ]

        if any(word in normalized for word in ("hello", "hi", "hey", "good morning", "good afternoon", "good evening")):
            return [
                {
                    "id": 1,
                    "action_type": "voice",
                    "description": "Greet the user",
                    "params": {"question": "Hello. How can I help?"},
                }
            ]

        if any(word in normalized for word in ("thank you", "thanks", "thankyou")):
            return [
                {
                    "id": 1,
                    "action_type": "voice",
                    "description": "Acknowledge the user",
                    "params": {"question": "You're welcome."},
                }
            ]

        if self._looks_like_time_request(normalized):
            return [
                {
                    "id": 1,
                    "action_type": "voice",
                    "description": "Answer the current local time",
                    "params": {"question": self._current_time_phrase()},
                }
            ]

        if self._looks_like_date_request(normalized):
            return [
                {
                    "id": 1,
                    "action_type": "voice",
                    "description": "Answer the current local date",
                    "params": {"question": self._current_date_phrase()},
                }
            ]

        if "screenshot" in normalized or "screen shot" in normalized:
            return [
                {
                    "id": 1,
                    "action_type": "screenshot",
                    "description": "Capture a screenshot",
                    "params": {},
                }
            ]

        if "clipboard" in normalized:
            return [
                {
                    "id": 1,
                    "action_type": "get_clipboard",
                    "description": "Read clipboard contents",
                    "params": {},
                }
            ]

        open_app_name = self._extract_open_app_name(goal)
        if open_app_name:
            return [
                {
                    "id": 1,
                    "action_type": "open_app",
                    "description": f"Open {open_app_name}",
                    "params": {"app_name": open_app_name},
                }
            ]

        if any(word in normalized for word in ("what can you do", "help", "capabilities")):
            return [
                {
                    "id": 1,
                    "action_type": "voice",
                    "description": "Describe basic capabilities",
                    "params": {
                        "question": "I can open apps, take screenshots, read your clipboard, and answer simple questions.",
                    },
                }
            ]

        return [
            {
                "id": 1,
                "action_type": "voice",
                "description": "Ask for clarification",
                "params": {"question": "Could you rephrase that a bit more specifically?"},
            }
        ]

    def _looks_like_time_request(self, normalized_goal: str) -> bool:
        patterns = (
            r"\bwhat(?:'s| is)? the time\b",
            r"\bwhat time is it\b",
            r"\btime right now\b",
            r"\bcurrent time\b",
        )
        return any(re.search(pattern, normalized_goal) for pattern in patterns)

    def _looks_like_date_request(self, normalized_goal: str) -> bool:
        patterns = (
            r"\bwhat(?:'s| is)? the date\b",
            r"\bwhat(?:'s| is)? today(?:'s)? date\b",
            r"\bwhat day is it\b",
        )
        return any(re.search(pattern, normalized_goal) for pattern in patterns)

    def _current_time_phrase(self) -> str:
        now = datetime.now()
        time_text = now.strftime("%I:%M %p").lstrip("0")
        return f"It is {time_text}."

    def _current_date_phrase(self) -> str:
        now = datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}."

    def _extract_open_app_name(self, goal: str) -> str:
        match = re.search(
            r"\b(?:open|launch|start|bring up|show)\s+(?:the\s+)?(?P<app>[a-z0-9][a-z0-9\s._-]{1,40})",
            goal,
            flags=re.IGNORECASE,
        )
        if not match:
            return ""
        app = match.group("app").strip().strip(".,!?")
        if not app:
            return ""
        app = re.sub(r"\s+", " ", app)
        known_map = {
            "notes": "Notes",
            "safari": "Safari",
            "chrome": "Google Chrome",
            "google chrome": "Google Chrome",
            "mail": "Mail",
            "messages": "Messages",
            "finder": "Finder",
            "calculator": "Calculator",
            "calendar": "Calendar",
        }
        lowered = app.lower()
        if lowered in known_map:
            return known_map[lowered]
        return app.title()

    def _hint_message(self, hints: list[dict]) -> str:
        """Format structured hints into explicit planning instructions."""
        lines = ["Structured planning hints from prior interactions:"]
        for hint in hints:
            hint_type = hint.get("type", "hint")
            value = hint.get("value", "")
            reason = hint.get("reason", "")
            if hint_type == "chain" and hint.get("chain"):
                strength = hint.get("strength", "1")
                domain = hint.get("domain", "general")
                lines.append(
                    f"- [{hint_type}] {value}: {reason} Preferred action order: {hint['chain']} Strength: {strength} Domain: {domain}"
                )
            else:
                lines.append(f"- [{hint_type}] {value}: {reason}")
        lines.append("Honor these hints when deciding whether to clarify, validate prerequisites, or choose a lower-latency path.")
        return "\n".join(lines)

    def _apply_preferred_chain(self, plan: list[dict], hints: list[dict]) -> list[dict]:
        """Reorder compatible subtasks toward the strongest learned chain."""
        if not plan or not hints:
            return plan

        preferred_hint = self._preferred_chain_hint(hints)
        if not preferred_hint:
            return plan
        preferred_chain = [part.strip() for part in str(preferred_hint["chain"]).split("->") if part.strip()]

        weight_map = {action: index for index, action in enumerate(preferred_chain)}
        matched_count = sum(1 for task in plan if task.get("action_type") in weight_map)
        if matched_count < 2:
            return plan

        indexed_plan = list(enumerate(plan))

        def sort_key(item: tuple[int, dict]) -> tuple[int, int]:
            original_index, task = item
            action_type = task.get("action_type", "")
            if action_type in weight_map:
                return (0, weight_map[action_type])
            return (1, original_index)

        original_actions = [task.get("action_type", "") for task in plan]
        reordered = [task for _, task in sorted(indexed_plan, key=sort_key)]
        reordered_actions = [task.get("action_type", "") for task in reordered]
        if reordered_actions != original_actions:
            self.last_plan_metadata = {
                "bias_applied": True,
                "bias_type": "preferred_chain",
                "preferred_chain": preferred_hint["chain"],
                "strength": preferred_hint.get("strength", "1"),
                "domain": preferred_hint.get("domain", "general"),
                "matched_count": matched_count,
                "original_order": original_actions,
                "reordered_order": reordered_actions,
            }
            logger.info(
                "Planner bias applied: %s -> %s (strength=%s, domain=%s)",
                original_actions,
                reordered_actions,
                preferred_hint.get("strength", "1"),
                preferred_hint.get("domain", "general"),
            )
        return self._renumber_plan(reordered)

    def _preferred_chain_hint(self, hints: list[dict]) -> dict | None:
        """Pick the strongest preferred action chain hint from the available hints."""
        chain_hints = [hint for hint in hints if hint.get("type") == "chain" and hint.get("chain")]
        if not chain_hints:
            return None
        return max(chain_hints, key=lambda hint: int(hint.get("strength", "1")))

    def _renumber_plan(self, plan: list[dict]) -> list[dict]:
        """Keep plan ids sequential after a planner-side reorder."""
        renumbered = []
        for index, task in enumerate(plan, start=1):
            updated = dict(task)
            updated["id"] = index
            renumbered.append(updated)
        return renumbered
