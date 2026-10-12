"""Ownership and worktree safety against real Git repositories/processes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/agentic-workspace.py'
SPEC = importlib.util.spec_from_file_location('workspace', SCRIPT)
WORKSPACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKSPACE)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.repo = self.directory / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'app.py').write_text('initial\n')
        self.git('add', 'app.py')
        self.git('commit', '-qm', 'Initial')
        self.a = self.directory / 'a'
        self.b = self.directory / 'b'
        WORKSPACE.create(self.repo, 'feat/a', str(self.a))
        WORKSPACE.create(self.repo, 'feat/b', str(self.b))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def owner(self, name):
        return {'id': name, 'task': 'PR-' + name, 'plan_sha256': 'a' * 64}

    def resource(self, kind, name):
        return {'type': kind, 'name': name}

    def reserve(self, name, path, *resources):
        return WORKSPACE.reserve(self.repo, self.owner(name), str(path), list(resources))

    def test_create_preserves_dirty_index_and_worktree(self):
        (self.repo / 'app.py').write_text('staged\n')
        self.git('add', 'app.py')
        (self.repo / 'app.py').write_text('unstaged\n')
        (self.repo / 'untracked').write_text('pending')
        before = self.git('status', '--porcelain')
        index = (self.repo / '.git/index').read_bytes()
        result = WORKSPACE.create(self.repo, 'feat/c', str(self.directory / 'c'))
        self.assertEqual(result['branch'], 'feat/c')
        self.assertEqual(before, self.git('status', '--porcelain'))
        self.assertEqual(index, (self.repo / '.git/index').read_bytes())
        (self.a / 'app.py').write_text('pending a\n')
        self.assertTrue(WORKSPACE.inspect(self.repo, str(self.a))['dirty'])

    def test_create_refuses_existing_destinations_branches_and_main(self):
        for branch, path in [('main', self.directory / 'c'), ('feat/a', self.directory / 'c'),
                             ('feat/c', self.a), ('feat/c', self.directory / 'a/../c')]:
            with self.subTest(branch=branch, path=path), self.assertRaises(WORKSPACE.Blocked):
                WORKSPACE.create(self.repo, branch, str(path))
        self.assertEqual((self.a / 'app.py').read_text(), 'initial\n')
        alias = self.directory / 'alias'
        alias.symlink_to(self.a, target_is_directory=True)
        with self.assertRaises(WORKSPACE.Blocked):
            WORKSPACE.inspect(self.repo, str(alias))

    def test_shared_registry_and_one_writer_per_worktree(self):
        self.reserve('a', self.a, self.resource('file', 'src/a.py'))
        with self.assertRaises(WORKSPACE.Blocked):
            WORKSPACE.reserve(self.b, self.owner('b'), str(self.b),
                              [self.resource('file', 'src/a.py')])
        with self.assertRaises(WORKSPACE.Blocked):
            self.reserve('b', self.a, self.resource('file', 'src/b.py'))
        self.reserve('b', self.b, self.resource('file', 'src/b.py'))
        with self.assertRaises(WORKSPACE.Blocked):
            WORKSPACE.release(self.repo, 'unknown')
        WORKSPACE.release(self.a, 'a')
        self.assertTrue(self.a.exists())
        with self.assertRaises(WORKSPACE.Blocked):
            self.reserve('c', self.b, self.resource('file', 'src/c.py'))

    def test_typed_resources_and_directory_glob_conflicts(self):
        for kind in sorted(WORKSPACE.TYPES - {'file'}):
            with self.subTest(kind=kind):
                self.reserve('a', self.a, self.resource(kind, 'users'))
                with self.assertRaises(WORKSPACE.Blocked):
                    self.reserve('b', self.b, self.resource(kind, 'users'))
                WORKSPACE.release(self.repo, 'a')
        for pattern in ['src', 'src/', 'src/**/*.py', 'src/user*.py', '*']:
            with self.subTest(pattern=pattern):
                self.reserve('a', self.a, self.resource('file', pattern))
                with self.assertRaises(WORKSPACE.Blocked):
                    self.reserve('b', self.b, self.resource('file', 'src/users/model.py'))
                WORKSPACE.release(self.repo, 'a')

    def test_invalid_metadata_paths_aliases_and_registry_fail_closed(self):
        (self.a / 'linked').symlink_to(self.directory, target_is_directory=True)
        for name in ['../secret', 'src/../secret', './app.py', 'src//app.py', '.git/config',
                     'linked/secret', '.git*', '.git/config*', 'src/./*.py']:
            with self.subTest(name=name), self.assertRaises(WORKSPACE.Blocked):
                self.reserve('a', self.a, self.resource('file', name))
        for resources in [[], None, [{}], [{'type': 'unknown', 'name': 'x'}]]:
            with self.assertRaises(WORKSPACE.Blocked):
                WORKSPACE.reserve(self.repo, self.owner('a'), str(self.a), resources)
        with self.assertRaises(WORKSPACE.Blocked):
            WORKSPACE.reserve(self.repo, {'id': 'a'}, str(self.a),
                              [self.resource('file', 'a.py')])
        with self.assertRaises(WORKSPACE.Blocked):
            self.reserve('a', self.repo, self.resource('file', 'a.py'))
        self.reserve('a', self.a, self.resource('file', 'a.py'))
        state = self.repo / '.git/agentic-workspace/owners.json'
        before = state.read_bytes()
        with self.assertRaises(WORKSPACE.Blocked):
            self.reserve('a', self.a, self.resource('file', 'b.py'))
        self.assertEqual(before, state.read_bytes())
        for invalid in ['[]', '{"other": {}}', '{"other": {"id": "other", '
                        '"worktree": "/tmp/x", "resources": [{}]}}']:
            state.write_text(invalid)
            with self.assertRaises(WORKSPACE.Blocked):
                self.reserve('b', self.b, self.resource('file', 'b.py'))
            self.assertEqual(state.read_text(), invalid)
        state.write_text('{broken')
        with self.assertRaises(ValueError):
            self.reserve('b', self.b, self.resource('file', 'b.py'))
        self.assertEqual(state.read_text(), '{broken')

    def test_concurrent_processes_only_one_resource_owner(self):
        processes = []
        for number in range(8):
            path = self.directory / f'concurrent-{number}'
            WORKSPACE.create(self.repo, f'feat/concurrent-{number}', str(path))
            processes.append(subprocess.Popen([
                'python3', str(SCRIPT), 'reserve', '--repo', str(path), '--path', str(path),
                '--owner', f'owner-{number}', '--task', 'test', '--plan-sha256', 'a' * 64,
                '--resources', json.dumps([self.resource('table', 'users')])],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        outcomes = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(stderr, '')
            result = json.loads(stdout)
            self.assertEqual(process.returncode, 0 if result['verdict'] == 'PASS' else 1)
            outcomes.append(result['verdict'])
        self.assertEqual(outcomes.count('PASS'), 1)
        state = json.loads((self.repo / '.git/agentic-workspace/owners.json').read_text())
        self.assertEqual(len(state), 1)
        self.assertEqual(self.git('status', '--short'), '')


if __name__ == '__main__':
    unittest.main()
