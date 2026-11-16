#!/usr/bin/env python3
"""Passive, bounded capture of the Codex TUI <-> app-server WebSocket JSON protocol.

Evidence for agentic-context-observe.py only: metadata and SHA-256 digests, never prompts,
titles, transcripts or error texts. The relay forwards bytes unchanged and emits nothing.
"""
import argparse
import hashlib
import json
import os
import re
import select
import signal
import socket
import stat
import struct
import threading
import time
from datetime import datetime, timezone

VERSION = 1
MAX_EVENTS = 100000
MAX_HEADERS = 16384
IDENT = re.compile(r'[A-Za-z0-9._:/-]{1,128}')
METHOD = re.compile(r'[A-Za-z0-9._/-]{1,80}')


class CaptureError(Exception):
    """Setup failure; messages never contain payloads or paths' contents."""


def _ident(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return value if isinstance(value, str) and IDENT.fullmatch(value) else None


def _word(value):
    return value if isinstance(value, str) and METHOD.fullmatch(value) else None


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _output(text):
    """Digest of the final value: plain text or a JSON object with one string field.
    Returns (sha256 or None, ambiguous)."""
    if not isinstance(text, str):
        return None, True
    try:
        parsed = json.loads(text)
    except ValueError:
        return _digest(text), False
    if isinstance(parsed, dict):
        values = list(parsed.values())
        if len(values) == 1 and isinstance(values[0], str):
            return _digest(values[0]), False
        return None, True
    if isinstance(parsed, list):
        return None, True
    return _digest(text), False


def _dict(value):
    return value if isinstance(value, dict) else {}


def _embedded(turns):
    """Minimal metadata (type, id, phase, final-output hash) of every embedded item.
    Any unknown shape becomes an 'invalid' entry: it is never silently dropped."""
    entries = []
    for turn in turns:
        if 'items' not in turn:
            continue
        items = turn['items']
        if not isinstance(items, list):
            entries.append({'type': 'invalid'})
            continue
        for item in items:
            if not isinstance(item, dict):
                entries.append({'type': 'invalid'})
                continue
            entry = {'type': _word(item.get('type')) or 'invalid'}
            for key, value in (('id', _ident(item.get('id'))), ('phase', _word(item.get('phase')))):
                if value is not None:
                    entry[key] = value
            if entry['type'] == 'agentMessage' and entry.get('phase') == 'final_answer':
                digest, entry['output_ambiguous'] = _output(item.get('text'))
                if digest:
                    entry['output_sha256'] = digest
            entries.append(entry)
    return entries


def _summary(direction, message):
    """Filtered metadata of one JSON-RPC message; ValueError if not a JSON-RPC object."""
    if not isinstance(message, dict):
        raise ValueError('shape')
    params, result = _dict(message.get('params')), _dict(message.get('result'))
    event = {'direction': direction}
    if 'method' in message:
        event['kind'] = 'request' if 'id' in message else 'notification'
        event['method'] = _word(message['method']) or 'invalid'
    elif 'id' in message and ('result' in message or 'error' in message):
        event['kind'] = 'response'
        event['ok'] = 'error' not in message and 'result' in message
    else:
        raise ValueError('shape')
    if 'id' in message:
        event['id'] = _ident(message['id'])
    containers = (params, result)
    if any(box.get(key) is not None and not isinstance(box.get(key), dict)
           for box in containers for key in ('thread', 'turn', 'item')):
        event['shape_invalid'] = True
    threads = [_dict(box.get('thread')) for box in containers]
    turns = [_dict(box.get('turn')) for box in containers]
    thread_ids = {_ident(value) for value in [params.get('threadId')] + [t.get('id') for t in threads]
                  if _ident(value) is not None}
    turn_ids = {_ident(value) for value in [params.get('turnId')] + [t.get('id') for t in turns]
                if _ident(value) is not None}
    if len(thread_ids) > 1 or len(turn_ids) > 1:
        event['conflict'] = True             # contradictory identities: never resolved
    else:
        event['thread'] = next(iter(thread_ids), None)
        event['turn'] = next(iter(turn_ids), None)
    status = next((_word(t.get('status')) for t in turns if _word(t.get('status'))), None)
    ephemeral = [box.get('ephemeral') for box in [params] + threads if 'ephemeral' in box]
    for key, value in (('client', _ident(_dict(params.get('clientInfo')).get('name'))),
                       ('status', status), ('ephemeral', ephemeral[0] if ephemeral else None)):
        if isinstance(value, bool) or (isinstance(value, str) and key != 'ephemeral'):
            event[key] = value
    listed = [t if isinstance(t, dict) else {'items': None}
              for thread in threads if isinstance(thread.get('turns'), list)
              for t in thread['turns']]
    embedded = _embedded(turns + listed)
    if embedded:
        event['turn_items'] = embedded
    item = _dict(params.get('item'))
    if item:
        event['item'] = _word(item.get('type')) or 'invalid'
        event['phase'] = _word(item.get('phase'))
        event['item_id'] = _ident(item.get('id'))
        if event['item'] == 'agentMessage' and event['phase'] == 'final_answer':
            event['output_sha256'], event['output_ambiguous'] = _output(item.get('text'))
    if event.get('method') == 'thread/name/set':
        name = params.get('name')
        event['name_sha256'] = _digest(name) if isinstance(name, str) else None
    return {key: value for key, value in event.items() if value is not None}


class CaptureLog:
    """Ordered, bounded metadata log. A report taken while a connection is open is a
    checkpoint: nothing asserts that the connection's life has ended."""
    def __init__(self):
        self._lock = threading.Lock()
        self._events, self._errors = [], set()
        self._connections, self._seq = {}, 0

    def error(self, code):
        with self._lock:
            self._errors.add(code)

    def message(self, connection, direction, message):
        name = _ident(connection)
        try:
            if name is None or direction not in ('client', 'server'):
                raise ValueError('shape')
            event = _summary(direction, message)
        except ValueError:
            return self.error('invalid-message')
        with self._lock:
            if self._connections.get(name, {}).get('closed'):
                self._errors.add('message-after-close')
                return
            self._connections.setdefault(name, {'closed': False})
            last = self._events[-1] if self._events else None
            key = ('connection', 'direction', 'kind', 'method', 'thread', 'turn')
            event['connection'] = name
            if (last and 'delta' in event.get('method', '').lower()
                    and all(last.get(k) == event.get(k) for k in key)):
                last['count'] = last.get('count', 1) + 1   # token streams stay bounded
                return
            if len(self._events) >= MAX_EVENTS:
                self._errors.add('capture-overflow')
                return
            self._seq += 1
            event.update(seq=self._seq, mono_ms=int(time.monotonic() * 1000),
                         utc=datetime.now(timezone.utc).isoformat(timespec='milliseconds'))
            self._events.append(event)

    def close(self, connection):
        name = _ident(connection)
        with self._lock:
            if name is None:
                self._errors.add('invalid-message')
            else:
                self._connections.setdefault(name, {})['closed'] = True

    def report(self, transient=()):
        """`transient` codes describe the live state only; they are never stored."""
        with self._lock:
            return json.loads(json.dumps({
                'version': VERSION, 'errors': sorted(self._errors | set(transient)),
                'connections': self._connections, 'events': self._events}))


class _Wire:
    """Incremental parser for one direction: HTTP upgrade header, then WebSocket frames."""
    def __init__(self, limit):
        self.limit, self.buffer = limit, bytearray()
        self.upgraded, self.fragments, self.started = False, bytearray(), False
        self.dead = False

    def pending(self):
        return bool(self.buffer or self.fragments or self.started) or not self.upgraded

    def feed(self, data):
        """Yield JSON messages; raise ValueError(code) on unsupported or invalid wire."""
        self.buffer.extend(data)
        if not self.upgraded:
            end = self.buffer.find(b'\r\n\r\n')
            if end < 0:
                if len(self.buffer) > MAX_HEADERS:
                    raise ValueError('handshake-invalid')
                return
            head = bytes(self.buffer[:end]).split(b'\r\n')[0]
            del self.buffer[:end + 4]
            self.upgraded = True
            if head.startswith(b'HTTP/') and head.split()[1:2] != [b'101']:
                raise ValueError('handshake-rejected')
        while True:
            parsed = self._frame()
            if parsed is None:
                return
            message = self._assemble(*parsed)
            if message is not None:
                yield message

    def _frame(self):
        buffer = self.buffer
        if len(buffer) < 2:
            return None
        first, second = buffer[0], buffer[1]
        opcode, size, offset = first & 15, second & 127, 2
        if first & 0x70 or opcode not in (0, 1, 2, 8, 9, 10):
            raise ValueError('unsupported-wire')
        if size == 126:
            if len(buffer) < 4:
                return None
            size, offset = struct.unpack('!H', bytes(buffer[2:4]))[0], 4
        elif size == 127:
            if len(buffer) < 10:
                return None
            size, offset = struct.unpack('!Q', bytes(buffer[2:10]))[0], 10
        if opcode >= 8 and (not first & 0x80 or size > 125):
            raise ValueError('unsupported-wire')
        if size > self.limit:
            raise ValueError('oversized-message')
        head = offset + (4 if second & 0x80 else 0)
        if len(buffer) < head + size:
            return None
        mask = bytes(buffer[offset:head])
        payload = bytes(buffer[head:head + size])
        del buffer[:head + size]
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return bool(first & 0x80), opcode, payload

    def _assemble(self, final, opcode, payload):
        if opcode >= 8:
            return None
        if opcode == 2 or (opcode == 0) != self.started:
            raise ValueError('unsupported-wire')
        self.fragments.extend(payload)
        if len(self.fragments) > self.limit:
            raise ValueError('oversized-message')
        self.started = not final
        if not final:
            return None
        data, self.fragments = bytes(self.fragments), bytearray()
        try:
            return json.loads(data.decode('utf-8'))
        except ValueError:
            raise ValueError('invalid-json') from None


class CaptureProxy:
    """Private Unix relay: TUI -> tui_socket -> upstream_socket, bytes untouched.
    `timeout` bounds connection and WebSocket handshake; open sessions are never timed out."""
    def __init__(self, upstream_socket, tui_socket, timeout=5, max_message=1048576):
        self.upstream, self.tui = str(upstream_socket), str(tui_socket)
        self.timeout, self.max_message = timeout, max_message
        self.log, self._stop = CaptureLog(), threading.Event()
        self._threads, self._lock, self._count = [], threading.Lock(), 0
        self._listener = None
        # Serializes parsing+logging with report(): a report never sees half a feed.
        self._wire_lock, self._open = threading.Lock(), {}

    def __enter__(self):
        parent = os.path.dirname(os.path.abspath(self.tui))
        try:
            info = os.lstat(parent)
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077):
                raise CaptureError('Dossier de socket non privé refusé.')
            if os.path.lexists(self.tui):
                raise CaptureError('Endpoint déjà présent : refus, non réclamé.')
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                old = os.umask(0o177)
                try:
                    listener.bind(self.tui)
                finally:
                    os.umask(old)
                listener.listen(8)
                listener.settimeout(0.05)
            except BaseException:
                listener.close()
                raise
        except OSError:
            raise CaptureError('Socket de capture impossible à créer.') from None
        self._listener = listener
        thread = threading.Thread(target=self._accept, name='capture-accept')
        self._threads.append(thread)
        thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        joined = set()
        while True:
            with self._lock:
                pending = [t for t in self._threads if t not in joined]
            if not pending:
                break
            for thread in pending:
                thread.join(timeout=10)
                joined.add(thread)
        self._listener.close()
        try:
            os.unlink(self.tui)      # only the socket this proxy created
        except OSError:
            pass

    def report(self):
        """Checkpoint consistent with the parsers: an open connection holding an incomplete
        header/frame/fragment adds a transient 'incomplete-stream' error, absent from later
        reports once the bytes complete. A truncation at close is definitive."""
        with self._wire_lock:
            partial = any(wire.pending() and not wire.dead
                          for wires in self._open.values() for wire in wires.values())
            report = self.log.report(('incomplete-stream',) if partial else ())
        report.update(upstream_socket=self.upstream, tui_socket=self.tui)
        return report

    def _accept(self):
        while not self._stop.is_set():
            try:
                client = self._listener.accept()[0]
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                self._count += 1
                thread = threading.Thread(target=self._serve, args=(client, 'tui-%d' % self._count),
                                          name='capture-connection')
                self._threads.append(thread)
                thread.start()

    def _serve(self, client, name):
        upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            upstream.settimeout(self.timeout)
            upstream.connect(self.upstream)
            upstream.settimeout(None)
        except OSError:
            self.log.error('upstream-unavailable')
            upstream.close(), client.close()
            return
        dead, started = threading.Event(), time.monotonic()
        wires = {'client': _Wire(self.max_message), 'server': _Wire(self.max_message)}
        with self._wire_lock:
            self._open[name] = wires
        pumps = [threading.Thread(target=self._pump, name='capture-pump', args=(
            name, 'client', client, upstream, wires, dead, started))]
        with self._lock:
            self._threads.extend(pumps)
            pumps[0].start()
        self._pump(name, 'server', upstream, client, wires, dead, started)
        pumps[0].join()
        for sock in (client, upstream):
            sock.close()
        with self._wire_lock:
            if (any(wire.pending() for wire in wires.values())
                    and not any(wire.dead for wire in wires.values())):
                self.log.error('truncated-stream')
            self.log.close(name)
            del self._open[name]

    def _pump(self, name, direction, source, target, wires, dead, started):
        wire = wires[direction]
        while not (self._stop.is_set() or dead.is_set()):
            if (direction == 'server' and not wire.upgraded
                    and time.monotonic() - started > self.timeout):
                self.log.error('handshake-timeout')
                dead.set()
                break
            if not select.select([source], [], [], 0.05)[0]:
                continue
            try:
                data = source.recv(65536)
            except OSError:
                data = b''
            if not data:
                try:
                    target.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                return
            if not wire.dead:       # capture before forwarding: reports never lag the peer
                with self._wire_lock:
                    try:
                        for message in wire.feed(data):
                            self.log.message(name, direction, message)
                    except ValueError as error:
                        wire.dead = True
                        self.log.error(str(error) if str(error) in (
                            'handshake-invalid', 'handshake-rejected', 'unsupported-wire',
                            'oversized-message', 'invalid-json') else 'invalid-message')
            try:
                target.sendall(data)
            except OSError:
                dead.set()
                return
        dead.set()
        for sock in (source, target):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _write_report(path, report):
    temporary = path + '.tmp'
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False)
    os.replace(temporary, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Capture passive du protocole TUI Codex.')
    parser.add_argument('--upstream', required=True, help='socket du serveur dédié')
    parser.add_argument('--tui', required=True, help='socket privé à fournir au TUI')
    parser.add_argument('--report', required=True, help='rapport JSON local, réécrit en continu')
    args = parser.parse_args(argv)
    stop = threading.Event()
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, lambda *_: stop.set())
    try:
        with CaptureProxy(args.upstream, args.tui) as proxy:
            while not stop.wait(0.25):
                _write_report(args.report, proxy.report())
        _write_report(args.report, proxy.report())
    except (CaptureError, OSError) as error:
        print('BLOCKED: %s' % (error if isinstance(error, CaptureError) else 'rapport illisible'),
              flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
