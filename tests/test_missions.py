"""#86: one PR, specialized missions, deterministic Verify and safe replay.

The executable is a local fake Codex CLI. These tests prove orchestration and
mutation detection, not enforcement by a real Codex sandbox or model behavior.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mission_run', SOURCE / 'scripts/agentic-run.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)

FAKE_CLI = r'''
import json, os, re, sys, time
from pathlib import Path
root = Path(__file__).resolve().parent
args = sys.argv[1:]
tree = Path(args[args.index('-C') + 1])
prompt = args[-1]
role = re.search(r'Rôle : ([\w-]+)', prompt).group(1)
mode = (root / 'mode').read_text().strip()
with (root / 'events').open('a') as stream:
    stream.write(json.dumps({'event':'launch', 'role':role,
                            'model':args[args.index('-m') + 1], 'pid':os.getpid()}) + '\n')
test = 'import unittest, a\nclass T(unittest.TestCase):\n    def test_RM1(self):\n        self.assertEqual(a.VALUE, 1)\n'
if role == 'test-author':
    if mode != 'test-noop':
        (tree / 'test_a.py').write_text(test)
    if mode == 'test-product':
        (tree / 'a.py').write_text('VALUE = 1\n')
    if mode == 'test-timeout':
        time.sleep(30)
elif role == 'implementer':
    if mode != 'impl-noop':
        (tree / 'a.py').write_text('VALUE = 1\n')
    if mode == 'impl-cheat':
        (tree / 'test_a.py').write_text(test.replace('1)', '2)'))
    if 'test-author' not in (root / 'events').read_text():
        (tree / 'test_a.py').write_text(test)
    if mode == 'impl-blocked':
        print('```handoff\n' + json.dumps({'status':'BLOCKED','blockers':['needs decision']}) + '\n```')
        sys.exit(0)
elif role == 'reviewer' and mode == 'review-write':
    (tree / 'a.py').write_text('VALUE = 2\n')
reply = {'status':'COMPLETED','summary':'local fake only', 'files':[], 'blockers':[]}
if role == 'reviewer' and mode != 'review-missing':
    reply['review'] = {'verdict':'PASS','findings':[]}
    if mode == 'review-major':
        reply['review']['findings'] = [{'severity':'Major','message':'AC missing'}]
    if mode == 'review-reject':
        reply['review']['verdict'] = 'CHANGES_REQUIRED'
if not (role == 'test-author' and mode == 'test-no-handoff'):
    print('```handoff\n' + json.dumps(reply) + '\n```')
'''

VERIFY = r'''
import json, subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parent
value = Path('a.py').read_text().strip()
with (root / 'events').open('a') as stream:
    stream.write(json.dumps({'event':'verify','value':value}) + '\n')
sys.exit(subprocess.call([sys.executable, '-m', 'unittest', 'discover']))
'''


class MissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'a.py').write_text('VALUE = 0\n')
        (self.repo / '.gitignore').write_text('__pycache__/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.tree = self.root / 'worktree'
        self.git('worktree', 'add', '-q', '-b', 'feat/example', str(self.tree))
        self.initial = self.git('rev-parse', 'HEAD')
        executable = self.root / 'codex'
        executable.write_text('#!' + sys.executable + '\n' + FAKE_CLI)
        executable.chmod(0o755)
        self.verify = self.root / 'verify.py'
        self.verify.write_text(VERIFY)
        (self.root / 'events').write_text('')
        self.mode('ok')
        self.manifest = self.root / 'plan.json'
        self.plan = {'version': 1, 'story': 'example', 'capabilities': ['value'], 'prs': [{
            'id': 'example', 'reason': 'Set the expected value', 'capabilities': ['value'],
            'files': ['a.py', 'test_a.py'], 'acceptance': ['RM1: VALUE is 1'],
            'tests': ['RM1 behavior'], 'contracts': [], 'depends_on': [],
            'branch': 'feat/example', 'worktree': str(self.tree), 'implementer': 'writer'}]}
        self.manifest.write_text(json.dumps(self.plan))
        self.state = self.root / 'state.json'
        self.config_path = self.root / 'config.json'
        self.config = {'version': 1, 'models': [
            {'id': role, 'harness': 'codex', 'model': role + '-model',
             'max_level': 'HIGH' if role == 'reviewer' else 'MEDIUM',
             'efforts': ['high'] if role == 'reviewer' else ['medium'], 'cost_rank': rank}
            for rank, role in enumerate(('test-author', 'implementer', 'reviewer'))],
            'run': {'timeout_seconds': 3, 'missions': {'enabled': True}},
            'routing_policy': {'version': 1, 'enabled': True, 'rules': [
                {'id': role, 'match': {'role': role}, 'prefer': [{'model': role}]}
                for role in ('test-author', 'implementer', 'reviewer')]}}
        self.environ = mock.patch.dict(os.environ, {
            'PATH': str(self.root) + os.pathsep + os.environ['PATH'],
            'PYTHONDONTWRITEBYTECODE': '1'})
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def git(self, *args, repo=None):
        return subprocess.run(['git', '-C', str(repo or self.repo), *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def mode(self, value):
        (self.root / 'mode').write_text(value)

    def events(self):
        return [json.loads(line) for line in (self.root / 'events').read_text().splitlines()]

    def roles(self):
        return [event['role'] for event in self.events() if event['event'] == 'launch']

    def delegate(self):
        self.config_path.write_text(json.dumps(self.config))
        return RUN.delegate(self.manifest, self.repo, config_path=self.config_path,
                            state=self.state, commands=[[sys.executable, str(self.verify)]])

    def assert_blocked(self, report):
        self.assertFalse(RUN.succeeded(report, False), report)
        self.assertNotIn('READY_FOR_HUMAN', json.dumps(report))

    def test_AC1_RM1_routes_each_mission_and_verifies_before_independent_review(self):
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        self.assertEqual(self.roles(), ['test-author', 'implementer', 'reviewer'])
        launches = [event for event in self.events() if event['event'] == 'launch']
        self.assertEqual([event['model'] for event in launches],
                         ['test-author-model', 'implementer-model', 'reviewer-model'])
        self.assertEqual(len({event['pid'] for event in launches}), 3)
        review_index = next(i for i, event in enumerate(self.events())
                            if event.get('role') == 'reviewer')
        self.assertTrue(any(event == {'event': 'verify', 'value': 'VALUE = 1'}
                            for event in self.events()[:review_index]))
        self.assertEqual(self.git('rev-parse', 'HEAD', repo=self.tree), self.initial)
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertNotIn('READY_FOR_HUMAN', json.dumps(report))

    def test_RM1_initially_passing_tests_also_allow_implementation_without_red_commit(self):
        (self.tree / 'a.py').write_text('VALUE = 1\n')
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        self.assertEqual(self.roles(), ['test-author', 'implementer', 'reviewer'])
        self.assertEqual(self.git('rev-parse', 'HEAD', repo=self.tree), self.initial)

    def test_RM1_test_author_cannot_change_product(self):
        self.mode('test-product')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), ['test-author'])

    def test_RM1_tests_only_success_without_tests_does_not_advance(self):
        self.mode('test-noop')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), ['test-author'])

    def test_RM1_tests_only_success_without_handoff_does_not_advance(self):
        self.mode('test-no-handoff')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), ['test-author'])

    def test_RM2_implementer_cannot_rewrite_transmitted_tests(self):
        self.mode('impl-cheat')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), ['test-author', 'implementer'])

    def test_RM3_failed_verify_prevents_review_even_if_agent_reports_completed(self):
        self.mode('impl-noop')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), ['test-author', 'implementer'])

    def test_RM3_reviewer_cannot_write(self):
        self.mode('review-write')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), ['test-author', 'implementer', 'reviewer'])

    def test_RM3_major_finding_blocks_even_when_verdict_says_pass(self):
        self.mode('review-major')
        self.assert_blocked(self.delegate())
        self.assertIn('reviewer', self.roles())

    def test_RM3_missing_review_result_is_not_success(self):
        self.mode('review-missing')
        self.assert_blocked(self.delegate())
        self.assertIn('reviewer', self.roles())

    def test_RM3_changes_required_review_is_not_success(self):
        self.mode('review-reject')
        self.assert_blocked(self.delegate())

    def test_RM4_finished_pipeline_reentry_does_not_launch_again(self):
        first = self.delegate()
        self.assertTrue(RUN.succeeded(first, False), first)
        events = self.events()
        second = self.delegate()
        self.assertTrue(RUN.succeeded(second, False), second)
        self.assertEqual(self.events(), events)

    def test_acceptance_can_resume_after_review_is_persisted_without_new_launch(self):
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        events = self.events()
        resumed = RUN.delegate(
            self.manifest, self.repo, config_path=self.config_path, state=self.state,
            commands=[[sys.executable, str(self.verify)]], accept=True)
        self.assertTrue(RUN.succeeded(resumed, False), resumed)
        self.assertTrue(resumed['example']['accepted'])
        self.assertEqual(self.events(), events)

    def test_RM4_blocked_stage_reentry_does_not_blindly_retry_or_advance(self):
        self.mode('impl-blocked')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), ['test-author', 'implementer'])
        events = self.events()
        self.mode('ok')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(), events)

    def test_RM4_mutated_content_invalidates_finished_pipeline_without_relaunch(self):
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        self.assertEqual(self.roles(), ['test-author', 'implementer', 'reviewer'])
        events = self.events()
        (self.tree / 'test_a.py').write_text('raise RuntimeError("mutated")\n')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(), events)

    def test_RM4_disabled_pipeline_keeps_legacy_single_implementer(self):
        self.config['run']['missions']['enabled'] = False
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        self.assertEqual(self.roles(), ['implementer'])

    def test_resume_after_stopped_handoff_before_transition_does_not_repeat_tests(self):
        scheduler = RUN.module('scheduler')
        original_module = RUN.module
        with mock.patch.object(RUN, 'module', side_effect=lambda name: (
                scheduler if name == 'scheduler' else original_module(name))):
            with mock.patch.object(scheduler.Scheduler, 'finish_mission',
                                   side_effect=RuntimeError('interrupted before transition')):
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    self.delegate()
        self.assertEqual(self.roles(), ['test-author'])
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        self.assertEqual(self.roles(), ['test-author', 'implementer', 'reviewer'])

    def test_changed_plan_invalidates_pipeline_without_relaunch(self):
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        events = self.events()
        self.plan['prs'][0]['reason'] += ' changed'
        self.manifest.write_text(json.dumps(self.plan))
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(), events)

    def test_legacy_planned_state_cannot_bypass_test_author_when_missions_enabled(self):
        RUN.module('scheduler').Scheduler(self.manifest, self.repo, self.state).resume()
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(), [])

    def test_uninitialized_gitlink_blocks_before_any_mission_launch(self):
        self.git('update-index', '--add', '--cacheinfo',
                 '160000,' + self.initial + ',library', repo=self.tree)
        self.git('commit', '-qm', 'gitlink fixture', repo=self.tree)
        self.assertFalse((self.tree / 'library').exists())
        self.plan['prs'][0]['files'].append('library')
        self.manifest.write_text(json.dumps(self.plan))
        report = self.delegate()
        self.assert_blocked(report)
        self.assertIn('gitlinks', json.dumps(report))
        self.assertEqual(self.roles(), [])

    def test_independent_review_retains_high_capacity_without_routing_policy(self):
        self.config['routing_policy']['enabled'] = False
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        review = next(event for event in self.events() if event.get('role') == 'reviewer')
        self.assertEqual(review['model'], 'reviewer-model')

    def test_disabled_config_cannot_reinterpret_finished_pipeline_as_legacy_success(self):
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        events = self.events()
        self.config['run']['missions']['enabled'] = False
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(), events)

    def test_changed_head_invalidates_pipeline_without_relaunch(self):
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        events = self.events()
        self.git('add', 'a.py', 'test_a.py', repo=self.tree)
        self.git('commit', '-qm', 'changed fixture HEAD', repo=self.tree)
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(), events)

    def test_unconfirmed_stop_keeps_owner_and_blocks_transition(self):
        original_wait = RUN.ProcessAdapter.wait

        def unconfirmed(adapter, task):
            return {**original_wait(adapter, task), 'stopped_confirmed': False}

        with mock.patch.object(RUN.ProcessAdapter, 'wait', unconfirmed):
            self.assert_blocked(self.delegate())
        task = json.loads(self.state.read_text())['tasks']['example']
        self.assertIn('owner', task)
        self.assertTrue(task['active'])
        events = self.events()
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(), events)

    def test_mismatched_handoff_identity_cannot_release_or_advance(self):
        original_wait = RUN.ProcessAdapter.wait

        def mismatched(adapter, task):
            return {**original_wait(adapter, task), 'agent_id': 'another-runtime'}

        with mock.patch.object(RUN.ProcessAdapter, 'wait', mismatched):
            self.assert_blocked(self.delegate())
        task = json.loads(self.state.read_text())['tasks']['example']
        self.assertIn('owner', task)
        self.assertTrue(task['active'])
        self.assertEqual(self.roles(), ['test-author'])

    def test_reviewer_receipt_cannot_reuse_observed_writer_identity(self):
        original_launch = RUN.ProcessAdapter.launch
        writer = {}

        def reused(adapter, task):
            receipt = original_launch(adapter, task)
            if task['role'] == 'implementer':
                writer['agent_id'] = receipt['agent_id']
            elif task['role'] == 'reviewer':
                receipt['agent_id'] = writer['agent_id']
            return receipt

        with mock.patch.object(RUN.ProcessAdapter, 'launch', reused):
            self.assert_blocked(self.delegate())
        task = json.loads(self.state.read_text())['tasks']['example']
        self.assertFalse(task['independent_review'])
        self.assertIn('owner', task)
        self.assertEqual(self.roles(), ['test-author', 'implementer'])

    def test_explicit_requeue_retains_mission_and_locked_tests(self):
        self.mode('impl-blocked')
        self.assert_blocked(self.delegate())
        persisted = json.loads(self.state.read_text())
        task = persisted['tasks']['example']
        scheduler = RUN.module('scheduler').Scheduler(
            self.manifest, self.repo, self.state,
            models=RUN.build_inventory(self.config)[0],
            routing_policy=self.config['routing_policy'], missions=True,
            execution_context={'config': self.config,
                               'commands': [[sys.executable, str(self.verify)]]})
        scheduler.requeue('example', {
            'orchestrator_verified': True, 'reason': 'decision resolved', 'proof': 'fixture',
            'plan_sha256': task['plan_sha256'], 'agent_id': task['agent_id'],
            'stopped_confirmed': True, 'identity_verified': True,
            'snapshot': RUN.module('quality').snapshot(self.tree)})
        self.mode('ok')
        self.assertTrue(RUN.succeeded(self.delegate(), False))
        self.assertEqual(self.roles(), ['test-author', 'implementer', 'implementer', 'reviewer'])


if __name__ == '__main__':
    unittest.main()
