import importlib.util
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
