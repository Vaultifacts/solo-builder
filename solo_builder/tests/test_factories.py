"""Tests for solo_builder/tests/factories.py (TASK-324 / TD-TEST-003)."""
import unittest

from solo_builder.tests.factories import (
    make_subtask, make_dag, make_state, make_multi_task_state,
)


class TestMakeSubtask(unittest.TestCase):

    def test_default_status_is_pending(self):
        st = make_subtask()
        self.assertEqual(st["status"], "Pending")

    def test_custom_status(self):
        st = make_subtask("Verified")
        self.assertEqual(st["status"], "Verified")

    def test_has_required_keys(self):
        st = make_subtask()
        for key in ("status", "shadow", "last_update", "output", "description"):
            self.assertIn(key, st)

    def test_custom_output_and_description(self):
        st = make_subtask(output="done", description="do something")
        self.assertEqual(st["output"], "done")
        self.assertEqual(st["description"], "do something")


class TestMakeDag(unittest.TestCase):

    def test_default_creates_two_subtasks(self):
        dag = make_dag()
        subtasks = dag["Task 0"]["branches"]["Branch A"]["subtasks"]
        self.assertEqual(len(subtasks), 2)

    def test_custom_subtasks(self):
        dag = make_dag({"X1": "Running", "X2": "Pending", "X3": "Verified"})
        subtasks = dag["Task 0"]["branches"]["Branch A"]["subtasks"]
        self.assertEqual(set(subtasks.keys()), {"X1", "X2", "X3"})
        self.assertEqual(subtasks["X1"]["status"], "Running")

    def test_custom_task_and_branch_names(self):
        dag = make_dag(task="MyTask", branch="MyBranch")
        self.assertIn("MyTask", dag)
        self.assertIn("MyBranch", dag["MyTask"]["branches"])

    def test_depends_on_is_empty_list(self):
        dag = make_dag()
        self.assertEqual(dag["Task 0"]["depends_on"], [])

    def test_task_status(self):
        dag = make_dag(task_status="Verified")
        self.assertEqual(dag["Task 0"]["status"], "Verified")


class TestMakeState(unittest.TestCase):

    def test_has_step_and_dag(self):
        state = make_state()
        self.assertIn("step", state)
        self.assertIn("dag", state)

    def test_default_step_is_10(self):
        state = make_state()
        self.assertEqual(state["step"], 10)

    def test_custom_step(self):
        state = make_state(step=42)
        self.assertEqual(state["step"], 42)

    def test_custom_subtasks_propagate(self):
        state = make_state({"Z1": "Running"})
        subtasks = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        self.assertIn("Z1", subtasks)

    def test_all_verified_no_pending(self):
        state = make_state({"A1": "Verified", "A2": "Verified"})
        subtasks = state["dag"]["Task 0"]["branches"]["Branch A"]["subtasks"]
        self.assertTrue(all(v["status"] == "Verified" for v in subtasks.values()))


class TestMakeMultiTaskState(unittest.TestCase):

    def test_has_two_tasks(self):
        state = make_multi_task_state()
        self.assertEqual(len(state["dag"]), 2)

    def test_step_is_20(self):
        state = make_multi_task_state()
        self.assertEqual(state["step"], 20)

    def test_task1_depends_on_task0(self):
        state = make_multi_task_state()
        self.assertIn("Task 0", state["dag"]["Task 1"]["depends_on"])

    def test_total_subtask_count(self):
        state = make_multi_task_state()
        total = sum(
            len(b["subtasks"])
            for t in state["dag"].values()
            for b in t["branches"].values()
        )
        self.assertEqual(total, 6)  # A1+A2 + B1 + C1+C2 + D1

    def test_verified_count(self):
        state = make_multi_task_state()
        verified = sum(
            1
            for t in state["dag"].values()
            for b in t["branches"].values()
            for s in b["subtasks"].values()
            if s["status"] == "Verified"
        )
        self.assertEqual(verified, 3)  # A1, A2, B1


if __name__ == "__main__":
    unittest.main()
