"""Runner tests: real Git worktrees and the real Scheduler, with a fake harness process."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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
