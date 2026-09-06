import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("evaluate.py")
SPEC = importlib.util.spec_from_file_location("agent_eval", MODULE_PATH)
agent_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(agent_eval)


class EvaluationTests(unittest.TestCase):
    def test_passing_case(self):
        case = {
            "case_id": "ok",
            "expected_terminal_state": "completed",
            "required_evidence": ["receipt"],
            "forbidden_events": ["duplicate_effect"],
            "max_attempts": 2,
            "unique_effect_receipts": True,
        }
        run = {
            "case_id": "ok",
            "terminal_state": "completed",
            "evidence": ["receipt"],
            "events": ["readback"],
            "attempts": 1,
            "effects": [{"receipt_id": "r-1"}],
        }
        self.assertEqual(agent_eval.evaluate_case(case, run), [])

    def test_duplicate_receipt_fails(self):
        case = {
            "case_id": "dup",
            "expected_terminal_state": "completed",
            "unique_effect_receipts": True,
        }
        run = {
            "case_id": "dup",
            "terminal_state": "completed",
            "effects": [{"receipt_id": "r-1"}, {"receipt_id": "r-1"}],
        }
        failures = agent_eval.evaluate_case(case, run)
        self.assertIn("duplicate external-effect receipt detected", failures)

    def test_missing_input_must_not_mutate(self):
        case = {
            "case_id": "missing",
            "expected_terminal_state": "blocked",
            "required_evidence": ["missing_input_reported"],
            "forbidden_events": ["external_write", "invented_input"],
            "max_attempts": 1,
        }
        run = {
            "case_id": "missing",
            "terminal_state": "blocked",
            "evidence": ["missing_input_reported"],
            "events": ["external_write"],
            "attempts": 1,
            "effects": [],
        }
        failures = agent_eval.evaluate_case(case, run)
        self.assertIn("forbidden event observed: external_write", failures)


if __name__ == "__main__":
    unittest.main()
