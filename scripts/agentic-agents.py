#!/usr/bin/env python3
"""Register bundled agents in native project directories without overwriting custom files."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


ROLES = ('explorer', 'implementer', 'reviewer')


def _safe(path):
    """Inspect before resolving, so a symlink cannot disappear into its target."""
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError(f'Refusing symlink: {item}')
        if item != path and item.exists() and not item.is_dir():
            raise ValueError(f'Not a directory: {item}')
    return path


def profiles(method_root):
    """Return native relative paths mapped to exact canonical profile bytes."""
    root = _safe(method_root)
    result = {}
    for family, suffix in (('codex', 'toml'), ('claude', 'md')):
        for role in ROLES:
            source = _safe(root / family / 'agents' / f'{role}.{suffix}')
            if not source.is_file():
                raise ValueError(f'Missing agent profile: {source}')
            result[f'.{family}/agents/agentic-{role}.{suffix}'] = source.read_bytes()
    return result


def _git(project, *args):
    result = subprocess.run(['git', '-C', str(project), *args], capture_output=True)
    if result.returncode:
        raise ValueError(f'Git command failed: {" ".join(args[:2])}')
    return result.stdout


def _exclusion(project, paths):
    root = Path(_git(project, 'rev-parse', '--show-toplevel').decode().strip())
    if root.resolve() != project.resolve():
        raise ValueError('Local agent installation requires the Git repository root.')
    tracked = _git(project, 'ls-files', '-z', '--', *paths).split(b'\0')
    if any(tracked):
        raise ValueError('Refusing a tracked native agent in local mode.')
    # --path-format=absolute resolves symlinks, hiding an unsafe exclude target.
    raw = Path(_git(project, 'rev-parse', '--git-path', 'info/exclude').decode().strip())
    exclude = _safe(raw if raw.is_absolute() else project / raw)
    if exclude.exists() and not exclude.is_file():
        raise ValueError(f'Not a file: {exclude}')
    original = exclude.read_bytes() if exclude.exists() else b''
    missing = ['/' + rel for rel in paths if ('/' + rel).encode() not in original.splitlines()]
    planned = original
    if missing:
        planned += b'\n# Personal Agentic native profiles\n'
        planned += ('\n'.join(missing) + '\n').encode()
    # A throwaway Git directory lets real Git evaluate project .gitignore files
    # against the proposed info/exclude without mutating the project for preflight.
    with tempfile.TemporaryDirectory(prefix='agentic-agent-ignore-') as directory:
        shadow = Path(directory)
        subprocess.run(['git', 'init', '--bare', '-q', str(shadow)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        (shadow / 'info/exclude').write_bytes(planned)
        command = ['git', '--git-dir', str(shadow), '--work-tree', str(project),
                   '-c', 'core.bare=false']
        configured = subprocess.run(['git', '-C', str(project), 'config', '--path',
                                     '--get', 'core.excludesFile'], capture_output=True)
        if configured.returncode == 0:
            command += ['-c', 'core.excludesFile=' + configured.stdout.decode().strip()]
        for rel in paths:
            result = subprocess.run(command + ['check-ignore', '--no-index', '-q', '--', rel],
                                    cwd=project, capture_output=True)
            if result.returncode:
                raise ValueError(f'Team ignore rules expose native profile: {rel}')
    return exclude, planned


def sync(method_root, project, local=False, dry_run=False, previous=None, check=False):
    """Preflight every profile, then add/update permitted native copies.

    previous is a pre-update snapshot from profiles(old_method_root). Its bytes
    authorize replacement only while the native copy still matches that snapshot.
    An explicit snapshot preserves and reports customized native files instead of
    blocking updates to unrelated profiles. check and dry_run never write project files.
    """
    wanted = profiles(method_root)
    root = _safe(project)
    if not root.is_dir():
        raise ValueError(f'Missing project directory: {root}')
    report = {key: [] for key in ('added', 'updated', 'unchanged', 'customized')}
    writes = []
    for rel, payload in wanted.items():
        destination = _safe(root / rel)
        if destination.exists() and not destination.is_file():
            raise ValueError(f'Not a file: {destination}')
        current = destination.read_bytes() if destination.exists() else None
        if current is None:
            report['added'].append(rel)
            writes.append((destination, payload))
        elif current == payload:
            report['unchanged'].append(rel)
        elif previous is not None and current == previous.get(rel):
            report['updated'].append(rel)
            writes.append((destination, payload))
        elif previous is not None:
            report['customized'].append(rel)
        else:
            raise ValueError(f'Native agent already exists with different content: {rel}')
    exclude, planned = _exclusion(root, list(wanted)) if local else (None, None)
    if check or dry_run:
        return report
    if exclude is not None:
        original = exclude.read_bytes() if exclude.exists() else None
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_bytes(planned)
        try:
            for rel in wanted:
                _git(root, 'check-ignore', '--no-index', '-q', '--', rel)
        except ValueError:
            if original is None:
                exclude.unlink()
            else:
                exclude.write_bytes(original)
            raise ValueError('Native profile exclusion failed; original exclude restored.')
    for destination, payload in writes:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method-root', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--local', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        result = sync(args.method_root, args.project, args.local, args.dry_run, check=args.check)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
