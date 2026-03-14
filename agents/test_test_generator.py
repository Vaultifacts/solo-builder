#!/usr/bin/env python3
"""
Tests for agents/test_generator.py — TestGenerator agent.

Run:
    python agents/test_test_generator.py
    python -m pytest agents/test_test_generator.py -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.test_generator import TestGenerator


def _make_dag(st_status="Review", output="def foo():\n    return 42\n"):
    return {
        "Task 0": {
            "status": "Running",
            "depends_on": [],
            "branches": {
                "Branch A": {
                    "status": "Running",
                    "subtasks": {
                        "A1": {
                            "status": st_status,
                            "shadow": "Done",
                            "last_update": 5,
                            "description": "Implement foo function in utils.py",
                            "output": output,
                        }
                    },
                }
            },
        }
    }


class TestHasPythonContent(unittest.TestCase):
    def setUp(self):
        self.tg = TestGenerator({"TEST_GENERATOR_ENABLED": False})

    def test_detects_py_file(self):
        self.assertTrue(self.tg._has_python_content("Modified utils/helper.py"))

    def test_detects_code(self):
        self.assertTrue(self.tg._has_python_content("def calculate():\n    return 1"))

    def test_detects_import(self):
        self.assertTrue(self.tg._has_python_content("import os\nfrom pathlib import Path"))

    def test_rejects_plain_text(self):
        self.assertFalse(self.tg._has_python_content("Everything looks good."))

    def test_rejects_empty(self):
        self.assertFalse(self.tg._has_python_content(""))


class TestExtractPyFiles(unittest.TestCase):
    def setUp(self):
        self.tg = TestGenerator({"TEST_GENERATOR_ENABLED": False})

    def test_extracts_files(self):
        files = self.tg.extract_py_files("Modified utils/helper.py and api/app.py")
        self.assertIn("utils/helper.py", files)
        self.assertIn("api/app.py", files)

    def test_deduplicates(self):
        files = self.tg.extract_py_files("Read foo.py then edit foo.py")
        self.assertEqual(files.count("foo.py"), 1)

    def test_empty_output(self):
        self.assertEqual(self.tg.extract_py_files("no files here"), [])


class TestStripFences(unittest.TestCase):
    def test_strips_python_fences(self):
        code = "```python\ndef foo():\n    pass\n```"
        result = TestGenerator._strip_fences(code)
        self.assertEqual(result, "def foo():\n    pass")

    def test_strips_plain_fences(self):
        code = "```\nx = 1\n```"
        result = TestGenerator._strip_fences(code)
        self.assertEqual(result, "x = 1")

    def test_no_fences_unchanged(self):
        code = "def foo():\n    pass"
        result = TestGenerator._strip_fences(code)
        self.assertEqual(result, code)


class TestWriteTestFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": False,
            "TEST_GENERATOR_ROOT": self.tmp,
            "TEST_GENERATOR_OUTPUT_DIR": "tests/generated",
        })

    def test_writes_file(self):
        path = self.tg._write_test_file("A1", "# test code\n", step=3)
        self.assertTrue(os.path.exists(path))
        self.assertIn("test_a1_step3.py", path)
        with open(path) as f:
            self.assertEqual(f.read(), "# test code\n")

    def test_creates_directory(self):
        self.tg._output_dir = os.path.join(self.tmp, "new", "dir")
        path = self.tg._write_test_file("B2", "pass\n", step=1)
        self.assertTrue(os.path.exists(path))

    def test_adds_trailing_newline(self):
        path = self.tg._write_test_file("C1", "pass", step=1)
        with open(path) as f:
            content = f.read()
        self.assertTrue(content.endswith("\n"))


class TestGenerateTestsDisabled(unittest.TestCase):
    def test_returns_zero_when_disabled(self):
        tg = TestGenerator({"TEST_GENERATOR_ENABLED": False})
        dag = _make_dag()
        result = tg.generate_tests(dag, {"A1": "review"}, 6, {"Branch A": []}, [])
        self.assertEqual(result, 0)

    def test_returns_zero_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            tg = TestGenerator({"TEST_GENERATOR_ENABLED": True})
        self.assertFalse(tg.available)


class TestGenerateTestsIntegration(unittest.TestCase):
    def test_generates_and_writes(self):
        tmp = tempfile.mkdtemp()
        tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": True,
            "TEST_GENERATOR_ROOT": tmp,
            "TEST_GENERATOR_OUTPUT_DIR": "tests/generated",
        })
        tg.available = True
        tg._client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=(
            "# auto-generated by TestGenerator\n"
            "def test_foo():\n"
            "    assert True\n"
            "def test_foo_edge():\n"
            "    assert 1 == 1\n"
        ))]
        tg._client.messages.create.return_value = mock_msg

        dag = _make_dag()
        memory = {"Branch A": []}
        alerts: list = []
        written = tg.generate_tests(dag, {"A1": "review"}, 6, memory, alerts)

        self.assertEqual(written, 1)
        # File should exist
        gen_dir = os.path.join(tmp, "tests", "generated")
        files = os.listdir(gen_dir)
        test_files = [f for f in files if f.startswith("test_") and f.endswith(".py")]
        self.assertEqual(len(test_files), 1)
        self.assertIn("test_a1_step6.py", test_files[0])
        # Alert should mention the file
        self.assertTrue(any("TestGenerator" in a for a in alerts))
        # Memory updated
        self.assertGreater(len(memory["Branch A"]), 0)

    def test_skips_non_python_output(self):
        tg = TestGenerator({"TEST_GENERATOR_ENABLED": True})
        tg.available = True
        tg._client = MagicMock()

        dag = _make_dag(output="Everything looks good, task completed successfully.")
        written = tg.generate_tests(dag, {"A1": "review"}, 6, {"Branch A": []}, [])

        self.assertEqual(written, 0)
        tg._client.messages.create.assert_not_called()

    def test_skips_started_actions(self):
        tg = TestGenerator({"TEST_GENERATOR_ENABLED": True})
        tg.available = True
        tg._client = MagicMock()

        dag = _make_dag(st_status="Running")
        written = tg.generate_tests(dag, {"A1": "started"}, 6, {"Branch A": []}, [])
        self.assertEqual(written, 0)

    def test_dedup_across_steps(self):
        tmp = tempfile.mkdtemp()
        tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": True,
            "TEST_GENERATOR_ROOT": tmp,
            "TEST_GENERATOR_OUTPUT_DIR": "tests/generated",
        })
        tg.available = True
        tg._client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="def test_x(): pass\ndef test_y(): pass\n")]
        tg._client.messages.create.return_value = mock_msg

        dag = _make_dag()
        tg.generate_tests(dag, {"A1": "review"}, 6, {"Branch A": []}, [])
        # Second call for same subtask — should be skipped
        written = tg.generate_tests(dag, {"A1": "review"}, 7, {"Branch A": []}, [])
        self.assertEqual(written, 0)


class TestSdkFailure(unittest.TestCase):
    def test_sdk_error_skips_gracefully(self):
        tmp = tempfile.mkdtemp()
        tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": True,
            "TEST_GENERATOR_ROOT": tmp,
            "TEST_GENERATOR_OUTPUT_DIR": "tests/generated",
        })
        tg.available = True
        tg._client = MagicMock()
        tg._client.messages.create.side_effect = Exception("API error")

        dag = _make_dag()
        alerts: list = []
        written = tg.generate_tests(dag, {"A1": "review"}, 6, {"Branch A": []}, alerts)

        self.assertEqual(written, 0)
        # Should NOT generate an alert on failure — just skip silently


class TestPromptContent(unittest.TestCase):
    def test_prompt_includes_description_and_output(self):
        tmp = tempfile.mkdtemp()
        tg = TestGenerator({
            "TEST_GENERATOR_ENABLED": True,
            "TEST_GENERATOR_ROOT": tmp,
            "TEST_GENERATOR_OUTPUT_DIR": "tests/generated",
        })
        tg.available = True
        tg._client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="def test_a(): pass\ndef test_b(): pass\n")]
        tg._client.messages.create.return_value = mock_msg

        dag = _make_dag(output="class Calculator:\n    def add(self, a, b): return a + b\n")
        tg.generate_tests(dag, {"A1": "review"}, 6, {"Branch A": []}, [])

        call_args = tg._client.messages.create.call_args
        prompt_text = call_args.kwargs["messages"][0]["content"]
        self.assertIn("Implement foo function", prompt_text)
        self.assertIn("Calculator", prompt_text)


if __name__ == "__main__":
    unittest.main()
