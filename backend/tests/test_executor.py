"""Keep execution output and traceback metadata consistent with the API contract."""

from pathlib import Path
import sys
import unittest
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.executor import execute_code
from runtime import executor


class ExecutorTests(unittest.TestCase):
    def test_success_returns_stdout_and_no_error(self):
        result = execute_code("print('completed')\n", "demo.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["stdout"], "completed\n")
        self.assertEqual(result["stderr"], "")
        self.assertIsNone(result["error"])

    def test_failure_preserves_output_before_the_error(self):
        result = execute_code("print('before failure')\nraise ValueError('example')\n", "demo.py")
        self.assertFalse(result["success"])
        self.assertEqual(result["stdout"], "before failure\n")
        self.assertIn("ValueError: example", result["stderr"])
        self.assertEqual(result["traceback"], result["stderr"])
        self.assertEqual(result["error"]["line_number"], 2)

    def test_syntax_errors_keep_the_source_line(self):
        result = execute_code("print('first')\nif True print('invalid')\n", "demo.py")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["type"], "SyntaxError")
        self.assertEqual(result["error"]["line_number"], 2)

    def test_stop_and_concurrent_runs_keep_the_correct_process(self):
        result = {}
        thread = threading.Thread(target=lambda: result.update(execute_code("import time\ntime.sleep(5)\n", "slow.py")))
        thread.start()
        try:
            deadline = time.monotonic() + 3
            while executor.CURRENT_PROCESS is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertIsNotNone(executor.CURRENT_PROCESS)
            busy = execute_code("print('second run')", "other.py")
            self.assertFalse(busy["success"])
            self.assertEqual(busy["error"]["type"], "ExecutionBusyError")
            self.assertTrue(executor.stop_execution())
        finally:
            executor.stop_execution()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(result["success"])
        self.assertTrue(execute_code("print('ready again')")["success"])


if __name__ == "__main__":
    unittest.main()
