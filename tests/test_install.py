"""Regression tests against real temporary Git repositories; stdlib only."""
import os
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
        self.install()
        for name in ['PRD', 'STORIES', 'STORY_REVIEW', 'ARCHITECTURE', 'DESIGN_SYSTEM']:
            self.assertTrue((self.repo / f'docs/product/{name}.md').is_file())
        self.assertEqual(list((self.repo / 'docs/agentic/work').iterdir()), [])
        subprocess.run(['bash', 'scripts/agentic-check.sh'], cwd=self.repo, check=True, capture_output=True)

    def test_existing(self):
        self.install('--existing')
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
        for pattern in ['!.agentic-local/', '!.agentic-local/\n!.agentic-local/docs/\n!.agentic-local/docs/agentic/\n!.agentic-local/docs/agentic/METHOD.md']:
            with self.subTest(pattern=pattern):
                (self.repo / '.gitignore').write_text(pattern + '\n')
                exclude = self.repo / '.git/info/exclude'
                exclude.write_text('original without newline')
                self.install('--local', ok=False)
                self.assertEqual(exclude.read_text(), 'original without newline')
                self.assertFalse((self.repo / '.agentic-local').exists())

    def test_collision_has_no_side_effect(self):
        (self.repo / 'AGENTS.md').write_text('team')
        self.install('--existing', ok=False)
        self.assertFalse((self.repo / 'docs').exists())
        self.assertEqual((self.repo / 'AGENTS.md').read_text(), 'team')

    def test_symlink_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.repo / 'docs').symlink_to(outside, target_is_directory=True)
        self.install(ok=False)
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
        self.install(force='1', ok=False)
        self.assertFalse((self.repo / 'docs').exists())

    def test_non_git_and_subdir_refused(self):
        plain = self.root / 'plain'
        plain.mkdir()
        self.install('--local', target=plain, ok=False)
        subdir = self.repo / 'subdir'
        subdir.mkdir()
        self.install('--local', target=subdir, ok=False)
        self.assertFalse((plain / '.agentic-local').exists())


if __name__ == '__main__':
    unittest.main()
