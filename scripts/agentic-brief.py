#!/usr/bin/env python3
"""Render a compact delegation brief and parse the structured handoff reply.

The brief is built only from a BUILD-validated delegation, so a cheaper model gets
a closed scope, exact commands and one reporting format. The reply is a claim:
mechanical gates, never this report, decide whether the work is acceptable.
"""
import argparse
import json
import re
import shlex
import sys
from pathlib import Path

FENCE = '`' * 3
STATUSES = ('COMPLETED', 'BLOCKED')
REPLY = re.compile(FENCE + r'handoff[ \t]*\r?\n(.*?)\r?\n?' + FENCE, re.DOTALL)
EXAMPLE = ('{"status":"COMPLETED|BLOCKED","summary":"...","files":["..."],'
           '"tests":[{"command":"...","result":"PASS|FAIL|NOT_RUN"}],'
           '"blockers":[],"deviations":[]}')


def bullets(items):
    return '\n'.join('- ' + item for item in items)


def render(delegation, commands=None, skills=None, max_skill_chars=6000):
    """commands: trusted argv lists; skills: loaded dicts with 'path'/'instructions'."""
    parts = ['# Mission ' + delegation['pr'], 'Objectif : ' + delegation['objective'],
             "## Critères d'acceptation", bullets(delegation['acceptance']),
             '## Périmètre fermé',
             'Travaille dans le worktree courant (branche `%s`). Fichiers autorisés, '
             'liste exhaustive :' % delegation['branch'], bullets(delegation['files']),
             'Tout autre fichier modifié, créé ou supprimé invalide la mission. '
             'Ne lis que le nécessaire.', '## Vérification']
    if commands:
        parts += ['Exécute exactement ces commandes, sans les modifier, jusqu\'au succès :',
                  bullets('`%s`' % shlex.join(command) for command in commands)]
    parts += ['Tests attendus par le plan :', bullets(delegation['tests']),
              'Ajoute ou adapte les tests du comportement. Ne supprime, ne désactive '
              'et n\'assouplis aucun test existant.', '## Interdits',
              bullets(delegation['prohibitions'] + [
                  'Ne commite pas, ne pousse pas, ne fusionne pas.',
                  'Règle métier manquante ou périmètre insuffisant : arrête-toi et '
                  'réponds BLOCKED, n\'invente rien.'])]
    budget = max_skill_chars
    for skill in skills or []:
        text = skill['instructions'][:max(budget, 0)]
        budget -= len(text)
        if text:
            suffix = '' if len(text) == len(skill['instructions']) else '\n(tronqué)'
            parts += ['## Instructions : ' + Path(skill['path']).parent.name, text + suffix]
    parts += ['## Fin de mission', 'Termine ta réponse par exactement un bloc :',
              FENCE + 'handoff\n' + EXAMPLE + '\n' + FENCE]
    return '\n'.join(parts) + '\n'


def parse_handoff(text):
    """Return the last well-formed handoff block, or None. Never raises."""
    if not isinstance(text, str):
        return None
    for raw in reversed(REPLY.findall(text)):
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(data, dict) or data.get('status') not in STATUSES:
            continue
        lists = {key: data.get(key, []) for key in ('files', 'blockers', 'deviations')}
        if not all(isinstance(value, list) and all(isinstance(i, str) for i in value)
                   for value in lists.values()):
            continue
        tests = data.get('tests', [])
        if not isinstance(tests, list) or not all(isinstance(t, dict) for t in tests):
            continue
        return {'status': data['status'], 'summary': str(data.get('summary', ''))[:2000],
                'tests': tests[:20], **{k: v[:50] for k, v in lists.items()}}
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('delegation', help='JSON file: a delegation or BUILD output')
    parser.add_argument('--command', action='append', default=[], help='verification command')
    args = parser.parse_args()
    data = json.loads(Path(args.delegation).read_text())
    sys.stdout.write(render(data.get('delegation', data),
                            [shlex.split(command) for command in args.command]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
