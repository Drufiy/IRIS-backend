"""Spawns, tracks, and cancels agents. Wires Planner → Executor pipeline."""

from time import perf_counter

from loguru import logger
from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent


class AgentManager:
    """
    Entry point consumed by IRISEventLoop.run().
    Orchestrates: goal → Planner → subtasks → Executor → result string.
    """

    def __init__(self, llm, memory, action_router, browser_agent, coding_agent, tts=None) -> None:
        self.llm     = llm
        self.memory  = memory
        self.planner = PlannerAgent(llm)
        self.coding_agent = coding_agent
        self.executor = ExecutorAgent(action_router, browser_agent, coding_agent, tts)
        self._active_agents: list = []

    async def run(self, goal: str, messages: list[dict]) -> dict:
        """Full pipeline: plan → execute → return structured result."""
        logger.info(f"AgentManager: processing goal — '{goal[:80]}'")
        hints = await self.memory.get_planning_hints(goal) if hasattr(self.memory, "get_planning_hints") else []
        started_at = perf_counter()

        # Step 1: Plan
        self._active_agents.append(self.planner)
        plan_started_at = perf_counter()
        subtasks = await self.planner.run(goal, messages, hints=hints)
        planning_seconds = perf_counter() - plan_started_at
        planner_metadata = dict(getattr(self.planner, "last_plan_metadata", {}))
        logger.info(f"Planner produced {len(subtasks)} subtasks")
        performance_metadata = {
            "planning_seconds": round(planning_seconds, 3),
            "execution_seconds": 0.0,
            "agent_total_seconds": round(perf_counter() - started_at, 3),
        }

        if not subtasks:
            return {
                "response": "I couldn't figure out how to do that. Could you rephrase?",
                "action_summary": "planner:empty",
                "trace": [],
                "metadata": {"planner": planner_metadata, "performance": performance_metadata},
            }

        # If the first subtask is a clarifying question, just speak it
        if len(subtasks) == 1 and subtasks[0].get("action_type") == "voice":
            question = subtasks[0].get("params", {}).get("question", subtasks[0].get("description", ""))
            return {
                "response": question,
                "action_summary": "planner:clarify",
                "trace": [
                    {
                        "id": subtasks[0].get("id", 1),
                        "action_type": "voice",
                        "description": subtasks[0].get("description", ""),
                        "result": question,
                    }
                ],
                "metadata": {"planner": planner_metadata, "performance": performance_metadata},
            }

        # Step 2: Execute
        self._active_agents.append(self.executor)
        execute_started_at = perf_counter()
        result = await self.executor.run(goal, messages, subtasks, hints=hints)
        performance_metadata["execution_seconds"] = round(perf_counter() - execute_started_at, 3)
        self._active_agents.clear()
        final_result = result or {"response": "Done.", "action_summary": "executor:done", "trace": []}
        final_result.setdefault("metadata", {})
        final_result["metadata"]["planner"] = planner_metadata
        performance_metadata["agent_total_seconds"] = round(perf_counter() - started_at, 3)
        final_result["metadata"]["performance"] = performance_metadata
        return final_result

    async def review_self_improvement_proposals(self, *, status: str = "pending", limit: int = 10) -> list[dict]:
        """Return queued self-improvement proposals for inspection or approval."""
        if not hasattr(self.memory, "read_improvement_proposals"):
            return []
        proposals = await self.memory.read_improvement_proposals(limit=limit, status=status)
        return list(proposals)

    async def run_next_self_improvement(
        self,
        repo_path: str,
        *,
        approve: bool = False,
        allow_auto: bool = False,
    ) -> dict:
        """
        Review or execute the highest-priority pending self-improvement proposal.

        When approve is False, returns a preview and leaves proposal state untouched.
        When approve is True, hands the proposal to the coding agent and updates status.
        """
        if not hasattr(self.memory, "select_next_proposal_for_coding"):
            return {
                "status": "unavailable",
                "message": "Memory manager does not support improvement proposals yet.",
            }

        proposal = await self.memory.select_next_proposal_for_coding()
        if proposal is None:
            return {
                "status": "empty",
                "message": "No pending self-improvement proposals are ready for coding.",
                "proposal": None,
            }

        approval_policy = proposal.get("approval_policy", {})
        requires_human_approval = bool(approval_policy.get("requires_human_approval", True))
        is_auto_eligible = approval_policy.get("mode") == "auto_eligible"

        if not approve and not (allow_auto and is_auto_eligible and not requires_human_approval):
            return {
                "status": "review",
                "message": "Self-improvement proposal ready for review.",
                "proposal": proposal,
                "approval_policy": approval_policy,
            }

        if self.coding_agent is None:
            return {
                "status": "unavailable",
                "message": "Coding agent is not configured for self-improvement execution.",
                "proposal": proposal,
                "approval_policy": approval_policy,
            }

        result = await self._execute_self_improvement_proposal(proposal, repo_path)

        return {
            "status": result.get("status", "unknown"),
            "message": result.get("message", ""),
            "proposal": proposal,
            "result": result,
            "approval_policy": approval_policy,
        }

    async def run_bounded_self_improvement_loop(
        self,
        repo_path: str,
        *,
        max_proposals: int = 1,
    ) -> dict:
        """
        Run a tightly bounded autonomous self-improvement pass.

        Safety rules:
        - only auto-eligible proposals may run without explicit approval
        - process at most `max_proposals` proposals
        - stop immediately after a non-ok result
        """
        if self.coding_agent is None:
            return {
                "status": "unavailable",
                "message": "Coding agent is not configured for autonomous self-improvement.",
                "processed": [],
                "skipped": [],
            }

        proposals = await self.review_self_improvement_proposals(status="pending", limit=50)
        auto_candidates = [
            proposal
            for proposal in proposals
            if proposal.get("approval_policy", {}).get("mode") == "auto_eligible"
            and not proposal.get("approval_policy", {}).get("requires_human_approval", True)
        ]
        auto_candidates.sort(key=self._proposal_sort_key, reverse=True)

        if not auto_candidates:
            return {
                "status": "empty",
                "message": "No auto-eligible self-improvement proposals are ready to run.",
                "processed": [],
                "skipped": proposals,
            }

        processed: list[dict] = []
        for proposal in auto_candidates[: max(1, max_proposals)]:
            execution_result = await self._execute_self_improvement_proposal(proposal, repo_path)
            result = {
                "status": execution_result.get("status", "unknown"),
                "message": execution_result.get("message", ""),
                "proposal": proposal,
                "result": execution_result,
                "approval_policy": proposal.get("approval_policy", {}),
            }
            processed.append(result)
            if execution_result.get("status") != "ok":
                return {
                    "status": "partial",
                    "message": "Autonomous self-improvement stopped after a non-successful attempt.",
                    "processed": processed,
                    "skipped": proposals,
                }

        return {
            "status": "ok",
            "message": f"Autonomous self-improvement processed {len(processed)} proposal(s).",
            "processed": processed,
            "skipped": [proposal for proposal in proposals if proposal not in auto_candidates[: max(1, max_proposals)]],
        }

    async def cancel_all(self) -> None:
        """Cancel all active agents."""
        for agent in self._active_agents:
            await agent.cancel()
        self._active_agents.clear()
        logger.info("All agents cancelled")

    async def _execute_self_improvement_proposal(self, proposal: dict, repo_path: str) -> dict:
        """Run a specific proposal through the coding agent with active-agent bookkeeping."""
        self._active_agents.append(self.coding_agent)
        try:
            return await self.coding_agent.run_proposal(
                proposal,
                repo_path,
                memory_manager=self.memory,
            )
        finally:
            self._active_agents = [agent for agent in self._active_agents if agent is not self.coding_agent]

    def _proposal_sort_key(self, proposal: dict) -> tuple[int, float, int, int, str]:
        """Prefer proposals with better measured outcomes, then priority, type, and recency."""
        priority_rank = {"high": 3, "medium": 2, "low": 1}
        type_rank = {"code_change": 3, "performance_tuning": 2, "workflow_promotion": 1}
        return (
            int(proposal.get("outcome_score", 0)),
            float(proposal.get("outcome_confidence", 0.0)),
            priority_rank.get(proposal.get("priority", "low"), 0),
            type_rank.get(proposal.get("proposal_type", ""), 0),
            proposal.get("created_at", ""),
        )
