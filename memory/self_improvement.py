"""Interaction logging primitives for IRIS self-improvement."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

from memory.long_term import LongTermMemory


class SelfImprovementManager:
    """Persists completed interactions for later reflection and reuse."""

    _STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "my",
        "of",
        "on",
        "or",
        "please",
        "the",
        "to",
        "with",
        "you",
    }

    def __init__(
        self,
        long_term: LongTermMemory,
        retrieval_limit: int = 10,
        proposal_cooldown_hours: int = 24,
        proposal_stale_age_hours: int = 72,
        human_review_escalation_threshold: int = 2,
    ) -> None:
        self.long_term = long_term
        self.retrieval_limit = retrieval_limit
        self.proposal_cooldown_hours = proposal_cooldown_hours
        self.proposal_stale_age_hours = proposal_stale_age_hours
        self.human_review_escalation_threshold = human_review_escalation_threshold

    async def record_interaction(
        self,
        *,
        user_input: str,
        response: str = "",
        status: str,
        latency_seconds: float,
        action_summary: str = "",
        error_message: str = "",
        satisfaction: str = "unknown",
        timing_breakdown: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Create and store a structured interaction record."""
        prior_interactions = await self.long_term.read_interactions()
        prior_proposals = await self.long_term.read_improvement_proposals()
        record = {
            "id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_input": user_input,
            "response": response,
            "status": status,
            "latency_seconds": round(float(latency_seconds), 3),
            "action_summary": action_summary,
            "error_message": error_message,
            "satisfaction": satisfaction,
            "timing_breakdown": self._normalize_timings(timing_breakdown or {}),
        }
        await self.long_term.save_interaction(record)
        reflection = self._build_reflection(record, prior_interactions=prior_interactions)
        await self.long_term.save_reflection(reflection)
        for proposal in self._build_improvement_proposals(
            record,
            reflection,
            prior_interactions=prior_interactions,
            prior_proposals=prior_proposals,
        ):
            await self.long_term.save_improvement_proposal(proposal)
        return record

    async def read_interactions(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return recent interaction records, newest first."""
        interactions = await self.long_term.read_interactions()
        if limit is None:
            return interactions
        return interactions[-limit:]

    async def read_reflections(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return recent reflection records, newest first."""
        reflections = await self.long_term.read_reflections()
        if limit is None:
            return reflections
        return reflections[-limit:]

    async def read_improvement_proposals(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return stored self-improvement proposals, oldest to newest by default."""
        proposals = await self.long_term.read_improvement_proposals()
        if limit is None:
            return proposals
        return proposals[-limit:]

    async def update_improvement_proposal(self, proposal_id: str, **updates: Any) -> dict[str, Any] | None:
        """Update the stored state of a proposal after review or execution."""
        return await self.long_term.update_improvement_proposal(proposal_id, **updates)

    async def append_improvement_proposal_history(
        self,
        proposal_id: str,
        event: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Append a history event to a stored proposal."""
        return await self.long_term.append_improvement_proposal_history(proposal_id, event)

    async def select_next_proposal_for_coding(
        self,
        *,
        allowed_statuses: tuple[str, ...] = ("pending",),
        allowed_types: tuple[str, ...] = ("code_change", "performance_tuning", "workflow_promotion"),
    ) -> dict[str, Any] | None:
        """Pick the highest-value proposal that is safe to hand to the coding agent."""
        await self.refresh_improvement_proposals()
        proposals = await self.long_term.read_improvement_proposals()
        candidates = [
            proposal
            for proposal in proposals
            if proposal.get("status") in allowed_statuses
            and proposal.get("proposal_type") in allowed_types
        ]
        if not candidates:
            return None
        candidates.sort(key=self._proposal_rank, reverse=True)
        return dict(candidates[0])

    async def refresh_improvement_proposals(self) -> list[dict[str, Any]]:
        """Age pending proposals upward and flag repeated escalations for human review."""
        proposals = await self.long_term.read_improvement_proposals()
        now = datetime.now(timezone.utc)
        refreshed: list[dict[str, Any]] = []

        escalation_counts: dict[tuple[str, str, str], int] = {}
        for proposal in proposals:
            if proposal.get("status") != "escalated":
                continue
            key = self._proposal_identity_key(proposal)
            escalation_counts[key] = escalation_counts.get(key, 0) + 1

        for proposal in proposals:
            updates: dict[str, Any] = {}
            created_at = self._parse_timestamp(
                proposal.get("created_at")
                or proposal.get("updated_at")
                or proposal.get("timestamp")
            )
            age_hours = None if created_at is None else (now - created_at).total_seconds() / 3600

            if (
                proposal.get("status") == "pending"
                and age_hours is not None
                and self.proposal_stale_age_hours > 0
                and age_hours >= self.proposal_stale_age_hours
            ):
                current_priority = proposal.get("priority", "low")
                promoted_priority = self._promote_priority(current_priority)
                stale_count = int(proposal.get("stale_count", 0)) + 1
                if promoted_priority != current_priority or stale_count != proposal.get("stale_count", 0):
                    updates["priority"] = promoted_priority
                    updates["stale_count"] = stale_count
                    updates["updated_at"] = now.isoformat()

            escalation_key = self._proposal_identity_key(proposal)
            if (
                proposal.get("status") == "escalated"
                and escalation_counts.get(escalation_key, 0) >= self.human_review_escalation_threshold
            ):
                updates["status"] = "needs_human_review"
                updates["human_review_reason"] = (
                    "Similar self-improvement proposals have escalated repeatedly and now need human review."
                )
                updates["updated_at"] = now.isoformat()

            if updates:
                refreshed_proposal = await self.long_term.update_improvement_proposal(proposal["id"], **updates)
                refreshed.append(refreshed_proposal or dict(proposal, **updates))

        return refreshed

    async def retrieve_lessons(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Find the most relevant stored lessons for a new task."""
        tokens = self._tokens(query)
        query_domain = self._infer_domain(query, "")
        reflections = await self.read_reflections()
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for reflection in reflections:
            keywords = set(reflection.get("keywords", []))
            score = len(tokens & keywords)
            if score == 0 and reflection.get("classification") == "failure" and tokens:
                continue
            if score == 0 and not tokens:
                continue
            domain_bonus = 1 if query_domain and reflection.get("domain") == query_domain else 0
            ranked.append((score, domain_bonus, reflection))
        ranked.sort(key=lambda item: (item[0], item[1], item[2].get("timestamp", "")), reverse=True)
        max_items = limit or self.retrieval_limit
        return [item[2] for item in ranked[:max_items]]

    def _build_reflection(self, record: dict[str, Any], prior_interactions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Derive a lightweight reusable lesson from an interaction record."""
        status = record.get("status", "unknown")
        error_message = record.get("error_message", "")
        latency_seconds = float(record.get("latency_seconds", 0.0))
        timing_breakdown = record.get("timing_breakdown", {})
        hints = self._build_hints(record, prior_interactions or [])
        if status == "success":
            classification = "success"
            lesson = "Successful pattern: reuse this approach for similar requests."
        elif status == "cancelled":
            classification = "partial"
            lesson = "User interrupted the task: keep future responses easier to stop and verify intent sooner."
        else:
            classification = "failure"
            if error_message:
                lesson = f"Failure pattern: avoid repeating this error and validate prerequisites first ({error_message})."
            else:
                lesson = "Failure pattern: add a validation step before repeating this action."

        if latency_seconds >= 5:
            lesson += " Response was slow; prefer fewer steps and lower-latency paths."
        slowest_stage = self._slowest_stage(timing_breakdown)
        if slowest_stage:
            lesson += f" Slowest stage recently: {slowest_stage.replace('_', ' ')}."

        return {
            "id": str(uuid4()),
            "interaction_id": record["id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "classification": classification,
            "lesson": lesson,
            "domain": self._infer_domain(record.get("user_input", ""), record.get("action_summary", "")),
            "keywords": sorted(self._tokens(record.get("user_input", "")) | self._tokens(record.get("action_summary", ""))),
            "hints": hints,
            "source_status": status,
        }

    def _build_improvement_proposals(
        self,
        record: dict[str, Any],
        reflection: dict[str, Any],
        *,
        prior_interactions: list[dict[str, Any]],
        prior_proposals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create reviewable improvement proposals from repeated failures or latency patterns."""
        proposals: list[dict[str, Any]] = []
        user_input = record.get("user_input", "")
        action_summary = record.get("action_summary", "")
        timing_breakdown = record.get("timing_breakdown", {})
        domain = reflection.get("domain", "general")
        repeated_failures = self._count_repeated_failures(record, prior_interactions)
        repeated_successes = self._count_repeated_successes(record, prior_interactions)

        if repeated_failures >= 2:
            proposal_type = "code_change" if domain in {"browser", "coding", "files", "auth"} else "behavior_tuning"
            approval_policy = self._approval_policy_for(proposal_type, domain, priority="high")
            proposals.append(
                {
                    "id": str(uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending",
                    "proposal_type": proposal_type,
                    "domain": domain,
                    "source_interaction_id": record["id"],
                    "trigger": "repeated_failures",
                    "priority": "high",
                    "approval_policy": approval_policy,
                    "title": f"Investigate repeated {domain} failures",
                    "summary": (
                        "Similar tasks have failed repeatedly. Review the failing flow and add a targeted fix "
                        "instead of retrying the same approach."
                    ),
                    "evidence": {
                        "user_input": user_input,
                        "action_summary": action_summary,
                        "error_message": record.get("error_message", ""),
                        "repeated_failures": repeated_failures,
                    },
                    "suggested_scope": self._suggest_scope(domain, action_summary),
                    "suggested_hints": [hint["value"] for hint in reflection.get("hints", [])],
                    "execution_history": [],
                    "attempt_count": 0,
                }
            )

        if float(record.get("latency_seconds", 0.0)) >= 5:
            slowest_stage = self._slowest_stage(timing_breakdown)
            approval_policy = self._approval_policy_for("performance_tuning", domain, priority="medium")
            proposals.append(
                {
                    "id": str(uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending",
                    "proposal_type": "performance_tuning",
                    "domain": domain,
                    "source_interaction_id": record["id"],
                    "trigger": "slow_task",
                    "priority": "medium",
                    "approval_policy": approval_policy,
                    "title": f"Reduce latency in {domain} flow",
                    "summary": (
                        "This task was noticeably slow. Review the slowest stage and trim context, actions, "
                        "or response length before attempting deeper architectural changes."
                    ),
                    "evidence": {
                        "user_input": user_input,
                        "action_summary": action_summary,
                        "latency_seconds": record.get("latency_seconds", 0.0),
                        "slowest_stage": slowest_stage,
                        "timing_breakdown": timing_breakdown,
                    },
                    "suggested_scope": self._suggest_scope(domain, action_summary),
                    "suggested_hints": [hint["value"] for hint in reflection.get("hints", []) if hint.get("type") == "performance"],
                    "execution_history": [],
                    "attempt_count": 0,
                }
            )

        if repeated_successes >= 2:
            chain_steps = self._extract_chain_steps(action_summary)
            if len(chain_steps) >= 2:
                approval_policy = self._approval_policy_for("workflow_promotion", domain, priority="low")
                proposals.append(
                    {
                        "id": str(uuid4()),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "status": "pending",
                        "proposal_type": "workflow_promotion",
                        "domain": domain,
                        "source_interaction_id": record["id"],
                        "trigger": "repeated_success_chain",
                        "priority": "low",
                        "approval_policy": approval_policy,
                        "title": f"Promote stable {domain} workflow",
                        "summary": (
                            "A similar multi-step workflow has succeeded repeatedly. Consider promoting it into "
                            "a stronger built-in heuristic or planner rule."
                        ),
                        "evidence": {
                            "user_input": user_input,
                            "action_summary": action_summary,
                            "repeated_successes": repeated_successes + 1,
                            "chain": " -> ".join(chain_steps),
                        },
                        "suggested_scope": self._suggest_scope(domain, action_summary),
                        "suggested_hints": [hint["value"] for hint in reflection.get("hints", []) if hint.get("type") in {"chain", "pattern"}],
                        "execution_history": [],
                        "attempt_count": 0,
                    }
                )

        return self._dedupe_proposals(
            proposals,
            prior_interactions=prior_interactions,
            prior_proposals=prior_proposals,
        )

    def _tokens(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text.lower())
            if token not in self._STOP_WORDS
        }

    def _build_hints(self, record: dict[str, Any], prior_interactions: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Turn a reflection into small structured planning hints."""
        status = record.get("status", "unknown")
        error_message = record.get("error_message", "").lower()
        latency_seconds = float(record.get("latency_seconds", 0.0))
        user_input = record.get("user_input", "").lower()
        action_summary = record.get("action_summary", "").lower()
        timing_breakdown = record.get("timing_breakdown", {})
        repeated_failures = self._count_repeated_failures(record, prior_interactions)
        repeated_successes = self._count_repeated_successes(record, prior_interactions)
        hints: list[dict[str, str]] = []

        if status == "cancelled":
            hints.append(
                {
                    "type": "interaction_style",
                    "value": "confirm_early",
                    "reason": "User interrupted a prior task, so verify intent earlier and keep the response interruptible.",
                }
            )
        if status == "error":
            hints.append(
                {
                    "type": "validation",
                    "value": "validate_prerequisites",
                    "reason": "A similar task failed before; check required inputs before acting.",
                }
            )
        if "selector" in error_message or "browser" in user_input:
            hints.append(
                {
                    "type": "browser",
                    "value": "wait_for_page_and_retry_selector",
                    "reason": "Browser-related tasks should wait for page readiness before selector lookup.",
                }
            )
        if "credential" in error_message or "login" in user_input:
            hints.append(
                {
                    "type": "auth",
                    "value": "ask_for_credentials_first",
                    "reason": "Authentication flows should confirm credentials availability before attempting login.",
                }
            )
        if latency_seconds >= 5:
            hints.append(
                {
                    "type": "performance",
                    "value": "prefer_lower_latency_path",
                    "reason": "A similar task was slow, so keep the next attempt shorter and more direct.",
                }
            )
        if float(timing_breakdown.get("planning_seconds", 0.0)) >= 2:
            hints.append(
                {
                    "type": "performance",
                    "value": "simplify_planning_context",
                    "reason": "Planning was slow before, so reduce extra prompt context and avoid unnecessary subtasks.",
                }
            )
        if float(timing_breakdown.get("execution_seconds", 0.0)) >= 3:
            hints.append(
                {
                    "type": "performance",
                    "value": "prefer_fewer_actions",
                    "reason": "Execution was the slowest part before, so prefer shorter action chains when possible.",
                }
            )
        if float(timing_breakdown.get("tts_seconds", 0.0)) >= 2:
            hints.append(
                {
                    "type": "performance",
                    "value": "keep_response_brief",
                    "reason": "Speech playback took a while before, so keep spoken responses concise when possible.",
                }
            )
        if repeated_failures >= 2:
            hints.append(
                {
                    "type": "reliability",
                    "value": "escalate_after_repeated_failures",
                    "reason": "Similar tasks have failed repeatedly, so ask for clarification or change approach before retrying.",
                }
            )
        if repeated_failures >= 1 and self._looks_risky(f"{user_input} {action_summary}"):
            hints.append(
                {
                    "type": "risk",
                    "value": "clarify_before_risky_action",
                    "reason": "A similar risky action has failed before, so confirm the exact target and intent first.",
                }
            )

        if status == "success":
            hints.append(
                {
                    "type": "pattern",
                    "value": "reuse_successful_approach",
                    "reason": "A similar task completed successfully before.",
                }
            )
            chain_steps = self._extract_chain_steps(record.get("action_summary", ""))
            if len(chain_steps) >= 2:
                domain = self._infer_domain(record.get("user_input", ""), record.get("action_summary", ""))
                hints.append(
                    {
                        "type": "chain",
                        "value": "reuse_action_chain",
                        "reason": "A similar request succeeded with this action order before.",
                        "chain": " -> ".join(chain_steps),
                        "strength": str(repeated_successes + 1),
                        "domain": domain,
                    }
                )

        return hints

    def _count_repeated_failures(self, record: dict[str, Any], prior_interactions: list[dict[str, Any]]) -> int:
        """Count prior failed interactions that look similar to the current one."""
        current_tokens = self._tokens(
            f"{record.get('user_input', '')} {record.get('action_summary', '')}"
        )
        if not current_tokens:
            return 0

        failures = 0
        for interaction in prior_interactions:
            if interaction.get("status") not in {"error", "cancelled"}:
                continue
            prior_tokens = self._tokens(
                f"{interaction.get('user_input', '')} {interaction.get('action_summary', '')}"
            )
            if len(current_tokens & prior_tokens) >= 2:
                failures += 1
        return failures

    def _looks_risky(self, text: str) -> bool:
        """Heuristic for actions that should prefer explicit clarification."""
        risky_terms = {
            "delete",
            "remove",
            "erase",
            "sudo",
            "login",
            "log in",
            "sign in",
            "email",
            "overwrite",
            "replace",
        }
        return any(term in text for term in risky_terms)

    def _extract_chain_steps(self, action_summary: str) -> list[str]:
        """Extract ordered action types from a compact action summary."""
        steps: list[str] = []
        for chunk in action_summary.split("->"):
            part = chunk.strip()
            if not part or ":" not in part:
                continue
            action_type = part.split(":", 1)[0].strip()
            if action_type and action_type not in {"planner", "executor", "agent_run"}:
                steps.append(action_type)
        return steps

    def _count_repeated_successes(self, record: dict[str, Any], prior_interactions: list[dict[str, Any]]) -> int:
        """Count prior successful interactions that reused the same action chain."""
        current_chain = self._extract_chain_steps(record.get("action_summary", ""))
        if len(current_chain) < 2:
            return 0

        current_tokens = self._tokens(record.get("user_input", ""))
        successes = 0
        for interaction in prior_interactions:
            if interaction.get("status") != "success":
                continue
            prior_chain = self._extract_chain_steps(interaction.get("action_summary", ""))
            if prior_chain != current_chain:
                continue
            prior_tokens = self._tokens(interaction.get("user_input", ""))
            if not current_tokens or len(current_tokens & prior_tokens) >= 1:
                successes += 1
        return successes

    def _infer_domain(self, user_input: str, action_summary: str) -> str:
        """Infer a coarse task domain for ranking reusable chains."""
        text = f"{user_input} {action_summary}".lower()
        domain_terms = {
            "browser": {"browser", "site", "web", "page", "navigate", "selector"},
            "weather": {"weather", "forecast", "temperature"},
            "email": {"email", "mail", "inbox", "send_email", "check_email"},
            "todo": {"task", "todo", "reminder", "list_tasks", "add_task"},
            "coding": {"code", "repo", "test", "write_file", "run_tests", "coding"},
            "files": {"file", "delete_file", "read_file", "write_file", "move_file"},
            "auth": {"login", "log in", "sign in", "credential", "browser_login"},
        }
        for domain, terms in domain_terms.items():
            if any(term in text for term in terms):
                return domain
        return "general"

    def _normalize_timings(self, timing_breakdown: dict[str, float]) -> dict[str, float]:
        """Round timing metrics for durable storage."""
        normalized: dict[str, float] = {}
        for key, value in timing_breakdown.items():
            try:
                normalized[key] = round(float(value), 3)
            except (TypeError, ValueError):
                continue
        return normalized

    def _slowest_stage(self, timing_breakdown: dict[str, Any]) -> str:
        """Return the slowest named stage, excluding the total aggregate."""
        filtered = {
            key: float(value)
            for key, value in timing_breakdown.items()
            if key != "total_seconds"
        }
        if not filtered:
            return ""
        return max(filtered, key=filtered.get)

    def _suggest_scope(self, domain: str, action_summary: str) -> list[str]:
        """Map a domain or action trace to the most likely modules to inspect."""
        scope_map = {
            "browser": ["browser/", "agents/executor.py", "agents/planner.py"],
            "coding": ["agents/coding_agent.py", "agents/agent_manager.py"],
            "files": ["actions/file_actions.py", "actions/safety.py"],
            "auth": ["browser/", "browser/login_handler.py", "agents/executor.py"],
            "email": ["actions/email_actions.py", "agents/executor.py"],
            "todo": ["actions/todo_actions.py", "agents/planner.py"],
            "weather": ["actions/weather_actions.py", "agents/planner.py"],
            "general": ["agents/planner.py", "agents/executor.py", "memory/self_improvement.py"],
        }
        scope = list(scope_map.get(domain, scope_map["general"]))
        if "voice" in action_summary.lower() and "voice/" not in scope:
            scope.append("voice/")
        return scope

    def _dedupe_proposals(
        self,
        proposals: list[dict[str, Any]],
        *,
        prior_interactions: list[dict[str, Any]],
        prior_proposals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Suppress identical proposals when a similar one already exists very recently."""
        del prior_interactions  # reserved for future ranking against recency windows
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        recent_existing = self._recent_proposal_keys(prior_proposals)
        for proposal in proposals:
            key = (
                proposal.get("proposal_type", ""),
                proposal.get("domain", ""),
                proposal.get("trigger", ""),
            )
            if key in seen:
                continue
            if key in recent_existing:
                continue
            seen.add(key)
            deduped.append(proposal)
        return deduped

    def _recent_proposal_keys(self, prior_proposals: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
        """Return proposal identity keys still inside the duplicate-suppression cooldown window."""
        if self.proposal_cooldown_hours <= 0:
            return set()

        now = datetime.now(timezone.utc)
        recent: set[tuple[str, str, str]] = set()
        for proposal in prior_proposals:
            created_at = self._parse_timestamp(
                proposal.get("created_at")
                or proposal.get("updated_at")
                or proposal.get("timestamp")
            )
            if created_at is None:
                continue
            age_hours = (now - created_at).total_seconds() / 3600
            if age_hours > self.proposal_cooldown_hours:
                continue
            recent.add(
                (
                    proposal.get("proposal_type", ""),
                    proposal.get("domain", ""),
                    proposal.get("trigger", ""),
                )
            )
        return recent

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """Parse an ISO timestamp into an aware datetime."""
        if not value or not isinstance(value, str):
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _proposal_rank(self, proposal: dict[str, Any]) -> tuple[int, int, str]:
        """Prefer high-priority proposals, then broader code-impact types, then recency."""
        priority_rank = {"high": 3, "medium": 2, "low": 1}
        type_rank = {"code_change": 3, "performance_tuning": 2, "workflow_promotion": 1}
        return (
            priority_rank.get(proposal.get("priority", "low"), 0),
            type_rank.get(proposal.get("proposal_type", ""), 0),
            proposal.get("created_at", ""),
        )

    def _approval_policy_for(self, proposal_type: str, domain: str, *, priority: str) -> dict[str, Any]:
        """Define whether a proposal may run automatically or needs explicit human approval."""
        risky_domains = {"browser", "auth", "files", "coding"}
        if proposal_type == "code_change":
            return {
                "mode": "manual",
                "requires_human_approval": True,
                "reason": "Code-change proposals require explicit approval before IRIS edits the repo.",
            }
        if proposal_type == "performance_tuning" and domain in risky_domains:
            return {
                "mode": "manual",
                "requires_human_approval": True,
                "reason": "This performance proposal touches a higher-risk domain and should be reviewed first.",
            }
        if proposal_type == "workflow_promotion" and priority == "low":
            return {
                "mode": "auto_eligible",
                "requires_human_approval": False,
                "reason": "Low-risk workflow promotions can be auto-eligible after review.",
            }
        return {
            "mode": "manual",
            "requires_human_approval": True,
            "reason": "This proposal should be reviewed before execution.",
        }

    def _promote_priority(self, priority: str) -> str:
        """Promote a proposal priority by one level, capping at high."""
        if priority == "low":
            return "medium"
        if priority == "medium":
            return "high"
        return "high"

    def _proposal_identity_key(self, proposal: dict[str, Any]) -> tuple[str, str, str]:
        """Return the stable identity key used for dedupe and escalation grouping."""
        return (
            proposal.get("proposal_type", ""),
            proposal.get("domain", ""),
            proposal.get("trigger", ""),
        )
