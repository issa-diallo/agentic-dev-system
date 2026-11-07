#!/usr/bin/env python3
"""Detect the stack and verification commands a project already defines.

Nothing is invented: commands come from declared scripts and configuration files.
Files are classified into profiles (front, back, data, contract, docs), each with its
own checks, so a front ticket and a back ticket get different verification. Heuristic:
the result lists its evidence and what is missing; override it in the config.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys

MARKERS = ('package.json', 'pyproject.toml', 'go.mod', 'Cargo.toml', 'pom.xml', 'build.gradle',
           'Makefile', 'requirements.txt')
FRONT_DEPS = {'react', 'vue', 'svelte', 'next', 'nuxt', '@angular/core', 'solid-js', 'preact', 'vite'}
BACK_DEPS = {'express', 'fastify', '@nestjs/core', 'koa', 'hono', 'prisma', 'typeorm', 'sequelize'}
FRONT_EXT = {'.tsx', '.jsx', '.vue', '.svelte', '.css', '.scss', '.sass', '.less', '.html'}
FRONT_DIRS = {'components', 'pages', 'views', 'styles', 'ui', 'frontend', 'client', 'web', 'public'}
BACK_DIRS = {'api', 'server', 'services', 'controllers', 'routes', 'backend', 'handlers'}
DATA_DIRS = {'migrations', 'migrate', 'prisma', 'alembic'}
CODE_EXT = {'.py', '.go', '.rs', '.java', '.kt', '.rb', '.php', '.ts', '.js', '.mjs', '.cs'}
DOC_EXT = {'.md', '.rst', '.txt'}
TEST_PATH = re.compile(r'(^|/)(tests?|__tests__|specs?|e2e)/|(^|/)test_[^/]*$|_test\.\w+$|\.(test|spec)\.\w+$')
CONTRACT = re.compile(r'(^|/)(openapi|swagger)[^/]*\.(ya?ml|json)$|\.proto$|\.graphql$|(^|/)contracts?/')
PLACEHOLDER = re.compile(r'no test specified|exit 1\s*$')
NODE_SCRIPTS = {'test': ('test:unit', 'test'), 'lint': ('lint',),
                'typecheck': ('typecheck', 'type-check', 'tsc'), 'e2e': ('test:e2e', 'e2e'),
                'build': ('build',)}
CHECKS = {'front': ('lint', 'typecheck', 'test'), 'back': ('lint', 'typecheck', 'test'),
          'data': ('test',), 'contract': ('contract', 'test'), 'code': ('lint', 'typecheck', 'test')}


def read(path):
    try:
        return Path(path).read_text(errors='replace')
    except OSError:
        return ''


def package_manager(directory):
    for lock, tool in (('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'), ('bun.lockb', 'bun'),
                       ('bun.lock', 'bun')):
        if (directory / lock).exists():
            return tool
    return 'npm'


def at(tool, directory, *rest):
    """argv running `tool rest` inside directory using the tool's own directory flag."""
    if directory in ('', '.'):
        return [tool, *rest]
    flag = {'npm': '--prefix', 'pnpm': '--dir', 'yarn': '--cwd', 'bun': '--cwd', 'make': '-C',
            'go': '-C'}.get(tool)
    return [tool, flag, directory, *rest] if flag else [tool, *rest]


def inspect_package(root, directory):
    """Return {'stack': set, 'checks': {kind: argv}, 'evidence': [...]} for one manifest dir."""
    base, rel = root / directory, directory or '.'
    stack, checks, evidence = set(), {}, []
    manifest = base / 'package.json'
    if manifest.exists():
        try:
            data = json.loads(read(manifest))
        except ValueError:
            data = {}
        deps = set(data.get('dependencies', {})) | set(data.get('devDependencies', {}))
        scripts = data.get('scripts', {}) if isinstance(data.get('scripts'), dict) else {}
        stack |= {'front' for d in deps & FRONT_DEPS} | {'back' for d in deps & BACK_DEPS} | {'node'}
        tool = package_manager(base)
        for kind, names in NODE_SCRIPTS.items():
            name = next((n for n in names if n in scripts and not PLACEHOLDER.search(scripts[n])), None)
            if name:
                checks[kind] = at(tool, rel, 'run', name)
        for name in scripts:
            if re.search(r'(openapi|schema|contract|codegen).*(check|lint|validate)|validate:(api|schema)', name):
                checks.setdefault('contract', at(tool, rel, 'run', name))
        evidence.append('%s/package.json (%s)' % (rel, tool))
    pyproject, requirements = read(base / 'pyproject.toml'), read(base / 'requirements.txt')
    if pyproject or requirements or (base / 'pytest.ini').exists() or (base / 'setup.cfg').exists():
        stack |= {'python'} | ({'back'} if re.search(r'django|fastapi|flask', pyproject + requirements, re.I) else set())
        pytest = '[tool.pytest' in pyproject or (base / 'pytest.ini').exists() or 'pytest' in requirements
        target = [] if rel == '.' else [rel]
        if pytest:
            checks['test'] = ['python3', '-m', 'pytest', '-q', *target]
        elif (base / 'tests').is_dir():
            checks['test'] = ['python3', '-m', 'unittest', 'discover', '-s', rel if rel != '.' else '.']
        if '[tool.ruff' in pyproject or (base / 'ruff.toml').exists():
            checks['lint'] = ['python3', '-m', 'ruff', 'check', rel]
        if '[tool.mypy' in pyproject or (base / 'mypy.ini').exists():
            checks['typecheck'] = ['python3', '-m', 'mypy', rel]
        evidence.append(rel + '/python configuration')
    if (base / 'go.mod').exists():
        stack |= {'go', 'back'}
        checks['test'] = at('go', rel, 'test', './...')
        checks['lint'] = at('go', rel, 'vet', './...')
        evidence.append(rel + '/go.mod')
    if (base / 'Cargo.toml').exists():
        stack |= {'rust', 'back'}
        checks['test'] = ['cargo', 'test'] + ([] if rel == '.' else ['--manifest-path', rel + '/Cargo.toml'])
        evidence.append(rel + '/Cargo.toml')
    if (base / 'pom.xml').exists():
        stack |= {'java', 'back'}
        checks['test'] = ['mvn', '-q', 'test'] + ([] if rel == '.' else ['-f', rel + '/pom.xml'])
        evidence.append(rel + '/pom.xml')
    makefile = read(base / 'Makefile')
    for kind in ('test', 'lint'):
        if kind not in checks and re.search(r'^%s\s*:' % kind, makefile, re.M):
            checks[kind] = at('make', rel, kind)
            evidence.append('%s/Makefile target %s' % (rel, kind))
    return {'stack': stack, 'checks': checks, 'evidence': evidence}


def package_of(root, path):
    """Nearest ancestor directory of path holding a manifest ('' for the root)."""
    parts = PurePosixPath(path).parent.parts
    for end in range(len(parts), -1, -1):
        directory = '/'.join(parts[:end])
        if any((root / directory / marker).exists() for marker in MARKERS):
            return directory
    return ''


def classify(path, stack):
    """Profile of one non-test file."""
    pure = PurePosixPath(path)
    parts, suffix = set(pure.parts[:-1]), pure.suffix.lower()
    if CONTRACT.search(path):
        return 'contract'
    if parts & DATA_DIRS or suffix == '.sql':
        return 'data'
    if suffix in DOC_EXT:
        return 'docs'
    if suffix in FRONT_EXT or (suffix in CODE_EXT and parts & FRONT_DIRS):
        return 'front'
    if suffix in CODE_EXT:
        if parts & BACK_DIRS:
            return 'back'
        if suffix in {'.ts', '.js', '.mjs'}:
            if 'front' in stack and 'back' not in stack:
                return 'front'
            return 'back' if 'back' in stack else 'code'
        return 'back'
    return 'code'


def profile_of(path, stack):
    if TEST_PATH.search(path):
        suffix = PurePosixPath(path).suffix.lower()
        return 'front' if suffix in {'.tsx', '.jsx', '.vue', '.svelte'} else 'test'
    return classify(path, stack)


def detect(root, files=None, e2e=False):
    """Return profiles, ordered argv checks, what is missing and the evidence."""
    root = Path(root).resolve()
    files = list(files or [])
    packages = {}
    for directory in {package_of(root, f) for f in files} or {''}:
        packages[directory] = inspect_package(root, directory)
    stacks = set().union(*(p['stack'] for p in packages.values()))
    profiles = sorted({profile_of(f, packages[package_of(root, f)]['stack']) for f in files} - {'test'})
    commands, missing, seen = [], [], set()
    for profile in profiles or ([] if files else ['code']):
        for kind in CHECKS.get(profile, ()):
            found = False
            for directory, info in sorted(packages.items()):
                argv = info['checks'].get(kind)
                if argv and tuple(argv) not in seen:
                    seen.add(tuple(argv))
                    commands.append({'profile': profile, 'kind': kind, 'argv': argv})
                found = found or bool(argv)
            if not found and kind == 'test':
                missing.append('%s: no test command declared' % profile)
        if profile == 'front' and e2e:
            for info in packages.values():
                argv = info['checks'].get('e2e')
                if argv and tuple(argv) not in seen:
                    seen.add(tuple(argv))
                    commands.append({'profile': 'front', 'kind': 'e2e', 'argv': argv})
        if profile == 'data':
            missing.append('data: migration up/down has no standard command; add it to the unit verify')
    return {'stacks': sorted(stacks), 'profiles': profiles, 'commands': commands,
            'missing': missing, 'evidence': sorted({e for p in packages.values() for e in p['evidence']})}


def split_units(files):
    """Group files by profile; order contract/data first, then back, then front."""
    groups = {}
    for path in files:
        groups.setdefault(profile_of(path, set()), []).append(path)
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='.')
    parser.add_argument('--file', action='append', default=[])
    parser.add_argument('--e2e', action='store_true')
    args = parser.parse_args()
    print(json.dumps(detect(args.repo, args.file, args.e2e), sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
