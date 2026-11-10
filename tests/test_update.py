import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('update', ROOT / 'update-agentic.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


def fake_source():
    src = Path(tempfile.mkdtemp())
    for rel, text in {'AGENTS.md': 'v2', 'COMMITS.md': 'c', 'docs/agentic/README.md': 'r2',
                      'docs/agentic/STATUS.md': 'never', 'docs/agentic/work/x.md': 'never',
                      'scripts/agentic-a.py': 'a2', 'scripts/other.py': 'skip'}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    return src


def install(files):
    project = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(text)
    return project


class UpdateTests(unittest.TestCase):
    def test_first_run_resources_are_added_without_replacing_saved_choices(self):
        src = fake_source()
        for relative in ('scripts/agentic-onboard.py', 'docs/agentic/ONBOARDING.md'):
            target = src / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        project = install({'.agentic-local/docs/agentic/README.md': 'r2',
                           '.agentic-local/agentic.config.json': '{"personal": "keep"}'})
        report = update.update(project, source=src, stamp='onboarding')
        for relative in ('scripts/agentic-onboard.py', 'docs/agentic/ONBOARDING.md'):
            self.assertIn(relative, report['added'])
            self.assertEqual((project / '.agentic-local' / relative).read_bytes(),
                             (src / relative).read_bytes())
        self.assertEqual((project / '.agentic-local/agentic.config.json').read_text(),
                         '{"personal": "keep"}')

    def test_native_profiles_migrate_update_and_preserve_customizations(self):
        src = fake_source()
        project = install({'.agentic-local/docs/agentic/README.md': 'r2'})
        subprocess.run(['git', 'init', '-q', str(project)], check=True)
        method = project / '.agentic-local'
        for client, suffix in [('codex', 'toml'), ('claude', 'md')]:
            for role in ('explorer', 'implementer', 'reviewer'):
                relative = f'{client}/agents/{role}.{suffix}'
                for base in (method, src):
                    target = base / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((ROOT / relative).read_bytes())
        update.record(method, source=src)
        report = update.update(project, source=src, stamp='native-first')
        native = project / '.codex/agents/agentic-explorer.toml'
        custom = project / '.claude/agents/agentic-reviewer.md'
        self.assertEqual(native.read_bytes(), (src / 'codex/agents/explorer.toml').read_bytes())
        original = native.read_bytes()
        custom.write_text('my reviewer\n')
        wanted = original + b'\n# updated source\n'
        (src / 'codex/agents/explorer.toml').write_bytes(wanted)
        before_exclude = (project / '.git/info/exclude').read_bytes()
        preview = update.update(project, source=src, dry_run=True, stamp='preview')
        self.assertEqual(native.read_bytes(), original)
        self.assertEqual((project / '.git/info/exclude').read_bytes(), before_exclude)
        self.assertIn('.codex/agents/agentic-explorer.toml', preview['native_agents']['updated'])
        report = update.update(project, source=src, stamp='native-next')
        self.assertEqual(native.read_bytes(), wanted)
        self.assertEqual(custom.read_text(), 'my reviewer\n')
        self.assertIn('.claude/agents/agentic-reviewer.md', report['native_agents']['customized'])
        self.assertEqual(subprocess.run(['git', '-C', str(project), 'check-ignore', '-q',
                                        '.codex/agents/agentic-explorer.toml']).returncode, 0)

    def test_mapping_rule_is_distributed_updated_and_customization_preserved(self):
        relative = 'rules/core/prefer-declarative-mapping.md'
        src = fake_source()
        rule = src / relative
        rule.parent.mkdir(parents=True)
        rule.write_text('CORE-DESIGN-001 v1')
        for local in (False, True):
            with self.subTest(local=local):
                prefix = '.agentic-local/' if local else ''
                project = install({prefix + 'docs/agentic/README.md': 'r2'})
                method = project / '.agentic-local' if local else project
                update.update(project, source=src, stamp='rule-add')
                installed = method / relative
                self.assertEqual(installed.read_bytes(), rule.read_bytes())
                rule.write_text('CORE-DESIGN-001 v2')
                update.update(project, source=src, stamp='rule-update')
                self.assertEqual(installed.read_bytes(), rule.read_bytes())
                installed.write_text('team rule')
                report = update.update(project, source=src, stamp='rule-custom')
                self.assertIn(relative, report['customized'])
                self.assertEqual(installed.read_text(), 'team rule')
                rule.write_text('CORE-DESIGN-001 v1')

    def test_managed_skips_project_data_and_foreign_scripts(self):
        files = update.managed(fake_source())
        self.assertEqual(sorted(files), ['AGENTS.md', 'COMMITS.md', 'docs/agentic/README.md',
                                         'scripts/agentic-a.py'])

    def test_pristine_updated_customized_kept_missing_added(self):
        src = fake_source()
        project = install({'docs/agentic/x': '', 'AGENTS.md': 'v1', 'COMMITS.md': 'c',
                           'docs/agentic/README.md': 'team edit'})
        (project / update.MANIFEST).write_text(
            '{"files": {"AGENTS.md": "%s"}}' % update.digest(project / 'AGENTS.md'))
        report = update.update(project, source=src, stamp='t')
        self.assertEqual(report['updated'], ['AGENTS.md'])
        self.assertEqual(report['customized'], ['docs/agentic/README.md'])
        self.assertEqual(report['added'], ['scripts/agentic-a.py'])
        self.assertEqual((project / 'AGENTS.md').read_text(), 'v2')
        self.assertEqual((project / 'docs/agentic/README.md').read_text(), 'team edit')
        work = project / 'docs/agentic/work/.update-t'
        self.assertEqual((work / 'backup/AGENTS.md').read_text(), 'v1')
        self.assertEqual((work / 'incoming/docs/agentic/README.md').read_text(), 'r2')
        again = update.update(project, source=src, stamp='u')
        self.assertEqual(again['updated'], [])

    def test_dry_run_changes_nothing_and_local_install_detected(self):
        src = fake_source()
        project = install({'.agentic-local/AGENTS.md': 'v1', '.agentic-local/docs/agentic/y': ''})
        report = update.update(project, dry_run=True, source=src)
        self.assertEqual(report['root'], str((project / '.agentic-local').resolve()))
        self.assertEqual((project / '.agentic-local/AGENTS.md').read_text(), 'v1')
        self.assertFalse((project / '.agentic-local' / update.MANIFEST).exists())

    def test_force_overwrites_with_backup(self):
        src = fake_source()
        project = install({'docs/agentic/README.md': 'team edit', 'AGENTS.md': 'v2'})
        report = update.update(project, force=True, source=src, stamp='f')
        self.assertEqual(report['forced'], ['docs/agentic/README.md'])
        self.assertEqual((project / 'docs/agentic/work/.update-f/backup/docs/agentic/README.md').read_text(),
                         'team edit')


if __name__ == '__main__':
    unittest.main()
