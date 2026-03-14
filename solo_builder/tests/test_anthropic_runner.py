"""Tests for runners/anthropic_runner.py — AnthropicRunner class."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runners.anthropic_runner import AnthropicRunner
from runners.cache import ResponseCache


class TestAnthropicRunnerInit(unittest.TestCase):
    def test_init_no_api_key_not_available(self):
        mock_anthropic = MagicMock()
        env = {k: v for k, v in __import__("os").environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict("os.environ", env, clear=True), \
             patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            runner = AnthropicRunner.__new__(AnthropicRunner)
            runner.model = "test"
            runner.max_tokens = 100
            runner.cache = None
            runner.client = None
            runner.async_client = None
            runner.available = runner._init()
        self.assertFalse(runner.available)

    def test_init_no_sdk_not_available(self):
        with patch.dict(sys.modules, {"anthropic": None}):
            runner = AnthropicRunner.__new__(AnthropicRunner)
            runner.model = "test"
            runner.max_tokens = 100
            runner.cache = None
            runner.client = None
            runner.async_client = None
            runner.available = runner._init()
        self.assertFalse(runner.available)

    def test_init_with_api_key_available(self):
        mock_anthropic = MagicMock()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            runner = AnthropicRunner.__new__(AnthropicRunner)
            runner.model = "test"
            runner.max_tokens = 100
            runner.cache = None
            runner.client = None
            runner.async_client = None
            runner.available = runner._init()
        self.assertTrue(runner.available)
        self.assertIsNotNone(runner.client)
        self.assertIsNotNone(runner.async_client)


class TestAnthropicRunnerRun(unittest.TestCase):
    def _make_runner(self):
        runner = AnthropicRunner.__new__(AnthropicRunner)
        runner.model = "test"
        runner.max_tokens = 100
        runner.cache = None
        runner.client = MagicMock()
        runner.async_client = MagicMock()
        runner.available = True
        return runner

    def test_run_unavailable(self):
        runner = self._make_runner()
        runner.available = False
        ok, msg = runner.run("hello")
        self.assertFalse(ok)
        self.assertIn("unavailable", msg)

    def test_run_success(self):
        runner = self._make_runner()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="  result  ")]
        runner.client.messages.create.return_value = mock_msg
        ok, result = runner.run("hello")
        self.assertTrue(ok)
        self.assertEqual(result, "result")

    def test_run_exception(self):
        runner = self._make_runner()
        runner.client.messages.create.side_effect = RuntimeError("API down")
        ok, msg = runner.run("hello")
        self.assertFalse(ok)
        self.assertIn("API down", msg)

    def test_run_with_cache_hit(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        cache = ResponseCache(cache_dir=tmp)
        key = ResponseCache.make_key("hello")
        cache.set(key, "cached_result")
        runner = self._make_runner()
        runner.cache = cache
        ok, result = runner.run("hello")
        self.assertTrue(ok)
        self.assertEqual(result, "cached_result")
        runner.client.messages.create.assert_not_called()
        import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_run_with_cache_miss_stores(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        cache = ResponseCache(cache_dir=tmp)
        runner = self._make_runner()
        runner.cache = cache
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="fresh")]
        runner.client.messages.create.return_value = mock_msg
        ok, result = runner.run("hello")
        self.assertTrue(ok)
        self.assertEqual(result, "fresh")
        # Verify it was cached
        key = ResponseCache.make_key("hello")
        self.assertEqual(cache.get(key), "fresh")
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


class TestAnthropicRunnerArun(unittest.TestCase):
    def _make_runner(self):
        runner = AnthropicRunner.__new__(AnthropicRunner)
        runner.model = "test"
        runner.max_tokens = 100
        runner.cache = None
        runner.client = MagicMock()
        runner.async_client = MagicMock()
        runner.available = True
        return runner

    def test_arun_unavailable(self):
        runner = self._make_runner()
        runner.available = False
        ok, msg = asyncio.run(runner.arun("hello"))
        self.assertFalse(ok)
        self.assertIn("unavailable", msg)

    def test_arun_success(self):
        runner = self._make_runner()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="async result")]
        runner.async_client.messages.create = AsyncMock(return_value=mock_msg)
        ok, result = asyncio.run(runner.arun("hello"))
        self.assertTrue(ok)
        self.assertEqual(result, "async result")

    def test_arun_exception(self):
        runner = self._make_runner()
        runner.async_client.messages.create = AsyncMock(side_effect=RuntimeError("timeout"))
        ok, msg = asyncio.run(runner.arun("hello"))
        self.assertFalse(ok)
        self.assertIn("timeout", msg)

    def test_arun_with_cache_hit(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        cache = ResponseCache(cache_dir=tmp)
        key = ResponseCache.make_key("async_hello")
        cache.set(key, "cached_async")
        runner = self._make_runner()
        runner.cache = cache
        ok, result = asyncio.run(runner.arun("async_hello"))
        self.assertTrue(ok)
        self.assertEqual(result, "cached_async")
        import shutil; shutil.rmtree(tmp, ignore_errors=True)

    def test_arun_with_cache_miss_stores(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        cache = ResponseCache(cache_dir=tmp)
        runner = self._make_runner()
        runner.cache = cache
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="async_fresh")]
        runner.async_client.messages.create = AsyncMock(return_value=mock_msg)
        ok, result = asyncio.run(runner.arun("async_hello"))
        self.assertTrue(ok)
        self.assertEqual(result, "async_fresh")
        key = ResponseCache.make_key("async_hello")
        self.assertEqual(cache.get(key), "async_fresh")
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
