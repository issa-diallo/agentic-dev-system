"""#89/#98: deterministic acceptance across two simulated subscriptions.

Real subprocesses, Git worktrees and existing gates; no inference, account access,
network or assertion about a real model's reasoning, image or MCP capabilities.
"""
import json
import sys
import unittest

import test_analysis as analyses
import test_missions as missions

RUN = analyses.RUN
LEVEL_ROUTING = {
    'LOW': {'type': 'documentation', 'complexity': 'low'},
    'MEDIUM': {},
    'HIGH': {'complexity': 'high'},
    'EXTRA_HIGH': {'risk': 'critical'},
}
LEVEL_EFFORT = {'LOW': 'low', 'MEDIUM': 'medium', 'HIGH': 'high', 'EXTRA_HIGH': 'xhigh'}


class MultiModelAcceptanceTests(unittest.TestCase):
    git = analyses.DualAnalysisTests.git
    events = analyses.DualAnalysisTests.events
    divergent_risk = analyses.DualAnalysisTests.divergent_risk
    write_arbitration = analyses.DualAnalysisTests.write_arbitration
    assert_no_build = analyses.DualAnalysisTests.assert_no_build

    def setUp(self):
        analyses.DualAnalysisTests.setUp(self)
        for entry in self.config['models']:
            entry['provider'] = {'codex': 'openai', 'claude': 'anthropic'}[entry['harness']]
            entry['efforts'].insert(0, 'low')
        self.config['routing_policy'] = {'version': 1, 'enabled': True, 'rules': [
            {'id': role, 'match': {'role': role},
             'prefer': [{'harness': 'codex'}, {'harness': 'claude'}]}
            for role in ('explorer', 'test-author', 'implementer', 'reviewer')]}
        self.config['run']['review_cycle'] = {
            'enabled': True, 'max_attempts': 7, 'max_corrections': 1, 'max_cost_rank': 1,
            'prefer_cross_provider': True, 'justification': 'Confront the prepared AC1 contract'}
        self.verify = self.root / 'verify.py'
        self.verify.write_text(missions.VERIFY.replace("root / 'events'", "root / 'bin' / 'events'"))

    def delegate(self):
        self.manifest.write_text(json.dumps(self.plan))
        self.config_path.write_text(json.dumps(self.config))
        (self.bin / 'opinions.json').write_text(json.dumps(self.opinions))
        return RUN.delegate(self.manifest, self.repo, config_path=self.config_path,
                            state=self.state, commands=[[sys.executable, str(self.verify)]])

    def launches(self):
        return [event for event in self.events() if 'role' in event]

    def qualify(self, level):
        self.plan['prs'][0]['routing'] = LEVEL_ROUTING[level]
        dual = level in ('HIGH', 'EXTRA_HIGH')
        if dual:
            self.divergent_risk()
            initial = self.delegate()
            self.assert_no_build(initial)
            self.assertEqual(len(self.launches()), 2)
            self.write_arbitration(initial)
        else:
            self.plan['prs'][0].pop('analysis')
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        launches = self.launches()
        expected = (['explorer', 'explorer'] if dual else [])
        expected += ['test-author', 'implementer', 'reviewer']
        self.assertEqual([event['role'] for event in launches], expected)
        self.assertEqual(launches[-1]['provider'], 'claude')
        self.assertTrue(report['example']['review_identity']['cross_provider'])
        events = self.events()
        review_index = next(i for i, event in enumerate(events) if event.get('role') == 'reviewer')
        self.assertIn({'event': 'verify', 'value': 'VALUE = 1'}, events[:review_index])
        history = json.loads(self.state.read_text())['tasks']['example']['mission_history']
        self.assertEqual(len(history), len(expected))
        executions = [item['task']['model_execution'] for item in history]
        self.assertEqual(len({item['session_id'] for item in executions}), len(expected))
        for item, event in zip(history, launches):
            task, proof = item['task'], item['task']['model_execution']
            with self.subTest(level=level, role=task['role'], provider=event['provider']):
                self.assertEqual(item['gate']['verdict'], 'PASS')
                self.assertTrue(task['stop_evidence']['stopped_confirmed'])
                self.assertTrue(task['stop_evidence']['identity_verified'])
                self.assertEqual(task['model_routing']['policy']['matched_rule'], task['role'])
                expected_level = 'HIGH' if task['role'] == 'reviewer' and not dual else level
                self.assertEqual(task['model_routing']['level'], expected_level)
                self.assertEqual(proof['requested']['model'], event['provider'] + '-test')
                self.assertEqual(proof['requested']['effort'], LEVEL_EFFORT[expected_level])
                model_flag = '-m' if event['provider'] == 'codex' else '--model'
                self.assertEqual(event['argv'][event['argv'].index(model_flag) + 1],
                                 proof['requested']['model'])
                if event['provider'] == 'codex':
                    self.assertIn('model_reasoning_effort="%s"' % LEVEL_EFFORT[expected_level],
                                  event['argv'])
                    self.assertIsNone(proof['observed']['model'])
                else:
                    self.assertEqual(proof['observed']['model'], 'claude-test')
                    self.assertTrue(proof['applied']['model'])
                self.assertIsNone(proof['observed']['effort'])
                self.assertFalse(proof['applied']['effort'])
                result = task['result']
                self.assertGreaterEqual(result['duration_seconds'], 0)
                self.assertIsNone(result['usage'])
                self.assertIsNone(result['cost_usd'])
                self.assertEqual(result['subscription']['quota'], 'not_verified')
                self.assertEqual(result['subscription']['overage'], 'not_verified')
        journal = RUN.attempts_file(self.repo).parent / 'runs.jsonl'
        self.assertEqual(len(journal.read_text().splitlines()), len(expected))
        self.assertEqual(self.git('rev-parse', 'HEAD', repo=self.tree), self.initial)
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertNotIn('READY_FOR_HUMAN', json.dumps(report))
        before = self.events()
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        self.assertEqual(self.events(), before)

    def test_RM7_LOW_keeps_one_writer_and_independent_review_without_dual_analysis(self):
        self.qualify('LOW')

    def test_RM7_MEDIUM_keeps_specialized_missions_without_dual_analysis(self):
        self.qualify('MEDIUM')

    def test_RM7_HIGH_requires_sourced_arbitration_then_cross_provider_review(self):
        self.qualify('HIGH')

    def test_RM7_EXTRA_HIGH_retains_analysis_and_stronger_routing_without_claiming_ship(self):
        self.qualify('EXTRA_HIGH')

    def assert_stopped_without_retry(self):
        first = self.delegate()
        self.assert_no_build(first)
        launches = self.launches()
        self.assertEqual(len(launches), 2)
        task = json.loads(self.state.read_text())['tasks']['example']
        self.assertFalse(task['active'])
        self.assertTrue(task['stop_evidence']['stopped_confirmed'])
        (self.bin / 'mode').write_text('ok')
        self.assert_no_build(self.delegate())
        self.assertEqual(self.launches(), launches)

    def test_RM9_quota_blocks_the_combined_policy_without_fallback_or_retry(self):
        (self.bin / 'mode').write_text('quota')
        self.assert_stopped_without_retry()

    def test_RM9_zero_exit_without_analysis_does_not_allow_build_or_retry(self):
        (self.bin / 'mode').write_text('missing-analysis')
        self.assert_stopped_without_retry()

    def test_RM9_changed_source_invalidates_sourced_arbitration_without_new_launch(self):
        self.divergent_risk()
        first = self.delegate()
        self.assert_no_build(first)
        self.write_arbitration(first)
        launches = self.launches()
        (self.tree / 'a.py').write_text('VALUE = 10\n')
        self.assert_no_build(self.delegate())
        self.assertEqual(self.launches(), launches)


if __name__ == '__main__':
    unittest.main()
