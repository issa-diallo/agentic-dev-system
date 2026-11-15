"""#112 S1–S6: Markdown checkpoints, structural validation and safe persistence.

Only disposable repositories are written. The public Markdown template supplies
label spelling; independent semantic checks below require the information in S1.
No test treats the document as instructions or certifies the truth of its claims.
"""
from concurrent.futures import ThreadPoolExecutor
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unicodedata
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / 'scripts/agentic-checkpoint.py'
TEMPLATE = SOURCE / 'docs/agentic/templates/HANDOFF.md'
MAX_BYTES = 2 * 1024 * 1024
MARKER = 'SENSITIVE_FIXTURE_112_DO_NOT_ECHO'
SECTIONS = ('État', 'Résumé', 'Fichiers modifiés', 'Tests exécutés',
            'Écarts au plan', 'Risques connus', 'Points à vérifier par le reviewer',
            'Git', 'Checkpoint de reprise / compaction')
LEGACY_LABELS = (
    'objectif et AC restant à satisfaire',
    'phase, dernier PASS et liens vers artefacts',
    'décisions et raisons, contraintes utilisateur et actions non autorisées',
    'faits confirmés / hypothèses',
    'erreurs ouvertes et blockers réels',
    'prochaine action concrète et lectures ciblées',
    'commandes exactes, environnement, date et emplacement des preuves',
    'mesures observables / métriques indisponibles',
)


def checkpoint_labels():
    checkpoint = TEMPLATE.read_text(encoding='utf-8').split('## ' + SECTIONS[-1], 1)[1]
    return re.findall(r'^- ([^:\n]+?)\s*:', checkpoint, re.M)


def manual_handoff(repo, state='IN_PROGRESS', note=MARKER):
    """Fill the documented schema manually, without using a product generator."""
    values = {
        'État': '`' + state + '`',
        'Résumé': 'Sauvegarde en cours. ' + note,
        'Fichiers modifiés': '- src/example.py : modification locale conservée.',
        'Tests exécutés': ('| Commande | Résultat |\n|---|---|\n'
                           '| python3 -m unittest | non exécuté — travail en cours |'),
        'Écarts au plan': 'Aucun — périmètre validé inchangé.',
        'Risques connus': 'N/A — aucune action distante dans cette fixture.',
        'Points à vérifier par le reviewer': 'Vérifier les AC S1–S6 avant livraison.',
        'Git': (f'- branch : feat/108-validated-handoff\n- worktree : {repo}\n'
                '- commit : inconnu — dépôt de test sans commit\n'
                '- PR : N/A — aucune PR publiée'),
        SECTIONS[-1]: '\n'.join(
            '- ' + label + ' : ' + (
                'inconnu — arrêt non observé, ownership conservé par writer-112.'
                if re.search(r'agent|process|ownership|arrêt', label, re.I)
                else 'Aucun — pas de fait supplémentaire pour cette mission locale.')
            for label in checkpoint_labels()),
    }
    return '# Handoff — #112 sauvegarde validée\n\n' + '\n\n'.join(
        '## ' + section + '\n\n' + values[section] for section in SECTIONS) + '\n'


def load_checkpoint():
    spec = importlib.util.spec_from_file_location('agentic_checkpoint_112', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Support dataclasses as well as ordinary modules without choosing an implementation.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_target(path, dir_fd=None):
    """Technical mock helper: resolve a possibly dir_fd-relative path to an absolute one."""
    path = Path(path)
    if dir_fd is not None and not path.is_absolute():
        return Path(os.readlink(f'/proc/self/fd/{dir_fd}')) / path
    return path


class TemplateContractTests(unittest.TestCase):
    def test_s1_historical_sections_labels_and_three_states_remain_documented(self):
        text = TEMPLATE.read_text(encoding='utf-8')
        headings = re.findall(r'^## (.+)$', text, re.M)
        for section in SECTIONS:
            self.assertEqual(headings.count(section), 1, section)
        for label in LEGACY_LABELS:
            self.assertIn(label, checkpoint_labels())
        for state in ('IN_PROGRESS', 'IMPLEMENTATION_COMPLETE', 'BLOCKED'):
            self.assertIn(state, text)

    def test_s1_checkpoint_labels_cover_continuity_information(self):
        labels = '\n'.join(checkpoint_labels()).casefold()
        normalized = ''.join(char for char in unicodedata.normalize('NFD', labels)
                             if unicodedata.category(char) != 'Mn')
        concepts = {
            'objectif/AC': r'objectif.*ac', 'contraintes utilisateur': r'contraintes utilisateur',
            'décisions/raisons': r'decisions.*raisons', 'pistes rejetées': r'pistes.*rejete',
            'terminé': r'termine|travail fait', 'en cours': r'en cours',
            'restant': r'restant|inacheve', 'non commité': r'non comm?it',
            'tests': r'tests', 'validité des preuves': r'validite.*preuves|preuves.*validite',
            'erreurs': r'erreurs', 'agents': r'agents', 'processus': r'processus',
            'ownership': r'ownership|proprietaire', 'arrêt des écrivains': r'arret',
            'actions externes effectuées': r'actions externes',
            'plan': r'plan', 'PR_SPLIT': r'pr_split', 'hash': r'hash|sha256|empreinte',
            'configuration': r'config', 'prochaine action': r'prochaine action',
            'première commande/lecture': r'premiere.*(commande|lecture)|(commande|lecture).*initiale',
        }
        for concept, pattern in concepts.items():
            with self.subTest(concept=concept):
                self.assertRegex(normalized, pattern)


class CheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCRIPT.is_file():
            raise AssertionError('S2 : scripts/agentic-checkpoint.py reste à implémenter')
        cls.api = load_checkpoint()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='checkpoint-112-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        (self.repo / '.git/info/exclude').write_text('/.agentic-local/\n', encoding='utf-8')
        self.local = self.repo / '.agentic-local'
        self.local.mkdir()
        self.destination = self.local / 'HANDOFF.md'
        self.source = self.root / 'DRAFT.md'
        self.text = manual_handoff(self.repo)
        self.source.write_text(self.text, encoding='utf-8')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    def assert_metadata(self, result, path, content):
        self.assertIsInstance(result, dict)
        self.assertIs(result.get('validated'), True)
        self.assertEqual(result.get('path'), str(path.resolve()))
        self.assertEqual(result.get('sha256'), hashlib.sha256(content).hexdigest())
        self.assertEqual(result.get('size_bytes'), len(content))
        self.assertEqual(result.get('validation'), 'structural')
        self.assertNotIn(MARKER, json.dumps(result))
        self.assertNotIn('content', result)

    def assert_cli_failure(self, result):
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertTrue(output.strip(), 'Un échec doit avoir un diagnostic')
        # Operational bound only; no error wording or private exception type is prescribed.
        self.assertLess(len(output.encode('utf-8')), 16 * 1024)
        self.assertNotIn(MARKER, output)
        self.assertNotIn('# Handoff', output)

    def save(self):
        return self.api.save_checkpoint(self.repo, self.source, self.destination)

    def assert_old_recoverable(self, old):
        candidates = [path for path in self.local.rglob('*')
                      if path.is_file() and not path.is_symlink() and path.read_bytes() == old]
        self.assertTrue(candidates, 'Au moins un ancien checkpoint doit rester exploitable')
        for path in candidates:
            self.assertEqual(self.git('check-ignore', '--', str(path)), str(path))
            self.assertEqual(self.git('ls-files', '--', str(path)), '')
            result = self.api.validate_checkpoint(self.repo, path)
            self.assert_metadata(result, path, old)
        return candidates

    def prepare_replacement(self):
        self.save()
        old = self.destination.read_bytes()
        self.source.write_text(self.text.replace(MARKER, 'version suivante'), encoding='utf-8')
        return old

    def test_s2_api_save_and_validate_return_exact_metadata_without_document(self):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            saved = self.save()
            checked = self.api.validate_checkpoint(
                self.repo, self.destination, expected_sha256=saved['sha256'])
        self.assert_metadata(saved, self.destination, self.text.encode())
        self.assert_metadata(checked, self.destination, self.text.encode())
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())
        self.assertNotIn(MARKER, output.getvalue() + errors.getvalue())

    def test_s2_cli_save_validate_and_hash_failure(self):
        saved = self.cli('save', '--repo', self.repo, '--source', self.source,
                         '--output', self.destination)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assert_metadata(json.loads(saved.stdout), self.destination, self.text.encode())
        checked = self.cli('validate', '--repo', self.repo, '--file', self.destination,
                           '--sha256', hashlib.sha256(self.text.encode()).hexdigest())
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assert_metadata(json.loads(checked.stdout), self.destination, self.text.encode())
        without_hash = self.cli('validate', '--repo', self.repo, '--file', self.destination)
        self.assertEqual(without_hash.returncode, 0, without_hash.stderr)
        self.assert_metadata(json.loads(without_hash.stdout), self.destination, self.text.encode())
        for result in (saved, checked):
            self.assertNotIn(MARKER, result.stdout + result.stderr)
        self.assert_cli_failure(self.cli('validate', '--repo', self.repo,
                                         '--file', self.destination, '--sha256', '0' * 64))

    def test_s2_cli_errors_are_bounded_and_do_not_echo_invalid_document(self):
        for data in (self.text.replace('## Résumé', '## Incomplet').encode(),
                     self.text.encode() + b'\xff', b'X' * (MAX_BYTES + 1) + MARKER.encode()):
            with self.subTest(size=len(data)):
                self.source.write_bytes(data)
                self.assert_cli_failure(self.cli('save', '--repo', self.repo,
                                                 '--source', self.source,
                                                 '--output', self.destination))
                self.assertFalse(self.destination.exists())

    def test_s3_invalid_replacement_preserves_previous_valid_checkpoint(self):
        old = self.prepare_replacement()
        self.source.write_text(self.text.replace('## Résumé', '## Incomplet'), encoding='utf-8')
        self.assert_cli_failure(self.cli('save', '--repo', self.repo, '--source', self.source,
                                         '--output', self.destination))
        self.assertEqual(self.destination.read_bytes(), old)
        self.assert_old_recoverable(old)

    def test_s3_manual_documents_accept_all_historical_and_in_progress_states(self):
        for state in ('IN_PROGRESS', 'IMPLEMENTATION_COMPLETE', 'BLOCKED'):
            with self.subTest(state=state):
                self.source.write_text(manual_handoff(self.repo, state), encoding='utf-8')
                self.assert_metadata(self.save(), self.destination, self.source.read_bytes())

    def test_s3_each_required_section_and_label_is_unique_and_nonempty(self):
        mutations = []
        for section in SECTIONS:
            pattern = r'(?ms)^## ' + re.escape(section) + r'\n.*?(?=^## |\Z)'
            block = re.search(pattern, self.text).group()
            mutations.extend([(section + ' absent', self.text.replace(block, '')),
                              (section + ' vide', self.text.replace(block, '## ' + section + '\n\n')),
                              (section + ' doublé', self.text + '\n' + block)])
        for label in [*checkpoint_labels(), 'branch', 'worktree', 'commit', 'PR']:
            pattern = r'(?m)^- ' + re.escape(label) + r'\s*:.*$'
            line = re.search(pattern, self.text).group()
            mutations.extend([(label + ' absent', self.text.replace(line, '')),
                              (label + ' vide', self.text.replace(line, '- ' + label + ' : ')),
                              (label + ' doublé', self.text.replace(line, line + '\n' + line))])
        for name, invalid in mutations:
            with self.subTest(mutation=name):
                self.destination.write_text(invalid, encoding='utf-8')
                with self.assertRaises(Exception):
                    self.api.validate_checkpoint(self.repo, self.destination)

    def test_s3_template_placeholders_and_unsupported_state_are_rejected(self):
        label = checkpoint_labels()[0]
        pattern = r'(?m)^- ' + re.escape(label) + r'\s*:.*$'
        invalid = [TEMPLATE.read_text(encoding='utf-8'), self.text.replace('`IN_PROGRESS`', '`DONE`')]
        for value in ('…', '...', '<à compléter>', 'TODO', 'Aucun', 'N/A'):
            invalid.append(re.sub(pattern, '- ' + label + ' : ' + value, self.text))
        for document in invalid:
            with self.subTest(document=invalid.index(document)):
                self.destination.write_text(document, encoding='utf-8')
                with self.assertRaises(Exception):
                    self.api.validate_checkpoint(self.repo, self.destination)

    def test_s3_motivated_absence_and_unknown_stop_remain_structural_only(self):
        self.save()
        before = self.destination.read_bytes()
        self.assertIn(b'inconnu', before)
        result = self.api.validate_checkpoint(self.repo, self.destination)
        self.assert_metadata(result, self.destination, before)
        self.assertEqual(self.destination.read_bytes(), before)
        for key in ('resume_authorized', 'stop_confirmed', 'ownership_transferred'):
            self.assertFalse(result.get(key, False), key)
        for key in ('status', 'verdict'):
            self.assertNotEqual(result.get(key), 'PASS', key)

    def test_s3_fenced_headings_and_labels_are_not_parsed_as_structure(self):
        for fence in ('```', '~~~~'):
            fenced = (f'\n{fence}markdown\n## État\n`BLOCKED`\n'
                      f'- {checkpoint_labels()[0]} : faux doublon\n{fence}\n')
            valid = self.text.replace('## Fichiers modifiés', fenced + '\n## Fichiers modifiés')
            self.destination.write_text(valid, encoding='utf-8')
            with self.subTest(fence=fence, valid=True):
                self.assert_metadata(self.api.validate_checkpoint(self.repo, self.destination),
                                     self.destination, valid.encode())
            invalid = valid.replace('## Résumé\n\nSauvegarde en cours. ' + MARKER,
                                    fence + '\n## Résumé\n' + fence)
            self.destination.write_text(invalid, encoding='utf-8')
            with self.subTest(fence=fence, valid=False), self.assertRaises(Exception):
                self.api.validate_checkpoint(self.repo, self.destination)

    def test_s4_validate_is_read_only_and_detects_later_hash_changes(self):
        saved = self.save()
        before = {path: (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns)
                  for path in self.repo.rglob('*') if path.is_file()}
        self.api.validate_checkpoint(self.repo, self.destination, saved['sha256'])
        after = {path: (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns)
                 for path in self.repo.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.destination.write_text(self.text + '\nNouvelle information.\n', encoding='utf-8')
        with self.assertRaises(Exception):
            self.api.validate_checkpoint(self.repo, self.destination, saved['sha256'])

    def test_s4_utf8_byte_limit_accepts_two_mib_and_refuses_one_more_byte(self):
        content = self.text.encode()
        content += b'\n' + b' ' * (MAX_BYTES - len(content) - 1)
        self.source.write_bytes(content)
        self.assert_metadata(self.save(), self.destination, content)
        self.source.write_bytes(content + b' ')
        with self.assertRaises(Exception):
            self.save()
        self.assertEqual(self.destination.read_bytes(), content)
        self.destination.write_bytes(content + b' ')
        with self.assertRaises(Exception):
            self.api.validate_checkpoint(self.repo, self.destination)
        self.destination.write_bytes(self.text.encode() + b'\xff')
        self.assert_cli_failure(self.cli('validate', '--repo', self.repo,
                                         '--file', self.destination))

    def test_s4_nonregular_and_symlink_sources_and_validation_files_are_refused(self):
        link = self.root / 'link.md'
        link.symlink_to(self.source)
        fifo = self.root / 'fifo.md'
        os.mkfifo(fifo)
        for path in (link, fifo, self.root, self.root / 'missing'):
            with self.subTest(path=path.name, action='save'):
                self.assert_cli_failure(self.cli('save', '--repo', self.repo,
                                                 '--source', path, '--output', self.destination))
            with self.subTest(path=path.name, action='validate'):
                self.assert_cli_failure(self.cli('validate', '--repo', self.repo, '--file', path))
        self.assertFalse(self.destination.exists())

    def test_s4_destinations_outside_ignored_local_or_tracked_are_refused(self):
        for path in (self.root / 'outside.md', self.repo / 'HANDOFF.md'):
            with self.subTest(path=path), self.assertRaises(Exception):
                self.api.save_checkpoint(self.repo, self.source, path)
            self.assertFalse(path.exists())
        (self.repo / '.git/info/exclude').write_text('', encoding='utf-8')
        with self.assertRaises(Exception):
            self.save()
        self.assertFalse(self.destination.exists())
        (self.repo / '.git/info/exclude').write_text('/.agentic-local/\n', encoding='utf-8')
        self.destination.write_text(self.text, encoding='utf-8')
        self.git('add', '-f', '.agentic-local/HANDOFF.md')
        before = self.destination.read_bytes()
        with self.assertRaises(Exception):
            self.save()
        self.assertEqual(self.destination.read_bytes(), before)

    def test_s4_effective_ignore_negation_is_respected(self):
        (self.repo / '.gitignore').write_text(
            '!.agentic-local/\n.agentic-local/*\n!.agentic-local/HANDOFF.md\n', encoding='utf-8')
        with self.assertRaises(Exception):
            self.save()
        self.assertFalse(self.destination.exists())

    def test_s4_symlink_destination_and_parent_cannot_escape_local(self):
        outside = self.root / 'sentinel.md'
        outside.write_text('preserved', encoding='utf-8')
        self.destination.symlink_to(outside)
        with self.assertRaises(Exception):
            self.save()
        self.assertEqual(outside.read_text(), 'preserved')
        linked = self.local / 'linked'
        linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(Exception):
            self.api.save_checkpoint(self.repo, self.source, linked / 'new.md')
        self.assertFalse((self.root / 'new.md').exists())

    def test_s4_symlink_local_directory_cannot_redirect_checkpoint_writes(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.local.rmdir()
        self.local.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(Exception):
            self.save()
        self.assertEqual(list(outside.iterdir()), [])

    def test_s4_success_preserves_verified_private_previous_markdown(self):
        old = self.prepare_replacement()
        result = self.save()
        self.assert_metadata(result, self.destination, self.source.read_bytes())
        copies = self.assert_old_recoverable(old)
        self.assertNotIn(self.destination, copies)
        for path in [self.destination, *copies]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_s4_candidate_is_private_synced_and_complete_before_atomic_replace(self):
        old = self.prepare_replacement()
        real_fsync, real_replace = os.fsync, os.replace
        synchronized = set()
        promoted = []

        def sync(fd):
            real_fsync(fd)
            metadata = os.fstat(fd)
            synchronized.add((metadata.st_dev, metadata.st_ino))

        def replace(source, destination, *args, **kwargs):
            if resolve_target(destination, kwargs.get('dst_dir_fd')) == self.destination:
                candidate = resolve_target(source, kwargs.get('src_dir_fd'))
                metadata = candidate.stat()
                self.assertTrue(candidate.is_relative_to(self.local))
                self.assertFalse(candidate.is_symlink())
                self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
                self.assertEqual(candidate.read_bytes(), self.source.read_bytes())
                self.assertIn((metadata.st_dev, metadata.st_ino), synchronized)
                self.assertEqual(self.destination.read_bytes(), old)
                promoted.append(candidate)
            return real_replace(source, destination, *args, **kwargs)

        with mock.patch.object(os, 'fsync', side_effect=sync), \
                mock.patch.object(os, 'replace', side_effect=replace):
            self.save()
        self.assertEqual(len(promoted), 1)

    def test_s4_sync_and_replace_errors_preserve_a_valid_previous_path(self):
        old = self.prepare_replacement()
        # Fail each reached syscall, including late directory synchronization.
        # Fresh subdirectories isolate the attempts and their backup files.
        for operation in ('fsync', 'replace'):
            real = getattr(os, operation)
            for fail_at in range(1, 7):
                directory = self.local / f'{operation}-{fail_at}'
                directory.mkdir()
                destination = directory / 'HANDOFF.md'
                destination.write_bytes(old)
                count = 0

                def injected(*args, **kwargs):
                    nonlocal count
                    count += 1
                    if count == fail_at:
                        raise OSError('injected storage failure')
                    return real(*args, **kwargs)

                with self.subTest(operation=operation, fail_at=fail_at):
                    with mock.patch.object(os, operation, side_effect=injected):
                        try:
                            result = self.api.save_checkpoint(self.repo, self.source, destination)
                        except Exception:
                            result = None
                    if count >= fail_at:
                        self.assertIsNone(result, 'Une erreur de persistance ne peut annoncer un succès')
                        paths = [p for p in directory.rglob('*')
                                 if p.is_file() and not p.is_symlink() and p.read_bytes() == old]
                        self.assertTrue(paths, 'Checkpoint précédent perdu après erreur')
                        self.api.validate_checkpoint(self.repo, paths[0])
                    else:
                        self.assert_metadata(result, destination, self.source.read_bytes())

    def test_s4_write_error_preserves_previous_checkpoint(self):
        old = self.prepare_replacement()
        # RLIMIT_FSIZE injects an actual write failure regardless of the I/O wrapper used.
        worker = '''import importlib.util, resource, signal, sys
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
spec = importlib.util.spec_from_file_location('checkpoint_worker', sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
try:
    module.save_checkpoint(*sys.argv[2:])
except Exception:
    print('write failed')
    sys.exit(1)
sys.exit(0)
'''
        result = subprocess.run([sys.executable, '-c', worker, str(SCRIPT), str(self.repo),
                                 str(self.source), str(self.destination)],
                                capture_output=True, text=True, timeout=10)
        self.assert_cli_failure(result)
        self.assert_old_recoverable(old)

    def test_s4_corrupt_candidate_is_rejected_before_promotion(self):
        old = self.prepare_replacement()
        real_sync = os.fsync
        corrupted = []

        def corrupt(fd):
            real_sync(fd)
            target = Path(os.readlink(f'/proc/self/fd/{fd}'))
            if target.is_file() and target.read_bytes() == self.source.read_bytes():
                with target.open('r+b') as stream:
                    stream.write(b'BROKEN')
                corrupted.append(target)

        with mock.patch.object(os, 'fsync', side_effect=corrupt), self.assertRaises(Exception):
            self.save()
        self.assertTrue(corrupted, 'Injection non atteinte')
        self.assertEqual(self.destination.read_bytes(), old)

    def test_s4_final_reread_failure_never_reports_success_and_keeps_backup(self):
        old = self.prepare_replacement()
        real_replace = os.replace
        promoted = []

        def corrupt(source, destination, *args, **kwargs):
            result = real_replace(source, destination, *args, **kwargs)
            if resolve_target(destination, kwargs.get('dst_dir_fd')) == self.destination:
                self.destination.write_bytes(b'corrupted after promotion')
                promoted.append(True)
            return result

        with mock.patch.object(os, 'replace', side_effect=corrupt), self.assertRaises(Exception):
            self.save()
        self.assertTrue(promoted, 'Injection non atteinte')
        self.assert_old_recoverable(old)

    def test_s4_corrupt_previous_copy_is_detected_before_replacing_checkpoint(self):
        old = self.prepare_replacement()
        real_sync = os.fsync
        corrupted = []

        def corrupt(fd):
            real_sync(fd)
            target = Path(os.readlink(f'/proc/self/fd/{fd}'))
            if target != self.destination and target.is_file() and target.read_bytes() == old:
                with target.open('r+b') as stream:
                    stream.write(b'BROKEN')
                corrupted.append(target)

        with mock.patch.object(os, 'fsync', side_effect=corrupt), self.assertRaises(Exception):
            self.save()
        self.assertTrue(corrupted, 'Copie précédente synchronisée non observée')
        self.assertEqual(self.destination.read_bytes(), old)

    def test_s4_previous_copy_remains_private_when_git_rules_expose_an_older_backup(self):
        old = self.prepare_replacement()
        self.save()
        backup = self.assert_old_recoverable(old)[0]
        # The implementation may refuse or select another safe previous path.
        relative = backup.relative_to(self.repo)
        rules = ['!/.agentic-local/', '/.agentic-local/**']
        rules.extend('!/' + parent.as_posix() + '/' for parent in reversed(relative.parents)
                     if parent.as_posix() not in ('.', '.agentic-local'))
        rules.append('!/' + relative.as_posix())
        (self.repo / '.gitignore').write_text('\n'.join(rules) + '\n', encoding='utf-8')
        exposed = subprocess.run(['git', '-C', str(self.repo), 'check-ignore', '-q', '--', str(backup)],
                                 capture_output=True)
        self.assertEqual(exposed.returncode, 1, 'La fixture doit exposer le précédent chemin')
        current = self.destination.read_bytes()
        self.source.write_text(self.text.replace(MARKER, 'troisième version'), encoding='utf-8')
        try:
            result = self.save()
        except Exception:
            self.assertEqual(self.destination.read_bytes(), current)
        else:
            self.assert_metadata(result, self.destination, self.source.read_bytes())
            self.assert_old_recoverable(current)

    def test_s4_concurrent_saves_do_not_promote_inside_another_save(self):
        old = self.prepare_replacement()
        second_source = self.root / 'SECOND.md'
        second_source.write_text(self.text.replace(MARKER, 'autre version'), encoding='utf-8')
        entered, release = threading.Event(), threading.Event()
        second_started = threading.Event()
        second_finished = threading.Event()
        real_replace = os.replace

        def replace(source, destination, *args, **kwargs):
            if resolve_target(destination, kwargs.get('dst_dir_fd')) == self.destination:
                if threading.current_thread().name.startswith('checkpoint-first'):
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError('Test synchronization timeout')
            return real_replace(source, destination, *args, **kwargs)

        def second_save():
            second_started.set()
            try:
                # An independent interpreter exercises the process boundary of the lock.
                return self.cli('save', '--repo', self.repo, '--source', second_source,
                                '--output', self.destination)
            finally:
                second_finished.set()

        with mock.patch.object(os, 'replace', side_effect=replace):
            with ThreadPoolExecutor(1, thread_name_prefix='checkpoint-first') as first_pool, \
                    ThreadPoolExecutor(1, thread_name_prefix='checkpoint-second') as second_pool:
                first = first_pool.submit(self.save)
                try:
                    self.assertTrue(entered.wait(5), 'Premier save non arrivé à la promotion')
                    second = second_pool.submit(second_save)
                    self.assertTrue(second_started.wait(5))
                    second_finished.wait(0.5)
                    self.assertEqual(self.destination.read_bytes(), old,
                                     'Un autre processus a promu sans le verrou exclusif')
                finally:
                    release.set()
                self.assert_metadata(first.result(timeout=5), self.destination,
                                     self.source.read_bytes())
                result = second.result(timeout=5)
                if result.returncode == 0:
                    self.assert_metadata(json.loads(result.stdout), self.destination,
                                         second_source.read_bytes())
                    expected = second_source.read_bytes()
                else:
                    # Fail-fast lock contention is allowed; no retry policy is prescribed.
                    self.assert_cli_failure(result)
                    expected = self.source.read_bytes()
                self.assertEqual(self.destination.read_bytes(), expected)
                self.api.validate_checkpoint(self.repo, self.destination)
        previous = self.source.read_bytes() if result.returncode == 0 else old
        self.assert_old_recoverable(previous)

    def test_s5_save_does_not_execute_document_or_change_git_product_or_credentials(self):
        product = self.repo / 'product.py'
        product.write_text('pending user change\n', encoding='utf-8')
        credentials = self.repo / '.codex/auth.json'
        credentials.parent.mkdir()
        credentials.write_text('synthetic credentials fixture\n', encoding='utf-8')
        marker = self.root / 'COMMAND_MUST_NOT_RUN'
        self.source.write_text(self.text + f'\n```sh\ntouch {marker}\n```\n', encoding='utf-8')
        status = self.git('status', '--porcelain=v1')
        git_before = {p: p.read_bytes() for p in (self.repo / '.git').rglob('*') if p.is_file()}
        real_io_open, real_open = io.open, open

        def check_open(real, path, *args, **kwargs):
            if not isinstance(path, int):
                self.assertNotEqual(Path(path).resolve(), credentials.resolve(),
                                    'Le checkpoint ne doit pas lire des credentials')
            return real(path, *args, **kwargs)

        with mock.patch('builtins.open', side_effect=lambda *a, **kw: check_open(real_open, *a, **kw)), \
                mock.patch.object(io, 'open', side_effect=lambda *a, **kw: check_open(real_io_open, *a, **kw)), \
                mock.patch.object(os, 'system', side_effect=AssertionError('Commande du document')):
            self.save()
            self.api.validate_checkpoint(self.repo, self.destination)
        self.assertFalse(marker.exists())
        self.assertEqual(product.read_text(), 'pending user change\n')
        self.assertEqual(credentials.read_text(), 'synthetic credentials fixture\n')
        self.assertEqual(self.git('status', '--porcelain=v1'), status)
        git_after = {p: p.read_bytes() for p in (self.repo / '.git').rglob('*') if p.is_file()}
        self.assertEqual(git_before, git_after)


class DistributionTests(unittest.TestCase):
    def install(self, source, root):
        repo = root / 'target'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        codex_home = root / 'private-codex-home'
        codex_home.mkdir()
        environment = {**os.environ, 'CODEX_HOME': str(codex_home), 'PYTHONDONTWRITEBYTECODE': '1'}
        before = {path.relative_to(repo): path.read_bytes()
                  for path in repo.rglob('*') if path.is_file()}
        result = subprocess.run(['bash', str(source / 'install-agentic.sh'), '--local', str(repo)],
                                capture_output=True, text=True, env=environment, timeout=30)
        return repo, result, before

    def test_s6_local_install_distributes_checkpoint_and_presence_check_requires_it(self):
        with tempfile.TemporaryDirectory(prefix='checkpoint-install-112-') as temporary:
            root = Path(temporary)
            repo, result, _ = self.install(SOURCE, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            local = repo / '.agentic-local'
            installed = local / 'scripts/agentic-checkpoint.py'
            self.assertTrue(installed.is_file(), 'S6 : checkpoint absent de la distribution LOCAL')
            self.assertEqual(installed.read_bytes(), SCRIPT.read_bytes())
            check = ['bash', 'scripts/agentic-check.sh', '--existing']
            passed = subprocess.run(check, cwd=local, capture_output=True, text=True, timeout=10)
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            draft = root / 'DRAFT.md'
            draft.write_text(manual_handoff(repo), encoding='utf-8')
            destination = local / 'docs/agentic/work/112/HANDOFF.md'
            destination.parent.mkdir(parents=True)
            saved = subprocess.run([sys.executable, str(installed), 'save', '--repo', str(repo),
                                    '--source', str(draft), '--output', str(destination)],
                                   capture_output=True, text=True, timeout=10)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertTrue(json.loads(saved.stdout)['validated'])
            installed.unlink()
            failed = subprocess.run(check, cwd=local, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('scripts/agentic-checkpoint.py', failed.stdout + failed.stderr)

    def test_s6_missing_checkpoint_source_is_refused_before_installation_writes(self):
        with tempfile.TemporaryDirectory(prefix='checkpoint-preflight-112-') as temporary:
            root = Path(temporary)
            source = root / 'source'
            shutil.copytree(SOURCE, source, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            script = source / 'scripts/agentic-checkpoint.py'
            if script.exists():
                script.unlink()
            repo, result, before = self.install(source, root)
            self.assertNotEqual(result.returncode, 0, 'S6 : source manquante acceptée')
            self.assertIn('scripts/agentic-checkpoint.py', result.stdout + result.stderr)
            self.assertFalse((repo / '.agentic-local').exists())
            self.assertFalse((repo / '.codex').exists())
            self.assertFalse((repo / '.claude').exists())
            after = {path.relative_to(repo): path.read_bytes()
                     for path in repo.rglob('*') if path.is_file()}
            self.assertEqual(before, after)


class ReviewFindingRegressionTests(unittest.TestCase):
    """Review findings: directory-fd confinement (Major) and private backups (Minor)."""
    @classmethod
    def setUpClass(cls):
        cls.api = load_checkpoint()

    setUp = CheckpointTests.setUp
    git = CheckpointTests.git
    save = CheckpointTests.save
    prepare_replacement = CheckpointTests.prepare_replacement
    assert_metadata = CheckpointTests.assert_metadata

    def test_major_parent_swapped_for_symlink_after_checks_never_writes_outside(self):
        outside = self.root / 'outside'
        outside.mkdir()
        parent = self.local / 'sub'
        parent.mkdir()
        destination = parent / 'HANDOFF.md'
        real_open = os.open
        swapped = []

        def racing_open(path, flags, *args, **kwargs):
            # First temporary candidate creation: swap the checked parent for a link.
            if (flags & os.O_EXCL) and '.tmp-' in str(path) and not swapped:
                swapped.append(True)
                parent.rename(self.local / 'sub-moved')
                parent.symlink_to(outside, target_is_directory=True)
            return real_open(path, flags, *args, **kwargs)

        result = None
        with mock.patch.object(os, 'open', side_effect=racing_open):
            try:
                result = self.api.save_checkpoint(self.repo, self.source, destination)
            except Exception:
                pass
        self.assertTrue(swapped, 'Injection non atteinte')
        self.assertEqual(list(outside.iterdir()), [], 'Écriture hors .agentic-local via lien')
        self.assertIsNone(result, 'Succès annoncé alors que le parent a changé')

    def test_major_parent_swapped_at_final_replace_never_overwrites_outside(self):
        outside = self.root / 'outside-final'
        outside.mkdir()
        sentinel = outside / 'HANDOFF.md'
        sentinel.write_bytes(b'outside sentinel')
        parent = self.local / 'final-sub'
        parent.mkdir()
        destination = parent / 'HANDOFF.md'
        destination.write_bytes(self.source.read_bytes() + b'\nancien\n')
        real_replace = os.replace
        swapped = []

        def racing_replace(source, target, *args, **kwargs):
            if Path(target).name == 'HANDOFF.md' and not swapped:
                swapped.append(True)
                # Homonymous candidate outside, then swap the checked parent for a link.
                shutil.copyfile(self.source, outside / Path(source).name)
                parent.rename(self.local / 'final-sub-moved')
                parent.symlink_to(outside, target_is_directory=True)
            return real_replace(source, target, *args, **kwargs)

        result = None
        with mock.patch.object(os, 'replace', side_effect=racing_replace):
            try:
                result = self.api.save_checkpoint(self.repo, self.source, destination)
            except Exception:
                pass
        self.assertTrue(swapped, 'Injection non atteinte')
        self.assertEqual(sentinel.read_bytes(), b'outside sentinel',
                         'Écrasement hors .agentic-local via promotion finale')
        self.assertIsNone(result, 'Succès annoncé alors que le parent a changé')

    def test_minor_existing_backup_with_same_bytes_is_made_private(self):
        old = self.prepare_replacement()
        self.save()
        backups = [p for p in self.local.glob('HANDOFF.previous-*.md') if p.read_bytes() == old]
        self.assertEqual(len(backups), 1)
        backups[0].chmod(0o644)
        # Current checkpoint returns to the backed-up bytes: the same backup name is reused.
        self.destination.write_bytes(old)
        self.source.write_text(self.text.replace(MARKER, 'troisième'), encoding='utf-8')
        current = self.destination.read_bytes()
        try:
            self.save()
        except Exception:
            pass
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.assertEqual(backups[0].read_bytes(), old)
        self.assertIn(self.destination.read_bytes(), (current, self.source.read_bytes()))

    def linked_worktree(self):
        """Linked worktree under .agentic-local, with a tracked README.md."""
        identity = ('-c', 'user.name=t', '-c', 'user.email=t@example.invalid')
        self.git(*identity, 'commit', '-q', '--allow-empty', '-m', 'init')
        nested = self.local / 'worktrees' / 'x'
        self.git('worktree', 'add', '-q', '-b', 'x', str(nested))
        (nested / 'README.md').write_text('suivi\n', encoding='utf-8')
        subprocess.run(['git', '-C', str(nested), 'add', 'README.md'], check=True)
        subprocess.run(['git', '-C', str(nested), *identity, 'commit', '-q', '-m', 'readme'],
                       check=True, capture_output=True)
        return nested

    def porcelain(self, repo):
        return subprocess.run(['git', '-C', str(repo), 'status', '--porcelain'], check=True,
                              capture_output=True, text=True).stdout

    def test_major_destination_in_linked_worktree_is_refused_untouched(self):
        nested = self.linked_worktree()
        before = (nested / 'README.md').read_bytes()
        with self.assertRaises(self.api.CheckpointError):
            self.api.save_checkpoint(self.repo, self.source, nested / 'README.md')
        self.assertEqual((nested / 'README.md').read_bytes(), before)
        self.assertEqual(self.porcelain(nested), '')

    def test_major_new_destinations_in_linked_worktree_are_refused(self):
        nested = self.linked_worktree()
        for destination in (nested / 'HANDOFF.md', nested / 'new-dir' / 'HANDOFF.md'):
            with self.subTest(destination=destination.relative_to(nested)):
                with self.assertRaises(self.api.CheckpointError) as caught:
                    self.api.save_checkpoint(self.repo, self.source, destination)
                self.assertNotIn(MARKER, str(caught.exception))
                self.assertFalse((nested / 'new-dir').exists())
                self.assertEqual(self.porcelain(nested), '')

    def test_major_destination_in_nested_repository_is_refused(self):
        other = self.local / 'other'
        other.mkdir()
        subprocess.run(['git', '-C', str(other), 'init', '-q'], check=True)
        with self.assertRaises(self.api.CheckpointError):
            self.api.save_checkpoint(self.repo, self.source, other / 'HANDOFF.md')
        self.assertEqual([p.name for p in other.iterdir()], ['.git'])

    def test_linked_worktree_as_repo_still_accepts_its_own_local_dir(self):
        nested = self.linked_worktree()
        destination = nested / '.agentic-local' / 'HANDOFF.md'
        result = self.api.save_checkpoint(nested, self.source, destination)
        self.assert_metadata(result, destination, self.source.read_bytes())

    def bare_repository(self):
        bare = self.local / 'bare.git'
        subprocess.run(['git', 'init', '-q', '--bare', str(bare)], check=True)
        return bare

    def test_major_existing_file_in_nested_bare_repository_is_preserved(self):
        bare = self.bare_repository()
        before = (bare / 'config').read_bytes()
        entries = sorted(p.name for p in bare.iterdir())
        with self.assertRaises(self.api.CheckpointError):
            self.api.save_checkpoint(self.repo, self.source, bare / 'config')
        self.assertEqual((bare / 'config').read_bytes(), before)
        self.assertEqual(sorted(p.name for p in bare.iterdir()), entries)
        subprocess.run(['git', f'--git-dir={bare}', 'config', '--list'], check=True,
                       capture_output=True)

    def test_major_new_destination_in_nested_bare_repository_is_refused(self):
        bare = self.bare_repository()
        entries = sorted(p.name for p in bare.iterdir())
        for destination in (bare / 'HANDOFF.md', bare / 'notes' / 'HANDOFF.md'):
            with self.subTest(destination=destination.relative_to(bare)):
                with self.assertRaises(self.api.CheckpointError):
                    self.api.save_checkpoint(self.repo, self.source, destination)
                self.assertEqual(sorted(p.name for p in bare.iterdir()), entries)

    def test_directory_with_only_head_file_is_still_accepted(self):
        plain = self.local / 'plain'
        plain.mkdir()
        (plain / 'HEAD').write_text('simple fichier\n', encoding='utf-8')
        destination = plain / 'HANDOFF.md'
        result = self.api.save_checkpoint(self.repo, self.source, destination)
        self.assert_metadata(result, destination, self.source.read_bytes())


if __name__ == '__main__':
    unittest.main()
