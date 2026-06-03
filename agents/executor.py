"""Executor agent — runs subtasks produced by the Planner, routing each to the correct engine."""

import asyncio

from actions.safety import SafetyLevel, classify
from loguru import logger
from agents.base_agent import BaseAgent


class ExecutorAgent(BaseAgent):
    """
    Takes a list of subtask dicts from the Planner and executes them in order.
    Routes each subtask to the ActionRouter, BrowserAgent, or CodingAgent.
    """

    def __init__(self, action_router, browser_agent, coding_agent, tts) -> None:
        super().__init__(name="Executor")
        self.actions = action_router
        self.browser = browser_agent
        self.coding  = coding_agent
        self.tts     = tts

    async def run(self, goal: str, context: list[dict], subtasks: list[dict] = None, hints: list[dict] | None = None) -> dict:
        """Execute a plan and return a structured execution result."""
        if not subtasks:
            return {"response": "No subtasks to execute.", "action_summary": "no_subtasks", "trace": []}

        self.is_running = True
        results: list[str] = []
        trace: list[dict] = []

        try:
            for task in subtasks:
                if not self.is_running:
                    logger.info("Executor cancelled mid-plan")
                    break

                action_type = task.get("action_type", "")
                description = task.get("description", "")
                params = task.get("params", {})
                task_id = task.get("id", "?")

                logger.info(f"Executor [{task_id}]: {action_type} — {description}")

                result = await self._dispatch(goal, action_type, params, description, hints or [])
                results.append(f"[{task_id}] {result}")
                trace.append(
                    {
                        "id": task_id,
                        "action_type": action_type,
                        "description": description,
                        "result": result,
                    }
                )

        except Exception as e:
            logger.error(f"Executor error: {e}")
            results.append(f"Error: {e}")
            trace.append(
                {
                    "id": "executor",
                    "action_type": "error",
                    "description": "executor exception",
                    "result": str(e),
                }
            )
        finally:
            self.is_running = False

        response = "; ".join(results) if results else "Done."
        logger.info(f"Executor finished: {response[:200]}")
        return {
            "response": response,
            "action_summary": self._summarize_trace(trace),
            "trace": trace,
        }

    async def _dispatch(self, goal: str, action_type: str, params: dict, description: str, hints: list[dict]) -> str:
        """Route a single subtask to the correct engine."""
        hint_values = {hint.get("value", "") for hint in hints}
        safety = classify(action_type)

        if (
            "clarify_before_risky_action" in hint_values
            and safety == SafetyLevel.DANGEROUS
            and not params.get("confirmed")
        ):
            return "This action is risky and similar attempts have gone badly before. Please confirm the exact target and intent first."

        if (
            "escalate_after_repeated_failures" in hint_values
            and safety in {SafetyLevel.WARN, SafetyLevel.DANGEROUS}
        ):
            return "I have hit similar failures before. Please give me a bit more detail or confirm a different approach before I try again."

        # Voice actions — speak directly
        if action_type == "voice":
            question = params.get("question", description)
            await self.tts.speak(question)
            return f"Spoke: {question}"

        # Browser actions
        if action_type == "browser":
            return await self._run_browser(goal, params, hints)

        # Code actions
        if action_type == "code":
            return await self._run_coding(params)

        # Everything else routes through the ActionRouter
        subtask = {"action_type": action_type, "params": params, "description": description}
        result = await self.actions.execute(subtask)
        return result.get("result", str(result.get("status", "unknown")))

    async def _run_browser(self, goal: str, params: dict, hints: list[dict]) -> str:
        """Execute a browser subtask."""
        try:
            hint_values = {hint.get("value", "") for hint in hints}
            goal_text = f"{goal} {params.get('intent', '')}".lower()
            if (
                "ask_for_credentials_first" in hint_values
                and any(term in goal_text for term in ("login", "log in", "sign in"))
                and not params.get("credentials_service")
            ):
                return "Before I log in, tell me which saved credentials to use."

            url = params.get("url")
            if url:
                await self.browser.start(headless=False)
                await self.browser.navigate(url)
                selector = params.get("selector", "body")
                text = await self.browser.extract_text(selector)
                if "wait_for_page_and_retry_selector" in hint_values and not text.strip():
                    await asyncio.sleep(0.25)
                    text = await self.browser.extract_text(selector)
                await self.browser.close()
                return f"Browsed {url}: {text[:200]}"
            return "Browser: no URL provided"
        except Exception as e:
            logger.error(f"Browser action error: {e}")
            return f"Browser error: {e}"

    async def _run_coding(self, params: dict) -> str:
        """Execute a coding subtask."""
        try:
            goal = params.get("goal", "")
            repo = params.get("repo_path", ".")
            result = await self.coding.run(goal, repo)
            return f"Coding: {result.get('status', 'unknown')} — {result.get('message', '')}"
        except Exception as e:
            logger.error(f"Coding action error: {e}")
            return f"Coding error: {e}"

    def _summarize_trace(self, trace: list[dict]) -> str:
        """Build a compact action summary for self-improvement logging."""
        if not trace:
            return "no_actions"
        parts = []
        for step in trace:
            action_type = step.get("action_type", "unknown")
            result = step.get("result", "")
            normalized = "ok"
            lowered = str(result).lower()
            if "error" in lowered:
                normalized = "error"
            elif "confirm" in lowered or "detail" in lowered or "credentials" in lowered:
                normalized = "clarify"
            elif "denied" in lowered:
                normalized = "denied"
            parts.append(f"{action_type}:{normalized}")
        return " -> ".join(parts)
