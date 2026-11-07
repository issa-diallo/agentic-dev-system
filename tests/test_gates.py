import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'agentic_gates', Path(__file__).resolve().parents[1] / 'scripts/agentic-gates.py')
GATES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATES)
OK = [[sys.executable, '-c', 'pass']]


class GatesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.write('keep.py', 'KEEP = 1\n')
        self.write('test_keep.py', 'def test():\n    assert True\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, name, text):
        (self.repo / name).write_text(text)

    def run_gates(self, files, commands=OK, settings=None, plan='abc'):
        return GATES.run(self.repo, self.base, files, commands, settings, plan)

    def status(self, report, name):
        return next(g['status'] for g in report['gates'] if g['name'] == name)

    def test_clean_delegation_passes_and_yields_acceptance_evidence(self):
        self.write('a.py', 'A = 1\n')
        self.write('test_a.py', 'def test():\n    assert True\n')
        report = self.run_gates(['a.py', 'test_a.py'])
        self.assertEqual(report['verdict'], 'PASS')
        evidence = report['acceptance_evidence']
        self.assertTrue(evidence['orchestrator_verified'])
        self.assertEqual(evidence['plan_sha256'], 'abc')
        self.assertEqual(evidence['snapshot']['head'], self.base)
        self.assertTrue(evidence['criteria'] and evidence['tests'])

    def test_change_outside_declared_files_fails_and_skips_commands(self):
        self.write('a.py', 'A = 1\n')
        self.write('test_a.py', 'x = 1\n')
        self.write('keep.py', 'KEEP = 2\n')
        report = self.run_gates(['a.py', 'test_a.py'])
        self.assertEqual(report['verdict'], 'BLOCKED')
        self.assertEqual(self.status(report, 'scope'), 'FAIL')
        self.assertEqual(self.status(report, 'commands'), 'SKIPPED')
        self.assertNotIn('acceptance_evidence', report)

    def test_source_without_test_fails_unless_disabled(self):
        self.write('a.py', 'A = 1\n')
        self.assertEqual(self.status(self.run_gates(['a.py']), 'tests-present'), 'FAIL')
        report = self.run_gates(['a.py'], settings={'require_tests': False})
        self.assertEqual(report['verdict'], 'PASS')

    def test_docs_only_change_needs_no_test(self):
        self.write('NOTES.md', 'text\n')
        self.assertEqual(self.run_gates(['NOTES.md'])['verdict'], 'PASS')

    def test_no_change_is_a_failure(self):
        self.assertEqual(self.status(self.run_gates(['a.py']), 'changes'), 'FAIL')

    def test_skip_markers_and_deleted_tests_fail(self):
        self.write('test_keep.py', 'import unittest\n@unittest.skip("later")\ndef test():\n    assert True\n')
        self.assertEqual(self.status(self.run_gates(['test_keep.py']), 'test-integrity'), 'FAIL')
        self.git('checkout', '-q', '--', 'test_keep.py')
        (self.repo / 'test_keep.py').unlink()
        self.assertEqual(self.status(self.run_gates(['test_keep.py']), 'test-integrity'), 'FAIL')

    def test_fewer_assertions_is_a_warning_not_a_failure(self):
        self.write('test_keep.py', 'def test():\n    pass\n')
        report = self.run_gates(['test_keep.py'])
        self.assertEqual(self.status(report, 'test-integrity'), 'WARN')
        self.assertEqual(report['verdict'], 'PASS')

    def test_secret_patterns_fail_but_literal_credential_only_warns(self):
        self.write('test_keep.py', 'def test():\n    assert 1\n')
        self.write('a.py', 'KEY = "AKIA' + 'ABCDEFGHIJKLMNOP"\n')
        report = self.run_gates(['a.py', 'test_keep.py'])
        self.assertEqual(self.status(report, 'secrets'), 'FAIL')
        self.assertNotIn('AKIAABCDEFGHIJKLMNOP', str(report))
        self.write('a.py', 'password = "not-a-real-secret-value"\n')
        report = self.run_gates(['a.py', 'test_keep.py'])
        self.assertEqual(self.status(report, 'secrets'), 'WARN')
        self.assertEqual(report['verdict'], 'PASS')

    def test_size_over_target_warns_by_default_and_fails_when_hard(self):
        self.write('a.py', ''.join('x%d = 1\n' % i for i in range(150)))
        self.write('test_a.py', 'def test():\n    assert True\n')
        files = ['a.py', 'test_a.py']
        self.assertEqual(self.status(self.run_gates(files), 'size'), 'WARN')
        hard = self.run_gates(files, settings={'size': {'mode': 'fail'}})
        self.assertEqual(self.status(hard, 'size'), 'FAIL')
        self.assertEqual(hard['verdict'], 'BLOCKED')

    def test_committed_staged_and_untracked_changes_are_all_seen(self):
        self.write('a.py', 'A = 1\n')
        self.git('add', 'a.py')
        self.git('commit', '-qm', 'agent commit')
        self.write('test_a.py', 'def test():\n    assert True\n')
        report = self.run_gates(['a.py', 'test_a.py'])
        self.assertEqual(report['changed'], ['a.py', 'test_a.py'])
        self.assertEqual(report['verdict'], 'PASS')

    def test_missing_or_failing_commands_block_without_evidence(self):
        self.write('a.py', 'A = 1\n')
        self.write('test_a.py', 'x = 1\n')
        files = ['a.py', 'test_a.py']
        self.assertEqual(self.status(self.run_gates(files, commands=[]), 'commands'), 'FAIL')
        bad = self.run_gates(files, commands=[[sys.executable, '-c', 'raise SystemExit(2)']])
        self.assertEqual(bad['verdict'], 'BLOCKED')
        self.assertNotIn('acceptance_evidence', bad)


if __name__ == '__main__':
    unittest.main()
