#!/usr/bin/env python3
"""Read-only companion panel for observed Codex subagents; no agent control."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import unicodedata


ENTER = '\x1b[?1049h\x1b[?25l'
LEAVE = '\x1b[?25h\x1b[?1049l'
CLEAR = '\x1b[H\x1b[2J'
COLORS = {'explorer': '\x1b[34m', 'implementer': '\x1b[32m', 'reviewer': '\x1b[35m'}
RESET = '\x1b[0m'


def load_observer():
    path = Path(__file__).with_name('agentic-observe.py')
    spec = importlib.util.spec_from_file_location('agentic_panel_observer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_text(value):
    """Untrusted metadata cannot add terminal controls, new rows or bidi overrides."""
    if not isinstance(value, str):
        return ''
    return ''.join(' ' if char in '\n\r\t' else char for char in value
                   if char in '\n\r\t' or not unicodedata.category(char).startswith('C')
                   and char not in '\u2028\u2029')


def cell_width(char):
    return 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in 'WF' else 1


def clip(value, width):
    result, used = [], 0
    for char in safe_text(value):
        size = cell_width(char)
        if used + size > width:
            break
        result.append(char)
        used += size
    return ''.join(result)


def pad(value, width):
    value = clip(value, width)
    return value + ' ' * max(0, width - sum(map(cell_width, value)))


def colors_enabled(mode, tty):
    if mode != 'auto':
        return mode == 'always'
    return tty and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb'


def role_color(role):
    role = safe_text(role)
    for prefix in ('agentic-', 'agentic_'):
        if role.startswith(prefix):
            role = role[len(prefix):]
            break
    return COLORS.get(role, '')


def state_text(agent):
    status = safe_text(agent.get('status'))
    if status == 'active':
        flags = agent.get('active_flags', [])
        if isinstance(flags, list) and 'waitingOnApproval' in flags:
            return 'attente approbation'
        if isinstance(flags, list) and 'waitingOnUserInput' in flags:
            return 'attente réponse'
        return 'actif'
    return {'idle': 'au repos', 'notLoaded': 'non chargé', 'systemError': 'erreur'}.get(status, 'inconnu')


def agent_row(agent, width, color):
    role = safe_text(agent.get('role')) or 'inconnu'
    name = safe_text(agent.get('nickname')) or safe_text(agent.get('id')) or '?'
    state = state_text(agent)
    if width < 30:
        return clip(role + ' : ' + state, width)
    role_width, name_width = min(24, width // 3), min(22, width // 3)
    plain_role = pad(role, role_width)
    state = clip(state, max(0, width - role_width - name_width - 4))
    selected = role_color(role) if color else ''
    shown_role = selected + plain_role + RESET if selected else plain_role
    return shown_role + '  ' + pad(name, name_width) + '  ' + state


def render(snapshot=None, width=80, height=24, color=False, unavailable=False):
    """Render a bounded frame; stale rows are never used for an unavailable source."""
    width, height = max(1, width), max(1, height)
    if unavailable:
        lines = ['Agents', 'Source Codex indisponible.',
                 'Les états précédents ne sont pas affichés.',
                 'Vérifier la session Codex et la connexion.']
        return '\n'.join(clip(line, width) for line in lines[:height])
    data = snapshot if isinstance(snapshot, dict) else {}
    title = 'Agents — ' + (safe_text(data.get('repo')) or 'dépôt inconnu')
    if height < 6:
        return '\n'.join(clip(line, width) for line in [title, 'Agrandir le terminal.'][:height])
    observed = safe_text(data.get('observed_at')) or 'inconnue'
    header = 'RÔLE / ÉTAT' if width < 30 else (
        pad('RÔLE', min(24, width // 3)) + '  ' + pad('NOM / ID', min(22, width // 3)) + '  ÉTAT')
    lines = [clip(title, width), clip('Observation : ' + observed, width), '',
             clip(header, width),
             '-' * width]
    agents = data.get('agents', [])
    agents = [agent for agent in agents if isinstance(agent, dict)] if isinstance(agents, list) else []
    available = max(0, height - len(lines) - 2)
    if agents:
        lines.extend(agent_row(agent, width, color) for agent in agents[:available])
    else:
        lines.append(clip('Aucun sous-agent observé.', width))
    if data.get('truncated') or len(agents) > available:
        lines.append(clip('Liste tronquée.', width))
    lines.append(clip('États d’exécution uniquement.', width))
    return '\n'.join(lines[:height])


def finite_number(minimum, maximum):
    def parse(value):
        try:
            number = float(value)
        except ValueError:
            raise argparse.ArgumentTypeError('Un nombre fini est requis.') from None
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f'Valeur finie entre {minimum} et {maximum} requise.')
        return number
    return parse


def count(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('Un entier entre 1 et 200 est requis.') from None
    if not 1 <= number <= 200:
        raise argparse.ArgumentTypeError('Un entier entre 1 et 200 est requis.')
    return number


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--repo', default='.', help='Dépôt à observer (et ses worktrees Git).')
    result.add_argument('--socket', help='Socket de contrôle du serveur Codex existant.')
    result.add_argument('--timeout', type=finite_number(0.001, 60), default=5,
                        help='Délai par observation en secondes, maximum 60.')
    result.add_argument('--limit', type=count, default=50, help='Nombre maximal de sous-agents (1 à 200).')
    result.add_argument('--interval', type=finite_number(0.2, 3600), default=2,
                        help='Rafraîchissement en secondes, entre 0.2 et 3600.')
    result.add_argument('--once', action='store_true', help='Afficher une seule observation.')
    result.add_argument('--json', action='store_true', help='Émettre un snapshot JSON unique, sans couleurs.')
    result.add_argument('--color', choices=('auto', 'always', 'never'), default='auto',
                        help='Couleurs ; always prime explicitement sur NO_COLOR.')
    return result


def observe(args, backend):
    try:
        data = backend.snapshot(repo=args.repo, socket_path=args.socket,
                                timeout=args.timeout, limit=args.limit)
        if not isinstance(data, dict) or not isinstance(data.get('agents'), list):
            return None
        return data
    except (backend.ObservationError, ValueError, TypeError, KeyError):
        return None


def public_snapshot(data):
    """Keep the JSON view metadata-only even if a future source adds more fields."""
    rows = []
    for agent in data['agents'][:200]:
        if not isinstance(agent, dict):
            continue
        row = {key: safe_text(agent.get(key)) for key in ('id', 'role', 'nickname', 'status', 'cwd')}
        row['parent_id'] = safe_text(agent['parent_id']) if isinstance(agent.get('parent_id'), str) else None
        flags = agent.get('active_flags', [])
        row['active_flags'] = [safe_text(flag) for flag in flags if isinstance(flag, str)] if isinstance(flags, list) else []
        rows.append(row)
    return {'source': 'codex-app-server', 'observed_at': safe_text(data.get('observed_at')),
            'repo': safe_text(data.get('repo')), 'agents': rows,
            'truncated': bool(data.get('truncated')) or len(data['agents']) > 200}


def main(argv=None):
    args = parser().parse_args(argv)
    tty = sys.stdout.isatty()
    live = tty and not (args.once or args.json) and os.environ.get('TERM') != 'dumb'
    colored = colors_enabled(args.color, tty)
    try:
        backend = load_observer()
        if not callable(backend.snapshot) or not issubclass(backend.ObservationError, Exception):
            backend = None
    except (ImportError, OSError, AttributeError, TypeError):
        backend = None
    try:
        if live:
            sys.stdout.write(ENTER)
            sys.stdout.flush()
        while True:
            data = observe(args, backend) if backend else None
            if args.json:
                payload = public_snapshot(data) if data is not None else {
                    'source': 'codex-app-server', 'error': 'Source Codex indisponible.'}
                sys.stdout.write(json.dumps(payload, ensure_ascii=False) + '\n')
            else:
                size = shutil.get_terminal_size(fallback=(80, 24))
                frame = render(data, width=size.columns, height=max(1, size.lines - 1),
                               color=colored, unavailable=data is None)
                sys.stdout.write((CLEAR if live else '') + frame + '\n')
            sys.stdout.flush()
            if not live:
                return 0 if data is not None else 1
            time.sleep(args.interval)
    except (KeyboardInterrupt, BrokenPipeError):
        return 0
    finally:
        if live:
            try:
                sys.stdout.write(LEAVE)
                sys.stdout.flush()
            except BrokenPipeError:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
