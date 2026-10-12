"""Routing recommendations never constitute a runtime model change."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "models", Path(__file__).resolve().parents[1] / "scripts/agentic-models.py")
MODELS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODELS)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {"runtime_overrides": True, "models": [
            {"id": "cheap", "max_level": "LOW", "efforts": ["low"], "cost_rank": 0},
            {"id": "standard", "max_level": "MEDIUM", "efforts": ["low", "medium"], "cost_rank": 1},
            {"id": "strong", "max_level": "EXTRA_HIGH", "efforts": ["high", "xhigh"], "cost_rank": 2}]}

    def route(self, **task):
        return MODELS.route(task, self.inventory)

    def test_simple_standard_complex_critical(self):
        for task, level, model, effort in (
                ({"type": "documentation", "complexity": "simple"}, "LOW", "cheap", "low"),
                ({"type": "implementation"}, "MEDIUM", "standard", "medium"),
                ({"complexity": "complex"}, "HIGH", "strong", "high"),
                ({"risk": "critical"}, "EXTRA_HIGH", "strong", "xhigh")):
            result = MODELS.route(task, self.inventory)
            self.assertEqual(result["level"], level)
            self.assertEqual(result["recommendation"], {"model": model, "effort": effort})

    def test_auth_and_migrations_require_strong_model(self):
        for kind in ("authentication", "authorization", "migration", "database_migration"):
            self.assertEqual(self.route(type=kind, complexity="simple")["level"], "EXTRA_HIGH")

    def test_missing_model_or_effort_blocks(self):
        self.inventory["models"].pop()
        self.assertEqual(self.route(risk="critical")["verdict"], "BLOCKED")
        self.inventory["models"][1]["efforts"] = ["unsupported"]
        self.assertEqual(self.route()["verdict"], "BLOCKED")

    def test_no_fictitious_application_or_usage(self):
        self.inventory["runtime_overrides"] = False
        result = self.route()
        self.assertFalse(result["applied"])
        self.assertFalse(result["override_available"])
        for key in ("tokens", "api_cost", "codex_quota", "duration_seconds"):
            self.assertIsNone(result["metrics"][key])

    def test_diagnosed_escalation_and_next_task_descent(self):
        failures = [{"task_id": "a", "outcome": "FAIL", "level": "MEDIUM",
                     "diagnosis_kind": "capacity", "diagnosis": "Cannot resolve contract conflict"}]
        result = MODELS.route({"id": "a"}, self.inventory, failures)
        self.assertEqual(result["level"], "HIGH")
        self.assertEqual(result["recommendation"]["model"], "strong")
        next_task = {"id": "b", "type": "read", "complexity": "simple"}
        self.assertEqual(MODELS.route(next_task, self.inventory, failures)["level"], "LOW")

    def test_undiagnosed_failure_and_capacity_ceiling_block(self):
        failure = {"task_id": "a", "outcome": "FAIL", "level": "MEDIUM"}
        self.assertEqual(MODELS.route({"id": "a"}, self.inventory, [failure])["verdict"], "BLOCKED")
        failure.update(level="EXTRA_HIGH", diagnosis_kind="capacity", diagnosis="Still insufficient")
        self.assertEqual(MODELS.route({"id": "a"}, self.inventory, [failure])["verdict"], "BLOCKED")

    def test_explicit_tiers_and_relative_cost_order(self):
        self.inventory["models"].append(
            {"id": "specialist", "tiers": ["HIGH"], "efforts": ["high"], "cost_rank": 1.5})
        self.assertEqual(self.route(complexity="complex")["recommendation"]["model"], "specialist")
        self.assertEqual(self.route(risk="critical")["recommendation"]["model"], "strong")

    def test_invalid_inventory_fails_closed(self):
        self.inventory["models"][0]["cost_rank"] = float("nan")
        with self.assertRaises(ValueError):
            self.route()


if __name__ == "__main__":
    unittest.main()
