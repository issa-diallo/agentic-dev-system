#!/usr/bin/env python3
"""Strict observer of a Codex context transition across a TUI reconnection.

`snapshot` before the reconnection, `verify` after it. Exit 0 PASS, 1 BLOCKED, JSON on
stdout. Reasons are fixed codes: no prompt, title or server text is ever echoed.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

THREAD_ID = re.compile(r'[A-Za-z0-9-]{8,80}')
MAX_JSON = 256 * 1024 * 1024
MAX_ROLLOUT = 1024 * 1024 * 1024
AUXILIARY_NOTIFICATIONS = {
    'thread/started', 'thread/status/changed', 'thread/tokenUsage/updated',
    'thread/settings/updated', 'turn/started', 'turn/completed', 'item/started',
    'item/completed', 'item/agentMessage/delta', 'item/reasoning/summaryTextDelta',
    'item/reasoning/summaryPartAdded', 'item/reasoning/textDelta', 'turn/moderationMetadata'}
UNLOAD_METHODS = ('thread/unsubscribe', 'thread/closed')
AUXILIARY_ITEMS = {'agentMessage', 'userMessage', 'reasoning'}
RECEIPT_KEYS = ('transition_id', 'phase', 'thread_id', 'turn_id', 'attempts')


class Blocked(Exception):
    """A fixed reason code; never built from input content."""


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name.replace('-', '_') + '_observed', Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _refuse_constant(_):
    raise ValueError()       # NaN / Infinity are not JSON


def _read_json(path, code):
    try:
        with open(path, 'rb') as handle:
            data = handle.read(MAX_JSON + 1)
        if len(data) > MAX_JSON:
            raise ValueError()
        value = json.loads(data.decode('utf-8'), parse_constant=_refuse_constant)
    except (OSError, ValueError, TypeError, RecursionError):
        raise Blocked(code) from None
    if not isinstance(value, dict):
        raise Blocked(code)
    return value


# ------------------------------------------------------------------ runtime boundary

class LocalBackend:
    """Live boundary: RPC through the launcher's existing transport, /proc for processes."""
    def __init__(self):
        self._rpc = _load('agentic-context-launch').RealBackend().rpc

    def rpc(self, endpoint, method, params):
        return self._rpc(endpoint, method, params)

    def processes(self, endpoints):
        wanted, found = {'unix://' + endpoint for endpoint in endpoints}, []
        for entry in os.listdir('/proc'):
            if not entry.isdigit():
                continue
            try:
                if os.stat('/proc/' + entry).st_uid != os.getuid():
                    continue
                raw = Path('/proc/%s/cmdline' % entry).read_bytes().split(b'\0')
                argv = [part.decode('utf-8', 'surrogateescape') for part in raw[:-1]]
                if not wanted.intersection(argv):
                    continue
                stat = Path('/proc/%s/stat' % entry).read_text()
                found.append({'pid': int(entry), 'uid': os.getuid(),
                              'starttime': stat[stat.rindex(')') + 2:].split()[19],
                              'exe': os.readlink('/proc/%s/exe' % entry), 'argv': argv})
            except (OSError, ValueError, IndexError):
                continue     # exited or unreadable: cannot be matched
        return found


# ------------------------------------------------------------------ files

def _rollouts(home, thread):
    paths = []
    for name in ('sessions', 'archived_sessions'):
        paths += [path for path in (home / name).rglob('rollout-*-%s.jsonl' % thread)
                  if path.is_file() and not path.is_symlink()]
    return paths


def _count(paths):
    """Whole-rollout task events. Returns (started ids, completed ids, valid)."""
    started, completed, valid = [], [], True
    for path in paths:
        try:
            if path.stat().st_size > MAX_ROLLOUT:
                valid = False
                continue
            with path.open('rb') as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        valid = False
                        continue
                    payload = row.get('payload') if isinstance(row, dict) else None
                    if not isinstance(row, dict):
                        valid = False
                    elif row.get('type') == 'event_msg' and isinstance(payload, dict):
                        if payload.get('type') == 'task_started':
                            started.append(payload.get('turn_id'))
                        elif payload.get('type') == 'task_complete':
                            completed.append(payload.get('turn_id'))
        except OSError:
            valid = False
    return started, completed, valid


# ------------------------------------------------------------------ naming proof

HEX = re.compile(r'[0-9a-f]{64}')


def _optional(event, key, check):
    return key not in event or check(event[key])


def _is_ident(value):
    return not isinstance(value, bool) and isinstance(value, (str, int))


def _event_valid(event):
    """Structure of one capture event. The observer never trusts a summary field by type."""
    if not isinstance(event, dict) or 'conflict' in event or 'shape_invalid' in event:
        return False
    kind = event.get('kind')
    if not (isinstance(event.get('connection'), str) and event.get('direction') in ('client', 'server')
            and kind in ('request', 'notification', 'response') and type(event.get('seq')) is int):
        return False
    if kind == 'response':
        if not isinstance(event.get('ok'), bool) or 'method' in event:
            return False
    elif not isinstance(event.get('method'), str):
        return False
    if kind != 'notification' and 'id' not in event:
        return False
    items = event.get('turn_items', [])
    text = lambda value: isinstance(value, str)
    digest = lambda value: isinstance(value, str) and bool(HEX.fullmatch(value))
    flag = lambda value: isinstance(value, bool)
    if not (isinstance(items, list) and all(
            isinstance(item, dict) and isinstance(item.get('type'), str)
            and _optional(item, 'id', _is_ident) and _optional(item, 'phase', text)
            and _optional(item, 'output_sha256', digest)
            and _optional(item, 'output_ambiguous', flag) for item in items)):
        return False
    return (all(_optional(event, key, _is_ident) for key in ('id', 'thread', 'turn', 'item_id'))
            and all(_optional(event, key, text) for key in ('item', 'phase', 'client', 'status'))
            and all(_optional(event, key, digest) for key in ('output_sha256', 'name_sha256'))
            and all(_optional(event, key, lambda value: isinstance(value, bool))
                    for key in ('ephemeral', 'output_ambiguous')))


def _capture_valid(capture):
    events = capture['events']
    if not all(_event_valid(event) for event in events):
        return False
    # The collector numbers every retained event 1, 2, 3...: a start elsewhere or any gap
    # means events were lost (delta coalescing does not consume a number).
    return all(event['seq'] == index for index, event in enumerate(events, 1))


def _answer(events, request):
    """The only server response to this request on its connection, else None."""
    same = [e for e in events if e['connection'] == request['connection']]
    if len([e for e in same if e['direction'] == 'client' and e['kind'] == 'request'
            and e.get('id') == request.get('id')]) != 1:
        return None
    answers = [e for e in same if e['direction'] == 'server' and e['kind'] == 'response'
               and e.get('id') == request.get('id') and e['seq'] > request['seq']]
    return answers[0] if len(answers) == 1 and answers[0].get('ok') else None


def _plain_items(event):
    """Every embedded item of this event is a known non-tool kind."""
    return all(item.get('type') in AUXILIARY_ITEMS for item in event.get('turn_items', []))


def _unload_valid(events, mine, start, ask, turn, done):
    """Moderation metadata, unsubscribe and close of the auxiliary, each under exact correlation."""
    same = lambda e, direction, kind: (e['connection'] == start['connection']
                                       and e['direction'] == direction and e['kind'] == kind)
    for event in mine:
        if event.get('method') == 'turn/moderationMetadata' and not (
                same(event, 'server', 'notification') and event.get('turn') == turn
                and ask['seq'] < event['seq'] < done['seq']):
            return False
    unsubs = [e for e in mine if e.get('method') == 'thread/unsubscribe']
    closed = [e for e in mine if e.get('method') == 'thread/closed']
    if len(unsubs) > 1 or len(closed) > 1:
        return False
    ack = None
    if unsubs:
        ack = _answer(events, unsubs[0])
        if not (same(unsubs[0], 'client', 'request') and unsubs[0]['seq'] > done['seq'] and ack):
            return False
    if closed:
        if not (ack and same(closed[0], 'server', 'notification') and closed[0]['seq'] > ack['seq']
                and not any(e['seq'] > closed[0]['seq'] for e in mine)):
            return False
    return True


def _prove_naming(events, start, product):
    """Proof for one thread/start that is not the product thread. Returns (proof, step)."""
    connection = [e for e in events if e['connection'] == start['connection']]
    answer = _answer(events, start)
    init = connection[0]
    init_answer = _answer(events, init) if init['kind'] == 'request' else None
    if not (init['direction'] == 'client' and init.get('method') == 'initialize'
            and init.get('client') == 'codex-tui' and init_answer
            and init_answer['seq'] < start['seq']):
        return None, 'initialize'
    if not (str(start.get('id')).startswith('temporary-structured')
            and start.get('ephemeral') is True and answer
            and answer.get('ephemeral') is True and answer.get('thread')
            and answer['thread'] != product):
        return None, 'start'
    aux = answer['thread']
    turns = [e for e in events if e.get('thread') == aux and e['direction'] == 'client'
             and e['kind'] == 'request' and e.get('method') == 'turn/start']
    turn_answer = _answer(events, turns[0]) if len(turns) == 1 else None
    if not (turn_answer and isinstance(turn_answer.get('turn'), str)
            and turns[0]['connection'] == start['connection']
            and turns[0]['seq'] > answer['seq']):
        return None, 'turn'
    turn, ask = turn_answer['turn'], turns[0]
    # Embedded items of the two responses carry the same tool-free requirement.
    if not all(_plain_items(e) for e in (answer, turn_answer)):
        return None, 'activity'
    for event in events:
        involved = event.get('thread') == aux or (
            event['connection'] == start['connection'] and event['direction'] == 'server'
            and event['kind'] == 'request' and event.get('thread') is None)
        if not involved or event is answer or event is ask:
            continue
        if event.get('method') in UNLOAD_METHODS and event.get('thread') == aux:
            continue                 # exact correlation is proven below, after completion
        # Notifications may precede or follow the turn/start response (protocol order is
        # not assumed), but every turn-scoped one must follow the request itself.
        scoped = event.get('turn') is not None or event.get('method', '').startswith(('turn/', 'item/'))
        if not (event['connection'] == start['connection'] and event['direction'] == 'server'
                and event['kind'] == 'notification'
                and event.get('method') in AUXILIARY_NOTIFICATIONS
                and event['seq'] > start['seq'] and (not scoped or event['seq'] > ask['seq'])
                and event.get('turn') in (None, turn)
                and event.get('item', 'agentMessage') in AUXILIARY_ITEMS
                and _plain_items(event)):
            return None, 'activity'
    mine = [e for e in events if e.get('thread') == aux]
    for method in ('thread/started', 'turn/started', 'turn/completed'):
        if len([e for e in mine if e.get('method') == method]) > 1:
            return None, 'activity'          # a lifecycle step happens once
    finals = [e for e in mine if e.get('turn') == turn
              and e.get('method') == 'item/completed' and e.get('item') == 'agentMessage'
              and e.get('phase') == 'final_answer']
    done = [e for e in mine if e.get('turn') == turn
            and e.get('method') == 'turn/completed' and e.get('status') == 'completed']
    if len(finals) != 1 or len(done) != 1 or done[0]['seq'] < finals[0]['seq']:
        return None, 'completion'
    if any(e['seq'] > done[0]['seq'] and e.get('method') not in (
            'thread/status/changed', 'thread/tokenUsage/updated') + UNLOAD_METHODS for e in mine):
        return None, 'completion'            # nothing of the turn may follow its completion
    if not _unload_valid(events, mine, start, ask, turn, done[0]):
        return None, 'completion'
    title = finals[0].get('output_sha256')
    identity = finals[0].get('item_id')
    if finals[0].get('output_ambiguous') or not title or identity is None:
        return None, 'output'
    # Check canonical identity before type/phase: relabelling the same item cannot hide
    # a contradiction. Other nonfinal items remain legitimate on this auxiliary turn.
    final_identity = {'id': identity, 'type': 'agentMessage', 'phase': 'final_answer'}
    seen = {id(e): e for e in mine + [answer, turn_answer]}
    for event in seen.values():
        representations = [(item, True) for item in event.get('turn_items', [])]
        if 'item' in event:
            representations.append(({
                'id': event.get('item_id'), 'type': event['item'], 'phase': event.get('phase'),
                'output_sha256': event.get('output_sha256'),
                'output_ambiguous': event.get('output_ambiguous'),
            }, event.get('method') == 'item/completed'))
        for item, complete in representations:
            claims_final = item.get('type') == 'agentMessage' and item.get('phase') == 'final_answer'
            if item.get('id') != identity and not claims_final:
                continue
            if any(item.get(key) != value for key, value in final_identity.items()):
                return None, 'output'
            # An item/started body may contain partial text; only completed bodies and
            # embedded final summaries assert the final output. Deltas are not bodies.
            if complete and (item.get('output_ambiguous') is not False
                    or item.get('output_sha256') != title):
                return None, 'output'
    names = [e for e in connection if e['direction'] == 'client' and e['kind'] == 'request'
             and e.get('method') == 'thread/name/set' and e.get('thread') == product
             and e.get('name_sha256') == title and e['seq'] > done[0]['seq']]
    if len(names) != 1 or not _answer(events, names[0]):
        return None, 'name'
    return {'thread_id': aux, 'connection': start['connection'], 'turn_id': turn,
            'title_sha256': title, 'proof': 'tui-naming-chain'}, None


def _analyze(capture, product):
    """Targeted proof over the whole capture. Returns (proven auxiliaries, reasons)."""
    events, reasons, proven = capture['events'], [], {}
    for start in events:
        if not (start['direction'] == 'client' and start['kind'] == 'request'
                and start.get('method') == 'thread/start'):
            continue
        answer = _answer(events, start)
        if answer and answer.get('thread') == product and answer.get('ephemeral') is not True:
            continue
        proof, step = _prove_naming(events, start, product)
        if proof:
            proven[proof['thread_id']] = proof
        else:
            reasons.append('naming-' + step)
    return proven, reasons


# ------------------------------------------------------------------ observation

def _role(record, upstream, tui):
    argv = record.get('argv')
    argv = argv if isinstance(argv, list) else []
    ends = ('unix://' + upstream, 'unix://' + tui)
    if not any(part in ends for part in argv):
        return 'other'
    if (os.path.basename(str(record.get('exe'))) != 'codex' or record.get('uid') != os.getuid()):
        return 'wrapper'
    if 'app-server' in argv and ('--listen', 'unix://' + upstream) in zip(argv, argv[1:]):
        return 'server'
    if ('--remote', 'unix://' + tui) in zip(argv, argv[1:]):
        return 'tui'
    return 'wrapper'


def _observe(command, request, before, backend):
    """Collect everything; `raw` holds the strict legacy rule, `all` the reconciled one."""
    raw, extra, report = [], [], {
        'version': 1, 'command': command, 'counts': {'task_started': 0, 'task_complete': 0},
        'auxiliary_threads': [], 'processes': [], 'loaded_threads': []}

    def fail(code, both=True):
        raw.append(code)
        if both:
            extra.append(code)
    try:
        paths = [request.get(key) for key in ('state', 'receipt', 'capture')]
        home = request.get('codex_home') or os.environ.get('CODEX_HOME') or Path.home() / '.codex'
        if not all(isinstance(path, str) for path in paths):
            raise Blocked('request-invalid')
        home = Path(home)
        state = _read_json(paths[0], 'state-invalid')
        product, turn_id = state.get('thread_id'), state.get('turn_id')
        server = state.get('server') if isinstance(state.get('server'), dict) else {}
        if not (isinstance(product, str) and THREAD_ID.fullmatch(product)
                and isinstance(turn_id, str) and turn_id and state.get('phase') == 'submitted'
                and isinstance(state.get('socket'), str)):
            raise Blocked('state-invalid')
    except Blocked as stop:
        fail(str(stop))
        return report, raw, extra, None
    try:
        receipt = _read_json(paths[1], 'receipt-invalid')
        if any(receipt.get(key) != state.get(key) for key in RECEIPT_KEYS):
            fail('receipt-mismatch')
    except Blocked as stop:
        fail(str(stop))
    # Whole rollout, always counted, even when another check refuses.
    files = _rollouts(home, product)
    started, completed, valid = _count(files)
    report['counts'] = {'task_started': len(started), 'task_complete': len(completed),
                        'files': len(files)}
    if not (len(files) == 1 and valid and started == [turn_id] and completed == [turn_id]):
        fail('rollout-turns')
    # Capture evidence.
    capture = None
    try:
        capture = _read_json(paths[2], 'capture-invalid')
        if (capture.get('version') != 1 or not isinstance(capture.get('errors'), list)
                or not isinstance(capture.get('events'), list)
                or capture.get('upstream_socket') != state['socket']
                or not isinstance(capture.get('tui_socket'), str)):
            raise Blocked('capture-invalid')
        if capture['errors']:
            raise Blocked('capture-errors')
        if not _capture_valid(capture):
            raise Blocked('capture-invalid')
    except Blocked as stop:
        capture = None
        fail(str(stop))
    backend = backend or LocalBackend()
    loaded = None
    try:
        data = backend.rpc(state['socket'], 'thread/loaded/list', {}).get('data')
        if not (isinstance(data, list) and all(isinstance(item, str) for item in data)):
            raise Blocked('loaded-invalid')
        loaded = data
        report['loaded_threads'] = list(data)
        if product not in data:
            fail('product-not-loaded')
        else:
            thread = backend.rpc(state['socket'], 'thread/read',
                                 {'threadId': product, 'includeTurns': False}).get('thread')
            thread = thread if isinstance(thread, dict) else {}
            if (thread.get('id') != product or thread.get('ephemeral') is True
                    or (thread.get('status') or {}).get('type') != 'idle'):
                fail('product-not-idle')
        if data != [product]:
            fail('loaded-set', both=False)       # legacy strict rule only
    except Exception as error:                   # transport/RPC failures carry no content
        fail(str(error) if isinstance(error, Blocked) else 'rpc-unavailable')
    server_identity = None
    if capture:
        rows = backend.processes([state['socket'], capture['tui_socket']])
        roles = [(row, _role(row, state['socket'], capture['tui_socket'])) for row in rows]
        report['processes'] = [
            {'pid': row.get('pid'), 'starttime': row.get('starttime'), 'role': role,
             'exe': os.path.basename(str(row.get('exe')))} for row, role in roles]
        servers = [row for row, role in roles if role == 'server']
        if (len(servers) != 1 or str(servers[0].get('pid')) != str(server.get('pid'))
                or str(servers[0].get('starttime')) != str(server.get('starttime'))):
            fail('server-identity')
        else:
            server_identity = {'pid': servers[0]['pid'], 'starttime': str(servers[0]['starttime'])}
        if len([1 for _, role in roles if role == 'tui']) != 1:
            fail('tui-process')
        try:
            proven, reasons = _analyze(capture, product)
        except Exception:                        # never lose the counters or leak a message
            proven, reasons = {}, ['capture-invalid']
        extra.extend(reasons)
        unknown = [item for item in (loaded or []) if item != product and item not in proven]
        if unknown:
            extra.append('loaded-thread-unproven')
        for thread in proven:
            if _rollouts(home, thread):
                extra.append('auxiliary-rollout')
        loaded_aux = set(loaded or []) - {product}
        for thread, row in proven.items():
            report['auxiliary_threads'].append(dict(row, loaded=thread in loaded_aux))
        report['capture'] = {'events': len(capture['events']),
                             'connections': len(capture.get('connections') or {})}
    baseline = {'transition_id': state.get('transition_id'), 'thread_id': product,
                'turn_id': turn_id, 'server': server_identity,
                'auxiliary': sorted({row['thread_id'] for row in report['auxiliary_threads']}
                                    | (set(loaded or []) - {product}))}
    return report, raw, extra, baseline


def _compare(before, baseline, report, extra):
    """Verify-only: the post-reconnection state must continue the snapshot."""
    old = before.get('baseline') if isinstance(before, dict) else None
    if (not isinstance(old, dict) or before.get('command') != 'snapshot'
            or before.get('verdict') != 'PASS'):
        extra.append('before-invalid')
        return
    if baseline is None or any(old.get(key) != baseline.get(key) for key in
                               ('transition_id', 'thread_id', 'turn_id', 'server')):
        extra.append('transition-changed')
    elif not set(baseline['auxiliary']) <= set(old.get('auxiliary') or []):
        extra.append('auxiliary-after-snapshot')


def observe(command, request, before=None, backend=None):
    request = request if isinstance(request, dict) else {}
    report, raw, extra, baseline = _observe(command, request, before, backend)
    if command == 'verify':
        _compare(before, baseline, report, extra)
    report['raw_reasons'], report['reasons'] = raw, extra
    report['raw_verdict'] = 'BLOCKED' if raw else 'PASS'
    report['verdict'] = 'BLOCKED' if extra else 'PASS'
    if command == 'snapshot':
        report['baseline'] = baseline
    return report


def snapshot(request, backend=None):
    return observe('snapshot', request, backend=backend)


def verify(request, before, backend=None):
    return observe('verify', request, before, backend)


def _blocked(code):
    return {'version': 1, 'verdict': 'BLOCKED', 'raw_verdict': 'BLOCKED', 'reasons': [code],
            'raw_reasons': [code], 'auxiliary_threads': [], 'processes': [],
            'counts': {'task_started': 0, 'task_complete': 0}}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Observateur strict de reconnexion de contexte.')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('snapshot', 'verify'):
        command = sub.add_parser(name)
        command.add_argument('--request', required=True, help='JSON: state, receipt, capture, codex_home')
        if name == 'verify':
            command.add_argument('--before', required=True, help='stdout JSON du snapshot')
    args = parser.parse_args(argv)
    try:
        request = _read_json(args.request, 'request-invalid')
        before = None
        if args.command == 'verify':
            try:
                before = _read_json(args.before, 'before-invalid')
            except Blocked:
                pass        # verify then reports 'before-invalid' and keeps its rollout counters
        report = observe(args.command, request, before)
    except Blocked as stop:
        report = _blocked(str(stop))
    except Exception:
        report = _blocked('observer-error')
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
