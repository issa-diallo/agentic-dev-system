"""#96: useful mission metadata without copying prompts or free-form CLI data."""
import json
import unittest

import test_review_cycle as reviews
import test_run as runner


class LegacyReportingTests(unittest.TestCase):
    setUp = runner.RunTests.setUp
    git, set_mode, config = runner.RunTests.git, runner.RunTests.set_mode, runner.RunTests.config
    quick, task, policy_run = runner.RunTests.quick, runner.RunTests.task, runner.RunTests.policy_run

    def journal(self):
        return (self.repo / '.git/agentic-runs/runs.jsonl').read_text()

    def test_RM1_legacy_run_records_role_decision_and_unknown_metrics_without_prompt(self):
        self.agent.write_text(self.agent.read_text() + '\nprint("PRIVATE-TRANSCRIPT")\n')
        report = self.quick()
        task, row = self.task(report), json.loads(self.journal())
        for item in (task, row):
            self.assertEqual((item['role'], item['phase']), ('implementer', 'BUILD'))
            decision = item['routing_decision']
            self.assertEqual(decision['source'], 'legacy')
            self.assertEqual(decision['level'], 'MEDIUM')
            self.assertIn('cost_rank', decision['reason'])
            self.assertEqual(decision['provenance'], 'model router recommendation')
            self.assertIsNone(item['attempts_used'])
            self.assertIsNone(item['usage'])
            self.assertIsNone(item['cost_usd'])
            self.assertGreaterEqual(item['duration_seconds'], 0)
            self.assertIsNone(item['model_execution']['observed']['model'])
        self.assertNotIn('PRIVATE-TRANSCRIPT', self.journal())
        self.assertNotIn('Deliver a', self.journal())
        self.assertTrue(runner.RUN.succeeded(report['tasks'], False))

    def test_RM1_policy_decision_is_visible_in_journal_and_nonmission_report(self):
        task = self.policy_run()['t1']
        row = json.loads(self.journal())
        for item in (task, row):
            decision = item['routing_decision']
            self.assertEqual(decision['source'], 'rule')
            self.assertEqual(decision['matched_rule'], 'build')
            self.assertEqual(decision['preference_index'], 0)
            self.assertFalse(decision['fallback_used'])
            self.assertIn('strong', decision['reason'])
        self.assertEqual(task['routing_decision'], row['routing_decision'])
        self.assertEqual(task['model_requested'], {'model': 'strong', 'effort': 'high'})

    def test_RM2_metadata_projects_only_routing_and_numeric_cli_counters(self):
        task = {'role': 'implementer', 'phase': 'BUILD', 'attempts_used': 2,
                'model_routing': {'reason': 'Chosen by policy', 'level': 'MEDIUM',
                                 'attempt_history': [{'diagnosis': 'PRIVATE-DIAGNOSIS'}],
                                 'escalations': ['PRIVATE-DIAGNOSIS'],
                                 'policy': {'source': 'rule', 'matched_rule': 'build',
                                            'prompt': 'PRIVATE-PROMPT'}},
                'result': {'usage': {'input_tokens': 0, 'output_tokens': 5,
                                     'cache_read_input_tokens': True,
                                     'cache_creation_input_tokens': 'PRIVATE-KEY',
                                     'metadata': {'prompt': 'PRIVATE-PROMPT'}},
                           'cost_usd': 0, 'duration_seconds': 0,
                           'handoff': {'summary': 'PRIVATE-HANDOFF'}}}
        metadata = runner.RUN.mission_metadata(task)
        self.assertEqual(metadata['usage'], {'input_tokens': 0, 'output_tokens': 5})
        self.assertEqual(metadata['cost_usd'], 0)
        self.assertEqual(metadata['attempts_used'], 2)
        self.assertNotIn('PRIVATE-', json.dumps(metadata))
        empty = runner.RUN.mission_metadata({})
        for field in ('role', 'phase', 'attempts_used', 'usage', 'cost_usd', 'duration_seconds'):
            self.assertIsNone(empty[field])
        self.assertIsNone(empty['routing_decision']['source'])
        for invalid in (True, 'PRIVATE-KEY', float('inf'), -1):
            task['result'].update(usage={'output_tokens': invalid}, cost_usd=invalid)
            metadata = runner.RUN.mission_metadata(task)
            self.assertIsNone(metadata['usage'])
            self.assertIsNone(metadata['cost_usd'])

    def test_RM3_dry_run_never_creates_execution_metrics_or_journal(self):
        task = self.task(self.quick(dry_run=True))
        self.assertEqual(task['role'], 'implementer')
        for field in ('attempts_used', 'usage', 'cost_usd', 'duration_seconds'):
            self.assertIsNone(task[field])
        self.assertFalse((self.repo / '.git/agentic-runs/runs.jsonl').exists())


class MissionReportingTests(unittest.TestCase):
    setUp = reviews.ReviewCycleTests.setUp
    git, mode = reviews.ReviewCycleTests.git, reviews.ReviewCycleTests.mode
    events, roles = reviews.ReviewCycleTests.events, reviews.ReviewCycleTests.roles
    configure, delegate = reviews.ReviewCycleTests.configure, reviews.ReviewCycleTests.delegate
    task = reviews.ReviewCycleTests.task

    def journal(self):
        return (self.repo / '.git/agentic-runs/runs.jsonl').read_text()

    def test_RM1_RM2_each_mission_retains_decision_attempt_and_observed_metrics(self):
        self.configure(cross=True)
        self.addCleanup(lambda: self.environ.stop())
        cli = self.root / 'claude'
        cli.write_text(cli.read_text().replace("'modelUsage':{'claude-review':{}}",
                       "'usage':{'output_tokens':5,'private':'PRIVATE-CLI'},"
                       "'total_cost_usd':0,'modelUsage':{'claude-review':{}}"))
        report = self.delegate()['example']
        rows = [json.loads(line) for line in self.journal().splitlines()]
        history = report['missions']
        self.assertEqual(len(rows), 3)
        self.assertEqual([item['attempts_used'] for item in history], [1, 2, 3])
        for row, mission, role in zip(rows, history, ('test-author', 'implementer', 'reviewer')):
            self.assertEqual(mission['role'], role)
            self.assertEqual(mission['phase'], 'BUILD')
            for key in ('role', 'phase', 'routing_decision', 'attempts_used', 'usage',
                        'cost_usd', 'duration_seconds', 'model_execution'):
                self.assertEqual(row[key], mission[key])
            self.assertGreaterEqual(mission['duration_seconds'], 0)
            self.assertEqual(mission['routing_decision']['source'], 'rule')
            self.assertIsNone(mission['model_execution']['observed']['effort'])
        self.assertIsNone(history[0]['usage'])
        self.assertIsNone(history[0]['cost_usd'])
        self.assertEqual(history[-1]['usage'], {'output_tokens': 5})
        self.assertEqual(history[-1]['cost_usd'], 0)
        self.assertEqual(history[-1]['model_execution']['provider'], 'anthropic')
        self.assertEqual(history[-1]['model_execution']['observed']['model'], 'claude-review')
        self.assertEqual(report['attempts_used'], 3)
        self.assertEqual(report['routing_decision'], history[-1]['routing_decision'])
        self.assertNotIn('PRIVATE-CLI', self.journal())
        before = self.journal()
        repeated = self.delegate()['example']
        self.assertEqual(repeated['missions'], history)
        self.assertEqual(self.journal(), before)
        self.assertNotIn('READY_FOR_HUMAN', json.dumps(report))

    def test_RM3_blocked_quota_is_recorded_without_changing_retry_or_gate_behavior(self):
        self.configure(cross=True)
        self.addCleanup(lambda: self.environ.stop())
        self.mode('quota')
        report = self.delegate()['example']
        row = json.loads(self.journal().splitlines()[-1])
        self.assertEqual(report['state'], 'BLOCKED')
        self.assertTrue(row['blocked'])
        self.assertEqual(row['role'], 'reviewer')
        self.assertEqual(row['attempts_used'], 3)
        self.assertIsNone(row['usage'])
        self.assertIsNone(row['cost_usd'])
        before = self.journal()
        self.assertEqual(self.delegate()['example']['state'], 'BLOCKED')
        self.assertEqual(self.journal(), before)
        self.assertFalse(self.task()['active'])


if __name__ == '__main__':
    unittest.main()
