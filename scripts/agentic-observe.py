#!/usr/bin/env python3
"""Read a minimal agent snapshot from an existing Codex app-server proxy."""
import argparse
import importlib.util
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import time
import unicodedata


MAX_MESSAGE = 1024 * 1024
SOURCES = ['subAgent', 'subAgentReview', 'subAgentCompact',
           'subAgentThreadSpawn', 'subAgentOther']


class ObservationError(Exception):
    """Observation is unavailable; never a verdict about an agent's work."""


def _text(value, default=''):
    if not isinstance(value, str):
        return default
    return ''.join(char for char in value
                   if not unicodedata.category(char).startswith('C'))[:500]


def _worktrees(repo, timeout):
    paths = {str(repo)}
    try:
        result = subprocess.run(['git', '-C', str(repo), 'worktree', 'list',
                                 '--porcelain', '-z'], capture_output=True,
                                timeout=min(timeout, 2), check=False)
        if result.returncode == 0:
            for field in result.stdout.split(b'\0'):
                if field.startswith(b'worktree '):
                    path = Path(os.fsdecode(field[9:])).resolve()
                    if path.is_dir():
                        paths.add(str(path))
    except (OSError, subprocess.TimeoutExpired):
        pass  # A non-Git directory can still be the cwd of a Codex session.
    return sorted(paths)


_SPEC = importlib.util.spec_from_file_location(
    'agentic_websocket', Path(__file__).with_name('agentic-websocket.py'))
_WS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_WS)


class _Proxy:
    def __init__(self, socket_path, deadline):
        self.transport = _WS.WebSocketProxy(socket_path, deadline)
        self.serial = 0

    def __enter__(self):
        try:
            self.transport.__enter__()
            return self
        except _WS.TransportError:
            raise ObservationError('Serveur Codex indisponible.') from None

    def __exit__(self, *args):
        return self.transport.__exit__(*args)

    def _send(self, message):
        try:
            self.transport.send_json(message)
        except _WS.TransportError:
            raise ObservationError('Connexion au serveur Codex indisponible.') from None

    def request(self, method, params):
        self.serial += 1
        self._send({'id':self.serial, 'method':method, 'params':params})
        while True:
            try:
                message = self.transport.read_json()
            except _WS.TransportError:
                raise ObservationError('Réponse du serveur Codex indisponible.') from None
            if type(message.get('id')) is not int or message['id'] != self.serial:
                continue
            if 'error' in message:
                raise ObservationError('Lecture du serveur Codex refusée.')
            result = message.get('result')
            if not isinstance(result, dict):
                raise ObservationError('Réponse Codex invalide.')
            return result


def _agents(data, allowed):
    if not isinstance(data, list) or len(data) > 200:
        raise ObservationError('Liste d’agents Codex invalide.')
    rows, seen = [], set()
    for thread in data:
        if not isinstance(thread, dict):
            raise ObservationError('Liste d’agents Codex invalide.')
        source, cwd = thread.get('source'), thread.get('cwd')
        if not isinstance(source, dict) or 'subAgent' not in source:
            continue
        if not isinstance(cwd, str):
            raise ObservationError('Métadonnées d’agent Codex invalides.')
        try:
            actual_cwd = str(Path(cwd).resolve())
        except (OSError, ValueError, RuntimeError):
            raise ObservationError('Métadonnées d’agent Codex invalides.') from None
        if actual_cwd not in allowed:
            continue
        identity = thread.get('id')
        if not isinstance(identity, str) or not identity:
            raise ObservationError('Métadonnées d’agent Codex invalides.')
        if identity in seen:
            continue
        seen.add(identity)
        subagent = source['subAgent']
        spawn = subagent.get('thread_spawn', {}) if isinstance(subagent, dict) else {}
        if not isinstance(spawn, dict):
            spawn = {}
        status = thread.get('status')
        status = status if isinstance(status, dict) else {}
        flags = status.get('activeFlags', [])
        if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
            raise ObservationError('Métadonnées d’agent Codex invalides.')
        parent = spawn.get('parent_thread_id')
        rows.append({'id':_text(identity),
                     'role':_text(thread.get('agentRole') or spawn.get('agent_role'), 'unknown') or 'unknown',
                     'nickname':_text(thread.get('agentNickname') or spawn.get('agent_nickname')),
                     'status':_text(status.get('type'), 'unknown') or 'unknown',
                     'active_flags':[_text(flag) for flag in flags],
                     'cwd':_text(actual_cwd),
                     'parent_id':_text(parent) if isinstance(parent, str) else None})
    return rows


def snapshot(repo='.', socket_path=None, timeout=5, limit=50):
    """Observe existing threads; this function never starts agents or model turns."""
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or timeout <= 0 or timeout > 60 or not math.isfinite(timeout)):
        raise ObservationError('Le délai doit être positif et ne pas dépasser 60 secondes.')
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ObservationError('La limite doit être comprise entre 1 et 200.')
    try:
        root = Path(repo).resolve()
        if not root.is_dir():
            raise ObservationError('Dépôt introuvable.')
        deadline = time.monotonic() + timeout
        allowed = _worktrees(root, timeout)
        with _Proxy(socket_path, deadline) as proxy:
            proxy.request('initialize', {'clientInfo':{'name':'agentic-observe', 'version':'1'},
                                         'capabilities':{'experimentalApi':True}})
            proxy._send({'method':'initialized', 'params':{}})
            result = proxy.request('thread/list', {'cwd':allowed, 'sourceKinds':SOURCES,
                                                   'modelProviders':[], 'useStateDbOnly':True,
                                                   'sortKey':'updated_at', 'limit':limit})
        rows = _agents(result.get('data'), set(allowed))
        return {'source':'codex-app-server',
                'observed_at':datetime.now(timezone.utc).isoformat(), 'repo':str(root),
                'agents':rows[:limit], 'truncated':bool(result.get('nextCursor')) or len(rows)>limit}
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ObservationError('Observation Codex indisponible.') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='.')
    parser.add_argument('--socket', dest='socket_path')
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()
    try:
        result = snapshot(**vars(args))
    except ObservationError as error:
        print(json.dumps({'error':str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
