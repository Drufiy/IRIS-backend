"""Planner agent — decomposes a user goal into ordered JSON subtasks."""

import json
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
            return self._apply_preferred_chain(plan, hints or [])
        except Exception as e:
            logger.error(f"Planner error: {e}")
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
                return [{"id": 1, "action_type": "voice", "description": "I couldn't plan that. Could you rephrase?", "params": {}}]

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
