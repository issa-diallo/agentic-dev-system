"""Native profile installation preserves team files and personal Git boundaries."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/agentic-agents.py'
SPEC = importlib.util.spec_from_file_location('agentic_agents', SCRIPT)
AGENTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGENTS)


class NativeAgentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.method = self.root / 'method'
        self.project = self.root / 'project'
        self.project.mkdir()
        self.git('init', '-q')
        for family, suffix in [('codex', 'toml'), ('claude', 'md')]:
            for role in ['explorer', 'implementer', 'reviewer']:
                path = self.method / family / 'agents' / f'{role}.{suffix}'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f'{family} {role} v1\n')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.project), *args],
                              check=True, capture_output=True, text=True).stdout

    def snapshot(self):
        return {str(p.relative_to(self.project)): p.read_bytes()
                for p in self.project.rglob('*') if p.is_file()}

    def sync(self, **kwargs):
        return AGENTS.sync(self.method, self.project, **kwargs)

    def target(self, family='codex', role='explorer'):
        suffix = 'toml' if family == 'codex' else 'md'
        return self.project / f'.{family}/agents/agentic-{role}.{suffix}'

    def test_native_registration_is_exact_and_preserves_other_configuration(self):
        config = self.project / '.codex/config.toml'
        config.parent.mkdir()
        config.write_text('team configuration')
        custom = self.target(role='team-reviewer')
        custom.parent.mkdir()
        custom.write_text('team profile')
        result = self.sync()
        self.assertEqual(len(result['added']), 6)
        self.assertEqual(config.read_text(), 'team configuration')
        self.assertEqual(custom.read_text(), 'team profile')
        for rel, content in AGENTS.profiles(self.method).items():
            self.assertEqual((self.project / rel).read_bytes(), content)
        self.assertEqual(len(self.sync()['unchanged']), 6)

    def test_collision_blocks_every_write(self):
        native = self.target('claude', 'reviewer')
        native.parent.mkdir(parents=True)
        native.write_text('customized')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.sync(local=True)
        self.assertEqual(before, self.snapshot())

    def test_previous_snapshot_updates_only_untouched_native_profiles(self):
        self.sync()
        previous = AGENTS.profiles(self.method)
        custom = self.target('claude', 'reviewer')
        custom.write_text('customized')
        for path in self.method.rglob('*'):
            if path.is_file():
                path.write_bytes(path.read_bytes().replace(b'v1', b'v2'))
        result = self.sync(previous=previous)
        self.assertEqual(len(result['updated']), 5)
        self.assertEqual(result['customized'], ['.claude/agents/agentic-reviewer.md'])
        self.assertEqual(custom.read_text(), 'customized')
        self.assertIn('v2', self.target().read_text())

    def test_local_registration_keeps_git_clean_with_exact_exclusions(self):
        before = self.git('status', '--porcelain')
        result = self.sync(local=True)
        self.assertEqual(len(result['added']), 6)
        self.assertEqual(self.git('status', '--porcelain'), before)
        exclude = (self.project / '.git/info/exclude').read_text()
        for rel in AGENTS.profiles(self.method):
            self.assertIn('/' + rel + '\n', exclude)
            self.git('check-ignore', '--no-index', '-q', rel)
        extra = self.target(role='another-reviewer')
        extra.write_text('new team profile')
        self.assertIn('?? .codex/', self.git('status', '--porcelain'))
        self.assertNotIn('/.codex/\n', exclude)

    def test_team_unignore_refused_without_any_write_even_in_preflight(self):
        (self.project / '.gitignore').write_text('!.codex/agents/*\n')
        before = self.snapshot()
        for kwargs in ({'local': True}, {'local': True, 'check': True},
                       {'local': True, 'dry_run': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.sync(**kwargs)
            self.assertEqual(before, self.snapshot())

    def test_team_nested_unignore_refused(self):
        folder = self.project / '.codex'
        folder.mkdir()
        (folder / '.gitignore').write_text('!agents/*\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.sync(local=True)
        self.assertEqual(before, self.snapshot())

    def test_check_and_dry_run_leave_project_untouched(self):
        before = self.snapshot()
        for kwargs in ({'check': True}, {'dry_run': True},
                       {'local': True, 'check': True}, {'local': True, 'dry_run': True}):
            self.assertEqual(len(self.sync(**kwargs)['added']), 6)
            self.assertEqual(before, self.snapshot())

    def test_tracked_native_profile_is_refused_even_when_deleted(self):
        native = self.target()
        native.parent.mkdir(parents=True)
        native.write_bytes(AGENTS.profiles(self.method)[str(native.relative_to(self.project))])
        self.git('add', str(native.relative_to(self.project)))
        native.unlink()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.sync(local=True)
        self.assertEqual(before, self.snapshot())

    def test_local_requires_git_root(self):
        nested = self.project / 'nested'
        nested.mkdir()
        plain = self.root / 'plain'
        plain.mkdir()
        for target in [nested, plain]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                AGENTS.sync(self.method, target, local=True)

    def test_source_missing_refused_before_target_writes(self):
        (self.method / 'claude/agents/reviewer.md').unlink()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.sync()
        self.assertEqual(before, self.snapshot())

    def test_source_and_destination_symlinks_and_file_parents_refused(self):
        for location in ['source', 'target-parent', 'target-file', 'file-parent']:
            with self.subTest(location=location), tempfile.TemporaryDirectory() as d:
                project = Path(d)
                if location == 'source':
                    source = self.method / 'codex/agents/explorer.toml'
                    original = source.read_bytes()
                    source.unlink()
                    source.symlink_to(self.method / 'codex/agents/reviewer.toml')
                elif location == 'target-parent':
                    (project / '.codex').symlink_to(self.project, target_is_directory=True)
                elif location == 'target-file':
                    path = project / '.codex/agents/agentic-explorer.toml'
                    path.parent.mkdir(parents=True)
                    path.symlink_to(self.method / 'codex/agents/explorer.toml')
                else:
                    (project / '.codex').write_text('team file')
                with self.assertRaises(ValueError):
                    AGENTS.sync(self.method, project)
                if location == 'source':
                    source.unlink()
                    source.write_bytes(original)

    def test_symlinked_exclude_refused_without_touching_destination(self):
        exclude = self.project / '.git/info/exclude'
        outside = self.root / 'external-exclude'
        outside.write_text('keep\n')
        exclude.unlink()
        exclude.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.sync(local=True)
        self.assertEqual(outside.read_text(), 'keep\n')
        self.assertFalse(self.target().exists())

    def test_linked_worktree_uses_resolved_git_exclude(self):
        (self.project / 'tracked').write_text('base')
        self.git('add', 'tracked')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'base')
        linked = self.root / 'linked'
        self.git('worktree', 'add', '-qb', 'linked', str(linked))
        AGENTS.sync(self.method, linked, local=True)
        result = subprocess.run(['git', '-C', str(linked), 'status', '--porcelain'],
                                check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout, '')

    def test_cli_preflight_json_and_nonzero_collision(self):
        command = ['python3', str(SCRIPT), '--method-root', str(self.method),
                   '--project', str(self.project), '--local', '--check']
        before = self.snapshot()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['added']), 6)
        self.assertEqual(before, self.snapshot())
        native = self.target()
        native.parent.mkdir(parents=True)
        native.write_text('custom')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
