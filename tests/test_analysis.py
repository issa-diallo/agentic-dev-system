"""#87: opt-in dual analysis uses real fake-CLI processes and blocks unsafe BUILD.

The CLIs below are local fixtures. Tests prove orchestration, evidence freshness,
and failure handling; they neither invoke inference nor prove a model's reasoning.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('analysis_run', SOURCE / 'scripts/agentic-run.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)

FAKE_CLI = r'''
import copy, json, os, re, sys, time
from pathlib import Path
root, name, args = Path(__file__).parent, Path(__file__).name, sys.argv[1:]
if args[:2] in (['auth', 'status'], ['login', 'status']):
    if name == 'codex':
        print('Logged in using ChatGPT', file=sys.stderr)
    else:
        print(json.dumps({'loggedIn': True, 'authMethod': 'claude.ai',
                          'apiProvider': 'firstParty', 'subscriptionType': 'pro'}))
    sys.exit(0)
if name == 'claude' and '--bare' in args:
    print(json.dumps({'type': 'result', 'is_error': True, 'result': 'Not logged in'}))
    sys.exit(1)
tree = Path(args[args.index('-C') + 1]) if name == 'codex' else Path.cwd()
prompt = args[-1] if name == 'codex' else args[args.index('-p') + 1]
role = re.search(r'Rôle : ([\w-]+)', prompt).group(1)
phase = re.search(r'phase : (\w+)', prompt).group(1)
mode = (root / 'mode').read_text().strip()
with (root / 'events').open('a') as stream:
    stream.write(json.dumps({'provider': name, 'role': role, 'phase': phase,
                            'pid': os.getpid(), 'prompt': prompt, 'argv': args}) + '\n')
reply = {'status': 'COMPLETED', 'summary': 'local fake only', 'files': [], 'blockers': []}
if role == 'explorer' and phase == 'PREPARE':
    bundle = json.loads(re.search(r'```analysis-input\n(.*?)\n```', prompt, re.S).group(1))
    reply['analysis'] = copy.deepcopy(json.loads((root / 'opinions.json').read_text())[name])
    reply['analysis']['bundle_sha256'] = bundle['bundle_sha256']
    if name == 'claude':
        if mode == 'fail':
            sys.exit(3)
        if mode == 'quota':
            print('usage limit reached', file=sys.stderr)
            sys.exit(1)
        if mode == 'timeout':
            time.sleep(30)
        if mode == 'missing-handoff':
            print('An unstructured opinion is not an accepted handoff')
            sys.exit(0)
        if mode == 'missing-analysis':
            reply.pop('analysis')
        if mode == 'wrong-bundle':
            reply['analysis']['bundle_sha256'] = '0' * 64
        if mode == 'write':
            (tree / 'a.py').write_text('VALUE = 99\n')
elif role == 'test-author':
    (tree / 'test_a.py').write_text('import unittest, a\nclass T(unittest.TestCase):\n'
                                  '    def test_value(self):\n'
                                  '        self.assertEqual(a.VALUE, 1)\n')
elif role == 'implementer':
    (tree / 'a.py').write_text('VALUE = 1\n')
elif role == 'reviewer':
    reply['review'] = {'verdict': 'PASS', 'findings': []}
text = '```handoff\n' + json.dumps(reply) + '\n```'
if name == 'claude':
    print(json.dumps({'type': 'result', 'result': text,
                      'session_id': 'claude-' + str(os.getpid()),
                      'modelUsage': {'claude-test': {}}}))
else:
    print(text)
'''


def opinion():
    references = {'acceptance': ['AC1'], 'rules': ['RM1'], 'sources': ['S1']}
    return {'decisions': [{'id': 'D1', 'statement': 'Set VALUE to 1',
                           'rationale': 'The prepared criterion requires the expected value.',
                           **references}],
            'risks': [],
            'assumptions': [{'id': 'A1', 'statement': 'No external service is needed',
                             'rationale': 'The supplied source is a local constant.',
                             **references}]}


class DualAnalysisTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo, self.bin, self.home = [self.root / p for p in ('repo', 'bin', 'home')]
        for path in (self.repo, self.bin, self.home):
            path.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'a.py').write_text('VALUE = 0\n')
        (self.repo / '.gitignore').write_text('__pycache__/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.tree = self.root / 'worktree'
        self.git('worktree', 'add', '-q', '-b', 'feat/value', str(self.tree))
        self.initial = self.git('rev-parse', 'HEAD')
        for name in ('codex', 'claude'):
            executable = self.bin / name
            executable.write_text('#!' + sys.executable + '\n' + FAKE_CLI)
            executable.chmod(0o755)
        (self.bin / 'events').write_text('')
        (self.bin / 'mode').write_text('ok')
        self.opinions = {'codex': opinion(), 'claude': opinion()}
        self.manifest, self.state = [self.root / p for p in ('plan.json', 'state.json')]
        self.arbitration = self.root / 'arbitration.json'
        self.plan = {'version': 1, 'story': 'example', 'capabilities': ['value'], 'prs': [{
            'id': 'example', 'reason': 'Set expected value', 'capabilities': ['value'],
            'files': ['a.py', 'test_a.py'], 'acceptance': ['AC1: VALUE equals 1'],
            'tests': ['RM1 behavior'], 'contracts': [], 'depends_on': [],
            'branch': 'feat/value', 'worktree': str(self.tree), 'implementer': 'writer',
            'routing': {'complexity': 'high'},
            'analysis': {'rules': [{'id': 'RM1', 'text': 'VALUE must equal 1'}],
                         'sources': [{'id': 'S1', 'path': 'a.py'}]}}]}
        self.config_path = self.root / 'config.json'
        self.config = {'version': 1, 'models': [
            {'id': name, 'harness': name, 'model': name + '-test', 'max_level': 'EXTRA_HIGH',
             'efforts': ['medium', 'high', 'xhigh'], 'cost_rank': rank}
            for rank, name in enumerate(('codex', 'claude'))],
            'run': {'timeout_seconds': 2, 'subscription_only': True,
                    'missions': {'enabled': True},
                    'double_analysis': {'enabled': True,
                                        'justification': 'Two analyses for a costly decision.',
                                        'arbitration_file': str(self.arbitration)}}}
        environment = {'PATH': str(self.bin) + os.pathsep + str(Path(shutil.which('git')).parent),
                       'HOME': str(self.home), 'LANG': 'C', 'PYTHONDONTWRITEBYTECODE': '1'}
        patcher = mock.patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        managed = mock.patch.object(RUN, 'CLAUDE_MANAGED_DIR', self.root / 'managed')
        managed.start()
        self.addCleanup(managed.stop)

    def git(self, *args, repo=None):
        return subprocess.run(['git', '-C', str(repo or self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def delegate(self, **kwargs):
        self.manifest.write_text(json.dumps(self.plan))
        self.config_path.write_text(json.dumps(self.config))
        (self.bin / 'opinions.json').write_text(json.dumps(self.opinions))
        return RUN.delegate(self.manifest, self.repo, config_path=self.config_path,
                            state=self.state,
                            commands=[[sys.executable, '-m', 'unittest', 'discover']], **kwargs)

    def events(self):
        return [json.loads(line) for line in (self.bin / 'events').read_text().splitlines()]

    def analyses(self):
        return [e for e in self.events() if e['role'] == 'explorer' and e['phase'] == 'PREPARE']

    def assert_no_build(self, report):
        self.assertFalse(RUN.succeeded(report, False), report)
        self.assertFalse(any(e['role'] in ('test-author', 'implementer') for e in self.events()))
        self.assertNotIn('READY_FOR_HUMAN', json.dumps(report))
        self.assertEqual(self.git('rev-parse', 'HEAD', repo=self.tree), self.initial)

    def divergent_risk(self):
        references = {'acceptance': ['AC1'], 'rules': ['RM1'], 'sources': ['S1']}
        for provider, status in (('codex', 'open'), ('claude', 'mitigated')):
            self.opinions[provider]['risks'] = [{
                'id': 'R1', 'statement': 'The selected value may be wrong',
                'severity': 'Critical', 'status': status,
                'mitigation': '' if status == 'open' else 'Verify VALUE against AC1',
                'rationale': 'This affects the only acceptance criterion.', **references}]

    def write_arbitration(self, report):
        summary = report['example']['analysis']
        result = {'bundle_sha256': summary['bundle_sha256'],
                  'opinions_sha256': summary['opinions_sha256'],
                  'orchestrator_verified': True, 'verdict': 'PASS',
                  'resolutions': [{'dispute_id': dispute['id'],
                                   'decision': 'Set VALUE to 1 and verify it',
                                   'acceptance': ['AC1'], 'rules': ['RM1'], 'sources': ['S1'],
                                   'rationale': 'AC1 and RM1 require 1; the source is explicit.',
                                   'mitigation': 'The prepared test verifies VALUE equals 1.'}
                                  for dispute in summary['disputes']]}
        document = {'version': 1, 'units': {'example': result}}
        self.arbitration.write_text(json.dumps(document))
        return document

    def test_AC1_two_independent_launches_same_contract_before_build(self):
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        events = self.events()
        self.assertEqual([(e['role'], e['phase']) for e in events],
                         [('explorer', 'PREPARE'), ('explorer', 'PREPARE'),
                          ('test-author', 'BUILD'), ('implementer', 'BUILD'), ('reviewer', 'BUILD')])
        analyses = self.analyses()
        self.assertEqual({e['provider'] for e in analyses}, {'codex', 'claude'})
        self.assertEqual(len({e['pid'] for e in analyses}), 2)
        self.assertEqual(analyses[0]['prompt'], analyses[1]['prompt'])
        self.assertNotIn('The prepared criterion requires the expected value.', analyses[1]['prompt'])
        self.assertEqual(report['example']['analysis']['verdict'], 'PASS')
        history = json.loads(self.state.read_text())['tasks']['example']['mission_history']
        stopped = [h['task'] for h in history if h['task']['phase'] == 'PREPARE']
        self.assertEqual(len(stopped), 2)
        self.assertEqual(len({t['model_execution']['session_id'] for t in stopped}), 2)
        for task in stopped:
            self.assertTrue(task['stop_evidence']['stopped_confirmed'])
            self.assertTrue(task['stop_evidence']['identity_verified'])
            self.assertEqual(task['result']['handoff']['status'], 'COMPLETED')
            self.assertIsNone(task['model_execution']['observed']['effort'])
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertEqual(self.git('rev-parse', 'HEAD', repo=self.tree), self.initial)

    def test_AC4_extra_high_uses_the_same_optional_gate(self):
        self.plan['prs'][0]['routing'] = {'risk': 'critical'}
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        self.assertEqual(len(self.analyses()), 2)

    def test_AC4_low_and_medium_never_trigger_two_analyses_from_reviewer_high_floor(self):
        for routing in ({'type': 'documentation', 'complexity': 'low'}, {}):
            with self.subTest(routing=routing):
                with tempfile.TemporaryDirectory() as directory:
                    self.state = Path(directory) / 'state.json'
                    self.plan['prs'][0]['routing'] = routing
                    self.plan['prs'][0].pop('analysis', None)
                    (self.bin / 'events').write_text('')
                    # Reset only fixture changes from the preceding mission.
                    (self.tree / 'a.py').write_text('VALUE = 0\n')
                    (self.tree / 'test_a.py').unlink(missing_ok=True)
                    report = self.delegate()
                    self.assertTrue(RUN.succeeded(report, False), report)
                    self.assertEqual(self.analyses(), [])

    def test_AC4_disabled_option_preserves_the_high_mission_pipeline(self):
        self.config['run']['double_analysis'] = {'enabled': False}
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        self.assertEqual(self.analyses(), [])

    def test_AC3_critical_disagreement_blocks_before_any_writer(self):
        self.divergent_risk()
        report = self.delegate()
        self.assert_no_build(report)
        summary = report['example']['analysis']
        self.assertEqual(summary['verdict'], 'BLOCKED')
        self.assertTrue(summary['disputes'])
        self.assertEqual(len(summary['opinions_sha256']), 2)
        self.assertEqual(len(self.analyses()), 2)

    def test_AC3_consensus_cannot_clear_an_identical_open_critical_risk(self):
        self.divergent_risk()
        self.opinions['claude'] = copy.deepcopy(self.opinions['codex'])
        report = self.delegate()
        self.assert_no_build(report)
        self.assertTrue(report['example']['analysis']['disputes'])

    def test_AC3_valid_sourced_arbitration_resumes_without_relaunching_analysis(self):
        self.divergent_risk()
        first = self.delegate()
        self.assert_no_build(first)
        self.write_arbitration(first)
        resumed = self.delegate()
        self.assertTrue(RUN.succeeded(resumed, False), resumed)
        self.assertEqual(resumed['example']['analysis']['verdict'], 'PASS')
        self.assertEqual(len(self.analyses()), 2)
        self.assertEqual([e['role'] for e in self.events()].count('implementer'), 1)

    def test_AC3_arbitration_must_match_both_opinions_and_reference_real_contract(self):
        self.divergent_risk()
        first = self.delegate()
        self.assert_no_build(first)
        document = self.write_arbitration(first)
        unit = document['units']['example']
        cases = [('stale-bundle', lambda: unit.update(bundle_sha256='0' * 64)),
                 ('stale-opinions', lambda: unit.update(opinions_sha256=['0' * 64] * 2)),
                 ('unverified', lambda: unit.update(orchestrator_verified=False)),
                 ('missing-resolution', lambda: unit.update(resolutions=[])),
                 ('unknown-criterion', lambda: unit['resolutions'][0].update(acceptance=['AC404'])),
                 ('unknown-rule', lambda: unit['resolutions'][0].update(rules=['RM404'])),
                 ('unknown-source', lambda: unit['resolutions'][0].update(sources=['S404'])),
                 ('empty-rationale', lambda: unit['resolutions'][0].update(rationale='')),
                 ('missing-mitigation', lambda: unit['resolutions'][0].update(mitigation=''))]
        pristine = copy.deepcopy(unit)
        for name, mutate in cases:
            with self.subTest(name=name):
                unit.clear()
                unit.update(copy.deepcopy(pristine))
                mutate()
                self.arbitration.write_text(json.dumps(document))
                self.assert_no_build(self.delegate())
                self.assertEqual(len(self.analyses()), 2)

    def test_AC3_decision_or_assumption_disagreement_is_exposed_not_averaged(self):
        self.opinions['claude']['decisions'][0]['statement'] = 'Set VALUE to 2'
        self.opinions['claude']['assumptions'][0]['statement'] = 'An external service is required'
        report = self.delegate()
        self.assert_no_build(report)
        disputes = report['example']['analysis']['disputes']
        self.assertTrue(any('D1' in d['id'] for d in disputes))
        self.assertTrue(any('A1' in d['id'] for d in disputes))

    def test_AC2_missing_provider_blocks_without_fallback_or_writer(self):
        self.config['models'][1]['enabled'] = False
        self.assert_no_build(self.delegate())
        self.assertNotIn('claude', [e['provider'] for e in self.analyses()])

    def test_AC2_failure_quota_timeout_and_missing_reports_do_not_invent_second_opinion(self):
        # Each subcase has its own scheduler state; fixture product must remain unchanged.
        for mode in ('fail', 'quota', 'timeout', 'missing-handoff', 'missing-analysis', 'wrong-bundle'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                self.state = Path(directory) / 'state.json'
                (self.bin / 'events').write_text('')
                (self.bin / 'mode').write_text(mode)
                self.config['run']['timeout_seconds'] = 0.2 if mode == 'timeout' else 2
                first = self.delegate()
                self.assert_no_build(first)
                self.assertLessEqual(len(self.analyses()), 2)
                task = json.loads(self.state.read_text())['tasks']['example']
                self.assertFalse(task['active'])
                self.assertTrue(task['stop_evidence']['stopped_confirmed'])
                launches = len(self.events())
                self.assert_no_build(self.delegate())
                self.assertEqual(len(self.events()), launches)

    def test_AC1_duplicate_runtime_correlation_sessions_are_not_independent(self):
        launch = RUN.ProcessAdapter.launch

        def repeated_session(adapter, task):
            receipt = launch(adapter, task)
            if task.get('phase') == 'PREPARE':
                execution = adapter.jobs[task['unit']['id']]['model_execution']
                execution['session_id'] = 'same-analysis-session'
                receipt['model_execution']['session_id'] = 'same-analysis-session'
            return receipt

        with mock.patch.object(RUN.ProcessAdapter, 'launch', repeated_session):
            self.assert_no_build(self.delegate())

    def test_AC1_analysis_worktree_mutation_is_blocked(self):
        (self.bin / 'mode').write_text('write')
        self.assert_no_build(self.delegate())

    def test_AC3_changed_source_cannot_reuse_arbitration_or_relaunch_blindly(self):
        self.divergent_risk()
        first = self.delegate()
        self.write_arbitration(first)
        (self.tree / 'a.py').write_text('VALUE = 10\n')
        self.assert_no_build(self.delegate())
        self.assertEqual(len(self.analyses()), 2)

    def test_AC1_unknown_citation_and_duplicate_opinion_ids_are_blocked(self):
        self.opinions['claude']['decisions'][0]['sources'] = ['S404']
        self.opinions['claude']['assumptions'] *= 2
        self.assert_no_build(self.delegate())

    def test_AC1_claude_analysis_has_no_write_tools_mcp_or_session_reuse_flags(self):
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        claude = next(e for e in self.analyses() if e['provider'] == 'claude')
        argv = claude['argv']
        self.assertNotIn('--bare', argv)
        self.assertIn('--safe-mode', argv)
        self.assertEqual(json.loads(argv[argv.index('--settings') + 1]),
                         {'disableAllHooks': True})
        self.assertIn('--tools', argv)
        self.assertEqual(argv[argv.index('--tools') + 1], '')
        self.assertIn('--strict-mcp-config', argv)
        self.assertIn('--disallowedTools', argv)
        self.assertIn('mcp__*', argv)
        self.assertNotIn('acceptEdits', argv)
        self.assertNotIn('--resume', argv)
        self.assertNotIn('--continue', argv)
        codex = next(e for e in self.analyses() if e['provider'] == 'codex')
        self.assertEqual(codex['argv'][codex['argv'].index('-s') + 1], 'read-only')

    def test_AC4_active_strategy_requires_justification_and_subscription_guards(self):
        self.config['run']['double_analysis'].pop('justification')
        with self.assertRaises((RUN.Blocked, ValueError)):
            self.delegate()
        self.assertEqual(self.events(), [])

    def test_AC4_strategy_cannot_bypass_subscription_policy(self):
        self.config['run']['subscription_only'] = False
        with self.assertRaises((RUN.Blocked, ValueError)):
            self.delegate()
        self.assertEqual(self.events(), [])

    def test_AC1_high_analysis_requires_a_prepared_source_contract(self):
        self.plan['prs'][0].pop('analysis')
        self.assert_no_build(self.delegate())
        self.assertEqual(self.events(), [])

    def test_AC1_high_analysis_requires_explicit_confined_sources(self):
        self.plan['prs'][0]['analysis']['sources'][0]['path'] = '../outside.py'
        self.assert_no_build(self.delegate())
        self.assertEqual(self.events(), [])


if __name__ == '__main__':
    unittest.main()
