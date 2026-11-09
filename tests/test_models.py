"""Routing recommendations never constitute a runtime model change."""
import importlib.util
import json
import subprocess
import sys
import tempfile
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

    def test_unknown_outcome_blocks_api_and_cli_even_after_pass(self):
        attempts = [{"task_id": "a", "outcome": "FAILED", "level": "MEDIUM"},
                    {"task_id": "a", "outcome": "PASS", "level": "MEDIUM"}]
        task = {"id": "a"}
        self.assertEqual(MODELS.route(task, self.inventory, attempts)["verdict"], "BLOCKED")
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps({"task": task, "capabilities": self.inventory,
                                             "attempts": attempts}))
            result = subprocess.run([sys.executable, str(Path(MODELS.__file__)), str(input_path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["verdict"], "BLOCKED")

    def test_malformed_history_is_not_silently_ignored(self):
        for observation in ({}, {"task_id": "other", "outcome": "UNKNOWN", "level": "LOW"}):
            result = MODELS.route({"id": "a"}, self.inventory, [observation])
            self.assertEqual(result["verdict"], "BLOCKED")

    def test_verified_correction_closes_failure_but_retains_history(self):
        failure = {"task_id": "a", "outcome": "FAIL", "level": "MEDIUM",
                   "diagnosis_kind": "implementation", "diagnosis": "Bug in validation"}
        corrected = {"task_id": "a", "outcome": "PASS", "level": "MEDIUM"}
        attempts = [failure, corrected]
        result = MODELS.route({"id": "a"}, self.inventory, attempts)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["metrics"]["attempts"], 2)
        self.assertEqual(len(result["attempt_history"]), 2)
        attempts.append(failure)
        self.assertEqual(MODELS.route({"id": "a"}, self.inventory, attempts)["verdict"], "BLOCKED")

    def test_explicit_tiers_and_relative_cost_order(self):
        self.inventory["models"].append(
            {"id": "specialist", "tiers": ["HIGH"], "efforts": ["high"], "cost_rank": 1.5})
        self.assertEqual(self.route(complexity="complex")["recommendation"]["model"], "specialist")
        self.assertEqual(self.route(risk="critical")["recommendation"]["model"], "strong")

    def test_invalid_inventory_fails_closed(self):
        self.inventory["models"][0]["cost_rank"] = float("nan")
        with self.assertRaises(ValueError):
            self.route()


class PolicyTests(unittest.TestCase):
    """Issue #84 RM1-4: advisory policy, safety floors and explicit choices."""
    def setUp(self):
        self.inventory = {'runtime_overrides': True, 'models': [
            {'id': 'codex-one', 'harness': 'codex', 'max_level': 'EXTRA_HIGH',
             'efforts': ['low', 'medium', 'high', 'xhigh'], 'cost_rank': 2,
             'modalities': ['text', 'image']},
            {'id': 'claude-one', 'harness': 'claude', 'max_level': 'HIGH',
             'efforts': ['medium', 'high'], 'cost_rank': 1, 'modalities': ['text']}]}
        self.policy = {'version': 1, 'enabled': True, 'rules': [
            {'id': 'build', 'match': {'role': 'implementer', 'phase': 'BUILD'},
             'priority': 1, 'prefer': [{'harness': 'codex'}], 'fallback': 'blocked'}]}
        self.task = {'role': 'implementer', 'phase': 'BUILD'}

    def route(self, task=None, policy=None):
        return MODELS.route(task or self.task, self.inventory,
                            policy=self.policy if policy is None else policy)

    def test_disabled_policy_is_exact_legacy(self):
        old = MODELS.route(self.task, self.inventory)
        self.assertEqual(self.route(policy={'version': 1, 'enabled': False, 'rules': []}), old)

    def test_role_phase_preference_and_explanation(self):
        result = self.route()
        self.assertEqual(result['recommendation']['model'], 'codex-one')
        self.assertEqual(result['policy']['matched_rule'], 'build')
        self.assertFalse(result['applied'])
        self.assertIsNone(result['observed'])
        self.assertEqual(result['verification'], 'not_verified')
        self.assertEqual(self.route({'role': 'explorer', 'phase': 'PREPARE'})[
            'recommendation']['model'], 'claude-one')

    def test_rule_priority_risk_and_no_order_tie_breaker(self):
        self.policy['rules'].append({'id': 'risky', 'match': {'risk': 'high'},
                                    'priority': 2, 'prefer': [{'model': 'claude-one'}]})
        task = {**self.task, 'risk': 'high'}
        self.assertEqual(self.route(task)['recommendation']['model'], 'claude-one')
        self.policy['rules'][1]['priority'] = 1
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')
        self.policy['rules'].reverse()
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')

    def test_user_override_wins_and_impossible_pin_blocks(self):
        task = {**self.task, 'routing_override': {'model': 'claude-one', 'effort': 'high'}}
        self.assertEqual(self.route(task)['recommendation'], {'model': 'claude-one', 'effort': 'high'})
        task['routing_override']['model'] = 'missing'
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')
        task['routing_override'] = {'model': 'codex-one', 'effort': 'ultra'}
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')

    def test_missing_preference_needs_explicit_fallback(self):
        self.policy['rules'][0]['prefer'] = [{'model': 'missing'}]
        self.assertEqual(self.route()['verdict'], 'BLOCKED')
        self.policy['rules'][0]['fallback'] = 'least_cost'
        result = self.route()
        self.assertEqual(result['recommendation']['model'], 'claude-one')
        self.assertTrue(result['policy']['fallback_used'])
        self.assertIn('fallback', result['reason'].lower())

    def test_unavailable_disabled_and_ordered_allowed_choices(self):
        for flag in ('available', 'enabled'):
            self.inventory['models'][0][flag] = False
            self.assertEqual(self.route()['verdict'], 'BLOCKED')
            self.policy['rules'][0]['prefer'].append({'model': 'claude-one'})
            self.assertEqual(self.route()['recommendation']['model'], 'claude-one')
            self.policy['rules'][0]['prefer'].pop()
            del self.inventory['models'][0][flag]

    def test_unsupported_effort_or_insufficient_capacity_blocks(self):
        self.policy['rules'][0]['effort'] = 'xhigh'
        self.inventory['models'][0]['efforts'] = ['medium', 'high']
        self.assertEqual(self.route()['verdict'], 'BLOCKED')
        self.policy['rules'][0]['effort'] = 'low'
        self.assertEqual(self.route()['verdict'], 'BLOCKED')

    def test_security_floor_cannot_be_lowered(self):
        rule = self.policy['rules'][0]
        rule.update(prefer=[{'model': 'claude-one'}], minimum_level='LOW')
        result = self.route({**self.task, 'type': 'security', 'complexity': 'simple'})
        self.assertEqual(result['verdict'], 'BLOCKED')
        rule.update(prefer=[{'model': 'codex-one'}])
        self.assertEqual(self.route({**self.task, 'risk': 'critical'})['level'], 'EXTRA_HIGH')

    def test_multimodal_compatibility_is_explicit(self):
        self.policy['rules'][0]['prefer'] = [{'model': 'claude-one'}]
        task = {**self.task, 'modalities': ['text', 'image']}
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')
        self.policy['rules'][0]['prefer'] = [{'model': 'codex-one'}]
        self.assertEqual(self.route(task)['verdict'], 'PASS')
        del self.inventory['models'][0]['modalities']
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')

    def test_reviewer_independence_uses_sessions_and_high_floor(self):
        for role in ('reviewer', 'lead-tech'):
            task = {'role': role, 'phase': 'SHIP', 'session_id': 'same',
                    'implementer_session_id': 'same'}
            self.assertEqual(self.route(task)['verdict'], 'BLOCKED')
            task['session_id'] = 'different'
            result = self.route(task)
            self.assertEqual(result['verdict'], 'PASS')
            self.assertEqual(result['level'], 'HIGH')
            del task['implementer_session_id']
            self.assertEqual(self.route(task)['verdict'], 'BLOCKED')

    def test_all_roles_and_phases_are_supported(self):
        for role in ('orchestrator', 'explorer', 'test-author', 'implementer', 'reviewer', 'lead-tech'):
            for phase in ('PREPARE', 'BUILD', 'SHIP'):
                task = {'role': role, 'phase': phase, 'session_id': 'review',
                        'implementer_session_id': 'builder'}
                self.assertEqual(self.route(task)['verdict'], 'PASS')

    def test_unknown_fields_and_invalid_policy_fail_closed(self):
        for patch in ({'enabled': 'false'}, {'version': 2}, {'rules': 'bad'}, {'typo': True}):
            self.assertEqual(self.route(policy={**self.policy, **patch})['verdict'], 'BLOCKED')
        for patch in ({'phase': 'RUN'}, {'role': 'unknown'}, {'risk': 'danger'}):
            self.assertEqual(self.route({**self.task, **patch})['verdict'], 'BLOCKED')
        self.policy['rules'][0]['fallback'] = 'silent'
        self.assertEqual(self.route()['verdict'], 'BLOCKED')

    def test_legacy_attempt_failure_cannot_be_bypassed(self):
        attempts = [{'task_id': 'a', 'outcome': 'FAIL', 'level': 'MEDIUM'}]
        result = MODELS.route({**self.task, 'id': 'a'}, self.inventory, attempts, self.policy)
        self.assertEqual(result['verdict'], 'BLOCKED')

    def test_cli_policy_and_invalid_json_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text(json.dumps({'task': self.task, 'capabilities': self.inventory,
                                        'routing_policy': self.policy}))
            command = [sys.executable, str(Path(MODELS.__file__)), str(path)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(json.loads(result.stdout)['recommendation']['model'], 'codex-one')
            self.policy['rules'][0]['effort'] = 'unsupported'
            path.write_text(json.dumps({'task': self.task, 'capabilities': self.inventory,
                                        'routing_policy': self.policy}))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['verdict'], 'BLOCKED')


    def test_override_does_not_lower_rule_floor_or_security(self):
        self.policy['rules'][0]['minimum_level'] = 'HIGH'
        task = {**self.task, 'routing_override': {'model': 'codex-one', 'effort': 'medium'}}
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')
        task['type'] = 'security'
        task['routing_override']['effort'] = 'high'
        self.assertEqual(self.route(task)['verdict'], 'BLOCKED')

    def test_explicit_high_tier_only_can_satisfy_review_floor(self):
        self.inventory['models'] = [{**self.inventory['models'][0], 'tiers': ['HIGH']}]
        result = self.route({'role': 'reviewer', 'phase': 'SHIP', 'session_id': 'r',
                             'implementer_session_id': 'i'})
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['level'], 'HIGH')

    def test_same_model_can_review_in_distinct_session(self):
        self.inventory['models'] = [self.inventory['models'][0]]
        task = {'role': 'reviewer', 'phase': 'SHIP', 'session_id': 'r',
                'implementer_session_id': 'i'}
        result = self.route(task)
        self.assertEqual(result['recommendation']['model'], 'codex-one')
        self.assertEqual(result['verdict'], 'PASS')

    def test_ordered_fallback_is_visible(self):
        self.policy['rules'][0]['prefer'] = [{'model': 'missing'}, {'harness': 'claude'}]
        result = self.route()
        self.assertEqual(result['policy']['preference_index'], 1)
        self.assertEqual(len(result['policy']['attempted_preferences']), 2)
        self.assertTrue(result['policy']['fallback_used'])

    def test_malformed_rule_even_unmatched_blocks(self):
        rule = {'id': 'bad', 'match': {'role': 'explorer'}, 'prefer': [{'model': 'codex-one'}]}
        for patch in ({'priority': True}, {'match': {'typo': 'BUILD'}},
                      {'effort': 'ultra'}, {'prefer': [{'model': 'codex-one', 'harness': 'codex'}]},
                      {'unknown': 'value'}):
            self.policy['rules'] = [self.policy['rules'][0], {**rule, **patch}]
            self.assertEqual(self.route()['verdict'], 'BLOCKED')
            self.policy['rules'].pop()


    def test_override_resolves_preference_conflict_without_lowering_floor(self):
        self.policy['rules'].append({**self.policy['rules'][0], 'id': 'conflict',
                                     'prefer': [{'model': 'claude-one'}]})
        self.assertEqual(self.route()['verdict'], 'BLOCKED')
        result = self.route({**self.task, 'routing_override': {'model': 'codex-one'}})
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['policy']['source'], 'override')

    def test_explicit_fallback_preserves_all_constraints(self):
        rule = self.policy['rules'][0]
        rule.update(prefer=[{'model': 'missing'}], fallback='least_cost')
        for task, effort in (({**self.task, 'risk': 'critical'}, 'high'),
                             ({**self.task, 'modalities': ['video']}, 'medium'),
                             (self.task, 'low')):
            rule['effort'] = effort
            self.assertEqual(self.route(task)['verdict'], 'BLOCKED')

    def test_invalid_metadata_and_override_are_not_ignored(self):
        for override in (None, {}, {'model': 'codex-one', 'typo': True}):
            self.assertEqual(self.route({**self.task, 'routing_override': override})['verdict'], 'BLOCKED')
        self.inventory['models'][0]['available'] = 'yes'
        self.assertEqual(self.route()['verdict'], 'BLOCKED')


if __name__ == "__main__":
    unittest.main()
