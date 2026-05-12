"""Executor agent — runs subtasks produced by the Planner, routing each to the correct engine."""

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

    async def run(self, goal: str, context: list[dict], subtasks: list[dict] = None) -> str:
        """Execute a plan (list of subtasks). Returns a summary string."""
        if not subtasks:
            return "No subtasks to execute."

        self.is_running = True
        results: list[str] = []

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

                result = await self._dispatch(action_type, params, description)
                results.append(f"[{task_id}] {result}")

        except Exception as e:
            logger.error(f"Executor error: {e}")
            results.append(f"Error: {e}")
        finally:
            self.is_running = False

        summary = "; ".join(results) if results else "Done."
        logger.info(f"Executor finished: {summary[:200]}")
        return summary

    async def _dispatch(self, action_type: str, params: dict, description: str) -> str:
        """Route a single subtask to the correct engine."""

        # Voice actions — speak directly
        if action_type == "voice":
            question = params.get("question", description)
            await self.tts.speak(question)
            return f"Spoke: {question}"

        # Browser actions
        if action_type == "browser":
            return await self._run_browser(params)

        # Code actions
        if action_type == "code":
            return await self._run_coding(params)

        # Everything else routes through the ActionRouter
        subtask = {"action_type": action_type, "params": params, "description": description}
        result = await self.actions.execute(subtask)
        return result.get("result", str(result.get("status", "unknown")))

    async def _run_browser(self, params: dict) -> str:
        """Execute a browser subtask."""
        try:
            url = params.get("url")
            if url:
                await self.browser.start(headless=False)
                await self.browser.navigate(url)
                text = await self.browser.extract_text()
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
