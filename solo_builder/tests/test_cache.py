"""Unit tests for solo_builder/runners/cache.py and related integrations.

Covers:
  - ResponseCache.make_key / get / set / clear / size
  - AnthropicRunner cache hit (skips API) and miss (calls API, stores result)
  - AnthropicRunner.arun cache hit
  - Executor CLAUDE_LOCAL=1 routing
  - make_cache() respects NOCACHE=1
"""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure solo_builder/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.cache import ResponseCache, make_cache
from runners.anthropic_runner import AnthropicRunner


# ═══════════════════════════════════════════════════════════════════════════════
# ResponseCache
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseCache(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.cache = ResponseCache(cache_dir=self._tmp)

    def tearDown(self):
        self.cache.clear()

    # ── make_key ─────────────────────────────────────────────────────────────

    def test_make_key_deterministic(self):
        k1 = ResponseCache.make_key("hello world")
        k2 = ResponseCache.make_key("hello world")
        self.assertEqual(k1, k2)

    def test_make_key_differs_for_different_inputs(self):
        k1 = ResponseCache.make_key("prompt A")
        k2 = ResponseCache.make_key("prompt B")
        self.assertNotEqual(k1, k2)

    def test_make_key_composite_differs_from_single(self):
        k1 = ResponseCache.make_key("prompt")
        k2 = ResponseCache.make_key("prompt", "tools")
        self.assertNotEqual(k1, k2)

    def test_make_key_is_hex_string(self):
        k = ResponseCache.make_key("test")
        self.assertEqual(len(k), 64)           # SHA-256 = 32 bytes = 64 hex chars
        int(k, 16)                             # should not raise

    # ── get / set ─────────────────────────────────────────────────────────────

    def test_get_returns_none_on_miss(self):
        self.assertIsNone(self.cache.get("nonexistent_key"))

    def test_set_and_get_roundtrip(self):
        key = ResponseCache.make_key("my prompt")
        self.cache.set(key, "my response")
        self.assertEqual(self.cache.get(key), "my response")

    def test_set_overwrites_existing_entry(self):
        key = ResponseCache.make_key("prompt")
        self.cache.set(key, "first")
        self.cache.set(key, "second")
        self.assertEqual(self.cache.get(key), "second")

    def test_get_returns_none_for_corrupted_file(self):
        key = "deadbeef" * 8
        path = Path(self._tmp) / f"{key}.json"
        path.write_text("not valid json", encoding="utf-8")
        self.assertIsNone(self.cache.get(key))

    def test_set_silently_ignores_invalid_dir(self):
        bad_cache = ResponseCache(cache_dir="/nonexistent/path/xyz")
        # Should not raise
        bad_cache.set("key", "value")

    # ── size ──────────────────────────────────────────────────────────────────

    def test_size_empty(self):
        self.assertEqual(self.cache.size(), 0)

    def test_size_increments_on_set(self):
        k1 = ResponseCache.make_key("a")
        k2 = ResponseCache.make_key("b")
        self.cache.set(k1, "response a")
        self.cache.set(k2, "response b")
        self.assertEqual(self.cache.size(), 2)

    def test_size_unchanged_on_overwrite(self):
        key = ResponseCache.make_key("prompt")
        self.cache.set(key, "v1")
        self.cache.set(key, "v2")
        self.assertEqual(self.cache.size(), 1)

    # ── clear ─────────────────────────────────────────────────────────────────

    def test_clear_removes_all_entries(self):
        self.cache.set(ResponseCache.make_key("x"), "x")
        self.cache.set(ResponseCache.make_key("y"), "y")
        count = self.cache.clear()
        self.assertEqual(count, 2)
        self.assertEqual(self.cache.size(), 0)

    def test_clear_returns_zero_when_empty(self):
        self.assertEqual(self.cache.clear(), 0)

    # ── persistence across instances ─────────────────────────────────────────

    def test_cache_persists_across_instances(self):
        key = ResponseCache.make_key("persistent prompt")
        self.cache.set(key, "stored result")

        second_instance = ResponseCache(cache_dir=self._tmp)
        self.assertEqual(second_instance.get(key), "stored result")

    # ── make_cache factory ────────────────────────────────────────────────────

    def test_make_cache_returns_instance_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NOCACHE", None)
            result = make_cache(cache_dir=self._tmp)
        self.assertIsInstance(result, ResponseCache)

    def test_make_cache_returns_none_when_nocache_set(self):
        with patch.dict(os.environ, {"NOCACHE": "1"}):
            result = make_cache(cache_dir=self._tmp)
        self.assertIsNone(result)

    def test_make_cache_returns_instance_when_nocache_zero(self):
        with patch.dict(os.environ, {"NOCACHE": "0"}):
            result = make_cache(cache_dir=self._tmp)
        self.assertIsInstance(result, ResponseCache)

    # ── hit / miss counters ───────────────────────────────────────────────────

    def test_hit_counter_increments_on_cache_hit(self):
        key = ResponseCache.make_key("prompt")
        self.cache.set(key, "response")
        self.cache.get(key)
        self.assertEqual(self.cache.stats()["hits"], 1)
        self.assertEqual(self.cache.stats()["misses"], 0)

    def test_miss_counter_increments_on_cache_miss(self):
        self.cache.get("nonexistent_key")
        self.assertEqual(self.cache.stats()["hits"], 0)
        self.assertEqual(self.cache.stats()["misses"], 1)

    def test_counters_accumulate_across_calls(self):
        key = ResponseCache.make_key("p")
        self.cache.set(key, "v")
        self.cache.get(key)       # hit
        self.cache.get(key)       # hit
        self.cache.get("miss1")   # miss
        self.assertEqual(self.cache.stats()["hits"], 2)
        self.assertEqual(self.cache.stats()["misses"], 1)

    def test_miss_on_corrupted_file(self):
        key = "deadbeef" * 8
        path = Path(self._tmp) / f"{key}.json"
        path.write_text("not valid json", encoding="utf-8")
        self.cache.get(key)
        self.assertEqual(self.cache.stats()["misses"], 1)

    # ── stats() ───────────────────────────────────────────────────────────────

    def test_stats_initial_state(self):
        s = self.cache.stats()
        self.assertEqual(s["hits"], 0)
        self.assertEqual(s["misses"], 0)
        self.assertEqual(s["size"], 0)
        self.assertEqual(s["estimated_tokens_saved"], 0)

    def test_stats_estimated_tokens_saved(self):
        key = ResponseCache.make_key("p")
        self.cache.set(key, "v")
        self.cache.get(key)   # 1 hit
        s = self.cache.stats()
        self.assertEqual(s["estimated_tokens_saved"], ResponseCache._AVG_TOKENS_PER_ENTRY)

    def test_stats_size_matches_disk(self):
        self.cache.set(ResponseCache.make_key("a"), "x")
        self.cache.set(ResponseCache.make_key("b"), "y")
        self.assertEqual(self.cache.stats()["size"], 2)


# ═══════════════════════════════════════════════════════════════════════════════
# AnthropicRunner + cache integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnthropicRunnerCache(unittest.TestCase):

    def _runner_with_cache(self, tmp_dir):
        cache = ResponseCache(cache_dir=tmp_dir)
        ar = AnthropicRunner(cache=cache)
        ar.available = True
        ar.client = MagicMock()
        ar.async_client = MagicMock()
        return ar, cache

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        ResponseCache(cache_dir=self._tmp).clear()

    # ── run() ─────────────────────────────────────────────────────────────────

    def test_run_cache_miss_calls_api(self):
        ar, _ = self._runner_with_cache(self._tmp)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="  api result  ")]
        ar.client.messages.create.return_value = mock_msg

        ok, output = ar.run("novel prompt")
        self.assertTrue(ok)
        self.assertEqual(output, "api result")
        ar.client.messages.create.assert_called_once()

    def test_run_cache_miss_stores_result(self):
        ar, cache = self._runner_with_cache(self._tmp)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="stored output")]
        ar.client.messages.create.return_value = mock_msg

        ar.run("store me")
        key = ResponseCache.make_key("store me")
        self.assertEqual(cache.get(key), "stored output")

    def test_run_cache_hit_skips_api(self):
        ar, cache = self._runner_with_cache(self._tmp)
        key = ResponseCache.make_key("cached prompt")
        cache.set(key, "cached result")

        ok, output = ar.run("cached prompt")
        self.assertTrue(ok)
        self.assertEqual(output, "cached result")
        ar.client.messages.create.assert_not_called()

    def test_run_no_cache_always_calls_api(self):
        ar = AnthropicRunner(cache=None)
        ar.available = True
        ar.client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="result")]
        ar.client.messages.create.return_value = mock_msg

        ar.run("prompt")
        ar.run("prompt")   # second call with same prompt
        self.assertEqual(ar.client.messages.create.call_count, 2)

    # ── arun() ────────────────────────────────────────────────────────────────

    def test_arun_cache_hit_skips_api(self):
        ar, cache = self._runner_with_cache(self._tmp)
        async_mock = AsyncMock()
        ar.async_client.messages.create = async_mock
        key = ResponseCache.make_key("async prompt")
        cache.set(key, "async cached")

        ok, output = asyncio.run(ar.arun("async prompt"))
        self.assertTrue(ok)
        self.assertEqual(output, "async cached")
        async_mock.assert_not_called()

    def test_arun_cache_miss_stores_result(self):
        ar, cache = self._runner_with_cache(self._tmp)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="async result")]
        ar.async_client.messages.create = AsyncMock(return_value=mock_msg)

        asyncio.run(ar.arun("new async prompt"))
        key = ResponseCache.make_key("new async prompt")
        self.assertEqual(cache.get(key), "async result")


# ═══════════════════════════════════════════════════════════════════════════════
# Executor CLAUDE_LOCAL routing
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutorLocalRouting(unittest.TestCase):

    def _make_dag(self, status="Running"):
        return {
            "Task 0": {
                "status": "Running",
                "depends_on": [],
                "branches": {
                    "A": {
                        "status": "Running",
                        "subtasks": {
                            "A1": {
                                "status": status,
                                "last_update": 0,
                                "shadow": "Pending",
                                "tools": "",
                                "description": "do something",
                            }
                        },
                    }
                },
            }
        }

    def _executor(self):
        from runners.executor import Executor
        with patch.dict(os.environ, {"NOCACHE": "1"}):
            ex = Executor(max_per_step=6, verify_prob=0.0)
        ex.review_mode = False
        ex.anthropic.available = False
        ex.sdk_tool.available  = False
        return ex

    def test_claude_local_routes_to_subprocess_when_available(self):
        ex = self._executor()
        ex.claude.available = True

        dag = self._make_dag("Running")
        from agents.planner import Planner
        plist = Planner(5).prioritize(dag, step=1)

        with patch.dict(os.environ, {"CLAUDE_LOCAL": "1"}):
            with patch.object(ex.claude, "run", return_value=(True, "local output")) as mock_run:
                with patch("runners.executor.add_memory_snapshot"):
                    ex.execute_step(dag, plist, step=1, memory_store={})

        mock_run.assert_called_once()

    def test_claude_local_skips_sdk_even_when_sdk_available(self):
        ex = self._executor()
        ex.claude.available  = True
        ex.sdk_tool.available = True

        dag_with_tools = self._make_dag("Running")
        dag_with_tools["Task 0"]["branches"]["A"]["subtasks"]["A1"]["tools"] = "Read,Glob"

        from agents.planner import Planner
        plist = Planner(5).prioritize(dag_with_tools, step=1)

        with patch.dict(os.environ, {"CLAUDE_LOCAL": "1"}):
            with patch.object(ex.claude, "run", return_value=(True, "local")) as mock_run:
                with patch("runners.executor.add_memory_snapshot"):
                    ex.execute_step(dag_with_tools, plist, step=1, memory_store={})

        # ClaudeRunner should be used, NOT SdkToolRunner
        mock_run.assert_called_once()

    def test_claude_local_with_unavailable_cli_falls_through(self):
        """CLAUDE_LOCAL=1 but claude CLI not installed → falls through to normal logic."""
        ex = self._executor()
        ex.claude.available   = False   # CLI not present
        ex.anthropic.available = False
        ex.sdk_tool.available  = False

        dag = self._make_dag("Running")
        from agents.planner import Planner
        plist = Planner(5).prioritize(dag, step=1)

        with patch.dict(os.environ, {"CLAUDE_LOCAL": "1"}):
            with patch("runners.executor.add_memory_snapshot"):
                with patch("runners.executor.random.random", return_value=0.99):
                    # verify_prob=0 so dice roll won't fire
                    actions = ex.execute_step(dag, plist, step=1, memory_store={})

        # No runner fired → action stays Running (dice roll disabled)
        self.assertEqual(actions, {})

    def test_no_claude_local_uses_normal_routing(self):
        """Without CLAUDE_LOCAL, normal SDK routing applies."""
        ex = self._executor()
        ex.claude.available    = True
        ex.anthropic.available = True

        dag = self._make_dag("Running")
        from agents.planner import Planner
        plist = Planner(5).prioritize(dag, step=1)

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="sdk result")]
        ex.anthropic.async_client = MagicMock()
        ex.anthropic.async_client.messages.create = AsyncMock(return_value=mock_msg)

        claude_run = MagicMock(return_value=(True, "subprocess result"))
        ex.claude.run = claude_run

        with patch.dict(os.environ, {"CLAUDE_LOCAL": "0"}):
            with patch("runners.executor.add_memory_snapshot"):
                ex.execute_step(dag, plist, step=1, memory_store={})

        # CLAUDE_LOCAL=0: should use SDK (anthropic), not subprocess (claude)
        claude_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
