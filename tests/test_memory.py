"""Tests for Aryan's memory modules."""

from __future__ import annotations

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
