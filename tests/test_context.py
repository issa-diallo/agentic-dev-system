"""Portable instruction contracts and real generations; no model execution."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

SOURCE = Path(__file__).resolve().parents[1]


def required_resources():
    docs = 'README METHOD WORKFLOW SCALING SAFETY EXISTING_PROJECT INSTALL LOCAL BOOTSTRAP CONTEXT MODELS OPTIONAL_TOOLS DEVELOPMENT PULL_REQUESTS'.split()
    return (['AGENTS.md', 'COMMITS.md', 'scripts/agentic-check.sh']
            + [f'docs/agentic/{name}.md' for name in docs]
            + [str(path.relative_to(SOURCE)) for folder in ['templates', 'roles']
               for path in sorted((SOURCE/'docs/agentic'/folder).glob('*.md'))])


def broken_links(root):
    errors = []
    for path in root.rglob('*.md'):
        if '.git' in path.parts:
            continue
        # Ignore fenced examples. Check Markdown inline local file destinations.
        text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
        for dest in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text):
            dest = dest.strip('<>')
            if urlsplit(dest).scheme or dest.startswith('#'):
                continue
            target = unquote(dest.split('#')[0])
            if target and not (path.parent / target).exists():
                errors.append(f'{path.relative_to(root)} -> {dest}')
    return errors


class ContextTests(unittest.TestCase):
    def test_source_links(self):
        self.assertEqual(broken_links(SOURCE), [])

    def test_root_invariants_and_size(self):
        text = (SOURCE / 'AGENTS.md').read_text()
        # Includes the native communication policy; remains below the 8,764-byte baseline.
        self.assertLess(len(text.encode()), 5400)
        for rule in ['Research/Design/Plan PASS', 'Verify obligatoire', 'review indépendante',
                     'Critical/Major', 'merge et cleanup', 'READY_FOR_HUMAN',
                     'BLOCKED, ADR et ARCHITECTURE', 'Fixes #<issue_number>',
                     'dépendance structurante échoue', 'secrets', 'tenant', 'rollback']:
            self.assertIn(rule, text)
        phases = 'PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Worktree Setup -> Execute -> Verify -> Review -> Goal -> Ship'
        self.assertIn(phases, text)
        self.assertIn(phases, (SOURCE/'docs/agentic/WORKFLOW.md').read_text())
        context = (SOURCE / 'docs/agentic/CONTEXT.md').read_text()
        self.assertEqual(re.findall(r'^\| (\d\d) \|', context, re.M), [f'{n:02}' for n in range(1, 27)])

    def test_progressive_architecture_contract(self):
        architecture = (SOURCE/'docs/agentic/templates/ARCHITECTURE.md').read_text()
        method = (SOURCE/'docs/agentic/METHOD.md').read_text()
        workflow = (SOURCE/'docs/agentic/WORKFLOW.md').read_text()
        orchestrator = (SOURCE/'docs/agentic/roles/ORCHESTRATOR.md').read_text()
        for word in ['Décisions reportées', 'BLOQUANT MAINTENANT',
                     'AVANT STORY', 'NON BLOQUANT', 'Déclencheur / story',
                     'sources', 'Architecture Gate']:
            self.assertIn(word, architecture)
        self.assertNotIn('stack complète sélectionnée', architecture)
        self.assertIn('difficilement réversible', method)
        self.assertIn('aucune décision différée requise', workflow)
        self.assertIn('trois options', orchestrator)

    def test_native_communication_contract(self):
        text = (SOURCE/'AGENTS.md').read_text()
        policy = text.split('## Communication commune à tous les agents', 1)[1]
        labels = re.findall(r'\*\*([^*]+) :\*\*', policy)
        self.assertEqual(labels, ['Résultat', 'Modifications', 'Validation',
                                  'Attention', 'Prochaine étape'])
        for obligation in ['résultat ou la réponse principale', 'Phrases courtes',
                           'ne pas recopier', 'chemins', 'erreurs pertinentes',
                           'blocages, risques, incertitudes et validations manquantes',
                           'étapes internes', 'sections vides omises',
                           'Instructions prioritaires', 'formats spécifiques PRD → Ship',
                           'Exactitude, sécurité, qualité et complétude',
                           'rapports techniques et', 'métier restent complets']:
            self.assertIn(obligation, policy)
        context = (SOURCE/'docs/agentic/CONTEXT.md').read_text()
        for safeguard in ['retours des sous-agents', 'ne remplace ni un artefact',
                          'PASS non prouvé', 'non exécuté', 'Aucun de ces outils']:
            self.assertIn(safeguard, context)

    def test_lead_tech_review_contract(self):
        role = (SOURCE/'docs/agentic/roles/REVIEWER.md').read_text()
        for rule in ['Profil Lead Tech', 'STANDARD/LARGE', 'LIGHT',
                     "distinct de l'implementer et du premier reviewer",
                     'Extra High', 'SHA de base et de tête', 'CI en attente/échec',
                     'BLOCKED', 'verdict précédent périmé', 'sans autorisation explicite',
                     'lead-tech-review.md', 'sans nouveau commit',
                     'ne lancent pas un service autonome']:
            self.assertIn(rule, role)
        review = (SOURCE/'docs/agentic/templates/REVIEW.md').read_text()
        ship = (SOURCE/'docs/agentic/templates/SHIP.md').read_text()
        self.assertIn('SHA base, SHA tête examinés', review)
        self.assertIn('Examen final Lead Tech', ship)
        self.assertIn('identiques à la PR actuelle', ship)
        self.assertIn('profil Lead Tech', (SOURCE/'AGENTS.md').read_text())
        self.assertEqual({p.stem for p in (SOURCE/'docs/agentic/roles').glob('*.md')},
                         {'ORCHESTRATOR', 'IMPLEMENTER', 'REVIEWER'})

    def test_all_modes_and_project_sizes(self):
        for mode in ['PRODUCT', 'EXISTING', 'LOCAL']:
            for scale in ['LIGHT', 'LARGE']:
                with self.subTest(mode=mode, scale=scale), tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
                    custom = repo / 'apps/api/AGENTS.md'
                    custom.parent.mkdir(parents=True)
                    custom.write_text('API contract: validate tenant; run api tests.\n')
                    if scale == 'LARGE':
                        web = repo / 'apps/web/AGENTS.md'
                        web.parent.mkdir(parents=True)
                        web.write_text('Web contract: consume stable API; run browser tests.\n')
                    args = [] if mode == 'PRODUCT' else ['--' + mode.lower()]
                    subprocess.run(['bash', str(SOURCE/'install-agentic.sh'), *args, str(repo)], check=True, capture_output=True)
                    dest = repo / '.agentic-local' if mode == 'LOCAL' else repo
                    self.assertEqual(broken_links(dest), [])
                    status = dest / 'docs/agentic/STATUS.md'
                    self.assertEqual(status.read_bytes(), (SOURCE/'docs/agentic/templates/STATUS.md').read_bytes())
                    status.write_text(status.read_text().replace('Selected mode: TODO', f'Selected mode: {scale}'))
                    self.assertIn(f'Selected mode: {scale}', status.read_text())
                    self.assertEqual(custom.read_text(), 'API contract: validate tenant; run api tests.\n')
                    if scale == 'LARGE':
                        self.assertEqual(web.read_text(), 'Web contract: consume stable API; run browser tests.\n')
                    for name in required_resources():
                        self.assertEqual((dest/name).read_bytes(), (SOURCE/name).read_bytes(), name)
                    self.assertEqual(list((dest/'docs/agentic/work').iterdir()), [])
                    self.assertFalse((dest/'.codex').exists())
                    self.assertFalse((dest/'node_modules').exists())
                    for forbidden in ['.headroom', '.mcp.json', 'package.json', 'requirements.txt']:
                        self.assertFalse((dest/forbidden).exists())
                    check = ['bash', 'scripts/agentic-check.sh'] + ([] if mode == 'PRODUCT' else ['--existing'])
                    result = subprocess.run(check, cwd=dest, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                    self.assertIn('phase gates require review', result.stdout)
                    (dest/'docs/agentic/MODELS.md').unlink()
                    self.assertNotEqual(subprocess.run(check, cwd=dest, capture_output=True).returncode, 0)

    def test_missing_sources_refused_before_writes(self):
        # Independent inventory: no derivation from either shell implementation.
        resources = required_resources()
        for missing in resources:
            for mode in ['PRODUCT', 'EXISTING', 'LOCAL']:
                with self.subTest(missing=missing, mode=mode), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    source = root/'source'
                    shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('.git', '__pycache__'))
                    (source/missing).unlink()
                    target = root/'target'
                    target.mkdir()
                    subprocess.run(['git', 'init', '-q', str(target)], check=True)
                    before = {str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()}
                    args=[] if mode=='PRODUCT' else ['--'+mode.lower()]
                    result=subprocess.run(['bash', str(source/'install-agentic.sh'), *args, str(target)], capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    after={str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()}
                    self.assertEqual(before, after)
                    self.assertFalse((target/'docs').exists())
                    self.assertFalse((target/'.agentic-local').exists())

    def test_required_resource_lists_match_independent_inventory(self):
        expected = set(required_resources())
        for file, marker, actual_expected in [
            ('install-agentic.sh', 'for source in ', expected),
            ('scripts/agentic-check.sh', 'for resource in ',
             expected - {'scripts/agentic-check.sh'} | {'docs/agentic/STATUS.md'})]:
            block = (SOURCE/file).read_text().split(marker, 1)[1].split('; do', 1)[0]
            self.assertEqual(set(block.replace(chr(92), '').split()), actual_expected)

    def test_local_generated_status_is_checked_without_source_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'source'
            shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            (source/'docs/agentic/STATUS.md').unlink()
            target = Path(tmp)/'target'
            target.mkdir()
            subprocess.run(['git', 'init', '-q', str(target)], check=True)
            (target/'.gitignore').write_text(
                '!.agentic-local/\n.agentic-local/*\n'
                '!.agentic-local/docs/\n.agentic-local/docs/*\n'
                '!.agentic-local/docs/agentic/\n.agentic-local/docs/agentic/*\n'
                '!.agentic-local/docs/agentic/STATUS.md\n')
            exclude = target/'.git/info/exclude'
            exclude.write_text('original without newline')
            before = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            result = subprocess.run(['bash', str(source/'install-agentic.sh'), '--local', str(target)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Team ignore rules expose local files', result.stderr)
            after = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertFalse((target/'.agentic-local').exists())
            # Absence of source STATUS itself is supported: only the template is needed.
            (target/'.gitignore').write_text('')
            subprocess.run(['bash', str(source/'install-agentic.sh'), '--local', str(target)], check=True, capture_output=True)
            self.assertEqual((target/'.agentic-local/docs/agentic/STATUS.md').read_bytes(),
                             (source/'docs/agentic/templates/STATUS.md').read_bytes())

    def test_source_status_never_inherited(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source'
            shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            (source/'docs/agentic/STATUS.md').write_text('SOURCE PRIVATE STORY PASS\n')
            target=Path(tmp)/'target'; target.mkdir()
            subprocess.run(['bash', str(source/'install-agentic.sh'), str(target)], check=True, capture_output=True)
            self.assertNotIn('SOURCE PRIVATE', (target/'docs/agentic/STATUS.md').read_text())
            self.assertNotEqual((target/'docs/product/PRD.md').read_bytes(), (SOURCE/'docs/product/PRD.md').read_bytes())


if __name__ == '__main__':
    unittest.main()
