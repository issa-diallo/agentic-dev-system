#!/usr/bin/env python3
"""Save and validate a HANDOFF.md checkpoint (structural validation only).

The document is data: it is never executed, and its claims (tests, stopped
agents, ownership) are neither verified nor turned into authorization to resume.
Validation checks sections, labels and placeholders; it is not a secret
scanner and does not detect every sensitive value.
Only HANDOFF Markdown is read and written; no Git state, product file, process
or credential is touched.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import unicodedata

MAX_BYTES = 2 * 1024 * 1024
LOCAL_DIR = '.agentic-local'
STATES = ('IN_PROGRESS', 'IMPLEMENTATION_COMPLETE', 'BLOCKED')
STATE_SECTION = 'État'
GIT_SECTION = 'Git'
CHECKPOINT_SECTION = 'Checkpoint de reprise / compaction'
SECTIONS = (STATE_SECTION, 'Résumé', 'Fichiers modifiés', 'Tests exécutés',
            'Écarts au plan', 'Risques connus', 'Points à vérifier par le reviewer',
            GIT_SECTION, CHECKPOINT_SECTION)
GIT_LABELS = ('branch', 'worktree', 'commit', 'PR')
CHECKPOINT_LABELS = (
    'objectif et AC restant à satisfaire',
    'phase, dernier PASS et liens vers artefacts',
    'décisions et raisons, contraintes utilisateur et actions non autorisées',
    'pistes rejetées et raisons',
    'travail terminé, en cours et restant',
    'changements non commités',
    'tests exécutés et validité des preuves',
    'faits confirmés / hypothèses',
    'erreurs ouvertes et blockers réels',
    'agents, processus et ownership, arrêt confirmé ou inconnu',
    'actions externes déjà effectuées',
    'plan, PR_SPLIT, hash et configuration',
    'prochaine action concrète et lectures ciblées',
    'première commande ou lecture à la reprise',
    'commandes exactes, environnement, date et emplacement des preuves',
    'mesures observables / métriques indisponibles',
)
SECTION_LABELS = {GIT_SECTION: GIT_LABELS, CHECKPOINT_SECTION: CHECKPOINT_LABELS}
PLACEHOLDERS = {'', '…', '...', 'todo', 'tbd', 'aucun', 'aucune', 'n/a', 'na', 'none',
                'néant', 'à compléter', 'a completer', 'aucun / liste'}
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
HEADING = re.compile(r'^## +(.+?)\s*$')
LABEL = re.compile(r'^- ([^:\n]+?)\s*:\s*(.*)$')
ANGLE = re.compile(r'<(?!https?://|mailto:)[^\W\d_][^<>\n]{0,80}>')
MAX_MESSAGE = 600


class CheckpointError(Exception):
    """Failure with a diagnostic that never contains document content."""


def _norm(text):
    return unicodedata.normalize('NFC', text)


def _placeholder(value):
    cleaned = re.sub(r'^[\s\-*•|]+', '', value.strip().strip('`').strip())
    cleaned = cleaned.strip('`|').strip().rstrip('.').strip().casefold()
    return cleaned in PLACEHOLDERS or not cleaned.strip('-*•|…. ')


def _read_regular(path, what, dir_fd=None):
    """Read a regular, non-symlink file of at most MAX_BYTES bytes.

    With dir_fd, PATH is a bare name resolved inside that verified directory."""
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=dir_fd)
    except OSError as error:
        raise CheckpointError(f'{what} illisible : {error.strerror}') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise CheckpointError(f'{what} : fichier régulier requis')
        chunks, total = [], 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise CheckpointError(f'{what} : taille supérieure à {MAX_BYTES} octets')
            chunks.append(chunk)
        return b''.join(chunks)
    except OSError as error:
        raise CheckpointError(f'{what} illisible : {error.strerror}') from None
    finally:
        os.close(fd)


def _parse(text):
    """Return {section: [bodies]} and non-fenced lines, ignoring fenced blocks."""
    sections, outside = {}, []
    current, fence = None, None
    for line in text.split('\n'):
        marker = FENCE.match(line)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence) \
                    and not marker.group(2).strip():
                fence = None
            if current is not None:
                current.append((line, True))
            continue
        if marker:
            fence = marker.group(1)
            if current is not None:
                current.append((line, True))
            continue
        heading = HEADING.match(line)
        if heading:
            current = []
            sections.setdefault(_norm(heading.group(1)), []).append(current)
            outside.append(line)
            continue
        outside.append(line)
        if current is not None:
            current.append((line, False))
    return sections, outside


def _check_structure(text):
    sections, outside = _parse(text)
    for line in outside:
        if ANGLE.search(line):
            raise CheckpointError('placeholder de template restant')
    for name in SECTIONS:
        found = sections.get(_norm(name), [])
        if len(found) != 1:
            raise CheckpointError(f'section « {name} » absente ou en double')
        body = found[0]
        content = [line for line, _ in body if line.strip()]
        if not content or all(_placeholder(line) for line in content):
            raise CheckpointError(f'section « {name} » vide ou placeholder')
        if name == STATE_SECTION:
            state = ' '.join(line.strip().strip('`').strip() for line in content)
            if state not in STATES:
                raise CheckpointError('état non supporté')
        labels = SECTION_LABELS.get(name)
        if labels:
            _check_labels(name, body, labels)


def _check_labels(section, body, expected):
    values = {}
    last = None
    for line, fenced in body:
        if fenced:
            last = None
            continue
        match = LABEL.match(line)
        if match:
            last = _norm(match.group(1))
            values.setdefault(last, []).append(match.group(2))
        elif last and line[:1] in (' ', '\t') and line.strip():
            values[last][-1] += ' ' + line.strip()
        else:
            last = None
    for label in expected:
        entries = values.get(_norm(label), [])
        if len(entries) != 1:
            raise CheckpointError(f'label « {label} » ({section}) absent ou en double')
        if _placeholder(entries[0]):
            raise CheckpointError(f'label « {label} » ({section}) vide ou placeholder')


def _check_content(data):
    if b'\x00' in data:
        raise CheckpointError('octet NUL interdit')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise CheckpointError('UTF-8 invalide') from None
    _check_structure(text)


def _metadata(path, data, resolve=True):
    return {'validated': True, 'path': str(Path(path).resolve() if resolve else path),
            'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data),
            'validation': 'structural'}


def validate_checkpoint(repo, path, expected_sha256=None):
    """Read-only structural validation; returns metadata, never the content."""
    if not Path(repo).is_dir():
        raise CheckpointError('dépôt introuvable')
    data = _read_regular(path, 'checkpoint')
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None:
        expected = str(expected_sha256).strip().lower()
        if not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise CheckpointError('sha256 attendu invalide')
        if expected != digest:
            raise CheckpointError('sha256 différent de la valeur attendue')
    _check_content(data)
    return _metadata(path, data)


def _git(repo, *args):
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}
    try:
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                              env=env, timeout=20).returncode
    except (OSError, subprocess.SubprocessError):
        raise CheckpointError('git indisponible pour vérifier l\'exclusion') from None


def _require_private_local(repo, path):
    """Path must be under repo/.agentic-local, link-free, ignored and untracked."""
    if _git(repo, 'rev-parse', '--git-dir') != 0:
        raise CheckpointError('dépôt Git requis')
    if _git(repo, 'ls-files', '--error-unmatch', '--', str(path)) == 0:
        raise CheckpointError('chemin suivi par Git refusé')
    if _git(repo, 'check-ignore', '-q', '--', str(path)) != 0:
        raise CheckpointError('chemin non exclu de Git refusé')


def _locate(repo, destination):
    base = Path(os.path.abspath(repo))
    real = Path(os.path.realpath(repo))
    target = Path(os.path.abspath(destination))
    for root in (base, real):
        try:
            relative = target.relative_to(root)
        except ValueError:
            continue
        if len(relative.parts) >= 2 and relative.parts[0] == LOCAL_DIR:
            return real, relative
    raise CheckpointError(f'destination hors de {LOCAL_DIR}/')


DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _close_all(fds):
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def _exists(name, dir_fd):
    try:
        return os.lstat(name, dir_fd=dir_fd)
    except FileNotFoundError:
        return None


def _git_tree(dir_fd):
    """True if the directory is a Git work tree, bare repository, gitdir or worktree admin dir."""
    if _exists('.git', dir_fd) is not None:
        return True
    if _exists('HEAD', dir_fd) is None:
        return False
    return any(_exists(name, dir_fd) is not None for name in ('objects', 'refs', 'commondir'))


def _open_directories(root, relative):
    """Open root and every parent as directory fds (no symlink followed), creating
    missing ones. Returns the fds, root first; the caller closes them."""
    fds = []
    try:
        fds.append(os.open(str(root), DIR_FLAGS))
        for part in relative.parts[:-1]:
            try:
                fds.append(os.open(part, DIR_FLAGS, dir_fd=fds[-1]))
                if _git_tree(fds[-1]):
                    raise CheckpointError('destination dans un autre dépôt ou worktree Git : '
                                          'utiliser ce dépôt comme --repo')
            except FileNotFoundError:
                try:
                    os.mkdir(part, 0o700, dir_fd=fds[-1])
                    fds.append(os.open(part, DIR_FLAGS, dir_fd=fds[-1]))
                except OSError as error:
                    raise CheckpointError(f'répertoire non créé : {error.strerror}') from None
            except OSError:
                raise CheckpointError("lien ou fichier à la place d'un répertoire refusé") from None
    except OSError:
        _close_all(fds)
        raise CheckpointError('répertoire illisible') from None
    except BaseException:
        _close_all(fds)
        raise
    return fds


def _verify_namespace(root, relative, fds):
    """The path chain must still lead to the very directories held open."""
    current = Path(root)
    chain = [current] + [current.joinpath(*relative.parts[:i + 1])
                         for i in range(len(relative.parts) - 1)]
    for path, fd in zip(chain, fds):
        try:
            info = os.lstat(path)
            held = os.fstat(fd)
        except OSError:
            raise CheckpointError('espace de noms parent modifié pendant la sauvegarde') from None
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (held.st_dev, held.st_ino):
            raise CheckpointError('espace de noms parent modifié pendant la sauvegarde')


def _write_private(dir_fd, name, data):
    """Write data to a new private file inside dir_fd, sync it and verify it by re-reading.

    Returns the temporary bare name."""
    temporary = f'.{name}.tmp-{os.getpid()}-{secrets.token_hex(6)}'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                 | os.O_CLOEXEC, 0o600, dir_fd=dir_fd)
    try:
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError('écriture interrompue')
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        if _read_regular(temporary, 'candidat', dir_fd) != data:
            raise CheckpointError('relecture du candidat différente')
    except BaseException:
        _discard(temporary, dir_fd)
        raise
    return temporary


def _discard(name, dir_fd):
    try:
        os.unlink(name, dir_fd=dir_fd)
    except OSError:
        pass


def _preserve_previous(repo, final, dir_fd, old):
    """Keep a verified private (0600) copy of the previous file next to the destination."""
    digest = hashlib.sha256(old).hexdigest()[:16]
    backup = final.with_name(f'{final.stem}.previous-{digest}{final.suffix}')
    _require_private_local(repo, backup)
    info = _exists(backup.name, dir_fd)
    if info is not None and stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 \
            and _read_regular(backup.name, 'copie précédente', dir_fd) == old:
        return backup
    # Missing, non-private or different copy: recreate a private one atomically.
    temporary = _write_private(dir_fd, backup.name, old)
    try:
        os.replace(temporary, backup.name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        os.fsync(dir_fd)
    except BaseException:
        _discard(temporary, dir_fd)
        raise
    if _read_regular(backup.name, 'copie précédente', dir_fd) != old:
        raise CheckpointError('copie précédente non vérifiée')
    if stat.S_IMODE(os.lstat(backup.name, dir_fd=dir_fd).st_mode) != 0o600:
        raise CheckpointError('copie précédente non privée')
    return backup


def save_checkpoint(repo, source, destination):
    """Validate SOURCE and promote it atomically to DESTINATION under .agentic-local."""
    data = _read_regular(source, 'source')
    _check_content(data)
    root, relative = _locate(repo, destination)
    if not root.is_dir():
        raise CheckpointError('dépôt introuvable')
    _require_private_local(root, root / relative)
    fds = _open_directories(root, relative)
    try:
        dir_fd = fds[-1]
        name = relative.parts[-1]
        final = root.joinpath(*relative.parts)
        info = _exists(name, dir_fd)
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise CheckpointError('destination : fichier régulier requis')
        lock_fd = os.open(f'.{name}.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                          0o600, dir_fd=dir_fd)
        try:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise CheckpointError('sauvegarde concurrente en cours (verrou exclusif)') from None
            _verify_namespace(root, relative, fds)
            _require_private_local(root, final)
            _verify_namespace(root, relative, fds)
            old = None
            if _exists(name, dir_fd) is not None:
                old = _read_regular(name, 'checkpoint précédent', dir_fd)
            if old is not None:
                _preserve_previous(root, final, dir_fd, old)
            candidate = _write_private(dir_fd, name, data)
            try:
                _verify_namespace(root, relative, fds)
                os.replace(candidate, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            except BaseException:
                _discard(candidate, dir_fd)
                raise
            os.fsync(dir_fd)
            _verify_namespace(root, relative, fds)
            if _read_regular(name, 'checkpoint final', dir_fd) != data:
                raise CheckpointError('relecture finale différente : '
                                      "ancien checkpoint conservé en copie précédente s'il existait")
            _check_content(data)
            return _metadata(final, data, resolve=False)
        finally:
            os.close(lock_fd)
    finally:
        _close_all(fds)


def _message(error):
    if isinstance(error, CheckpointError):
        text = str(error)
    elif isinstance(error, OSError):
        text = f'erreur système : {error.strerror or type(error).__name__}'
    else:
        text = f'erreur inattendue : {type(error).__name__}'
    return text[:MAX_MESSAGE]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Sauvegarde et validation STRUCTURELLE de HANDOFF.md '
                    '(ni vérité des faits, ni autorisation de reprise).')
    commands = parser.add_subparsers(dest='command', required=True)
    save = commands.add_parser('save', help='valider (structurel) puis sauvegarder atomiquement')
    save.add_argument('--repo', required=True)
    save.add_argument('--source', required=True, help='brouillon HANDOFF Markdown')
    save.add_argument('--output', required=True, help='destination sous .agentic-local/')
    check = commands.add_parser('validate', help='validation structurelle en lecture seule')
    check.add_argument('--repo', required=True)
    check.add_argument('--file', required=True)
    check.add_argument('--sha256', help='empreinte attendue')
    args = parser.parse_args(argv)
    try:
        if args.command == 'save':
            result = save_checkpoint(args.repo, args.source, args.output)
        else:
            result = validate_checkpoint(args.repo, args.file, args.sha256)
    except Exception as error:  # diagnostics are bounded and never include the document
        print(f'agentic-checkpoint: {_message(error)}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
