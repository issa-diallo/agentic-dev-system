import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path('skills/catalog.json')
GUIDE = Path('docs/agentic/SKILL_CATALOG.md')


class SkillCatalogTests(unittest.TestCase):
    def test_audited_scope_and_reference_only_directory(self):
        catalog = json.loads((ROOT / CATALOG).read_text())
        self.assertEqual(catalog['version'], 1)
        entries = catalog['skills']
        ids = {entry['id'] for entry in entries}
        self.assertEqual(len(entries), len(ids))
        approved = {entry['capability'] for entry in entries if entry['status'] == 'approved'}
        self.assertTrue({'frontend', 'canvas', 'copywriting', 'seo-audit', 'seo-page',
                         'geo', 'security', 'debugging', 'memory', 'context-optimization',
                         'multi-agent'} <= approved)
        directory = 'ComposioHQ/awesome-claude-skills'
        self.assertIn(directory, [item['repo'] for item in catalog['discovery']])
        for entry in entries:
            with self.subTest(entry=entry['id']):
                self.assertNotEqual(entry['repo'], directory)
                self.assertNotIn('superpowers', (entry['repo'] + '/' + entry['id']).lower())
                self.assertRegex(entry['id'], r'^[a-z0-9-]+/[a-z0-9-]+$')
                self.assertRegex(entry['commit'], r'^[a-f0-9]{40}$')
                self.assertTrue(entry['name'] and entry['description'] and entry['risks'])
                self.assertEqual(Path(entry['path']).name, 'SKILL.md')
                self.assertIn(entry['id'], (ROOT / GUIDE).read_text())
                self.assertLessEqual(set(entry['depends_on']), ids)
                if entry['capability'] == 'video':
                    self.assertEqual(entry['status'], 'blocked')
                    self.assertFalse(entry['agents'])
                    continue
                self.assertCountEqual(entry['agents'], ['codex', 'claude'])
                self.assertTrue(all(entry['triggers']) and entry['triggers'])
                self.assertEqual(set(entry['files_sha256']), {entry['path'], entry['terms']})
                for digest in [entry['extracted_sha256'], *entry['files_sha256'].values()]:
                    self.assertRegex(digest, r'^[a-f0-9]{64}$')
                previous_end = 0
                self.assertTrue(entry['ranges'])
                for start, end in entry['ranges']:
                    self.assertLess(previous_end, start)
                    self.assertLessEqual(start, end)
                    previous_end = end

    def test_landing_page_mentions_need_a_delivery_intent(self):
        """Check the registry's AND/OR contract independently of routing weights."""
        entries = json.loads((ROOT / CATALOG).read_text())['skills']
        candidates = {'frontend', 'copywriting', 'seo-audit', 'seo-page'}
        examples = {
            'créer une landing page SaaS commerciale': {'frontend', 'copywriting'},
            'mesurer le trafic de la landing page SaaS': set(),
            'auditer le SEO de la landing page SaaS': {'seo-page'},
            'auditer le SEO du site': {'seo-audit'},
            'audit the SEO of the landing page': {'seo-page'},
            'measure traffic to the SaaS landing page': set(),
        }
        for objective, expected in examples.items():
            with self.subTest(objective=objective):
                text = ' ' + objective.casefold() + ' '

                def contains(term):
                    return ' ' + term.casefold() + ' ' in text

                matches = {entry['capability'] for entry in entries
                           if entry['capability'] in candidates
                           and all(any(map(contains, group)) for group in entry['triggers'])
                           and not any(map(contains, entry['excludes']))}
                self.assertEqual(matches, expected)

    def test_distribution_and_upgrade_have_no_external_skill_bodies(self):
        for mode in ('--shared', '--local'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project = root / 'project'
                subprocess.run(['git', 'init', '-q', str(project)], check=True)
                env = dict(os.environ, HOME=str(root / 'home'), CODEX_HOME=str(root / 'codex'))
                subprocess.run(['bash', str(ROOT / 'install-agentic.sh'), mode, str(project)],
                               env=env, check=True, capture_output=True)
                method = project / '.agentic-local' if mode == '--local' else project
                for path in (CATALOG, GUIDE):
                    self.assertEqual((method / path).read_bytes(), (ROOT / path).read_bytes())
                self.assertFalse(any((project / '.agents').glob('skills/*/SKILL.md')))
                self.assertFalse(any((project / '.claude').glob('skills/*/SKILL.md')))
                self.assertFalse(any((root / 'home').rglob('SKILL.md')))
                # Earlier installations never shipped the catalog. The updater adds it.
                (method / CATALOG).unlink()
                subprocess.run([sys.executable, str(ROOT / 'update-agentic.py'), str(project)],
                               check=True, capture_output=True, env=env)
                self.assertEqual((method / CATALOG).read_bytes(), (ROOT / CATALOG).read_bytes())
