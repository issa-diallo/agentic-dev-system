"""Runner tests: real Git worktrees and the real Scheduler, with a fake harness process."""
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
SPEC = importlib.util.spec_from_file_location('agentic_run', SOURCE / 'scripts/agentic-run.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
FENCE = '`' * 3

AGENT = '''
import sys, time
from pathlib import Path
worktree = Path(sys.argv[1])
mode = Path(__file__).with_name('mode').read_text().strip()
if mode == 'sleep':
    time.sleep(30)
if mode == 'fail':
    sys.exit(3)
if mode != 'noop':
    (worktree / 'a.py').write_text('VALUE = 1\\n')
    (worktree / 'test_a.py').write_text(
        'import unittest, a\\nclass T(unittest.TestCase):\\n'
        '    def test(self):\\n        self.assertEqual(a.VALUE, 1)\\n')
if mode == 'outside':
    (worktree / 'other.py').write_text('x = 1\\n')
reply = {'blocked': '{"status":"BLOCKED","summary":"need rule","blockers":["rule missing"]}'}.get(
    mode, '{"status":"COMPLETED","summary":"ok","files":["a.py","test_a.py"]}')
print('done')
print('FENCEhandoff\\n' + reply + '\\nFENCE')
'''.replace('FENCE', FENCE)


class RunTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'base.txt').write_text('base\n')
        (self.repo / '.gitignore').write_text('__pycache__/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.agent = self.root / 'agent.py'
        self.agent.write_text(AGENT)
        self.set_mode('ok')
        self.tests = ['%s -m unittest discover' % sys.executable]

    def git(self, *args, repo=None):
        return subprocess.run(['git', '-C', str(repo or self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def set_mode(self, mode):
        self.agent.with_name('mode').write_text(mode)

    def config(self, **run):
        models = [{'id': 'cheap', 'harness': 'fake', 'model': 'x', 'max_level': 'MEDIUM',
                   'efforts': ['medium'], 'cost_rank': 1},
                  {'id': 'strong', 'harness': 'fake', 'model': 'y', 'max_level': 'HIGH',
                   'efforts': ['high'], 'cost_rank': 5}]
        config = {'version': 1, 'models': models, 'run': {'timeout_seconds': 20, **run},
                  'harnesses': {'fake': {'argv': [sys.executable, str(self.agent), '{worktree}',
                                                  '{prompt}']}}}
        path = self.root / 'config.json'
        path.write_text(json.dumps(config))
        return str(path)

    def quick(self, task_id='t1', **kwargs):
        return RUN.quick(self.repo, task_id, 'Deliver a', ['a.py', 'test_a.py'], ['A is 1'],
                         self.tests, worktree_root=self.root / 'wt', config_path=self.config(),
                         **kwargs)

    def task(self, report, task_id='t1'):
        return report['tasks'][task_id]

    def test_quick_runs_agent_then_gates_and_leaves_worktree_for_the_orchestrator(self):
        report = self.quick()
        task = self.task(report)
        self.assertEqual(task['state'], 'COMPLETED')
        self.assertEqual(task['gates']['verdict'], 'PASS')
        self.assertEqual(task['model_requested'], {'model': 'cheap', 'effort': 'medium'})
        self.assertEqual(task['result']['handoff']['status'], 'COMPLETED')
        self.assertTrue((Path(report['worktree']) / 'a.py').exists())
        self.assertEqual(self.git('rev-parse', 'HEAD', repo=report['worktree']),
                         self.git('rev-parse', 'HEAD'))  # nothing committed or merged
        self.assertTrue(RUN.succeeded(report['tasks'], False))

    def test_accept_flag_accepts_only_when_gates_pass(self):
        self.assertTrue(self.task(self.quick(accept=True))['accepted'])

    def test_write_outside_scope_blocks_the_task(self):
        self.set_mode('outside')
        task = self.task(self.quick())
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertNotIn('gates', task)

    def test_agent_reported_blocker_blocks_with_its_reason(self):
        self.set_mode('blocked')
        task = self.task(self.quick())
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertIn('rule missing', task['blockers'])

    def test_no_change_fails_the_gates_even_when_the_agent_claims_success(self):
        self.set_mode('noop')
        report = self.quick()
        task = self.task(report)
        self.assertEqual(task['state'], 'COMPLETED')
        self.assertEqual(task['gates']['verdict'], 'BLOCKED')
        self.assertFalse(RUN.succeeded(report['tasks'], False))

    def test_timeout_kills_the_agent_and_blocks(self):
        self.set_mode('sleep')
        report = RUN.quick(self.repo, 't1', 'Deliver a', ['a.py', 'test_a.py'], ['A is 1'],
                           self.tests, worktree_root=self.root / 'wt',
                           config_path=self.config(timeout_seconds=1))
        task = self.task(report)
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertTrue(any('timeout' in b for b in task['blockers']))

    def test_harness_failure_blocks_with_its_exit_code(self):
        self.set_mode('fail')
        task = self.task(self.quick())
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertIn('exit code 3', task['blockers'])

    def test_agent_is_not_started_before_the_launch_receipt_is_confirmed(self):
        spawned = []

        class Probe:
            def __init__(self, argv, **kwargs):
                self.pid, self.stdin, self.returncode = 4242, self, 0
                spawned.append(argv)

            def write(self, data):
                spawned.append(('stdin', data))

            def close(self):
                pass

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0
        self.quick(popen=Probe)
        self.assertEqual(spawned[1], ('stdin', b'go\n'))
        self.assertIn(RUN.GATE, spawned[0])

    def test_dry_run_routes_and_builds_argv_without_spawning_or_touching_files(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('dry run must not spawn')
        report = self.quick(dry_run=True, popen=forbidden)
        task = self.task(report)
        self.assertEqual(task['state'], 'COMPLETED')
        self.assertTrue(task['result']['dry_run'])
        self.assertIn('<brief.md>', task['result']['argv'])
        self.assertFalse((Path(report['worktree']) / 'a.py').exists())
        self.assertNotIn('gates', task)

    def test_undiagnosed_failure_blocks_the_next_attempt_instead_of_escalating(self):
        report = self.quick(dry_run=True)
        RUN.record_attempt(self.repo, {'task_id': 't1', 'outcome': 'FAIL', 'level': 'MEDIUM'})
        again = RUN.delegate(report['plan'], self.repo, self.config(), dry_run=True)
        self.assertEqual(again['t1']['state'], 'BLOCKED')
        self.assertIsNone(again['t1']['model_requested'])

    def test_diagnosed_capacity_failure_escalates_to_the_stronger_model(self):
        report = self.quick(dry_run=True)
        self.assertEqual(self.task(report)['model_requested']['model'], 'cheap')
        RUN.record_attempt(self.repo, {'task_id': 't1', 'outcome': 'FAIL', 'level': 'MEDIUM',
                                       'diagnosis_kind': 'capacity', 'diagnosis': 'cannot reason'})
        again = RUN.delegate(report['plan'], self.repo, self.config(), dry_run=True)
        self.assertEqual(again['t1']['model_requested'], {'model': 'strong', 'effort': 'high'})

    def test_record_attempt_validates_input(self):
        for bad in ({}, {'task_id': 'a', 'outcome': 'MAYBE', 'level': 'LOW'},
                    {'task_id': 'a', 'outcome': 'FAIL', 'level': 'HUGE'}):
            with self.assertRaises(RUN.Blocked):
                RUN.record_attempt(self.repo, bad)

    def test_quick_refuses_bad_ids_and_reused_branches(self):
        with self.assertRaises(RUN.Blocked):
            self.quick(task_id='Bad Id')
        self.quick()
        with self.assertRaises(Exception):
            self.quick()

    def policy_run(self, *, routing=None, rule=None, model_tokens=True, dry_run=False,
                   alternate_harness=False, mode=None):
        report = self.quick(dry_run=True)
        if mode:
            self.set_mode(mode)
        plan = Path(report['plan'])
        data = json.loads(plan.read_text())
        data['prs'][0]['routing'] = routing or {'role': 'implementer', 'phase': 'BUILD'}
        plan.write_text(json.dumps(data))
        path = Path(self.config())
        config = json.loads(path.read_text())
        if mode == 'sleep':
            config['run']['timeout_seconds'] = 1
        config['routing_policy'] = {'version': 1, 'enabled': True, 'rules': [
            {'id': 'build', 'match': {'role': 'implementer', 'phase': 'BUILD'},
             'prefer': [{'model': 'strong'}], **(rule or {})}]}
        config['harnesses']['fake']['argv'] += ['{model}', '{effort}'] if model_tokens else []
        if alternate_harness:
            alternate = self.root / 'alternate-cli'
            alternate.write_text('#!' + sys.executable + '\n' + self.agent.read_text())
            alternate.chmod(0o700)
            config['models'][1]['harness'] = 'alternate'
            config['harnesses']['alternate'] = {
                'argv': [str(alternate), '{worktree}', '{prompt}', '{model}', '{effort}']}
        path.write_text(json.dumps(config))
        self.actual_plan, self.actual_config = plan, path
        return RUN.delegate(plan, self.repo, path, state=self.root / 'actual.json', dry_run=dry_run)

    def test_AC1_role_phase_policy_reaches_real_cli_and_persists_receipt_stop(self):
        self.agent.write_text(self.agent.read_text().replace('import sys, time', 'import sys, time, json')
                              .replace("print('done')", "print(json.dumps(sys.argv))"))
        task = self.policy_run()['t1']
        self.assertEqual(task['state'], 'COMPLETED')
        self.assertEqual(task['model_requested'], {'model': 'strong', 'effort': 'high'})
        state = json.loads((self.root / 'actual.json').read_text())['tasks']['t1']
        evidence = task['model_execution']
        self.assertEqual(evidence['selected'], {'model': 'strong', 'effort': 'high'})
        self.assertEqual(evidence['requested'], {'model': 'y', 'effort': 'high'})
        self.assertEqual(evidence['harness'], 'fake')
        self.assertGreater(evidence['pid'], 0)
        self.assertIsNone(evidence['provider'])
        self.assertIsNone(evidence['cli_session_id'])
        self.assertIsNone(evidence['observed']['model'])
        self.assertIsNone(evidence['observed']['effort'])
        self.assertFalse(evidence['applied']['model'])
        self.assertFalse(evidence['applied']['effort'])
        self.assertTrue(evidence['transmitted']['model'])
        self.assertTrue(evidence['transmitted']['effort'])
        self.assertEqual(state['model_execution'], evidence)
        self.assertTrue(state['stop_evidence']['stopped_confirmed'])
        self.assertFalse(state['active'])
        self.assertNotIn('owner', state)
        stdout = (Path(task['result']['log']) / 'stdout.log').read_text()
        self.assertIn('"y", "high"', stdout)
        self.assertFalse(state['model_applied'])
        before = (self.repo / '.git' / 'agentic-runs' / 'runs.jsonl').read_text()
        RUN.delegate(self.actual_plan, self.repo, self.actual_config, state=self.root / 'actual.json')
        self.assertEqual((self.repo / '.git' / 'agentic-runs' / 'runs.jsonl').read_text(), before)

    def test_AC1_harness_preference_runs_the_alternate_binary(self):
        task = self.policy_run(alternate_harness=True,
                               rule={'prefer': [{'harness': 'alternate'}]})['t1']
        self.assertEqual(task['state'], 'COMPLETED')
        self.assertEqual(task['model_execution']['harness'], 'alternate')
        state = json.loads((self.root / 'actual.json').read_text())['tasks']['t1']
        self.assertTrue(state['agent_id'].startswith(str(self.root / 'alternate-cli') + ':pid:'))
        self.assertEqual(task['model_execution']['requested']['model'], 'y')

    def test_AC3_active_policy_blocked_handoff_does_not_redispatch_after_reboot(self):
        task = self.policy_run(mode='blocked')['t1']
        self.assertEqual(task['state'], 'BLOCKED')
        before = (self.repo / '.git' / 'agentic-runs' / 'runs.jsonl').read_text()
        RUN.delegate(self.actual_plan, self.repo, self.actual_config, state=self.root / 'actual.json')
        self.assertEqual((self.repo / '.git' / 'agentic-runs' / 'runs.jsonl').read_text(), before)
        state = json.loads((self.root / 'actual.json').read_text())['tasks']['t1']
        self.assertTrue(state['stop_evidence']['stopped_confirmed'])
        self.assertNotIn('owner', state)

    def test_AC3_active_policy_timeout_is_stopped_and_never_redispatched(self):
        task = self.policy_run(mode='sleep')['t1']
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertTrue(any('timeout' in b for b in task['blockers']))
        before = (self.repo / '.git' / 'agentic-runs' / 'runs.jsonl').read_text()
        RUN.delegate(self.actual_plan, self.repo, self.actual_config, state=self.root / 'actual.json')
        self.assertEqual((self.repo / '.git' / 'agentic-runs' / 'runs.jsonl').read_text(), before)
        state = json.loads((self.root / 'actual.json').read_text())['tasks']['t1']
        self.assertTrue(state['stop_evidence']['stopped_confirmed'])
        self.assertNotIn('owner', state)

    def test_AC1_read_only_role_blocks_incompatible_harness_without_fallback(self):
        task = self.policy_run(routing={'role': 'explorer', 'phase': 'PREPARE'})['t1']
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertTrue(any('read-only' in b for b in task['blockers']))
        self.assertIsNone(json.loads((self.root / 'actual.json').read_text())['tasks']['t1']['agent_id'])

    def test_AC1_read_only_reviewer_uses_codex_read_only_sandbox_and_role_brief(self):
        initial = self.quick(dry_run=True)
        plan = Path(initial['plan'])
        data = json.loads(plan.read_text())
        data['prs'][0]['routing'] = {'role': 'reviewer', 'phase': 'SHIP',
                                     'session_id': 'review', 'implementer_session_id': 'writer'}
        plan.write_text(json.dumps(data))
        executable = self.root / 'codex'
        executable.write_text('#!' + sys.executable + '\nimport sys,json\nprint(json.dumps(sys.argv))\n')
        executable.chmod(0o700)
        config = {'version': 1, 'models': [
            {'id': 'review-model', 'harness': 'codex', 'model': 'review-cli-model',
             'max_level': 'HIGH', 'efforts': ['high'], 'cost_rank': 1}],
                  'routing_policy': {'version': 1, 'enabled': True, 'rules': []}}
        path = self.root / 'review-config.json'
        path.write_text(json.dumps(config))
        with mock.patch.dict(os.environ, {'PATH': str(self.root) + os.pathsep + os.environ['PATH']}):
            task = RUN.delegate(plan, self.repo, path, state=self.root / 'review.json')['t1']
        self.assertEqual(task['state'], 'COMPLETED')
        stdout = json.loads((Path(task['result']['log']) / 'stdout.log').read_text())
        self.assertEqual(stdout[stdout.index('-s') + 1], 'read-only')
        self.assertIn('Ne modifie aucun fichier', stdout[-1])
        self.assertIn('reviewer', stdout[-1])
        self.assertNotIn('Ajoute ou adapte les tests', stdout[-1])
        self.assertEqual(self.git('status', '--porcelain', repo=initial['worktree']), '')

    def test_AC2_cli_observation_exact_alias_multiple_and_missing_remain_distinct(self):
        executable = self.root / 'claude'
        config = {'version': 1, 'models': [
            {'id': 'candidate', 'harness': 'claude', 'model': 'requested-model',
             'max_level': 'MEDIUM', 'efforts': ['medium'], 'cost_rank': 1}]}
        path = self.root / 'claude-config.json'
        path.write_text(json.dumps(config))
        for index, (models, expected, applied) in enumerate([
                ({'requested-model': {}}, 'requested-model', True),
                ({'requested-model-version': {}}, 'requested-model-version', False),
                ({'one': {}, 'two': {}}, None, False), (None, None, False)]):
            with self.subTest(models=models):
                payload = {'result': 'ok', 'session_id': 'cli-session-' + str(index)}
                if models is not None:
                    payload['modelUsage'] = models
                executable.write_text('#!' + sys.executable + '\nprint(' + repr(json.dumps(payload)) + ')\n')
                executable.chmod(0o700)
                with mock.patch.dict(os.environ, {'PATH': str(self.root) + os.pathsep + os.environ['PATH']}):
                    report = RUN.quick(self.repo, 'obs' + str(index), 'Deliver a',
                                       ['a.py', 'test_a.py'], ['A is 1'], self.tests,
                                       worktree_root=self.root / 'wt', config_path=path)
                task = self.task(report, 'obs' + str(index))
                self.assertEqual(task['state'], 'COMPLETED', task['blockers'])
                evidence = task['model_execution']
                scheduler = RUN.module('scheduler').Scheduler(report['plan'], self.repo)
                legacy = scheduler.resume()['tasks']['obs' + str(index)]
                self.assertIsNone(legacy['model_observed'])
                self.assertFalse(legacy['model_applied'])
                self.assertEqual(evidence['observed']['model'], expected)
                self.assertEqual(evidence['applied']['model'], applied)
                self.assertIsNone(evidence['observed']['effort'])
                self.assertFalse(evidence['transmitted']['effort'])
                self.assertFalse(evidence['applied']['effort'])
                self.assertEqual(evidence['cli_session_id'], 'cli-session-' + str(index))
                self.assertNotEqual(evidence['session_id'], evidence['cli_session_id'])

    def test_AC2_dry_run_never_attests_execution_or_effective_model(self):
        task = self.policy_run(dry_run=True)['t1']
        evidence = task['model_execution']
        self.assertIsNone(evidence['pid'])
        self.assertIsNone(evidence['session_id'])
        self.assertIsNone(evidence['observed']['model'])
        self.assertFalse(evidence['transmitted']['model'])
        self.assertFalse(evidence['applied']['model'])

    def test_AC1_explicit_effort_not_transmissible_blocks_before_process(self):
        task = self.policy_run(rule={'effort': 'high'}, model_tokens=False)['t1']
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertTrue(any('effort' in blocker for blocker in task['blockers']))
        self.assertIsNone(json.loads((self.root / 'actual.json').read_text())['tasks']['t1']['agent_id'])

    def test_AC1_missing_model_placeholder_blocks_active_policy(self):
        task = self.policy_run(model_tokens=False)['t1']
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertTrue(any('model' in blocker for blocker in task['blockers']))

    def test_AC1_policy_impossible_spawns_nothing(self):
        task = self.policy_run(rule={'prefer': [{'model': 'absent'}]})['t1']
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertIsNone(task['model_requested'])
        self.assertEqual(list((self.repo / '.git' / 'agentic-runs').rglob('stdout.log')), [])


class ConfigAndArgvTests(unittest.TestCase):
    CONFIG = {'version': 1, 'models': [
        {'id': 'a', 'harness': 'claude', 'model': 'haiku', 'max_level': 'MEDIUM',
         'efforts': ['medium'], 'cost_rank': 1},
        {'id': 'b', 'harness': 'opencode', 'model': 'p/m', 'max_level': 'MEDIUM',
         'efforts': ['medium'], 'cost_rank': 0, 'enabled': False},
        {'id': 'c', 'harness': 'codex', 'model': 'g', 'max_level': 'HIGH',
         'efforts': ['high'], 'cost_rank': 3}]}

    def test_inventory_drops_disabled_models_and_missing_binaries(self):
        inventory, index = RUN.build_inventory(self.CONFIG, which=lambda name: name == 'claude')
        self.assertEqual([m['id'] for m in inventory['models']], ['a'])
        self.assertEqual(sorted(index), ['a'])
        self.assertTrue(inventory['runtime_overrides'])
        self.assertEqual(sorted(RUN.build_inventory(self.CONFIG, which=lambda name: True)[1]),
                         ['a', 'c'])

    def test_inventory_preserves_policy_harness_and_modalities_and_unavailability(self):
        models = [{**self.CONFIG['models'][0], 'modalities': ['text', 'image']},
                  {**self.CONFIG['models'][2], 'available': False}]
        inventory, index = RUN.build_inventory({**self.CONFIG, 'models': models}, which=lambda name: True)
        self.assertEqual(inventory['models'][0]['harness'], 'claude')
        self.assertEqual(inventory['models'][0]['modalities'], ['text', 'image'])
        self.assertEqual(list(index), ['a'])

    def test_config_rejects_bad_versions_placeholders_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            def load(data):
                path = Path(directory) / 'c.json'
                path.write_text(json.dumps(data))
                return RUN.load_config(path)
            with self.assertRaises(RUN.Blocked):
                load({**self.CONFIG, 'version': 2})
            placeholder = [{**self.CONFIG['models'][0], 'model': '<fill me>'}]
            with self.assertRaises(RUN.Blocked):
                load({**self.CONFIG, 'models': placeholder})
            twice = [self.CONFIG['models'][0]] * 2
            with self.assertRaises(RUN.Blocked):
                RUN.build_inventory({**self.CONFIG, 'models': twice}, which=lambda name: True)

    def values(self, **extra):
        return {'prompt': 'P', 'model': 'm', 'effort': 'low', 'worktree': '/w', 'max_turns': 7,
                'tools': ['Read', 'Bash(make test)'], **extra}

    def test_presets_build_expected_commands(self):
        claude = RUN.build_argv({'preset': 'claude'}, self.values())
        self.assertEqual(claude[:3], ['claude', '-p', 'P'])
        self.assertEqual(claude[-3:], ['--allowedTools', 'Read', 'Bash(make test)'])
        self.assertNotIn('--dangerously-skip-permissions', claude)
        self.assertEqual(claude[claude.index('--max-turns') + 1], '7')
        codex = RUN.build_argv({'preset': 'codex'}, self.values())
        self.assertEqual(codex[:2], ['codex', 'exec'])
        self.assertIn('model_reasoning_effort="low"', codex)
        self.assertEqual(codex[-1], 'P')
        self.assertEqual(RUN.build_argv({'preset': 'opencode', 'extra_args': ['--x']},
                                        self.values()), ['opencode', 'run', '-m', 'm', '--x', 'P'])

    def test_custom_argv_replaces_placeholders(self):
        argv = RUN.build_argv({'argv': ['tool', '--m={model}', '{prompt}']}, self.values())
        self.assertEqual(argv, ['tool', '--m=m', 'P'])

    def test_child_environment_keeps_only_allowlisted_variables(self):
        environ = {'PATH': '/bin', 'HOME': '/h', 'ANTHROPIC_API_KEY': 'k', 'AWS_SECRET_ACCESS_KEY': 's',
                   'GITHUB_TOKEN': 't', 'CUSTOM': 'c'}
        claude = RUN.child_env({'preset': 'claude'}, environ)
        self.assertEqual(sorted(claude), ['ANTHROPIC_API_KEY', 'HOME', 'PATH'])
        extra = RUN.child_env({'argv': ['x'], 'env_passthrough': ['CUSTOM']}, environ)
        self.assertEqual(sorted(extra), ['CUSTOM', 'HOME', 'PATH'])

    def test_claude_json_output_exposes_reply_usage_and_cost_only_when_reported(self):
        out = json.dumps({'type': 'result', 'result': 'hello', 'usage': {'output_tokens': 5},
                          'total_cost_usd': 0.01, 'modelUsage': {'claude-x': {}}})
        self.assertEqual(RUN.parse_output({'preset': 'claude'}, out),
                         ('hello', {'output_tokens': 5}, 0.01, ['claude-x']))
        self.assertEqual(RUN.parse_output({'preset': 'claude'}, 'plain'), ('plain', None, None, None))
        self.assertEqual(RUN.parse_output({'preset': 'codex'}, out), (out, None, None, None))


class TemplateAndAdapterTests(unittest.TestCase):
    def test_shipped_config_template_loads_and_routes_without_the_disabled_model(self):
        config = RUN.load_config(SOURCE / 'docs/agentic/templates/agentic.config.json')
        inventory, index = RUN.build_inventory(config, which=lambda name: True)
        self.assertEqual(sorted(index), ['cheap', 'mid', 'strong'])
        route = RUN.module('models').route({'id': 't', 'type': 'implementation'}, inventory)
        self.assertEqual(route['recommendation']['model'], 'cheap')

    def test_every_codex_role_has_a_claude_counterpart(self):
        codex = {p.stem for p in (SOURCE / 'codex/agents').glob('*.toml')}
        agents = RUN.claude_agents()
        self.assertEqual({name.replace('agentic-', '') for name in agents}, codex)
        self.assertEqual(agents['agentic-explorer']['tools'], ['Read', 'Grep', 'Glob'])
        self.assertNotIn('Edit', agents['agentic-reviewer']['tools'])

    def test_claude_agents_requires_frontmatter(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'x.md').write_text('no frontmatter')
            with self.assertRaises(RUN.Blocked):
                RUN.claude_agents(directory)

    def test_launcher_preserves_native_agents_activation_and_mission_to_claude(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'claude'
            fake.write_text('#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n')
            fake.chmod(0o755)
            env = {'PATH': directory + ':/usr/bin:/bin'}
            script = str(SOURCE / 'scripts/agentic-claude.sh')

            def launch(*args):
                out = subprocess.run(['bash', script, *args], env=env, capture_output=True,
                                     text=True, check=True).stdout
                return json.loads(out)
            plain = launch('--model', 'haiku')
            self.assertEqual(plain, ['--model', 'haiku'])
            run = launch('run', 'Fix the bug', '-p')
            self.assertEqual(run[0], '--append-system-prompt')
            self.assertIn('DELEGATION.md', run[1])
            self.assertEqual(run[2:], ['-p', 'Fix the bug'])
            self.assertNotEqual(subprocess.run(['bash', script, 'run'], env=env,
                                               capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
