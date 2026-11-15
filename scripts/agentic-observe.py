#!/usr/bin/env python3
"""Read a minimal agent snapshot from an existing Codex app-server proxy."""
import argparse
import importlib.util
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import stat
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

MAX_HEAD = 256 * 1024
MAX_TAIL = 2 * 1024 * 1024


def _unavailable(reason):
    return ObservationError('Mesure de contexte indisponible : %s.' % reason)


def _resolved(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return str(Path(value).resolve())
    except (OSError, ValueError, RuntimeError):
        return None


def _timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    try:
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _check(deadline):
    if time.monotonic() >= deadline:
        raise _unavailable('délai dépassé')


def _pread(descriptor, length, offset, deadline):
    """Chunked bounded read; the deadline is checked around every system call."""
    chunks = []
    while length > 0:
        _check(deadline)
        chunk = os.pread(descriptor, min(length, 65536), offset)
        if not chunk:
            break
        chunks.append(chunk)
        length -= len(chunk)
        offset += len(chunk)
    _check(deadline)
    return b''.join(chunks)


def _read_rollout(path, deadline):
    """Return (first line, complete lines of a bounded tail) from a regular file."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
    except (OSError, ValueError):
        raise _unavailable('journal de session illisible') from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise _unavailable('journal de session non régulier')
        size = info.st_size
        head = _pread(descriptor, min(size, MAX_HEAD), 0, deadline)
        first, newline, _ = head.partition(b'\n')
        if not newline:
            raise _unavailable('métadonnées de session absentes ou trop grandes')
        start = max(size - MAX_TAIL, 0)
        tail = _pread(descriptor, size - start, start, deadline)
    except OSError:
        raise _unavailable('journal de session illisible') from None
    finally:
        os.close(descriptor)
    lines = tail.split(b'\n')
    lines.pop()  # Trailing fragment: empty or a partial concurrent append.
    if start > 0 and lines:
        lines.pop(0)  # The window may begin inside a line.
    return first, lines


def _json_line(raw):
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


MAX_COUNT = 10 ** 12
MAX_AGE = 10 ** 9


def _count(value, minimum):
    if type(value) is not int or value < minimum or value > MAX_COUNT:
        return None
    return value


def snapshot_context(repo, thread_id, socket_path=None, timeout=5, max_age=120):
    """Measure current context occupancy of one thread; strictly read-only."""
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or timeout <= 0 or timeout > 60 or not math.isfinite(timeout)):
        raise ObservationError('Le délai doit être positif et ne pas dépasser 60 secondes.')
    if (isinstance(max_age, bool) or not isinstance(max_age, (int, float))
            or max_age <= 0 or max_age > MAX_AGE or not math.isfinite(max_age)):
        raise ObservationError('L’âge maximal doit être positif et borné.')
    if not isinstance(thread_id, str) or not thread_id or len(thread_id) > 200:
        raise ObservationError('Identifiant de thread invalide.')
    try:
        root = Path(repo).resolve()
        if not root.is_dir():
            raise ObservationError('Dépôt introuvable.')
        deadline = time.monotonic() + timeout
        allowed = set(_worktrees(root, timeout))
        with _Proxy(socket_path, deadline) as proxy:
            proxy.request('initialize', {'clientInfo':{'name':'agentic-observe', 'version':'1'},
                                         'capabilities':{'experimentalApi':True}})
            proxy._send({'method':'initialized', 'params':{}})
            result = proxy.request('thread/read', {'threadId':thread_id, 'includeTurns':False})
        thread = result.get('thread')
        if not isinstance(thread, dict) or thread.get('id') != thread_id:
            raise _unavailable('thread différent de celui demandé')
        cwd = _resolved(thread.get('cwd'))
        if cwd is None or cwd not in allowed:
            raise _unavailable('répertoire du thread non autorisé')
        path = thread.get('path')
        if not isinstance(path, str) or not path or '\0' in path:
            raise _unavailable('journal de session absent')
        first, lines = _read_rollout(path, deadline)
        meta = _json_line(first)
        payload = meta.get('payload') if meta and meta.get('type') == 'session_meta' else None
        if (not isinstance(payload, dict) or payload.get('id') != thread_id
                or _resolved(payload.get('cwd')) != cwd):
            raise _unavailable('métadonnées de session non confirmées')
        event = None
        for raw in reversed(lines):
            _check(deadline)
            if not raw.strip():
                continue
            row = _json_line(raw)
            if row is None:
                raise _unavailable('journal de session invalide après le compteur')
            body = row.get('payload') if row and row.get('type') == 'event_msg' else None
            if isinstance(body, dict) and body.get('type') == 'token_count':
                event = row
                break
        if event is None:
            raise _unavailable('aucun compteur de tokens récent')
        measured = _timestamp(event.get('timestamp'))
        if measured is None:
            raise _unavailable('date du compteur invalide')
        info = event['payload'].get('info')
        last = info.get('last_token_usage') if isinstance(info, dict) else None
        used = _count(last.get('total_tokens'), 0) if isinstance(last, dict) else None
        capacity = _count(info.get('model_context_window'), 1) if isinstance(info, dict) else None
        if used is None or capacity is None:
            raise _unavailable('usage ou capacité invalide')
        _check(deadline)
        observed = datetime.now(timezone.utc)
        if measured > observed:
            raise _unavailable('date du compteur dans le futur')
        if (observed - measured).total_seconds() > max_age:
            raise _unavailable('compteur obsolète')
        percent = used * 100 / capacity
        if used * 100 >= 50 * capacity:
            state = 'target_exceeded'
        elif used * 100 >= 40 * capacity:
            state = 'handoff_required'
        else:
            state = 'below_threshold'
        return {'source':'codex-rollout', 'thread_id':thread_id, 'repo':str(root),
                'observed_at':observed.isoformat(),
                'measured_at':measured.isoformat(),
                'model_context_window':capacity, 'used_tokens':used,
                'used_percent':round(percent, 2),
                'remaining_percent':round(max(100 - percent, 0), 2),
                'basis':'last_total_tokens/model_context_window',
                'threshold_state':state}
    except (OSError, ValueError, ArithmeticError, subprocess.SubprocessError):
        raise _unavailable('lecture impossible') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='.')
    parser.add_argument('--socket', dest='socket_path')
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--context-thread', dest='context_thread')
    parser.add_argument('--max-age', type=float, default=120)
    args = parser.parse_args()
    try:
        if args.context_thread is not None:
            result = snapshot_context(args.repo, args.context_thread, args.socket_path,
                                      args.timeout, args.max_age)
        else:
            result = snapshot(args.repo, args.socket_path, args.timeout, args.limit)
    except ObservationError as error:
        print(json.dumps({'error':str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
