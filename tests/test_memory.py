"""Tests for Aryan's memory modules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from memory.memory_manager import MemoryManager
from memory.short_term import ShortTermMemory


class MemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_term_memory_honors_limit(self) -> None:
        memory = ShortTermMemory(limit=2)
        await memory.add({"content": "one"})
        await memory.add({"content": "two"})
        await memory.add({"content": "three"})
        messages = await memory.get_messages()
        self.assertEqual([item["content"] for item in messages], ["two", "three"])

    async def test_memory_manager_stores_and_retrieves_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            await manager.store("user", "Aryan likes offline models", tags=["preference"])
            await manager.store("user", "Aradhya owns the overlay work", tags=["team"])

            context = await manager.retrieve_context("offline models", top_k=1)
            self.assertEqual(len(context), 1)
            self.assertIn("offline", context[0]["text"])

            prompt = await manager.inject_into_prompt([{"role": "user", "content": "use offline models"}])
            self.assertEqual(prompt[0]["role"], "system")
            self.assertIn("Relevant memory context", prompt[0]["content"])

    async def test_memory_manager_learns_habits_and_graph_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            await manager.learn_habit("open music", "launch spotify")
            await manager.store("user", "Aryan discussed ProjectIris planning", tags=["planning"])

            context = await manager.retrieve_context("please open music")
            self.assertTrue(any(item["metadata"].get("type") == "habit" for item in context))

            graph_context = await manager.retrieve_context("ProjectIris")
            self.assertTrue(any(item["metadata"].get("type") == "graph" for item in graph_context))

    async def test_memory_manager_records_completed_interactions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="open the browser",
                response="Opening the browser now.",
                status="success",
                latency_seconds=1.2345,
                action_summary="agent_run:success",
                timing_breakdown={"planning_seconds": 0.25, "execution_seconds": 0.5, "tts_seconds": 0.2, "total_seconds": 1.2345},
            )

            interactions = await manager.read_interactions()
            self.assertEqual(len(interactions), 1)
            self.assertEqual(interactions[0]["user_input"], "open the browser")
            self.assertEqual(interactions[0]["status"], "success")
            self.assertEqual(interactions[0]["latency_seconds"], 1.234)
            self.assertEqual(interactions[0]["timing_breakdown"]["planning_seconds"], 0.25)
            self.assertEqual(interactions[0]["timing_breakdown"]["total_seconds"], 1.234)

            reflections = await manager.read_reflections()
            self.assertEqual(len(reflections), 1)
            self.assertEqual(reflections[0]["classification"], "success")
            self.assertTrue(reflections[0]["lesson"].startswith("Successful pattern"))
            self.assertTrue(
                any(hint["value"] == "reuse_successful_approach" for hint in reflections[0]["hints"])
            )

    async def test_memory_manager_generates_reusable_action_chain_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="check weather in browser",
                response="Done.",
                status="success",
                latency_seconds=1.0,
                action_summary="browser:ok -> get_weather:ok",
            )

            reflections = await manager.read_reflections()
            latest = reflections[-1]
            chain_hints = [hint for hint in latest["hints"] if hint["type"] == "chain"]
            self.assertEqual(len(chain_hints), 1)
            self.assertEqual(chain_hints[0]["value"], "reuse_action_chain")
            self.assertEqual(chain_hints[0]["chain"], "browser -> get_weather")
            self.assertEqual(chain_hints[0]["strength"], "1")
            self.assertEqual(chain_hints[0]["domain"], "browser")

            planning_hints = await manager.get_planning_hints("weather in browser")
            self.assertTrue(any(hint.get("chain") == "browser -> get_weather" for hint in planning_hints))

    async def test_memory_manager_scores_repeated_successful_chains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="check weather in browser",
                response="Done.",
                status="success",
                latency_seconds=1.0,
                action_summary="browser:ok -> get_weather:ok",
            )
            await manager.record_interaction(
                user_input="check weather in browser again",
                response="Done.",
                status="success",
                latency_seconds=0.9,
                action_summary="browser:ok -> get_weather:ok",
            )

            reflections = await manager.read_reflections()
            latest = reflections[-1]
            chain_hint = next(hint for hint in latest["hints"] if hint["type"] == "chain")
            self.assertEqual(chain_hint["strength"], "2")

    async def test_memory_manager_injects_relevant_lessons_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="open browser and check weather",
                response="Sorry, something went wrong.",
                status="error",
                latency_seconds=6.1,
                action_summary="agent_run:error browser weather",
                error_message="selector timeout",
                timing_breakdown={
                    "planning_seconds": 2.2,
                    "execution_seconds": 3.5,
                    "tts_seconds": 2.1,
                    "total_seconds": 6.1,
                },
            )

            prompt = await manager.inject_into_prompt(
                [{"role": "user", "content": "check weather in browser"}]
            )

            self.assertGreaterEqual(len(prompt), 2)
            self.assertEqual(prompt[0]["role"], "system")
            joined = "\n".join(item["content"] for item in prompt if item["role"] == "system")
            self.assertIn("Relevant lessons from past interactions", joined)
            self.assertIn("selector timeout", joined)
            self.assertIn("Reusable planning hints", joined)
            self.assertIn("wait_for_page_and_retry_selector", joined)
            self.assertIn("prefer_lower_latency_path", joined)
            self.assertIn("prefer_fewer_actions", joined)
            self.assertIn("keep_response_brief", joined)

    async def test_memory_manager_injects_action_chain_hints_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="check weather in browser",
                response="Done.",
                status="success",
                latency_seconds=1.0,
                action_summary="browser:ok -> get_weather:ok",
            )

            prompt = await manager.inject_into_prompt(
                [{"role": "user", "content": "please check weather in browser"}]
            )
            joined = "\n".join(item["content"] for item in prompt if item["role"] == "system")
            self.assertIn("Preferred order: browser -> get_weather", joined)
            self.assertIn("Strength: 1", joined)
            self.assertIn("Domain: browser", joined)

    async def test_memory_manager_prefers_domain_matched_stronger_chain_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="check weather in browser",
                response="Done.",
                status="success",
                latency_seconds=1.0,
                action_summary="browser:ok -> get_weather:ok",
            )
            await manager.record_interaction(
                user_input="check weather in browser tomorrow",
                response="Done.",
                status="success",
                latency_seconds=0.9,
                action_summary="browser:ok -> get_weather:ok",
            )
            await manager.record_interaction(
                user_input="list my tasks",
                response="Done.",
                status="success",
                latency_seconds=0.8,
                action_summary="list_tasks:ok -> add_task:ok",
            )

            planning_hints = await manager.get_planning_hints("weather in browser")
            self.assertEqual(planning_hints[0]["type"], "chain")
            self.assertEqual(planning_hints[0]["chain"], "browser -> get_weather")
            self.assertEqual(planning_hints[0]["strength"], "2")

    async def test_memory_manager_generates_repeated_failure_risk_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="delete the old deployment file",
                response="Sorry, something went wrong.",
                status="error",
                latency_seconds=1.2,
                action_summary="delete_file target deployment",
                error_message="permission denied",
            )
            await manager.record_interaction(
                user_input="delete the old deployment file",
                response="Sorry, something went wrong.",
                status="error",
                latency_seconds=1.1,
                action_summary="delete_file target deployment",
                error_message="permission denied",
            )
            await manager.record_interaction(
                user_input="delete the old deployment file",
                response="Sorry, something went wrong.",
                status="error",
                latency_seconds=1.0,
                action_summary="delete_file target deployment",
                error_message="permission denied",
            )

            reflections = await manager.read_reflections()
            latest = reflections[-1]
            hint_values = {hint["value"] for hint in latest["hints"]}
            self.assertIn("escalate_after_repeated_failures", hint_values)
            self.assertIn("clarify_before_risky_action", hint_values)
            proposals = await manager.read_improvement_proposals()
            self.assertTrue(any(proposal["trigger"] == "repeated_failures" for proposal in proposals))
            repeated_failure_proposal = next(
                proposal for proposal in proposals if proposal["trigger"] == "repeated_failures"
            )
            self.assertEqual(repeated_failure_proposal["proposal_type"], "code_change")
            self.assertEqual(repeated_failure_proposal["priority"], "high")
            self.assertTrue(repeated_failure_proposal["approval_policy"]["requires_human_approval"])

    async def test_memory_manager_generates_stage_specific_performance_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="summarize the latest browser results",
                response="Here is the summary.",
                status="success",
                latency_seconds=6.2,
                action_summary="browser:ok -> voice:ok",
                timing_breakdown={
                    "planning_seconds": 2.4,
                    "execution_seconds": 3.4,
                    "tts_seconds": 2.2,
                    "total_seconds": 6.2,
                },
            )

            reflections = await manager.read_reflections()
            latest = reflections[-1]
            hint_values = {hint["value"] for hint in latest["hints"]}
            self.assertIn("simplify_planning_context", hint_values)
            self.assertIn("prefer_fewer_actions", hint_values)
            self.assertIn("keep_response_brief", hint_values)
            self.assertIn("execution seconds", latest["lesson"].lower())
            proposals = await manager.read_improvement_proposals(status="pending")
            performance_proposal = next(
                proposal for proposal in proposals if proposal["trigger"] == "slow_task"
            )
            self.assertEqual(performance_proposal["proposal_type"], "performance_tuning")
            self.assertEqual(performance_proposal["evidence"]["slowest_stage"], "execution_seconds")
            self.assertIn("voice/", performance_proposal["suggested_scope"])
            self.assertTrue(performance_proposal["approval_policy"]["requires_human_approval"])

    async def test_memory_manager_queues_workflow_promotion_proposal_for_repeated_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            await manager.record_interaction(
                user_input="check weather in browser",
                response="Done.",
                status="success",
                latency_seconds=1.0,
                action_summary="browser:ok -> get_weather:ok",
            )
            await manager.record_interaction(
                user_input="check weather in browser again",
                response="Done.",
                status="success",
                latency_seconds=0.9,
                action_summary="browser:ok -> get_weather:ok",
            )
            await manager.record_interaction(
                user_input="check weather in browser tomorrow",
                response="Done.",
                status="success",
                latency_seconds=0.8,
                action_summary="browser:ok -> get_weather:ok",
            )

            proposals = await manager.read_improvement_proposals(status="pending")
            workflow_proposal = next(
                proposal for proposal in proposals if proposal["trigger"] == "repeated_success_chain"
            )
            self.assertEqual(workflow_proposal["proposal_type"], "workflow_promotion")
            self.assertEqual(workflow_proposal["domain"], "browser")
            self.assertEqual(workflow_proposal["evidence"]["chain"], "browser -> get_weather")
            self.assertEqual(workflow_proposal["priority"], "low")
            self.assertEqual(workflow_proposal["approval_policy"]["mode"], "auto_eligible")

    async def test_memory_manager_selects_next_pending_proposal_for_coding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            for _ in range(3):
                await manager.record_interaction(
                    user_input="delete the old deployment file",
                    response="Sorry, something went wrong.",
                    status="error",
                    latency_seconds=1.0,
                    action_summary="delete_file target deployment",
                    error_message="permission denied",
                )

            next_proposal = await manager.select_next_proposal_for_coding()
            self.assertIsNotNone(next_proposal)
            self.assertEqual(next_proposal["trigger"], "repeated_failures")
            self.assertEqual(next_proposal["priority"], "high")

            updated = await manager.update_improvement_proposal(next_proposal["id"], status="in_progress")
            self.assertEqual(updated["status"], "in_progress")
            refreshed = await manager.read_improvement_proposals()
            self.assertEqual(refreshed[0]["status"], "in_progress")

    async def test_memory_manager_appends_execution_history_to_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            for _ in range(3):
                await manager.record_interaction(
                    user_input="delete the old deployment file",
                    response="Sorry, something went wrong.",
                    status="error",
                    latency_seconds=1.0,
                    action_summary="delete_file target deployment",
                    error_message="permission denied",
                )

            proposal = await manager.select_next_proposal_for_coding()
            await manager.append_improvement_proposal_history(
                proposal["id"],
                {"event": "started", "status": "in_progress", "message": "Proposal execution started."},
            )
            await manager.append_improvement_proposal_history(
                proposal["id"],
                {"event": "finished", "status": "completed", "message": "Applied fix."},
            )

            refreshed = await manager.read_improvement_proposals()
            self.assertEqual(refreshed[0]["attempt_count"], 2)
            self.assertEqual(refreshed[0]["execution_history"][0]["event"], "started")
            self.assertEqual(refreshed[0]["execution_history"][-1]["event"], "finished")

    async def test_memory_manager_suppresses_duplicate_proposals_within_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "improvement_proposal_cooldown_hours": 24,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            for _ in range(3):
                await manager.record_interaction(
                    user_input="delete the old deployment file",
                    response="Sorry, something went wrong.",
                    status="error",
                    latency_seconds=1.0,
                    action_summary="delete_file target deployment",
                    error_message="permission denied",
                )
            proposals_after_first_wave = await manager.read_improvement_proposals()
            self.assertEqual(len([p for p in proposals_after_first_wave if p["trigger"] == "repeated_failures"]), 1)

            for _ in range(3):
                await manager.record_interaction(
                    user_input="delete the old deployment file",
                    response="Sorry, something went wrong.",
                    status="error",
                    latency_seconds=1.0,
                    action_summary="delete_file target deployment",
                    error_message="permission denied",
                )
            proposals_after_second_wave = await manager.read_improvement_proposals()
            self.assertEqual(len([p for p in proposals_after_second_wave if p["trigger"] == "repeated_failures"]), 1)

    async def test_memory_manager_allows_repeat_proposals_when_cooldown_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "improvement_proposal_cooldown_hours": 0,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)

            for _ in range(3):
                await manager.record_interaction(
                    user_input="delete the old deployment file",
                    response="Sorry, something went wrong.",
                    status="error",
                    latency_seconds=1.0,
                    action_summary="delete_file target deployment",
                    error_message="permission denied",
                )
            for _ in range(3):
                await manager.record_interaction(
                    user_input="delete the old deployment file",
                    response="Sorry, something went wrong.",
                    status="error",
                    latency_seconds=1.0,
                    action_summary="delete_file target deployment",
                    error_message="permission denied",
                )

            proposals = await manager.read_improvement_proposals()
            self.assertGreaterEqual(len([p for p in proposals if p["trigger"] == "repeated_failures"]), 2)

    async def test_memory_manager_ages_stale_pending_proposals_upward(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "improvement_proposal_stale_age_hours": 1,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
            await manager.long.save_improvement_proposal(
                {
                    "id": "stale-1",
                    "created_at": stale_time,
                    "status": "pending",
                    "proposal_type": "workflow_promotion",
                    "domain": "browser",
                    "trigger": "repeated_success_chain",
                    "priority": "low",
                    "title": "Promote stable browser workflow",
                }
            )

            refreshed = await manager.refresh_improvement_proposals()
            self.assertEqual(len(refreshed), 1)
            proposals = await manager.read_improvement_proposals()
            self.assertEqual(proposals[0]["priority"], "medium")
            self.assertEqual(proposals[0]["stale_count"], 1)

    async def test_memory_manager_flags_repeated_escalations_for_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "improvement_human_review_escalation_threshold": 2,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            now = datetime.now(timezone.utc).isoformat()
            for index in range(2):
                await manager.long.save_improvement_proposal(
                    {
                        "id": f"esc-{index}",
                        "created_at": now,
                        "status": "escalated",
                        "proposal_type": "code_change",
                        "domain": "browser",
                        "trigger": "repeated_failures",
                        "priority": "high",
                        "title": "Investigate repeated browser failures",
                    }
                )

            refreshed = await manager.refresh_improvement_proposals()
            self.assertEqual(len(refreshed), 2)
            proposals = await manager.read_improvement_proposals()
            self.assertTrue(all(proposal["status"] == "needs_human_review" for proposal in proposals))
            self.assertIn("human review", proposals[0]["human_review_reason"].lower())

    async def test_memory_manager_marks_completed_proposal_as_regressed_after_similar_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "improvement_proposal_cooldown_hours": 0,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            created_at = datetime.now(timezone.utc).isoformat()
            await manager.long.save_improvement_proposal(
                {
                    "id": "completed-1",
                    "created_at": created_at,
                    "status": "completed",
                    "proposal_type": "code_change",
                    "domain": "browser",
                    "trigger": "repeated_failures",
                    "priority": "high",
                    "title": "Investigate repeated browser failures",
                    "summary": "Tighten browser flow.",
                    "evidence": {
                        "user_input": "check weather in browser",
                        "action_summary": "browser:error selector timeout",
                        "error_message": "selector timeout",
                    },
                    "execution_history": [],
                    "attempt_count": 0,
                }
            )

            for _ in range(3):
                await manager.record_interaction(
                    user_input="check weather in browser",
                    response="Sorry, something went wrong.",
                    status="error",
                    latency_seconds=1.0,
                    action_summary="browser:error selector timeout",
                    error_message="selector timeout",
                )

            proposals = await manager.read_improvement_proposals()
            regressed = next(proposal for proposal in proposals if proposal["id"] == "completed-1")
            self.assertEqual(regressed["status"], "regressed")
            self.assertEqual(regressed["regression_count"], 1)
            self.assertEqual(regressed["execution_history"][-1]["event"], "regression_detected")

            new_failure_proposal = next(
                proposal for proposal in proposals
                if proposal.get("id") != "completed-1" and proposal["trigger"] == "repeated_failures"
            )
            self.assertTrue(new_failure_proposal["regression_detected"])
            self.assertIn("completed-1", new_failure_proposal["related_regressed_proposal_ids"])
            self.assertTrue(new_failure_proposal["approval_policy"]["requires_human_approval"])
            self.assertIn("regressed", new_failure_proposal["approval_policy"]["reason"].lower())

    async def test_memory_manager_scores_proposal_outcomes_from_execution_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            now = datetime.now(timezone.utc).isoformat()
            await manager.long.save_improvement_proposal(
                {
                    "id": "workflow-1",
                    "created_at": now,
                    "status": "completed",
                    "proposal_type": "workflow_promotion",
                    "domain": "browser",
                    "trigger": "repeated_success_chain",
                    "priority": "low",
                    "title": "Promote weather workflow",
                    "execution_history": [
                        {"event": "started", "status": "in_progress"},
                        {"event": "finished", "status": "completed", "message": "Applied fix."},
                    ],
                    "attempt_count": 2,
                }
            )

            await manager.refresh_improvement_proposals()
            proposals = await manager.read_improvement_proposals()
            scored = proposals[0]
            self.assertGreater(scored["outcome_score"], 0)
            self.assertGreater(scored["outcome_confidence"], 0.0)
            self.assertEqual(scored["last_outcome_status"], "completed")
            self.assertEqual(scored["outcome_summary"]["successful_runs"], 1)
            self.assertEqual(scored["outcome_summary"]["failed_runs"], 0)

    async def test_memory_manager_penalizes_regressed_proposal_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            now = datetime.now(timezone.utc).isoformat()
            await manager.long.save_improvement_proposal(
                {
                    "id": "completed-good",
                    "created_at": now,
                    "status": "completed",
                    "proposal_type": "workflow_promotion",
                    "domain": "browser",
                    "trigger": "repeated_success_chain",
                    "priority": "low",
                    "title": "Promote browser workflow",
                    "execution_history": [
                        {"event": "finished", "status": "completed"},
                    ],
                    "attempt_count": 1,
                }
            )
            await manager.long.save_improvement_proposal(
                {
                    "id": "regressed-1",
                    "created_at": now,
                    "status": "regressed",
                    "proposal_type": "workflow_promotion",
                    "domain": "browser",
                    "trigger": "repeated_success_chain",
                    "priority": "low",
                    "title": "Promote browser workflow",
                    "execution_history": [
                        {"event": "finished", "status": "completed"},
                        {"event": "regression_detected", "status": "regressed"},
                    ],
                    "regression_count": 1,
                    "attempt_count": 1,
                }
            )

            await manager.refresh_improvement_proposals()
            proposals = {proposal["id"]: proposal for proposal in await manager.read_improvement_proposals()}
            self.assertLess(proposals["regressed-1"]["outcome_score"], proposals["completed-good"]["outcome_score"])
            self.assertEqual(proposals["regressed-1"]["last_outcome_status"], "regressed")

    async def test_memory_manager_prefers_pending_proposal_with_better_outcome_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "short_term_limit": 5,
                "top_k_retrieval": 2,
                "habit_retrieval_limit": 2,
                "interaction_retrieval_limit": 5,
                "chroma_path": str(Path(tmp) / ".chroma"),
                "embedding_model": "BAAI/bge-m3",
                "long_term_path": str(Path(tmp) / "memory.json"),
            }
            manager = MemoryManager(config)
            now = datetime.now(timezone.utc).isoformat()
            await manager.long.save_improvement_proposal(
                {
                    "id": "workflow-good",
                    "created_at": now,
                    "status": "pending",
                    "proposal_type": "workflow_promotion",
                    "domain": "browser",
                    "trigger": "repeated_success_chain",
                    "priority": "low",
                    "title": "Promote stable browser workflow",
                    "execution_history": [
                        {"event": "finished", "status": "completed"},
                    ],
                    "attempt_count": 1,
                }
            )
            await manager.long.save_improvement_proposal(
                {
                    "id": "workflow-bad",
                    "created_at": now,
                    "status": "pending",
                    "proposal_type": "workflow_promotion",
                    "domain": "browser",
                    "trigger": "repeated_success_chain",
                    "priority": "low",
                    "title": "Promote unstable browser workflow",
                    "execution_history": [
                        {"event": "finished", "status": "escalated"},
                    ],
                    "attempt_count": 1,
                }
            )

            next_proposal = await manager.self_improvement.select_next_proposal_for_coding(
                allowed_types=("workflow_promotion",),
            )
            self.assertIsNotNone(next_proposal)
            self.assertEqual(next_proposal["id"], "workflow-good")
