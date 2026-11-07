#!/usr/bin/env python3
"""Update an installed agentic-dev-system from this source checkout, safely.

Usage: python3 update-agentic.py <project> [--dry-run] [--force-customized]
Handles `--local` installs (.agentic-local) and shared installs (docs/agentic).
A manifest (.agentic-manifest.json) records the hash of each installed file:
- unchanged since install  -> replaced (old copy saved in work/.update-<ts>/backup)
- customized by the team   -> kept; the new version goes to work/.update-<ts>/incoming
- missing                  -> added
Without a manifest (older install) files that differ from the source count as
customized, so nothing the project edited is ever overwritten silently.
Project data (docs/agentic/work, STATUS.md, docs/product, docs/adr, agentic.config.json
once edited) is never touched.
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
MANIFEST = '.agentic-manifest.json'
SKIP_DIRS = {'work', '__pycache__'}
SKIP_FILES = {'STATUS.md'}
ROOT_FILES = ['AGENTS.md', 'COMMITS.md']
TREES = ['docs/agentic', 'scripts', 'skills', 'codex', 'claude/agents']
SCRIPT_PREFIX = 'agentic-'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def managed(source=SOURCE):
    """Relative paths this version distributes."""
    files = [f for f in ROOT_FILES if (source / f).is_file()]
    for tree in TREES:
        base = source / tree
        for path in sorted(base.rglob('*')) if base.is_dir() else []:
            rel = path.relative_to(source)
            if not path.is_file() or SKIP_DIRS & set(rel.parts) or path.name in SKIP_FILES:
                continue
            if tree == 'scripts' and not path.name.startswith(SCRIPT_PREFIX):
                continue
            if path.suffix == '.pyc':
                continue
            files.append(rel.as_posix())
    return files


def install_root(project):
    project = Path(project).resolve()
    local = project / '.agentic-local'
    if local.is_dir():
        return local
    if (project / 'docs/agentic').is_dir():
        return project
    raise SystemExit('No agentic install found in %s (.agentic-local or docs/agentic)' % project)


def update(project, dry_run=False, force=False, source=SOURCE, stamp=None):
    root = install_root(project)
    if root.resolve() == Path(source).resolve():
        raise SystemExit('Refusing to update the source repository itself.')
    stamp = stamp or time.strftime('%Y%m%dT%H%M%S')
    work = root / 'docs/agentic/work' / ('.update-' + stamp)
    manifest_path = root / MANIFEST
    try:
        recorded = json.loads(manifest_path.read_text()).get('files', {})
    except (OSError, ValueError):
        recorded = {}
    report = {'added': [], 'updated': [], 'unchanged': [], 'customized': [], 'forced': []}
    new_manifest = dict(recorded)
    for rel in managed(source):
        src, dest = Path(source) / rel, root / rel
        wanted = digest(src)
        if dest.is_symlink():
            report['customized'].append(rel)
            continue
        if not dest.exists():
            report['added'].append(rel)
        else:
            current = digest(dest)
            if current == wanted:
                report['unchanged'].append(rel)
                new_manifest[rel] = wanted
                continue
            if recorded.get(rel) == current:
                report['updated'].append(rel)
            elif force:
                report['forced'].append(rel)
            else:
                report['customized'].append(rel)
                if not dry_run:
                    target = work / 'incoming' / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, target)
                continue
            if not dry_run:
                backup = work / 'backup' / rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup)
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            new_manifest[rel] = wanted
    if not dry_run:
        manifest_path.write_text(json.dumps({'version': 1, 'files': new_manifest}, indent=1, sort_keys=True))
    report['root'] = str(root)
    report['review'] = str(work) if report['customized'] or report['updated'] or report['forced'] else None
    return report


def record(root, source=SOURCE):
    """Write the manifest for files identical to the source (called by the installer)."""
    root = Path(root)
    files = {rel: digest(root / rel) for rel in managed(source)
             if (root / rel).is_file() and digest(root / rel) == digest(Path(source) / rel)}
    (root / MANIFEST).write_text(json.dumps({'version': 1, 'files': files}, indent=1, sort_keys=True))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('project')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force-customized', action='store_true')
    parser.add_argument('--record', action='store_true', help='record the manifest of an install root')
    args = parser.parse_args()
    if args.record:
        record(args.project)
        return 0
    report = update(args.project, args.dry_run, args.force_customized)
    for key in ('added', 'updated', 'forced', 'customized'):
        print('%s: %d' % (key, len(report[key])))
        for rel in report[key]:
            print('  ' + rel)
    print('unchanged: %d' % len(report['unchanged']))
    if report['customized']:
        print('Customized files kept; compare with the incoming copies in %s/incoming' % report['review'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
