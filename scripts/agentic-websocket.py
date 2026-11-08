#!/usr/bin/env python3
"""Bounded local WebSocket JSON transport over `codex app-server proxy`."""
import base64
import hashlib
import json
import os
import selectors
import struct
import subprocess
import time


MAX_MESSAGE = 1024 * 1024
MAX_HEADERS = 16384
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


class TransportError(Exception):
    """Unavailable or invalid local transport, without server-content leakage."""


class WebSocketProxy:
    def __init__(self, socket_path, deadline):
        self.command = ['codex', 'app-server', 'proxy']
        if socket_path is not None:
            self.command += ['--sock', str(socket_path)]
        self.deadline, self.buffer = deadline, bytearray()
        self.process, self.selector = None, selectors.DefaultSelector()

    def __enter__(self):
        try:
            self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            os.set_blocking(self.process.stdout.fileno(), False)
            os.set_blocking(self.process.stdin.fileno(), False)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            self._handshake()
            return self
        except BaseException as error:
            # Failed __enter__ never triggers the context manager's __exit__.
            self.__exit__(None, None, None)
            if isinstance(error, (OSError, TransportError)):
                raise TransportError('Connexion WebSocket Codex indisponible.') from None
            raise

    def __exit__(self, *_):
        self.selector.close()
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=.5)
            self.process.stdin.close()
            self.process.stdout.close()

    def _remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TransportError('Délai WebSocket Codex dépassé.')
        return remaining

    def _write(self, payload):
        try:
            with selectors.DefaultSelector() as writer:
                writer.register(self.process.stdin, selectors.EVENT_WRITE)
                position = 0
                while position < len(payload):
                    if not writer.select(self._remaining()):
                        raise TransportError('Délai WebSocket Codex dépassé.')
                    try:
                        written = os.write(self.process.stdin.fileno(), payload[position:])
                        if not written:
                            raise TransportError('Connexion WebSocket Codex interrompue.')
                        position += written
                    except BlockingIOError:
                        continue
        except OSError:
            raise TransportError('Connexion WebSocket Codex interrompue.') from None

    def _receive(self):
        if not self.selector.select(self._remaining()):
            raise TransportError('Délai WebSocket Codex dépassé.')
        try:
            chunk = os.read(self.process.stdout.fileno(), 65536)
        except BlockingIOError:
            return
        except OSError:
            raise TransportError('Connexion WebSocket Codex interrompue.') from None
        if not chunk:
            raise TransportError('Connexion WebSocket Codex interrompue.')
        self.buffer.extend(chunk)

    def _exact(self, size):
        while len(self.buffer) < size:
            self._receive()
        self._remaining()
        data = bytes(self.buffer[:size])
        del self.buffer[:size]
        return data

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        request = ('GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n'
                   'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                   f'Sec-WebSocket-Key: {key}\r\n\r\n')
        self._write(request.encode('ascii'))
        while b'\r\n\r\n' not in self.buffer:
            if len(self.buffer) > MAX_HEADERS:
                raise TransportError('En-têtes WebSocket trop volumineux.')
            self._receive()
        offset = self.buffer.index(b'\r\n\r\n')
        if offset > MAX_HEADERS:
            raise TransportError('En-têtes WebSocket trop volumineux.')
        raw = self._exact(offset + 4)
        try:
            lines = raw.decode('ascii').split('\r\n')
            if len(lines[0].split()) < 2 or lines[0].split()[:2] != ['HTTP/1.1', '101']:
                raise ValueError()
            headers = {}
            for line in lines[1:]:
                if not line:
                    continue
                name, value = line.split(':', 1)
                name = name.strip().lower()
                if name in headers:
                    raise ValueError()
                headers[name] = value.strip()
            expected = base64.b64encode(hashlib.sha1((key + GUID).encode('ascii')).digest()).decode()
            if (headers.get('upgrade', '').lower() != 'websocket'
                    or 'upgrade' not in [v.strip().lower() for v in headers.get('connection', '').split(',')]
                    or headers.get('sec-websocket-accept') != expected
                    or 'sec-websocket-extensions' in headers):
                raise ValueError()
        except (UnicodeError, ValueError):
            raise TransportError('Handshake WebSocket Codex invalide.') from None

    def _send_frame(self, opcode, payload):
        size = len(payload)
        header = bytes([0x80 | opcode])
        if size < 126:
            header += bytes([0x80 | size])
        elif size < 65536:
            header += bytes([0x80 | 126]) + struct.pack('!H', size)
        else:
            header += bytes([0x80 | 127]) + struct.pack('!Q', size)
        mask = os.urandom(4)
        self._write(header + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))

    def send_json(self, message):
        try:
            payload = json.dumps(message, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ValueError, TypeError, UnicodeError):
            raise TransportError('Message JSON Codex invalide.') from None
        if len(payload) > MAX_MESSAGE:
            raise TransportError('Message JSON Codex trop volumineux.')
        self._send_frame(1, payload)

    def _frame(self, remaining):
        first, second = self._exact(2)
        final, opcode, size = bool(first & 0x80), first & 15, second & 127
        if first & 0x70 or second & 0x80 or opcode not in (0, 1, 8, 9, 10):
            raise TransportError('Trame WebSocket Codex invalide.')
        if size == 126:
            size = struct.unpack('!H', self._exact(2))[0]
            if size < 126:
                raise TransportError('Trame WebSocket Codex invalide.')
        elif size == 127:
            size = struct.unpack('!Q', self._exact(8))[0]
            if size < 65536 or size >= 2**63:
                raise TransportError('Trame WebSocket Codex invalide.')
        if opcode >= 8:
            if not final or size > 125:
                raise TransportError('Contrôle WebSocket Codex invalide.')
        elif size > remaining:
            raise TransportError('Message WebSocket Codex trop volumineux.')
        return final, opcode, self._exact(size)

    def read_json(self):
        fragments, started = bytearray(), False
        while True:
            final, opcode, payload = self._frame(MAX_MESSAGE - len(fragments))
            if opcode == 8:
                raise TransportError('Connexion WebSocket Codex fermée.')
            if opcode == 9:
                self._send_frame(10, payload)
                continue
            if opcode == 10:
                continue
            if (opcode == 0 and not started) or (opcode == 1 and started):
                raise TransportError('Fragmentation WebSocket Codex invalide.')
            fragments.extend(payload)
            if not final:
                started = True
                continue
            try:
                message = json.loads(fragments.decode('utf-8'))
                if not isinstance(message, dict):
                    raise ValueError()
                return message
            except (ValueError, UnicodeError):
                raise TransportError('Réponse JSON Codex invalide.') from None
