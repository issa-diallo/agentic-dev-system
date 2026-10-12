#!/usr/bin/env python3
"""Cooperative Git workspace ownership, not an OS sandbox.

Reservations persist until their owner explicitly releases them. They do not
prove delegation, PR_SPLIT, or permission to merge. POSIX flock is required.
File globs conservatively lock their literal directory prefix. Logical config,
module, and other names do not imply file ownership: reserve physical files too.
Owner identity is asserted by the trusted orchestrator; release is not an
authentication boundary and must not be exposed to untrusted agents.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

TYPES = {'file', 'module', 'api', 'table', 'migration', 'contract',
         'interface', 'config', 'test', 'deploy'}


class Blocked(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Blocked(message)


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    require(result.returncode == 0, 'Git failed: ' + result.stderr.strip())
    return result.stdout.strip()


def root(repo):
    return Path(git(repo, 'rev-parse', '--show-toplevel')).resolve()


def clean_path(value):
    require(isinstance(value, str) and value and '\0' not in value, 'path required')
    path = Path(value)
    require('..' not in path.parts and '.' not in value.split('/'), 'path alias/traversal refused')
    require(str(path) == value, 'path must be normalized')
    return path


def worktrees(repo):
    raw = subprocess.run(['git', '-C', str(repo), 'worktree', 'list', '--porcelain', '-z'],
                         capture_output=True, check=True).stdout
    return [Path(item[9:].decode()).resolve() for item in raw.split(b'\0')
            if item.startswith(b'worktree ')]


def inspect(repo, path):
    directory = clean_path(str(path))
    if not directory.is_absolute():
        directory = root(repo) / directory
    require(directory == directory.resolve(), 'symlink worktree alias refused')
    require(directory in worktrees(repo), 'not a registered worktree')
    return {'path': str(directory), 'branch': git(directory, 'branch', '--show-current'),
            'head': git(directory, 'rev-parse', 'HEAD'),
            'status': git(directory, 'status', '--porcelain=v1'),
            'dirty': bool(git(directory, 'status', '--porcelain=v1'))}


def create(repo, branch, path, base='HEAD'):
    require(isinstance(branch, str) and branch not in ('main', 'master')
            and not branch.startswith('-'), 'dedicated branch required')
    git(repo, 'check-ref-format', '--branch', branch)
    directory = clean_path(str(path))
    if not directory.is_absolute():
        directory = root(repo) / directory
    require(directory == directory.resolve(), 'symlink path refused')
    require(not directory.exists() and not directory.is_symlink(), 'destination exists')
    refs = git(repo, 'for-each-ref', '--format=%(refname)', 'refs/heads/' + branch).splitlines()
    require('refs/heads/' + branch not in refs, 'branch exists')
    require(isinstance(base, str) and base and not base.startswith('-'), 'invalid base')
    commit = git(repo, 'rev-parse', '--verify', '--end-of-options', base + '^{commit}')
    git(repo, 'worktree', 'add', '-b', branch, '--', str(directory), commit)
    return inspect(repo, str(directory))


@contextmanager
def registry(repo):
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    require(not common.is_symlink(), 'symlink common directory refused')
    directory = common / 'agentic-workspace'
    require(not directory.is_symlink(), 'symlink registry refused')
    directory.mkdir(mode=0o700, exist_ok=True)
    lock_path = directory / 'lock'
    state_path = directory / 'owners.json'
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        require(not state_path.is_symlink(), 'symlink state refused')
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        require(isinstance(state, dict), 'invalid registry')
        for identifier, entry in state.items():
            require(isinstance(identifier, str) and isinstance(entry, dict)
                    and entry.get('id') == identifier
                    and isinstance(entry.get('worktree'), str)
                    and isinstance(entry.get('resources'), list), 'invalid registry entry')
            require(all(isinstance(item, dict) and item.get('type') in TYPES
                        and isinstance(item.get('name'), str)
                        for item in entry['resources']), 'invalid registry resources')
        yield state
        fd, temporary = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(state, output, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, state_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def normalize_resource(resource, workspace):
    require(isinstance(resource, dict), 'resource must be object')
    kind, name = resource.get('type'), resource.get('name')
    require(kind in TYPES and isinstance(name, str) and name.strip() == name and name,
            'resource requires recognized type and name')
    require(not any(ord(char) < 32 for char in name), 'control character in resource')
    if kind == 'file':
        require(not name.startswith('/') and '..' not in name.split('/')
                and '.' not in name.split('/') and '//' not in name
                and not any(part == '.git' or part.startswith('.git*')
                            or part.startswith('.git?') or part.startswith('.git[')
                            for part in name.split('/')), 'relative file required')
        glob = re.search(r'[*?\[]', name)
        if glob:
            prefix = name[:glob.start()]
            name = prefix.rsplit('/', 1)[0] if '/' in prefix else ''
        else:
            name = name.rstrip('/')
        if name:
            path = clean_path(name)
            require(not path.is_absolute() and '.git' not in path.parts, 'invalid file')
            require(workspace / path == (workspace / path).resolve(), 'symlink file alias refused')
        return {'type': kind, 'name': name}
    # Logical resource names are exact identifiers; hierarchical/glob aliases are refused.
    require('..' not in name.split('/') and not any(c in name for c in '*?['),
            'invalid logical resource')
    require('//' not in name and not name.endswith('/')
            and '.' not in name.split('/'), 'resource alias refused')
    return {'type': kind, 'name': name}


def conflicts(left, right):
    if left['type'] != right['type']:
        return False
    a, b = left['name'], right['name']
    if left['type'] != 'file':
        return a == b
    return not a or not b or a == b or a.startswith(b + '/') or b.startswith(a + '/')


def reserve(repo, owner, worktree, resources):
    require(isinstance(owner, dict), 'owner must include id, task and plan_sha256')
    require(all(isinstance(owner.get(key), str) and owner[key].strip()
                for key in ('id', 'task', 'plan_sha256')), 'owner metadata required')
    require(re.fullmatch(r'[0-9a-f]{64}', owner['plan_sha256']), 'SHA256 plan hash required')
    information = inspect(repo, str(worktree))
    require(information['branch'] not in ('', 'main', 'master'), 'dedicated writable branch required')
    workspace = Path(information['path'])
    require(isinstance(resources, list) and resources, 'resources required')
    selected = [normalize_resource(resource, workspace) for resource in resources]
    reservation = {**owner, 'worktree': str(workspace), 'resources': selected}
    with registry(repo) as state:
        if owner['id'] in state:
            require(state[owner['id']] == reservation, 'owner already has a different reservation')
        for identifier, existing in state.items():
            if identifier == owner['id']:
                continue
            require(existing['worktree'] != str(workspace), 'worktree already has a writer')
            require(not any(conflicts(a, b) for a in selected for b in existing['resources']),
                    'resource owned by ' + identifier)
        state[owner['id']] = reservation
    return reservation


def release(repo, owner):
    require(isinstance(owner, str) and owner, 'owner id required')
    with registry(repo) as state:
        require(owner in state, 'owner has no reservation; nothing released')
        released = state.pop(owner)
    return released


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'inspect', 'reserve', 'release'])
    parser.add_argument('--repo', default='.')
    parser.add_argument('--path')
    parser.add_argument('--branch')
    parser.add_argument('--base', default='HEAD')
    parser.add_argument('--owner')
    parser.add_argument('--task')
    parser.add_argument('--plan-sha256')
    parser.add_argument('--resources', help='JSON array of {type, name}')
    args = parser.parse_args()
    try:
        if args.action == 'create':
            result = create(args.repo, args.branch, args.path, args.base)
        elif args.action == 'inspect':
            result = inspect(args.repo, args.path)
        elif args.action == 'reserve':
            owner = {'id': args.owner, 'task': args.task, 'plan_sha256': args.plan_sha256}
            result = reserve(args.repo, owner, args.path, json.loads(args.resources or 'null'))
        else:
            result = release(args.repo, args.owner)
        print(json.dumps({'verdict': 'PASS', 'result': result}))
        return 0
    except (Blocked, OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        print(json.dumps({'verdict': 'BLOCKED', 'reason': str(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
