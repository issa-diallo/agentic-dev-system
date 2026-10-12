"""Regression tests against real temporary Git repositories; stdlib only."""
import os
import importlib.util
import json
import shutil
import selectors
import sys
import tomllib
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'team project'
        self.repo.mkdir()
        self.git('init', '-q')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def install(self, *args, ok=True, target=None, force='0'):
        result = subprocess.run(
            ['bash', str(SOURCE / 'install-agentic.sh'), *args, str(target or self.repo)],
            text=True, capture_output=True, env={**os.environ, 'FORCE': force})
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_fresh_product(self):
        self.install('--shared')
        for name in ['PREPARE', 'PRD', 'STORIES', 'STORY_REVIEW', 'ARCHITECTURE', 'DESIGN_SYSTEM']:
            self.assertTrue((self.repo / f'docs/product/{name}.md').is_file())
        self.assertEqual(list((self.repo / 'docs/agentic/work').iterdir()), [])
        subprocess.run(['bash', 'scripts/agentic-check.sh'], cwd=self.repo, check=True, capture_output=True)

    def test_existing(self):
        self.install('--shared', '--existing')
        self.assertFalse((self.repo / 'docs/product').exists())
        self.assertFalse((self.repo / 'docs/adr').exists())
        subprocess.run(['bash', 'scripts/agentic-check.sh', '--existing'], cwd=self.repo, check=True, capture_output=True)

    def test_local_preserves_team_and_status(self):
        for name in ['AGENTS.md', 'COMMITS.md', '.gitignore']:
            (self.repo / name).write_text('team rules\n')
        self.git('add', '.')
        before = self.git('status', '--porcelain')
        exclude = self.repo / '.git/info/exclude'
        exclude.write_text('existing-pattern')
        self.install('--local')
        self.assertEqual(before, self.git('status', '--porcelain'))
        self.assertTrue(exclude.read_text().startswith('existing-pattern\n'))
        for name in ['AGENTS.md', 'COMMITS.md', '.gitignore']:
            self.assertEqual((self.repo / name).read_text(), 'team rules\n')
        self.assertFalse((self.repo / '.agentic-local/docs/product').exists())
        self.assertFalse((self.repo / '.github').exists())
        subprocess.run(['bash', 'scripts/agentic-check.sh', '--existing'], cwd=self.repo / '.agentic-local', check=True, capture_output=True)
        saved = exclude.read_text()
        self.install('--local', ok=False)
        self.assertEqual(exclude.read_text(), saved)

    def test_team_unignore_refused_and_exclude_restored(self):
        for pattern in ['!.agentic-local/\n.agentic-local/*\n!.agentic-local/future-private.txt', '!.agentic-local/', '!.agentic-local/\n!.agentic-local/docs/\n!.agentic-local/docs/agentic/\n!.agentic-local/docs/agentic/METHOD.md']:
            with self.subTest(pattern=pattern):
                (self.repo / '.gitignore').write_text(pattern + '\n')
                exclude = self.repo / '.git/info/exclude'
                exclude.write_text('original without newline')
                self.install('--local', ok=False)
                self.assertEqual(exclude.read_text(), 'original without newline')
                self.assertFalse((self.repo / '.agentic-local').exists())

    def test_collision_has_no_side_effect(self):
        (self.repo / 'AGENTS.md').write_text('team')
        self.install('--shared', '--existing', ok=False)
        self.assertFalse((self.repo / 'docs').exists())
        self.assertEqual((self.repo / 'AGENTS.md').read_text(), 'team')

    def test_symlink_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.repo / 'docs').symlink_to(outside, target_is_directory=True)
        self.install('--shared', ok=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_tracked_deleted_local_path_refused(self):
        local = self.repo / '.agentic-local'
        local.mkdir()
        (local / 'file').write_text('tracked')
        self.git('add', '.')
        (local / 'file').unlink()
        local.rmdir()
        self.install('--local', ok=False)
        self.assertFalse(local.exists())

    def test_worktree(self):
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--allow-empty', '-qm', 'Initial')
        worktree = self.root / 'linked worktree'
        self.git('worktree', 'add', '-qb', 'test-local', str(worktree))
        self.install('--local', target=worktree)
        result = subprocess.check_output(['git', '-C', str(worktree), 'status', '--porcelain'], text=True)
        self.assertEqual(result, '')

    def test_invalid_options_and_force(self):
        self.install('--unknown', ok=False)
        self.install('--local', '--shared', ok=False)
        self.install('--shared', '--local', ok=False)
        self.install(force='1', ok=False)
        self.assertFalse((self.repo / 'docs').exists())

    def test_v2_distribution_and_real_skill_routing_without_native_pollution(self):
        for path in ['.codex/config.toml', '.agents/skills/team/SKILL.md']:
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('team content')
        self.git('add', '.')
        before = self.git('status', '--porcelain')
        index = (self.repo / '.git/index').read_bytes()
        self.install()
        method = self.repo / '.agentic-local'
        for script in ['build', 'workspace', 'skills', 'models', 'scheduler', 'quality']:
            self.assertTrue((method / f'scripts/agentic-{script}.py').is_file())
        for role in ['explorer', 'implementer', 'reviewer']:
            data = tomllib.loads((method / f'codex/agents/{role}.toml').read_text())
            self.assertEqual(set(data), {'name', 'description', 'developer_instructions'})
        skills = list((method / 'skills').glob('*/SKILL.md'))
        self.assertEqual(len(skills), 6)
        for path in ['.codex/config.toml', '.agents/skills/team/SKILL.md']:
            self.assertEqual((self.repo / path).read_text(), 'team content')
        self.assertEqual(self.git('status', '--porcelain'), before)
        self.assertEqual((self.repo / '.git/index').read_bytes(), index)
        spec = importlib.util.spec_from_file_location('installed_skills', method / 'scripts/agentic-skills.py')
        router = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(router)
        for task, files, expected in [
                ('Add authenticated API endpoint', ['api/accounts.py'], 'api-design-backend-security'),
                ('Add SQL migration', ['migrations/003.sql'], 'database-migrations'),
                ('Fix React rendering', ['src/components/Profile.tsx'], 'frontend-patterns')]:
            result = router.select(task, files, [method / 'skills'])
            self.assertEqual({item['name'] for item in result['selected']}, {expected})
            self.assertEqual(result['loaded'], [])
            self.assertEqual(result['applied'], 'NOT_OBSERVED')
        self.git('add', '-A')
        self.assertFalse(any('.agentic-local' in p for p in self.git('diff', '--cached', '--name-only').splitlines()))
        self.git('add', '-f', '.agentic-local/codex/agents/explorer.toml')
        guard = subprocess.run(['bash', str(method / 'scripts/agentic-staged-check.sh')],
                               cwd=self.repo, capture_output=True)
        self.assertNotEqual(guard.returncode, 0)

    def test_v2_missing_source_preflight_leaves_target_unchanged(self):
        for missing in ['scripts/agentic-scheduler.py', 'codex/agents/reviewer.toml',
                        'skills/frontend-patterns/SKILL.md']:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'source'
                shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('.git', '__pycache__'))
                (source / missing).unlink()
                before = {str(p.relative_to(self.repo)): p.read_bytes()
                          for p in self.repo.rglob('*') if p.is_file()}
                result = subprocess.run(['bash', str(source / 'install-agentic.sh'), str(self.repo)],
                                        capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                after = {str(p.relative_to(self.repo)): p.read_bytes()
                         for p in self.repo.rglob('*') if p.is_file()}
                self.assertEqual(before, after)

    def test_shared_v2_collision_is_refused_before_writes(self):
        profile = self.repo / 'codex/agents/explorer.toml'
        profile.parent.mkdir(parents=True)
        profile.write_text('team profile')
        self.install('--shared', ok=False)
        self.assertEqual(profile.read_text(), 'team profile')
        self.assertFalse((self.repo / 'AGENTS.md').exists())

    def test_shared_skill_parent_file_refused_before_writes(self):
        parent = self.repo / 'skills/frontend-patterns'
        parent.parent.mkdir()
        parent.write_text('team data')
        self.install('--shared', ok=False)
        self.assertEqual(parent.read_text(), 'team data')
        self.assertFalse((self.repo / 'AGENTS.md').exists())

    def test_launcher_preserves_argv_home_and_permissions(self):
        self.install()
        binary = self.root / 'bin'
        binary.mkdir()
        fake = binary / 'codex'
        fake.write_text('#!' + sys.executable + '\nimport os,json,sys\n'
                        'print(json.dumps({"argv":sys.argv[1:],"home":os.environ.get("CODEX_HOME")}))\n')
        fake.chmod(0o755)
        args = ['exec', '--sandbox', 'read-only', 'quoted "prompt"; literal $HOME']
        env = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH'],
               'CODEX_HOME': 'unchanged-sentinel'}
        result = subprocess.run(['bash', str(self.repo / '.agentic-local/scripts/agentic-codex.sh'), *args],
                                text=True, capture_output=True, env=env, cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['argv'][6:], args)
        self.assertEqual(value['home'], 'unchanged-sentinel')
        self.assertNotIn('danger-full-access', json.dumps(value))
        for offset, role in enumerate(['explorer', 'implementer', 'reviewer']):
            self.assertEqual(value['argv'][2 * offset], '-c')
            key, path = value['argv'][2 * offset + 1].split('=', 1)
            self.assertEqual(key, f'agents.agentic_{role}.config_file')
            self.assertEqual(json.loads(path), str(self.repo / f'.agentic-local/codex/agents/{role}.toml'))

    def test_launcher_run_activates_method_with_literal_mission(self):
        self.install()
        binary = self.root / 'bin'
        binary.mkdir()
        fake = binary / 'codex'
        fake.write_text('#!' + sys.executable + '\nimport os,json,sys\n'
                        'print(json.dumps({"argv":sys.argv[1:],"home":os.environ.get("CODEX_HOME")}))\n')
        fake.chmod(0o755)
        mission = 'Build API; $(touch forbidden) "literal"\nSecond line'
        env = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH'],
               'CODEX_HOME': 'unchanged-sentinel'}
        launcher = self.repo / '.agentic-local/scripts/agentic-codex.sh'
        result = subprocess.run(['bash', str(launcher), 'run', mission, '--sandbox', 'read-only'],
                                text=True, capture_output=True, env=env, cwd=self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['home'], 'unchanged-sentinel')
        self.assertEqual(value['argv'][6:8], ['--sandbox', 'read-only'])
        self.assertEqual(len(value['argv']), 9)
        prompt = value['argv'][-1]
        self.assertTrue(prompt.endswith(mission))
        self.assertIn(str(self.repo / '.agentic-local/docs/agentic/LOCAL.md'), prompt)
        self.assertIn(str(self.repo / '.agentic-local/skills'), prompt)
        self.assertIn('repository and team rules first', prompt)
        self.assertFalse((self.repo / 'forbidden').exists())
        missing = subprocess.run(['bash', str(launcher), 'run'], capture_output=True, env=env)
        self.assertEqual(missing.returncode, 2)

    @unittest.skipUnless(shutil.which('codex'), 'Codex CLI unavailable; native parse not observed')
    def test_native_config_initialize_with_isolated_home_and_negative_control(self):
        for invalid in [False, True]:
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                profile = home / 'agent.toml'
                profile.write_text((SOURCE / 'codex/agents/explorer.toml').read_text() +
                                   ('\nunrecognized_agentic_field = true\n' if invalid else ''))
                command = ['codex', '-c', 'agents.agentic_test.config_file=' + json.dumps(str(profile)),
                           'app-server', '--strict-config']
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True,
                                           env={**os.environ, 'CODEX_HOME': str(home)})
                try:
                    request = {'id': 1, 'method': 'initialize', 'params': {
                        'clientInfo': {'name': 'agentic-install-test', 'version': '1'},
                        'capabilities': {'experimentalApi': True}}}
                    process.stdin.write(json.dumps(request) + '\n')
                    process.stdin.flush()
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ)
                        self.assertTrue(selector.select(10), 'initialize timed out')
                        response = json.loads(process.stdout.readline())
                    self.assertIn('result', response)
                finally:
                    process.terminate()
                    _, stderr = process.communicate(timeout=5)
                self.assertEqual('unknown field' in stderr.lower(), invalid)
                self.assertFalse((home / 'auth.json').exists())

    def test_non_git_and_subdir_refused(self):
        plain = self.root / 'plain'
        plain.mkdir()
        self.install(target=plain, ok=False)
        subdir = self.repo / 'subdir'
        subdir.mkdir()
        self.install('--local', target=subdir, ok=False)
        self.assertFalse((plain / '.agentic-local').exists())


if __name__ == '__main__':
    unittest.main()
