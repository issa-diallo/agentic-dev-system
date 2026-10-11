"""Local-install safety and real guarded commits in disposable repositories."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class CommitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'project'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def install(self, *args, target=None):
        return subprocess.run(['bash', str(SOURCE / 'install-agentic.sh'), *args,
                               str(target or self.repo)], check=True, capture_output=True)

    def run_script(self, name, *args, ok=True, repo=None):
        target = repo or self.repo
        result = subprocess.run(['bash', str(target / '.agentic-local/scripts' / name), *args],
                                cwd=target, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def guard(self, **kwargs):
        return self.run_script('agentic-staged-check.sh', **kwargs)

    def commit(self, *args, **kwargs):
        return self.run_script('agentic-commit.sh', *args, **kwargs)

    def write(self, path, text):
        dest = self.repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        return dest

    def test_default_status_add_and_business_commit(self):
        self.install()
        self.assertEqual(self.git('status', '--short'), '')
        self.write('.agentic-local/docs/agentic/work/17/research.md', 'personal decisions')
        for path in ['src/app.py', 'docs/product/PRD.md', 'docs/adr/decision.md',
                     'AGENTS.md', '.github/workflows/app.yml', '.codex/config.toml']:
            self.write(path, 'application or team document\n')
        before = self.git('status', '--short')
        self.git('add', '-A')
        self.guard()
        self.commit('-m', 'Business changes')
        committed = self.git('show', '--pretty=', '--name-only', 'HEAD').splitlines()
        self.assertEqual(set(committed), {'src/app.py', 'docs/product/PRD.md',
                                         'docs/adr/decision.md', 'AGENTS.md',
                                         '.github/workflows/app.yml', '.codex/config.toml'})
        self.assertEqual(self.git('status', '--short'), '')
        self.git('add', '.')
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')
        self.assertNotEqual(before, '')

    def test_existing_dirty_index_and_git_rules_preserved(self):
        self.write('.gitignore', 'cache/\n')
        self.write('staged.txt', 'staged')
        self.git('add', '.')
        self.write('staged.txt', 'working changes')
        self.write('untracked.txt', 'pending')
        self.git('config', 'core.hooksPath', '../custom-hooks')
        config = (self.repo / '.git/config').read_bytes()
        index = (self.repo / '.git/index').read_bytes()
        before = self.git('status', '--short')
        self.install('--existing')
        self.assertEqual(self.git('status', '--short'), before)
        self.assertEqual((self.repo / '.git/index').read_bytes(), index)
        self.assertEqual((self.repo / '.git/config').read_bytes(), config)
        self.assertEqual((self.repo / '.gitignore').read_text(), 'cache/\n')
        self.guard()

    def test_forced_add_unusual_personal_name_blocks_commit(self):
        self.install()
        path = '.agentic-local/docs/agentic/work/private note\nsecret.md'
        self.write(path, 'private content')
        self.git('add', '-f', '--', path)
        self.guard(ok=False)
        self.commit('-m', 'Must refuse', ok=False)
        self.assertNotEqual(subprocess.run(['git', '-C', str(self.repo),
                                           'rev-parse', '--verify', 'HEAD'],
                                          capture_output=True).returncode, 0)

    def test_inherited_personal_paths_and_rename_copy_sources(self):
        original = 'notes/my decisions\nprivate.md'
        self.write(original, 'personal decisions and work in progress\n' * 10)
        self.git('add', '.')
        self.git('commit', '-qm', 'Legacy files')
        self.install()
        (self.repo / '.agentic-local/personal-paths.nul').write_bytes(os.fsencode(original) + b'\0')
        self.write(original, 'changed personal decisions')
        self.git('add', '--', original)
        self.guard(ok=False)
        self.git('restore', '--staged', '--worktree', '--', original)
        self.git('mv', '--', original, 'public.md')
        self.guard(ok=False)
        self.git('restore', '--staged', '--worktree', '--', original)
        self.git('rm', '--cached', '--', 'public.md')
        (self.repo / 'public.md').unlink()
        shutil.copyfile(self.repo / original, self.repo / 'copied.md')
        self.git('add', 'copied.md')
        self.guard(ok=False)

    def test_business_document_with_similar_markdown_is_allowed(self):
        self.write('docs/agentic/work/17/research.md',
                   '# Research\n\n## Scope\n\n' + 'Personal notes and hypotheses.\n' * 10)
        self.git('add', '.')
        self.git('commit', '-qm', 'Legacy notes')
        self.install()
        self.write('docs/product/PRD.md',
                   '# Research\n\n## Scope\n\n' + 'Approved business requirements.\n' * 10)
        self.git('add', 'docs/product/PRD.md')
        self.guard()
        self.commit('-m', 'Business document')

    def test_index_deletion_allowed_with_physical_content_preserved(self):
        path = 'docs/agentic/work/old/research.md'
        self.write(path, 'legacy decisions')
        self.git('add', '.')
        self.git('commit', '-qm', 'Legacy')
        self.install()
        self.git('rm', '--cached', '--', path)
        self.guard()
        self.commit('-m', 'Stop tracking personal research')
        self.assertEqual((self.repo / path).read_text(), 'legacy decisions')
        self.assertEqual(self.git('ls-files', '--', path), '')

    def test_wrapper_rejects_index_changing_options(self):
        path = 'docs/agentic/STATUS.md'
        self.write(path, 'legacy status')
        self.git('add', '.')
        self.git('commit', '-qm', 'Legacy')
        self.install()
        self.write(path, 'private status changed')
        self.guard()  # Nothing staged: -a would bypass this check without the wrapper.
        for args in [('-a', '-m', 'Unsafe'), ('--all', '-m', 'Unsafe'),
                     ('-m', 'Unsafe', path), ('--include', path),
                     ('--only', path), ('--pathspec-from-file=paths',), ('--interactive',)]:
            with self.subTest(args=args):
                self.commit(*args, ok=False)
        self.assertEqual(self.git('log', '-1', '--format=%s').strip(), 'Legacy')

    def test_broken_ignore_after_install_blocks_commit(self):
        self.install()
        self.write('app.py', 'business')
        self.git('add', 'app.py')
        self.write('.gitignore', '!.agentic-local/\n.agentic-local/*\n!.agentic-local/future-private.txt\n')
        self.guard(ok=False)  # Current children hidden, parent exposed for future names.
        self.commit('-m', 'Must refuse', ok=False)
        self.write('.gitignore', '!.agentic-local/\n')
        self.git('add', '-A')
        self.guard(ok=False)

    def test_missing_or_malformed_manifest_and_git_errors_fail_closed(self):
        self.install()
        (self.repo / '.agentic-local/personal-paths.nul').write_bytes(b'notes.txt')
        self.guard(ok=False)
        (self.repo / '.agentic-local/personal-paths.nul').write_bytes(b'../notes.txt\0')
        self.guard(ok=False)
        result = subprocess.run(['bash', str(SOURCE / 'scripts/agentic-staged-check.sh')],
                                cwd=self.temp.name, capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_multiple_worktrees_and_personal_notes_survive_update_refusal(self):
        self.git('commit', '--allow-empty', '-qm', 'Initial')
        self.install()
        self.write('.agentic-local/docs/agentic/STATUS.md', 'CURRENT STATUS AND DECISIONS')
        self.write('.agentic-local/docs/agentic/work/17/plan.md', 'IN PROGRESS')
        snapshot = {str(p.relative_to(self.repo)): p.read_bytes()
                    for p in (self.repo / '.agentic-local').rglob('*') if p.is_file()}
        result = subprocess.run(['bash', str(SOURCE / 'install-agentic.sh'), str(self.repo)],
                                capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(snapshot, {str(p.relative_to(self.repo)): p.read_bytes()
                                   for p in (self.repo / '.agentic-local').rglob('*') if p.is_file()})
        for num in [1, 2]:
            worktree = Path(self.temp.name) / f'worktree {num}'
            self.git('worktree', 'add', '-qb', f'story-{num}', str(worktree))
            self.install(target=worktree)
            subprocess.run(['git', '-C', str(worktree), 'add', '-A'], check=True)
            self.run_script('agentic-staged-check.sh', repo=worktree)
            self.assertEqual(subprocess.check_output(['git', '-C', str(worktree),
                                                     'status', '--short'], text=True), '')
        self.assertEqual((self.repo / '.git/info/exclude').read_text().count('/.agentic-local/'), 1)

    def test_empty_personal_copy_allows_empty_application_file(self):
        self.write('docs/agentic/work/old/research.md', '')
        self.git('add', '.')
        self.git('commit', '-qm', 'Legacy empty note')
        self.install()
        self.write('src/package/__init__.py', '')
        self.git('add', 'src/package/__init__.py')
        self.guard()
        self.commit('-m', 'Initialize package')
        self.assertEqual(self.git('show', '--pretty=', '--name-only').strip(),
                         'src/package/__init__.py')
        self.write('.agentic-local/empty-private.md', '')
        self.git('add', '-f', '.agentic-local/empty-private.md')
        self.guard(ok=False)  # An empty private destination is still forbidden.
        self.git('restore', '--staged', '--', '.agentic-local/empty-private.md')
        self.git('mv', 'docs/agentic/work/old/research.md', 'public-empty.md')
        self.guard(ok=False)  # A rename retains personal ownership, even if empty.

    def test_amend_root_personal_commit_refused_in_each_object_format(self):
        for object_format in ['sha1', 'sha256']:
            with self.subTest(object_format=object_format):
                repo = Path(self.temp.name) / object_format
                init = subprocess.run(['git', 'init', '-q', '--object-format=' + object_format,
                                       str(repo)], capture_output=True)
                if init.returncode:
                    self.skipTest('Installed Git does not support ' + object_format)
                previous = self.repo
                self.repo = repo
                try:
                    self.git('config', 'user.name', 'Test')
                    self.git('config', 'user.email', 'test@example.com')
                    self.write('docs/agentic/work/old/research.md', 'personal root note')
                    self.git('add', '.')
                    self.git('commit', '-qm', 'Private root')
                    self.install()
                    head = self.git('rev-parse', 'HEAD')
                    self.guard()  # Comparing to HEAD alone would miss this exposure.
                    self.commit('--amend', '--no-edit', ok=False)
                    self.assertEqual(self.git('rev-parse', 'HEAD'), head)
                finally:
                    self.repo = previous

    def test_amend_nonroot_personal_change_refused(self):
        self.write('app.py', 'application')
        self.git('add', '.')
        self.git('commit', '-qm', 'Business root')
        self.write('docs/agentic/STATUS.md', 'personal latest status')
        self.git('add', '.')
        self.git('commit', '-qm', 'Private nonroot')
        self.install()
        head = self.git('rev-parse', 'HEAD')
        self.guard()
        self.commit('--amend', '--no-edit', ok=False)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.git('rm', '--cached', 'docs/agentic/STATUS.md')
        self.commit('--amend', '--allow-empty', '-m', 'Remove private change')
        self.assertEqual(self.git('ls-files', '--', 'docs/agentic/STATUS.md'), '')
        self.assertEqual((self.repo / 'docs/agentic/STATUS.md').read_text(), 'personal latest status')

    def test_amend_safe_root_and_nonroot_commit(self):
        self.write('app.py', 'application')
        self.git('add', '.')
        self.git('commit', '-qm', 'Business root')
        self.install()
        self.commit('--amend', '-m', 'Correct root message')
        self.assertEqual(self.git('log', '-1', '--format=%s').strip(), 'Correct root message')
        self.write('app.py', 'updated application')
        self.git('add', 'app.py')
        self.commit('-m', 'Business nonroot')
        self.commit('--amend', '-m', 'Correct nonroot message')
        self.assertEqual(self.git('log', '-1', '--format=%s').strip(), 'Correct nonroot message')
        self.assertEqual(self.git('rev-list', '--count', 'HEAD').strip(), '2')

    def test_personal_gitlink_refused_despite_ignore_submodules_configuration(self):
        self.install()
        nested = self.repo / '.agentic-local'
        subprocess.run(['git', '-C', str(nested), 'init', '-q'], check=True)
        subprocess.run(['git', '-C', str(nested), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.com', 'commit', '--allow-empty',
                        '-qm', 'Nested method'], check=True)
        self.git('config', 'diff.ignoreSubmodules', 'all')
        config = (self.repo / '.git/config').read_bytes()
        subprocess.run(['git', '-C', str(self.repo), 'add', '-f', '.agentic-local'],
                       check=True, capture_output=True)
        self.assertEqual(self.git('diff', '--cached', '--name-status'), '')
        self.assertIn('160000', self.git('ls-files', '--stage'))
        self.guard(ok=False)
        self.commit('-m', 'Must reject private gitlink', ok=False)
        self.assertEqual((self.repo / '.git/config').read_bytes(), config)

    def test_copied_business_gitlink_with_external_commit_is_allowed(self):
        component = Path(self.temp.name) / 'component'
        subprocess.run(['git', 'init', '-q', str(component)], check=True)
        subprocess.run(['git', '-C', str(component), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.com', 'commit', '--allow-empty',
                        '-qm', 'Component commit'], check=True)
        commit_id = subprocess.check_output(['git', '-C', str(component),
                                             'rev-parse', 'HEAD'], text=True).strip()
        self.git('update-index', '--add', '--cacheinfo', '160000', commit_id, 'vendor/component-a')
        self.git('commit', '-qm', 'Application component')
        self.install()
        self.git('config', 'diff.ignoreSubmodules', 'all')
        config = (self.repo / '.git/config').read_bytes()
        self.git('update-index', '--add', '--cacheinfo', '160000', commit_id, 'vendor/component-b')
        self.assertNotEqual(subprocess.run(['git', '-C', str(self.repo), 'cat-file',
                                           '-e', commit_id], capture_output=True).returncode, 0)
        self.assertIn('C100', self.git('diff', '--cached', '--ignore-submodules=none',
                                      '--name-status', '--find-copies=100%', '--find-copies-harder'))
        self.guard()
        self.commit('-m', 'Share component across app modules')
        self.assertIn('vendor/component-b', self.git('ls-tree', '-r', 'HEAD'))
        self.assertEqual((self.repo / '.git/config').read_bytes(), config)

    def test_private_gitlink_copy_refused_without_reading_external_commit(self):
        component = Path(self.temp.name) / 'private-component'
        subprocess.run(['git', 'init', '-q', str(component)], check=True)
        subprocess.run(['git', '-C', str(component), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.com', 'commit', '--allow-empty',
                        '-qm', 'Private component'], check=True)
        commit_id = subprocess.check_output(['git', '-C', str(component),
                                             'rev-parse', 'HEAD'], text=True).strip()
        self.git('update-index', '--add', '--cacheinfo', '160000', commit_id,
                 'docs/agentic/work/private-component')
        self.git('commit', '-qm', 'Legacy private gitlink')
        self.install()
        self.git('update-index', '--add', '--cacheinfo', '160000', commit_id, 'vendor/component')
        result = self.guard(ok=False)
        self.assertIn('BLOCKED: personal Agentic path staged:', result.stderr)
        self.assertNotIn('Not a valid object name', result.stderr)

    def test_dangling_manifest_symlink_refused(self):
        self.install()
        manifest = self.repo / '.agentic-local/personal-paths.nul'
        manifest.symlink_to('missing-manifest.nul')
        self.write('app.py', 'business application')
        self.git('add', 'app.py')
        result = self.guard(ok=False)
        self.assertIn('Invalid personal path manifest', result.stderr)
        self.commit('-m', 'Must refuse invalid personal policy', ok=False)

    def test_documented_migration_and_targeted_rollback(self):
        paths = ['docs/agentic/work/17/research.md', 'docs/agentic/STATUS.md', 'personal.md']
        for path in paths:
            self.write(path, 'decisions, status and current work: ' + path)
        self.write('docs/product/PRD.md', 'legitimate business requirements')
        self.write('AGENTS.md', 'team instructions')
        self.git('add', '.')
        self.git('commit', '-qm', 'Legacy install and business docs')
        self.write(paths[0], 'uncommitted work in progress')
        self.write('docs/product/PRD.md', 'uncommitted business changes')
        self.write('untracked-app.py', 'new application work')
        before = {path: (self.repo / path).read_bytes() for path in paths}
        self.install()
        backup = self.repo / '.agentic-local/migration-backup'
        backup.mkdir()
        shutil.copyfile(self.repo / '.git/index', backup / 'index')
        shutil.copyfile(self.repo / '.git/info/exclude', backup / 'exclude')
        for path in paths:
            destination = backup / 'files' / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.repo / path, destination)
        manifest = self.repo / '.agentic-local/personal-paths.nul'
        manifest.write_bytes(b''.join(os.fsencode(path) + b'\0' for path in paths))
        # Review/approval is an explicit prerequisite in the documented procedure.
        exclude = self.repo / '.git/info/exclude'
        with exclude.open('a') as file:
            for path in paths:
                file.write('/' + path + '\n')
        self.git('--literal-pathspecs', 'rm', '--cached', '--', *paths)
        self.guard()
        self.assertEqual(before, {path: (self.repo / path).read_bytes() for path in paths})
        self.assertEqual(set(self.git('ls-files').splitlines()), {'AGENTS.md', 'docs/product/PRD.md'})
        dry_run = self.git('add', '--dry-run', '-A')
        self.assertNotIn('personal.md', dry_run)
        self.assertIn('untracked-app.py', dry_run)
        self.assertEqual(set(self.git('diff', '--cached', '--name-only').splitlines()), set(paths))
        # Pre-commit rollback: restore ONLY selected index entries, retain working changes.
        self.git('--literal-pathspecs', 'restore', '--source=HEAD', '--staged', '--', *paths)
        shutil.copyfile(backup / 'exclude', exclude)
        self.assertEqual(before, {path: (self.repo / path).read_bytes() for path in paths})
        self.assertEqual(set(self.git('ls-files').splitlines()), set(paths + ['AGENTS.md', 'docs/product/PRD.md']))
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')
        self.assertIn('uncommitted', (self.repo / paths[0]).read_text())
        self.assertEqual((self.repo / 'docs/product/PRD.md').read_text(), 'uncommitted business changes')
        self.assertEqual((self.repo / 'untracked-app.py').read_text(), 'new application work')


if __name__ == '__main__':
    unittest.main()
