#!/usr/bin/env python3
"""Deterministic gates for a delegated diff: scope, size, tests, secrets, commands.

Run by the trusted orchestrator, never by the delegated agent. Static gates run
first; trusted argv commands run only if none failed. PASS proves mechanical
properties of this diff, not that acceptance criteria are met: semantic review
stays independent. Output carries hashes and names, never raw logs or secrets.
"""
import argparse
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

DOC_SUFFIXES = {'.md', '.rst', '.txt'}
TEST_PATH = re.compile(r'(^|/)(tests?|__tests__|specs?)/|(^|/)test_[^/]*$|_test\.\w+$|\.(test|spec)\.\w+$')
SKIP = re.compile(r'@pytest\.mark\.(skip|xfail)|pytest\.skip\(|@unittest\.(skip|expectedFailure)|'
                  r'\b(it|test|describe)\.(skip|only)\(|\b(xit|xtest|xdescribe)\(|\bt\.Skip\(|'
                  r'@Ignore\b|@Disabled\b|#\[ignore\]')
ASSERTION = re.compile(r'\b(assert\w*|expect)\b')
SECRETS = {'aws-access-key': (r'\bAKIA[0-9A-Z]{16}\b', 'FAIL'),
           'private-key': (r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----', 'FAIL'),
           'github-token': (r'\bgh[pousr]_[A-Za-z0-9]{36,}\b', 'FAIL'),
           'slack-token': (r'\bxox[baprs]-[A-Za-z0-9-]{10,}', 'FAIL'),
           'literal-credential': (r'(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[\'"][^\'"\s]{12,}[\'"]',
                                  'WARN')}
SIZE = {'max_files': 3, 'max_lines': 100, 'mode': 'warn'}  # PULL_REQUESTS targets


def quality():
    path = Path(__file__).with_name('agentic-quality.py')
    spec = importlib.util.spec_from_file_location('gates_quality', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    result = subprocess.run(['git', '--literal-pathspecs', '-c', 'core.quotepath=off',
                             '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError('Git inspection failed: ' + args[0])
    return result.stdout


def collect(repo, base):
    """Return {path: {status, added, removed}} for committed, staged, dirty and untracked."""
    raw = git(repo, 'diff', '--name-status', '--no-renames', '--no-ext-diff', '-z', base, '--')
    items = raw.split(b'\0')
    changes = {}
    for status, name in zip(items[0::2], items[1::2]):
        changes[name.decode('utf-8', 'surrogateescape')] = {'status': status.decode(),
                                                            'added': [], 'removed': []}
    for name in git(repo, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0'):
        if name:
            changes[name.decode('utf-8', 'surrogateescape')] = {'status': 'A', 'added': [],
                                                                'removed': [], 'untracked': True}
    for path, info in changes.items():
        if info.get('untracked'):
            data = (Path(repo) / path).read_bytes()[:1024 * 1024]
            info['added'] = data.decode('utf-8', 'replace').splitlines()
            continue
        diff = git(repo, 'diff', '-U0', '--no-ext-diff', '--no-textconv', base, '--', path)
        for line in diff.decode('utf-8', 'replace').splitlines():
            if line.startswith('+') and not line.startswith('+++'):
                info['added'].append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                info['removed'].append(line[1:])
    return changes


def verdict(name, status, detail):
    return {'name': name, 'status': status, 'detail': detail}


def listed(names, limit=8):
    names = sorted(names)
    return ', '.join(names[:limit]) + (' (+%d)' % (len(names) - limit) if len(names) > limit else '')


def static_gates(changes, files, settings):
    gates, changed = [], set(changes)
    outside = changed - set(files)
    gates.append(verdict('scope', 'FAIL' if outside else 'PASS',
                         'outside declared files: ' + listed(outside) if outside
                         else '%d changed path(s), all declared' % len(changed)))
    if not changed:
        gates.append(verdict('changes', 'FAIL', 'no change produced'))
    lines = sum(len(i['added']) + len(i['removed']) for i in changes.values())
    size = {**SIZE, **settings.get('size', {})}
    over = [label for label, value, limit in (('files', len(changed), size['max_files']),
                                              ('lines', lines, size['max_lines']))
            if limit is not None and value > limit]
    gates.append(verdict('size', ('FAIL' if size['mode'] == 'fail' else 'WARN') if over else 'PASS',
                         '%d file(s), %d line(s); limits %s/%s' % (
                             len(changed), lines, size['max_files'], size['max_lines'])))
    tests = {p for p in changed if TEST_PATH.search(p)}
    sources = {p for p in changed - tests if Path(p).suffix not in DOC_SUFFIXES
               and changes[p]['status'] != 'D'}
    if settings.get('require_tests', True) and sources and not tests:
        gates.append(verdict('tests-present', 'FAIL', 'source changed without a test: ' + listed(sources)))
    else:
        gates.append(verdict('tests-present', 'PASS', '%d test path(s) changed' % len(tests)))
    deleted = {p for p in tests if changes[p]['status'] == 'D'}
    skipped = {p for p in tests if any(SKIP.search(line) for line in changes[p]['added'])}
    weakened = {p for p in tests - deleted
                if sum(bool(ASSERTION.search(x)) for x in changes[p]['removed'])
                > sum(bool(ASSERTION.search(x)) for x in changes[p]['added'])}
    problems = [label + ': ' + listed(found) for label, found in
                (('deleted', deleted), ('skip/only added', skipped)) if found]
    gates.append(verdict('test-integrity', 'FAIL' if problems else ('WARN' if weakened else 'PASS'),
                         '; '.join(problems) or ('fewer assertions in: ' + listed(weakened)
                                                 if weakened else 'no test removed or disabled')))
    found = {}
    for path, info in changes.items():
        for label, (pattern, level) in SECRETS.items():
            if any(re.search(pattern, line) for line in info['added']):
                found.setdefault((label, level), set()).add(path)
    hard = {k: v for k, v in found.items() if k[1] == 'FAIL'}
    gates.append(verdict('secrets', 'FAIL' if hard else ('WARN' if found else 'PASS'),
                         '; '.join('%s in %s' % (k[0], listed(v)) for k, v in sorted(found.items()))
                         or 'no credential pattern in added lines'))
    ids = settings.get('rule_ids') or []
    if ids:
        text = '\n'.join(line for p in tests for line in changes[p]['added'])
        lost = [i for i in ids if not re.search(r'(?<![A-Za-z0-9])%s(?![A-Za-z0-9])' % re.escape(i), text, re.I)]
        gates.append(verdict('traceability', 'FAIL' if lost else 'PASS',
                             'rule(s) without a test naming them: ' + ', '.join(lost) if lost
                             else 'every business rule is named by a test'))
    return gates, lines


def run(repo, base, files, commands, settings=None, plan_sha256=None):
    """Return a report. settings: require_tests, size{max_files,max_lines,mode}, timeout."""
    settings = settings or {}
    changes = collect(repo, base)
    gates, lines = static_gates(changes, files, settings)
    failed = any(g['status'] == 'FAIL' for g in gates)
    report = {'gates': gates, 'stats': {'files': len(changes), 'lines': lines},
              'changed': sorted(changes), 'commands': None,
              'base': git(repo, 'rev-parse', base).decode().strip(), 'plan_sha256': plan_sha256}
    docs_only = bool(changes) and all(Path(p).suffix in DOC_SUFFIXES for p in changes)
    if settings.get('baseline_only') and not failed:
        # Tests-before-code is not TDD: either initial result is informative.
        checks = (quality().run_checks(repo, commands, settings.get('timeout', 600))
                  if commands else {'verdict': 'NOT_RUN', 'checks': [], 'unchanged': True})
        report['commands'] = checks
        failed = (not checks['unchanged'] or any(
            c['timed_out'] or c['output_limit_exceeded'] or c['returncode'] is None
            for c in checks['checks']))
        gates.append(verdict('baseline', 'FAIL' if failed else 'PASS',
                             'initial test result: ' + checks['verdict']))
    elif settings.get('expect_red') and not commands:
        gates.append(verdict('red', 'FAIL', 'no verification command configured'))
        failed = True
    elif not commands and docs_only and not failed:
        gates.append(verdict('commands', 'PASS', 'documentation only, no command required'))
        report['commands'] = {'verdict': 'PASS', 'checks': []}
    elif not commands:
        gates.append(verdict('commands', 'FAIL', 'no verification command configured'))
        failed = True
    elif failed:
        gates.append(verdict('commands', 'SKIPPED', 'an earlier gate failed'))
    else:
        checks = quality().run_checks(repo, commands, settings.get('timeout', 600))
        report['commands'] = checks
        detail = '; '.join('%s rc=%s%s' % (shlex.join(c)[:60], k['returncode'],
                                           ' timeout' if k['timed_out'] else '')
                           for c, k in zip(commands, checks['checks']))
        if settings.get('expect_red'):
            # Red phase: the new tests must fail now. Cause (assertion vs. import error)
            # is not verifiable from hashed output: the green phase and review confirm it.
            red = checks['verdict'] != 'PASS' and not any(k['timed_out'] for k in checks['checks'])
            gates.append(verdict('red', 'PASS' if red else 'FAIL',
                                 detail + ('' if red else ' (tests must fail before implementation)')))
            failed = not red
        else:
            gates.append(verdict('commands', 'PASS' if checks['verdict'] == 'PASS' else 'FAIL', detail))
            failed = checks['verdict'] != 'PASS'
    report['verdict'] = 'BLOCKED' if failed else 'PASS'
    if not failed:
        snapshot = quality().snapshot(repo)
        report['snapshot'] = snapshot
        if plan_sha256:
            report['acceptance_evidence'] = {
                'status': 'PASS', 'orchestrator_verified': True,
                'source': 'agentic-gates.py deterministic gates; semantic review remains independent',
                'criteria': ['gate %s: %s' % (g['name'], g['detail']) for g in gates
                             if g['status'] in ('PASS', 'WARN')],
                'tests': ['%s -> rc %s%s, output sha256 %s' % (
                    shlex.join(c), k['returncode'], ' (red, expected)' if settings.get('expect_red') else '',
                    k['output_sha256'][:16])
                          for c, k in zip(commands, report['commands']['checks'])],
                'head': snapshot['head'], 'snapshot': snapshot, 'plan_sha256': plan_sha256}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='.', help='assigned worktree root')
    parser.add_argument('--base', required=True, help='commit the delegation started from')
    parser.add_argument('--file', action='append', required=True, help='declared file (repeat)')
    parser.add_argument('--command', action='append', default=[], help='trusted command (repeat)')
    parser.add_argument('--config', help='JSON config; its "gates" section supplies defaults')
    parser.add_argument('--plan-sha256')
    args = parser.parse_args()
    try:
        settings = json.loads(Path(args.config).read_text()).get('gates', {}) if args.config else {}
        commands = [shlex.split(c) for c in args.command] or settings.get('commands', [])
        result = run(args.repo, args.base, args.file, commands, settings, args.plan_sha256)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'verdict': 'BLOCKED', 'reason': str(error)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
