"""TDD flow: red tests first (must fail), committed, then green with tests locked."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('agentic_run_tdd', SOURCE / 'scripts/agentic-run.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
FENCE = '`' * 3

AGENT = '''
import sys
from pathlib import Path
worktree, prompt = Path(sys.argv[1]), sys.argv[2]
mode = Path(__file__).with_name('mode').read_text().strip()
TEST = ('import unittest, a\\nclass T(unittest.TestCase):\\n'
        '    def test_rm1(self):\\n        self.assertEqual(a.VALUE, %d)\\n')
red = 'UNIQUEMENT les tests' in prompt
if red:
    name = 'test_other.py' if mode == 'untraced' else 'test_a.py'
    body = TEST % 1
    if mode == 'untraced':
        body = body.replace('test_rm1', 'test_x')
    (worktree / name).write_text(body)
    if mode == 'passing':
        (worktree / 'a.py').write_text('VALUE = 1\\n')
else:
    (worktree / 'a.py').write_text('VALUE = 1\\n')
    if mode == 'cheat':
        (worktree / 'test_a.py').write_text(TEST % 2)
        (worktree / 'a.py').write_text('VALUE = 2\\n')
print('FENCEhandoff\\n{"status":"COMPLETED","summary":"x","files":[]}\\nFENCE')
'''.replace('FENCE', FENCE)


class TddTests(unittest.TestCase):
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

    tdd_config = {}

    def config(self):
        models = [{'id': 'cheap', 'harness': 'fake', 'model': 'x', 'max_level': 'MEDIUM',
                   'efforts': ['medium'], 'cost_rank': 1},
                  {'id': 'strong', 'harness': 'fake', 'model': 'y', 'max_level': 'HIGH',
                   'efforts': ['high'], 'cost_rank': 5},
                  {'id': 'top', 'harness': 'fake', 'model': 'z', 'max_level': 'EXTRA_HIGH',
                   'efforts': ['xhigh'], 'cost_rank': 9}]
        config = {'version': 1, 'models': models, 'run': {'timeout_seconds': 20, 'tdd': {'enabled': True, **self.tdd_config}},
                  'harnesses': {'fake': {'argv': [sys.executable, str(self.agent), '{worktree}',
                                                  '{prompt}']}}}
        path = self.root / 'config.json'
        path.write_text(json.dumps(config))
        return str(path)

    def quick(self, rules=('RM1: A vaut 1',), task_id='t1', **kwargs):
        return RUN.quick(self.repo, task_id, 'Livrer a', ['a.py', 'test_a.py'], ['A est 1'], self.tests,
                         worktree_root=self.root / 'wt', config_path=self.config(), rules=list(rules),
                         **kwargs)

    def test_red_then_green_commits_tests_first_and_locks_them(self):
        report = self.quick()
        self.assertEqual(report['phase'], 'green')
        self.assertTrue(RUN.succeeded(report['tasks'], False))
        red = report['red']['t1-red']
        self.assertEqual(red['gates']['verdict'], 'PASS')
        self.assertIn('red', [g['name'] for g in red['gates']['gates']])
        self.assertIn('traceability', [g['name'] for g in red['gates']['gates']])
        log = self.git('log', '--format=%s', repo=report['worktree'])
        self.assertIn('Tests (rouge)', log)
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD', repo=report['worktree']), 'test_a.py')

    def test_tests_that_already_pass_block_the_red_phase(self):
        self.set_mode('passing')
        report = self.quick()
        self.assertEqual(report['phase'], 'red')
        self.assertFalse(RUN.succeeded(report['tasks'], False))

    def test_rule_without_a_test_naming_it_blocks(self):
        report = self.quick(rules=('RM1: A vaut 1', 'RM2: B vaut 2'))
        self.assertEqual(report['phase'], 'red')
        gates = {g['name']: g for g in report['tasks']['t1-red']['gates']['gates']}
        self.assertEqual(gates['traceability']['status'], 'FAIL')

    def test_editing_the_locked_tests_in_green_is_a_scope_failure(self):
        self.set_mode('cheat')
        report = self.quick()
        green = report['tasks']['t1']
        self.assertEqual(report['phase'], 'green')
        self.assertNotEqual(green['state'], 'COMPLETED')
        self.assertTrue(green['blockers'], green)
        self.assertFalse(RUN.succeeded(report['tasks'], False))

    def test_tdd_requires_rules_and_tests_unless_opted_out(self):
        with self.assertRaises(RUN.Blocked):
            self.quick(rules=())
        with self.assertRaises(RUN.Blocked):
            RUN.quick(self.repo, 't2', 'x', ['a.py'], ['ac'], self.tests, worktree_root=self.root / 'wt',
                      config_path=self.config(), rules=['RM1: x'])

    def test_red_phase_can_use_a_stronger_model_than_green(self):
        self.tdd_config = {'red_level': 'HIGH', 'green_level': 'LOW', 'review_before_green': False}
        report = self.quick()
        self.assertEqual(report['red']['t1-red']['model_requested']['model'], 'strong')
        self.assertEqual(report['tasks']['t1']['model_requested']['model'], 'cheap')

    def test_default_levels_use_the_economical_model_without_review_pause(self):
        report = self.quick()
        self.assertEqual(report['phase'], 'green')
        self.assertEqual(report['red']['t1-red']['model_requested']['model'], 'cheap')

    def test_risky_ticket_pauses_after_red_commit_then_resumes_green_only(self):
        paused = RUN.quick(self.repo, 't1', 'Login password reset', ['a.py', 'test_a.py'], ['A'],
                           self.tests, worktree_root=self.root / 'wt', config_path=self.config(),
                           rules=['RM1: A vaut 1'])
        self.assertEqual(paused['phase'], 'awaiting-review')
        self.assertFalse((Path(paused['worktree']) / 'a.py').exists())
        self.assertIn('Tests (rouge)', self.git('log', '-1', '--format=%s', repo=paused['worktree']))
        done = RUN.quick(self.repo, 't1', 'Login password reset', ['a.py', 'test_a.py'], ['A'],
                         self.tests, worktree_root=self.root / 'wt', config_path=self.config(),
                         green_only=True)
        self.assertEqual(done['phase'], 'green')
        self.assertTrue(RUN.succeeded(done['tasks'], False))

    def test_explicit_review_flag_overrides_the_heuristic(self):
        self.assertEqual(self.quick(review=True)['phase'], 'awaiting-review')
        self.assertEqual(self.quick(review=False, rules=('RM1: login',), task_id='t2')['phase'], 'green')

    def test_green_only_refuses_without_red_commit(self):
        with self.assertRaises(RUN.Blocked):
            RUN.quick(self.repo, 't9', 'x', ['a.py', 'test_a.py'], ['A'], self.tests,
                      worktree_root=self.root / 'wt', config_path=self.config(), green_only=True)

    def test_bad_tdd_settings_are_rejected(self):
        with self.assertRaises(RUN.Blocked):
            RUN.tdd_settings({'run': {'tdd': {'red_level': 'ULTRA'}}})

    def test_no_tdd_keeps_the_single_phase_flow(self):
        report = self.quick(tdd=False)
        self.assertNotIn('phase', report)
        self.assertIn('t1', report['tasks'])


if __name__ == '__main__':
    unittest.main()
