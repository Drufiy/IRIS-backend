"""Coding agent for autonomous repo edits, test execution, and debug retries."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    logger = logging.getLogger("iris.coding_agent")

from agents.base_agent import BaseAgent

try:
    from core.state_manager import IRISState
except Exception:  # pragma: no cover
    IRISState = None

CODING_SYSTEM = ""
try:
    with open("configs/prompts/coding_agent.txt", "r", encoding="utf-8") as file_handle:
        CODING_SYSTEM = file_handle.read()
except FileNotFoundError:
    logger.warning("coding_agent.txt prompt not found - using empty system prompt")

MAX_DEBUG_ITERATIONS = 5
TestRunner = Callable[[str], Awaitable[dict[str, Any]]]


class CodingAgent(BaseAgent):
    """Runs the read-plan-write-test-debug loop for code subtasks."""

    def __init__(
        self,
        llm,
        state_manager=None,
        action_router=None,
        test_runner: TestRunner | None = None,
        max_debug_iterations: int = MAX_DEBUG_ITERATIONS,
    ) -> None:
        super().__init__(name="Coding")
        self.llm = llm
        self.state = state_manager
        self.actions = action_router
        self.test_runner = test_runner or self._run_tests
        self.max_debug_iterations = max_debug_iterations

    async def run(self, goal: str, repo_path: str) -> dict[str, Any]:
        """Execute the coding loop against a repository path."""
        self.is_running = True
        repo_context = self._read_repo(repo_path)
        messages = [{"role": "user", "content": f"Repo:\n{repo_context}\n\nGoal: {goal}"}]

        await self._transition("ACTING")

        try:
            for iteration in range(self.max_debug_iterations):
                response = await self.llm.complete(messages, system=CODING_SYSTEM, task_type="code")
                step = self._parse_step(response)
                action = step.get("action") or step.get("step", "")

                if action == "write_file":
                    file_path = step.get("file_path", "")
                    await self._write_file(repo_path, file_path, step.get("content", ""))
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"File written: {file_path}. Run tests."})
                    continue

                if action == "run_tests":
                    result = await self.test_runner(repo_path)
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"Test result: {json.dumps(result)}"})
                    if result.get("passed"):
                        return {
                            "status": "ok",
                            "message": "Tests passed.",
                            "iterations": iteration + 1,
                            "output": result.get("output", ""),
                        }
                    continue

                if action == "complete":
                    return {
                        "status": "ok",
                        "message": step.get("content", "Done"),
                        "iterations": iteration + 1,
                    }

                if action in {"debug", "plan", "read"}:
                    messages.append({"role": "assistant", "content": response})
                    continue

                if action == "escalate":
                    return {
                        "status": "escalate",
                        "message": step.get("content", step.get("reasoning", "Escalated by coding agent")),
                        "iterations": iteration + 1,
                    }

                return {
                    "status": "error",
                    "message": f"Unknown coding action: {action}",
                    "iterations": iteration + 1,
                }

            return {
                "status": "escalate",
                "message": "Max debug iterations reached",
                "iterations": self.max_debug_iterations,
            }
        finally:
            self.is_running = False
            await self._transition("INTERACTIVE")

    async def run_proposal(
        self,
        proposal: dict[str, Any],
        repo_path: str,
        *,
        memory_manager=None,
    ) -> dict[str, Any]:
        """Execute a single approved self-improvement proposal through the normal coding loop."""
        proposal_id = proposal.get("id", "")
        if memory_manager is not None and proposal_id:
            await memory_manager.update_improvement_proposal(
                proposal_id,
                status="in_progress",
            )

        goal = self._goal_from_proposal(proposal)
        result = await self.run(goal, repo_path)
        result["proposal_id"] = proposal_id
        result["proposal_title"] = proposal.get("title", "")

        if memory_manager is not None and proposal_id:
            next_status = "completed" if result.get("status") == "ok" else "escalated"
            await memory_manager.update_improvement_proposal(
                proposal_id,
                status=next_status,
                resolution=result.get("message", ""),
            )

        return result

    def _parse_step(self, response: str) -> dict[str, Any]:
        """Parse the model output into a structured coding step."""
        try:
            step = json.loads(response)
        except json.JSONDecodeError:
            clean = response.strip()
            if clean.startswith("```json"):
                clean = clean[len("```json") :]
            clean = clean.strip()
            if clean.endswith("```"):
                clean = clean[:-3].strip()
            step = json.loads(clean)

        normalized = dict(step)
        normalized.setdefault("step", "")
        normalized.setdefault("action", normalized["step"])
        return normalized

    def _read_repo(self, repo_path: str) -> str:
        """Read a bounded subset of Python files for repo context."""
        root = Path(repo_path)
        if not root.exists():
            return ""

        collected: list[str] = []
        for file_path in sorted(root.rglob("*.py")):
            if "__pycache__" in file_path.parts:
                continue
            if any(part.startswith(".") for part in file_path.parts):
                continue
            try:
                relative = file_path.relative_to(root).as_posix()
                collected.append(f"# {relative}\n{file_path.read_text(encoding='utf-8')}")
            except Exception as exc:
                logger.warning(f"Skipping repo file {file_path}: {exc}")
            if len(collected) >= 20:
                break
        return "\n\n".join(collected)

    async def _write_file(self, repo_path: str, relative_path: str, content: str) -> None:
        """Write a full file either directly or via the action router."""
        if not relative_path:
            raise ValueError("write_file step missing file_path")

        target_path = Path(repo_path) / relative_path
        if self.actions is not None:
            result = await self.actions.execute(
                {
                    "action_type": "write_file",
                    "description": f"Write {relative_path}",
                    "params": {
                        "file_path": str(target_path.resolve()),
                        "content": content,
                    },
                }
            )
            if result.get("status") != "ok":
                raise RuntimeError(result.get("result", "write_file action failed"))
            return

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

    async def _run_tests(self, repo_path: str) -> dict[str, Any]:
        """Run the repository unit tests and capture output."""
        python_cmd = await self._resolve_python_command()
        command = [python_cmd, "-m", "unittest", "discover", "-s", "tests", "-v"]
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        return {"passed": process.returncode == 0, "output": output}

    async def _resolve_python_command(self) -> str:
        """Resolve a usable Python launcher."""
        for candidate in ("py", "python"):
            try:
                process = await asyncio.create_subprocess_exec(
                    candidate,
                    "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
                if process.returncode == 0:
                    return candidate
            except FileNotFoundError:
                continue
        raise RuntimeError("No Python interpreter available for coding-agent test execution.")

    async def _transition(self, state_name: str) -> None:
        """Update the shared UI state when a state manager is available."""
        if self.state is None:
            return
        try:
            target_state = getattr(IRISState, state_name) if IRISState is not None else state_name
            await self.state.transition(target_state)
        except Exception as exc:
            logger.warning(f"CodingAgent state transition failed: {exc}")

    def _goal_from_proposal(self, proposal: dict[str, Any]) -> str:
        """Translate a structured self-improvement proposal into a bounded coding goal."""
        title = proposal.get("title", "Self-improvement proposal")
        summary = proposal.get("summary", "")
        domain = proposal.get("domain", "general")
        priority = proposal.get("priority", "medium")
        scope = proposal.get("suggested_scope", [])
        evidence = proposal.get("evidence", {})
        hint_values = proposal.get("suggested_hints", [])

        scope_text = ", ".join(scope) if scope else "relevant local modules"
        evidence_lines = []
        for key in ("user_input", "action_summary", "error_message", "latency_seconds", "slowest_stage", "chain"):
            value = evidence.get(key)
            if value not in {None, ""}:
                evidence_lines.append(f"- {key}: {value}")
        hints_text = ", ".join(hint_values) if hint_values else "none"

        parts = [
            f"Proposal: {title}",
            f"Priority: {priority}",
            f"Domain: {domain}",
            summary,
            f"Suggested scope: {scope_text}",
            f"Suggested hints to preserve or strengthen: {hints_text}",
            "Implement a narrow fix for this proposal, keep changes scoped to the suggested modules, and run tests before finishing.",
        ]
        if evidence_lines:
            parts.append("Evidence:\n" + "\n".join(evidence_lines))
        return "\n\n".join(part for part in parts if part)
