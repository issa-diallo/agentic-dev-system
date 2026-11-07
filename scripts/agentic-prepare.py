#!/usr/bin/env python3
"""Mechanical help for PREPARE: skeleton from detected stack, check, unit split.

init   writes a PREPARE skeleton with rubrics already marked N/A when the touched
       files make them irrelevant, the detected verification commands and tables.
check  verifies structure only (rubrics, AC->verification, open questions, TODO);
       it never grants PASS on content quality: review stays independent.
units  splits files into contract/data -> back -> front units with a default DAG.
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

RUBRICS = ['PRD', 'TRD', 'APP_FLOW', 'UX_UI_BRIEF', 'BACKEND_SCHEMA', 'IMPLEMENTATION_PLAN']
ORDER = ['contract', 'data', 'back', 'code', 'front', 'docs']
TRIVIAL = {'max_files': 2, 'max_lines': 30}
ROW = re.compile(r'^\|(.+)\|\s*$')


def detector():
    path = Path(__file__).with_name('agentic-detect.py')
    spec = importlib.util.spec_from_file_location('prepare_detect', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_trivial(files, lines, profiles):
    """Trivial ticket: tiny, single profile, no contract or data change."""
    return (len(files) <= TRIVIAL['max_files'] and lines <= TRIVIAL['max_lines']
            and len(set(profiles) - {'docs'}) <= 1 and not {'contract', 'data'} & set(profiles))


def units(files, root='.'):
    det = detector()
    found = det.detect(root, files)
    stack = set(found['stacks'])
    groups = {}
    for path in files:
        profile = det.profile_of(path, stack)
        groups.setdefault('code' if profile == 'test' else profile, []).append(path)
    for path in [f for f in files if det.profile_of(f, stack) == 'test']:
        owner = next((p for p in ('back', 'code', 'front') if p in groups and p != 'test'), None)
        if owner and path not in groups[owner]:
            groups[owner].append(path)
    ordered = [p for p in ORDER if p in groups]
    result, previous = [], None
    for profile in ordered:
        unit = {'id': profile, 'files': sorted(set(groups[profile])),
                'depends_on': [previous] if previous and profile in ('back', 'code', 'front') else []}
        if profile == 'front' and 'back' in ordered:
            unit['depends_on'] = ['back'] if not {'contract', 'data'} & set(ordered) else ['contract' if 'contract' in ordered else 'data', 'back']
        if profile in ('back', 'code') and {'contract', 'data'} & set(ordered):
            unit['depends_on'] = [p for p in ('contract', 'data') if p in ordered]
        result.append(unit)
        previous = profile
    return result


def init(ticket, files, root, mode=None, lines=0):
    det = detector()
    found = det.detect(root, files)
    profiles = found['profiles']
    mode = mode or ('LIGHT' if is_trivial(files, lines, profiles) else 'STANDARD')
    has_ui = 'front' in profiles
    has_data = bool({'back', 'data', 'contract'} & set(profiles))
    na = lambda reason: 'N/A — ' + reason
    out = ['# PREPARE — ' + ticket, '',
           'Mode : %s. Profils détectés : %s. Stacks : %s.' % (
               mode, ', '.join(profiles) or 'inconnu', ', '.join(found['stacks']) or 'inconnues'),
           '', '## Repères', 'Fichiers et décisions déjà connus (chemin : rôle). TODO', '',
           '## PRD', 'Problème, objectif, scope/non-scope. TODO', '',
           "Critères d'acceptation -> vérification :", '',
           '| AC | Vérification (commande ou preuve) |', '|---|---|', '| TODO | TODO |', '',
           '## TRD', 'Stack observée, contrats, dépendances. TODO', '',
           '## APP_FLOW', 'Parcours et états. TODO' if has_ui else na('aucun fichier front dans le périmètre'), '',
           '## UX_UI_BRIEF', 'Design system, responsive, accessibilité. TODO' if has_ui
           else na('aucune UI touchée'), '',
           '## BACKEND_SCHEMA', 'Modèles, contrats, auth, migrations. TODO' if has_data
           else na('aucune donnée ni API touchée'), '',
           '## IMPLEMENTATION_PLAN', 'Unités (contrat/données d\'abord) :', '']
    for unit in units(files, root):
        out.append('- %s : %s (dépend de : %s)' % (unit['id'], ', '.join(unit['files']),
                                                  ', '.join(unit['depends_on']) or 'rien'))
    out += ['', 'Vérification détectée :']
    out += ['- `%s` (%s)' % (' '.join(c['argv']), c['profile']) for c in found['commands']] or [
        '- aucune commande détectée : à fournir']
    out += ['- manque : ' + m for m in found['missing']]
    out += ['', '## Questions ouvertes', '', '| Question | Bloquante | Statut | Réponse |', '|---|---|---|---|',
            '', '## Gate PREPARE', '', 'Verdict : DRAFT. Preuves : TODO. Blockers : TODO.', '']
    return '\n'.join(out)


def section(text, name):
    match = re.search(r'^## %s\s*$(.*?)(?=^## |\Z)' % re.escape(name), text, re.M | re.S)
    return match.group(1).strip() if match else None


def rows(body):
    result = []
    for line in (body or '').splitlines():
        match = ROW.match(line.strip())
        if match and not set(match.group(1)) <= set('-| :'):
            result.append([c.strip() for c in match.group(1).split('|')])
    return result[1:]


def check(text):
    problems = []
    for name in RUBRICS + ['Gate PREPARE']:
        body = section(text, name)
        if body is None:
            problems.append('missing section ' + name)
        elif not body.startswith('N/A') and 'TODO' in body.replace('Preuves : TODO', '').replace(
                'Blockers : TODO', ''):
            problems.append('TODO left in ' + name)
        elif body.startswith('N/A') and len(body) < 8:
            problems.append('N/A without reason in ' + name)
    table = [r for r in rows(section(text, 'PRD')) if len(r) >= 2]
    if not table:
        problems.append('no acceptance criteria -> verification table')
    problems += ['criterion without verification: ' + r[0][:40] for r in table
                 if not r[1] or r[1].upper() == 'TODO']
    questions = rows(section(text, 'Questions ouvertes'))
    problems += ['blocking question open: ' + q[0][:40] for q in questions
                 if len(q) >= 3 and q[1].lower() in ('oui', 'yes') and q[2].lower() != 'résolue'
                 and q[2].lower() != 'resolved']
    return {'verdict': 'BLOCKED' if problems else 'READY', 'problems': problems,
            'note': 'READY is structural only; PASS needs independent review of content'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('init')
    a.add_argument('ticket')
    a.add_argument('--repo', default='.')
    a.add_argument('--file', action='append', default=[])
    a.add_argument('--mode')
    a.add_argument('--lines', type=int, default=0)
    b = sub.add_parser('check')
    b.add_argument('path')
    c = sub.add_parser('units')
    c.add_argument('--repo', default='.')
    c.add_argument('--file', action='append', required=True)
    args = parser.parse_args()
    if args.command == 'init':
        sys.stdout.write(init(args.ticket, args.file, args.repo, args.mode, args.lines))
        return 0
    if args.command == 'units':
        print(json.dumps(units(args.file, args.repo)))
        return 0
    result = check(Path(args.path).read_text())
    print(json.dumps(result))
    return 0 if result['verdict'] == 'READY' else 1


if __name__ == '__main__':
    sys.exit(main())
