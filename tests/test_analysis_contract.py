"""Regression cases for evidence omitted from Git snapshots and declared coverage."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import unittest
from unittest import mock

import test_analysis as fixtures

RUN = fixtures.RUN


class AnalysisContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DualAnalysisTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def ignored_source(self):
        fixture = self.fixture
        exclude = Path(fixture.git('rev-parse', '--git-path', 'info/exclude', repo=fixture.tree))
        if not exclude.is_absolute():
            exclude = fixture.tree / exclude
        with exclude.open('a') as stream:
            stream.write('\ncontext.txt\n')
        source = fixture.tree / 'context.txt'
        source.write_text('The prepared context.')
        fixture.plan['prs'][0]['analysis']['sources'][0]['path'] = 'context.txt'
        return source

    @contextmanager
    def scheduler_runtime(self):
        scheduler, module = RUN.module('scheduler'), RUN.module
        with mock.patch.object(RUN, 'module', side_effect=lambda name:
                               scheduler if name == 'scheduler' else module(name)):
            yield scheduler

    def pause_before_writer(self, scheduler):
        assign = scheduler.Scheduler._assign

        def hold(instance, state, pr):
            if state['tasks'][pr].get('mission_index') == 2:
                raise ValueError('fixture pause before first writer')
            return assign(instance, state, pr)

        with mock.patch.object(scheduler.Scheduler, '_assign', hold):
            report = self.fixture.delegate()
        self.fixture.assert_no_build(report)
        self.assertEqual(len(self.fixture.analyses()), 2)
        return report

    def requeue_current(self, scheduler):
        captured, initialize = [], scheduler.Scheduler.__init__

        def capture(instance, *args, **kwargs):
            initialize(instance, *args, **kwargs)
            captured.append(instance)

        with mock.patch.object(scheduler.Scheduler, '__init__', capture):
            self.fixture.delegate()
        state = json.loads(self.fixture.state.read_text())
        task = state['tasks']['example']
        evidence = {'orchestrator_verified': True, 'reason': 'Explicit fixture reconciliation',
                    'proof': 'Current plan, observed stopped runtime and content inspected',
                    'plan_sha256': state['plan_sha256'],
                    'snapshot': scheduler.snapshot(self.fixture.tree)}
        if task.get('agent_id') is not None:
            evidence.update(agent_id=task['agent_id'], stopped_confirmed=True,
                            identity_verified=True)
        error = None
        try:
            captured[-1].requeue('example', evidence)
        except ValueError as caught:
            error = caught
        return self.fixture.delegate(), error

    def pause_after_writer(self, role):
        wait = RUN.ProcessAdapter.wait

        def hold(adapter, task):
            observation = wait(adapter, task)
            if task.get('phase') == 'BUILD' and task.get('role') == role:
                observation.update(outcome='BLOCKED', blockers=['fixture pause after real write'])
            return observation

        with mock.patch.object(RUN.ProcessAdapter, 'wait', hold):
            report = self.fixture.delegate()
        self.assertFalse(RUN.succeeded(report, False))
        self.assertEqual(len(self.fixture.analyses()), 2)

    def assert_stale_consensus(self, report):
        summary = report['example']['analysis']
        self.assertEqual(summary['verdict'], 'BLOCKED')
        self.assertTrue(summary['stale'])
        self.assertEqual(summary['historical_verdict'], 'PASS')

    def test_requeue_cannot_reuse_consensus_after_scope_plan_and_snapshot_change(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_before_writer(scheduler)
            fixture.plan['prs'][0]['files'].append('b.py')
            (fixture.tree / 'b.py').write_text('NEW_SCOPE = True\n')
            report, _ = self.requeue_current(scheduler)
        fixture.assert_no_build(report)
        self.assert_stale_consensus(report)
        self.assertEqual(len(fixture.analyses()), 2)

    def test_requeue_cannot_replace_prewrite_snapshot_even_with_unchanged_sources(self):
        fixture = self.fixture
        fixture.plan['prs'][0]['files'].append('b.py')
        with self.scheduler_runtime() as scheduler:
            self.pause_before_writer(scheduler)
            (fixture.tree / 'b.py').write_text('CHANGED_INPUT = True\n')
            report, _ = self.requeue_current(scheduler)
        fixture.assert_no_build(report)
        self.assert_stale_consensus(report)

    def test_requeue_cannot_reuse_consensus_after_base_head_changes(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_before_writer(scheduler)
            fixture.git('commit', '--allow-empty', '-qm', 'fixture changed base', repo=fixture.tree)
            report, _ = self.requeue_current(scheduler)
        self.assertFalse(RUN.succeeded(report, False))
        self.assertFalse(any(e['phase'] == 'BUILD' for e in fixture.events()))
        self.assert_stale_consensus(report)

    def test_requeue_cannot_reuse_consensus_after_execution_config_changes(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_before_writer(scheduler)
            fixture.config['run']['max_turns'] = 12
            report, _ = self.requeue_current(scheduler)
        fixture.assert_no_build(report)
        self.assert_stale_consensus(report)

    def test_requeue_cannot_reuse_consensus_after_routing_policy_changes(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_before_writer(scheduler)
            fixture.config['routing_policy'] = {'version': 1, 'enabled': True, 'rules': [{
                'id': 'new-policy', 'match': {'role': 'implementer', 'phase': 'BUILD'},
                'prefer': [{'model': 'codex'}], 'fallback': 'blocked'}]}
            report, _ = self.requeue_current(scheduler)
        fixture.assert_no_build(report)
        self.assert_stale_consensus(report)

    def test_explicit_requeue_preserves_consensus_when_prewrite_contract_is_unchanged(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_before_writer(scheduler)
            report, error = self.requeue_current(scheduler)
        self.assertIsNone(error)
        self.assertTrue(RUN.succeeded(report, False), report)
        self.assertEqual(len(fixture.analyses()), 2)

    def test_first_writer_requeue_preserves_observed_authorization_and_test_changes(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_after_writer('test-author')
            before = json.loads(fixture.state.read_text())['tasks']['example']
            proof = before.get('analysis_consumption')
            self.assertIsNotNone(proof)
            self.assertEqual(proof['receipt']['agent_id'], before['agent_id'])
            self.assertTrue(proof['receipt']['launch_observed'])
            self.assertTrue((fixture.tree / 'test_a.py').exists())
            report, error = self.requeue_current(scheduler)
        self.assertIsNone(error)
        self.assertTrue(RUN.succeeded(report, False), report)
        after = json.loads(fixture.state.read_text())['tasks']['example']
        self.assertEqual(after['analysis_consumption'], proof)
        self.assertTrue(any(h['task'].get('analysis_consumption') == proof
                            for h in after['mission_history']))
        self.assertEqual(len(fixture.analyses()), 2)

    def test_implementer_requeue_preserves_legitimate_source_changes_on_same_contract(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_after_writer('implementer')
            self.assertEqual((fixture.tree / 'a.py').read_text(), 'VALUE = 1\n')
            report, error = self.requeue_current(scheduler)
        self.assertIsNone(error)
        self.assertTrue(RUN.succeeded(report, False), report)
        self.assertEqual(len(fixture.analyses()), 2)

    def test_consumed_authorization_cannot_validate_a_new_contract_after_requeue(self):
        fixture = self.fixture
        with self.scheduler_runtime() as scheduler:
            self.pause_after_writer('implementer')
            launches = len(fixture.events())
            fixture.plan['prs'][0]['acceptance'].append('AC2: a new prepared criterion')
            report, _ = self.requeue_current(scheduler)
        self.assertFalse(RUN.succeeded(report, False))
        self.assertEqual(len(fixture.events()), launches)
        self.assert_stale_consensus(report)

    def test_empty_opinions_cannot_turn_two_exits_into_consensus(self):
        fixture = self.fixture
        fixture.opinions['codex'] = {key: [] for key in ('decisions', 'risks', 'assumptions')}
        fixture.assert_no_build(fixture.delegate())

    def test_completed_envelope_with_blockers_cannot_authorize_build(self):
        fixture, wait = self.fixture, RUN.ProcessAdapter.wait

        def blocked(adapter, task):
            observation = wait(adapter, task)
            if task.get('phase') == 'PREPARE':
                observation['result']['handoff']['blockers'] = ['An unresolved requirement remains']
            return observation

        with mock.patch.object(RUN.ProcessAdapter, 'wait', blocked):
            fixture.assert_no_build(fixture.delegate())

    def test_valid_citations_are_insufficient_when_other_ac_and_rules_are_omitted(self):
        fixture = self.fixture
        unit = fixture.plan['prs'][0]
        unit['acceptance'].append('AC2: prepared requirement must be examined')
        unit['analysis']['rules'].append({'id': 'RM2', 'text': 'Examine the second requirement'})
        fixture.assert_no_build(fixture.delegate())

    def test_changed_ignored_source_after_second_handoff_blocks_consensus(self):
        fixture, source = self.fixture, self.ignored_source()
        wait = RUN.ProcessAdapter.wait

        def changed(adapter, task):
            observation = wait(adapter, task)
            if task.get('phase') == 'PREPARE' and task.get('analysis_provider') == 'claude':
                source.write_text('Changed after analysis.')
            return observation

        with mock.patch.object(RUN.ProcessAdapter, 'wait', changed):
            fixture.assert_no_build(fixture.delegate())
        self.assertEqual(len(fixture.analyses()), 2)

    def test_changed_ignored_source_before_first_build_assignment_blocks_writer(self):
        fixture, source = self.fixture, self.ignored_source()
        scheduler = RUN.module('scheduler')
        assign, module = scheduler.Scheduler._assign, RUN.module

        def changed(instance, state, pr):
            if state['tasks'][pr].get('mission_index') == 2:
                source.write_text('Changed immediately before BUILD.')
            return assign(instance, state, pr)

        with mock.patch.object(scheduler.Scheduler, '_assign', changed), mock.patch.object(
                RUN, 'module', side_effect=lambda name: scheduler if name == 'scheduler' else module(name)):
            fixture.assert_no_build(fixture.delegate())
        self.assertEqual(len(fixture.analyses()), 2)

    def test_changed_ignored_source_after_launch_cannot_release_first_writer(self):
        fixture, source = self.fixture, self.ignored_source()
        launch = RUN.ProcessAdapter.launch

        def changed(adapter, task):
            receipt = launch(adapter, task)
            if task.get('role') == 'test-author':
                source.write_text('Changed while the child waits at the handshake.')
                self.addCleanup(adapter.jobs[task['unit']['id']]['process'].stdin.close)
            return receipt

        with mock.patch.object(RUN.ProcessAdapter, 'launch', changed):
            fixture.assert_no_build(fixture.delegate())
        self.assertEqual(len(fixture.analyses()), 2)

    def test_active_policy_cannot_replace_claude_analysis_with_another_codex_launch(self):
        fixture = self.fixture
        fixture.config['routing_policy'] = {'version': 1, 'enabled': True, 'rules': [{
            'id': 'codex-only', 'match': {'role': 'explorer', 'phase': 'PREPARE'},
            'prefer': [{'model': 'codex'}], 'fallback': 'blocked'}]}
        fixture.assert_no_build(fixture.delegate())
        self.assertEqual([event['provider'] for event in fixture.analyses()], ['codex'])

    def test_malformed_arbitration_can_be_corrected_without_relaunching_agents(self):
        fixture = self.fixture
        fixture.divergent_risk()
        fixture.arbitration.write_text('{invalid')
        first = fixture.delegate()
        fixture.assert_no_build(first)
        fixture.write_arbitration(first)
        self.assertTrue(RUN.succeeded(fixture.delegate(), False))
        self.assertEqual(len(fixture.analyses()), 2)

    def test_unobserved_launch_or_stop_never_counts_as_an_opinion(self):
        fixture = self.fixture
        fixture.divergent_risk()
        fixture.assert_no_build(fixture.delegate())
        state = json.loads(fixture.state.read_text())
        task = state['tasks']['example']
        history = [h['task'] for h in task['mission_history'] if h['task']['phase'] == 'PREPARE']
        for key, value in (('runtime', 'simulated'), ('launch_status', 'UNKNOWN'), ('active', True)):
            with self.subTest(key=key):
                altered = copy.deepcopy(history)
                altered[1][key] = value
                with self.assertRaises(ValueError):
                    RUN.module('analysis').synthesize(altered, task['analysis_bundle'])


if __name__ == '__main__':
    unittest.main()
