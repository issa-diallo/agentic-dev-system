"""#119 AC1–5 / RM1–5: strict, private evidence for context reconnection.

Public contract (stdlib only; no Codex/model/process launch):
* capture.CaptureLog().message(connection, direction, JSON object), close(connection),
  report() -> JSON metadata. Directions are 'client' and 'server'. A report while
  the connection is alive is a checkpoint, not an assertion that its life ended.
* capture.CaptureProxy(upstream_socket, tui_socket, timeout=5, max_message=1048576)
  is a context manager: enter starts the private Unix relay, exit joins/stops it;
  report() has the same evidence contract as CaptureLog.report(), including an
  errors list. Runtime parsing/collection errors invalidate evidence in report();
  setup errors (including path collision) raise without leaking payloads.
* observer.snapshot(request, backend=None), verify(request, before, backend=None)
  return JSON dictionaries, including verdict/raw_verdict (PASS or BLOCKED),
  reasons, auxiliary_threads (entries with thread_id), counts (task_started and
  task_complete), and processes (entries with pid and role). Snapshot additionally
  carries the baseline needed by verify; callers do not synthesize proof booleans.
* request contains paths: state, receipt, capture, codex_home. The first three
  contain launcher state, launcher receipt, and CaptureLog/Proxy.report() JSON.
* A backend replaces only live RPC/process boundaries: rpc(endpoint, method,
  params) and processes(endpoints), returning observed records with pid, starttime,
  exe, argv, uid. Filesystem validation, proof and rollout counting stay real.
* CLI: snapshot --request FILE; verify --request FILE --before FILE. JSON stdout,
  exit 0 PASS / 1 BLOCKED. Save snapshot stdout as FILE for --before.

Fixtures deliberately contain private sentinels in prompts/titles/errors; neither
capture metadata nor observer output may retain them. Protocol fixtures cover the
supported subset of the 0.169 schema, not a claim about a live runtime's behavior.
RM6 / _identify chronology is a documentation/review check, not a source-text test.
"""
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import unittest


SOURCE = Path(__file__).resolve().parents[1]
CAPTURE = SOURCE / 'scripts/agentic-context-capture.py'
OBSERVER = SOURCE / 'scripts/agentic-context-observe.py'
PRODUCT = '019aaa11-1111-7111-8111-111111111111'
AUXILIARY = '019aaa11-2222-7222-8222-222222222222'
PRODUCT_TURN = '019aaa11-3333-7333-8333-333333333333'
AUXILIARY_TURN = '019aaa11-4444-7444-8444-444444444444'
OTHER_TURN = '019aaa11-5555-7555-8555-555555555555'
PROMPT = 'PRIVATE_PROMPT_SENTINEL_119'
TITLE = 'PRIVATE_TITLE_SENTINEL_119 élan'
ERROR = 'PRIVATE_SERVER_ERROR_SENTINEL_119'


def load_api(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def request(identifier, method, params):
    return {'id': identifier, 'method': method, 'params': params}


def notification(method, params):
    return {'method': method, 'params': params}


def naming_exchange(output=TITLE):
    """Actual request/response IDs, direction, turn and naming target matter."""
    return [
        ('client', request(1, 'initialize', {
            'clientInfo': {'name': 'codex-tui', 'version': '0.169.0'},
            'capabilities': {'experimentalApi': True}})),
        ('server', {'id': 1, 'result': {'userAgent': 'synthetic-codex'}}),
        ('client', notification('initialized', {})),
        ('client', request('temporary-structured-119', 'thread/start', {
            'ephemeral': True, 'dynamicTools': [], 'sandbox': 'read-only',
            'baseInstructions': PROMPT})),
        ('server', {'id': 'temporary-structured-119', 'result': {
            'thread': {'id': AUXILIARY, 'ephemeral': True, 'turns': []}}}),
        ('client', request(2, 'turn/start', {'threadId': AUXILIARY,
            'input': [{'type': 'text', 'text': PROMPT}],
            'sandboxPolicy': {'type': 'readOnly', 'networkAccess': False}})),
        ('server', {'id': 2, 'result': {'turn': {
            'id': AUXILIARY_TURN, 'status': 'inProgress', 'items': []}}}),
        ('server', notification('turn/started', {'threadId': AUXILIARY,
            'turn': {'id': AUXILIARY_TURN, 'status': 'inProgress', 'items': []}})),
        ('server', notification('item/completed', {'threadId': AUXILIARY,
            'turnId': AUXILIARY_TURN, 'completedAtMs': 100,
            'item': {'id': 'message-119', 'type': 'agentMessage',
                     'phase': 'final_answer', 'text': output}})),
        ('server', notification('turn/completed', {'threadId': AUXILIARY,
            'turn': {'id': AUXILIARY_TURN, 'status': 'completed', 'items': []}})),
        ('client', request(3, 'thread/name/set', {'threadId': PRODUCT, 'name': TITLE})),
        ('server', {'id': 3, 'result': {}}),
    ]


def capture_exchange(api, exchange, connection='tui-1', close=False):
    log = api.CaptureLog()
    for direction, message in exchange:
        log.message(connection, direction, copy.deepcopy(message))
    if close:
        log.close(connection)
    return log


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class RuntimeBoundary:
    """Read-only process/RPC fixture; never touches actual /proc or services."""
    def __init__(self, upstream, tui):
        self.loaded = [PRODUCT, AUXILIARY]
        self.calls = []
        self.records = [
            {'pid': 45001, 'starttime': '100', 'exe': '/opt/codex/bin/codex',
             'argv': ['codex', 'app-server', '--listen', 'unix://' + upstream],
             'uid': os.getuid()},
            {'pid': 45002, 'starttime': '101', 'exe': '/opt/codex/bin/codex',
             'argv': ['codex', '--remote', 'unix://' + tui], 'uid': os.getuid()},
            {'pid': 45003, 'starttime': '102', 'exe': '/usr/bin/python3',
             'argv': ['python3', 'wrapper.py', 'codex', '--remote', 'unix://' + tui],
             'uid': os.getuid()},
            {'pid': 45004, 'starttime': '103', 'exe': '/usr/bin/gnome-terminal',
             'argv': ['gnome-terminal', '--', 'codex', '--remote', 'unix://' + tui],
             'uid': os.getuid()},
        ]

    def rpc(self, endpoint, method, params):
        self.calls.append((endpoint, method, copy.deepcopy(params)))
        if method == 'thread/loaded/list':
            return {'data': list(self.loaded)}
        if method == 'thread/read':
            return {'thread': {'id': params['threadId'], 'status': {'type': 'idle'},
                               'ephemeral': False, 'turns': []}}
        raise AssertionError('Observer attempted a mutating or unexpected RPC: ' + method)

    def processes(self, endpoints):
        self.endpoints = list(endpoints)
        return copy.deepcopy(self.records)


class ObserverFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture = load_api(CAPTURE, 'context_capture_119_tests')
        cls.observer = load_api(OBSERVER, 'context_observer_119_tests')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='observe-119-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'codex-home'
        self.sessions = self.home / 'sessions/2026/11/16'
        self.sessions.mkdir(parents=True)
        self.upstream, self.tui = str(self.root / 'up.sock'), str(self.root / 'tui.sock')
        self.state = {'version': 1, 'transition_id': 'transition-119', 'phase': 'submitted',
            'thread_id': PRODUCT, 'turn_id': PRODUCT_TURN, 'attempts': 1,
            'socket': self.upstream, 'server': {'pid': 45001, 'starttime': '100'},
            'terminal': {'pid': 45003, 'starttime': '102'}, 'worktree': str(self.root)}
        self.receipt = {key: self.state[key] for key in
                        ('transition_id', 'phase', 'thread_id', 'turn_id', 'attempts')}
        self.observation = {name: str(self.root / (name + '.json'))
                            for name in ('state', 'receipt', 'capture')}
        self.observation['codex_home'] = str(self.home)
        write_json(Path(self.observation['state']), self.state)
        write_json(Path(self.observation['receipt']), self.receipt)
        self.log = capture_exchange(self.capture, naming_exchange())
        self.save_capture()
        self.runtime = RuntimeBoundary(self.upstream, self.tui)
        self.rollout = self.sessions / ('rollout-2026-11-16T12-00-00-' + PRODUCT + '.jsonl')
        self.write_rollout()

    def save_capture(self, report=None):
        report = self.log.report() if report is None else report
        # Endpoints belong to the collector's launch boundary, never naming evidence.
        report['upstream_socket'], report['tui_socket'] = self.upstream, self.tui
        write_json(Path(self.observation['capture']), report)

    def write_rollout(self, turns=(PRODUCT_TURN,), path=None):
        records = [{'type': 'session_meta', 'payload': {'id': PRODUCT}}]
        for turn in turns:
            records.extend({'type': 'event_msg', 'payload': {'type': event, 'turn_id': turn}}
                           for event in ('task_started', 'task_complete'))
        (path or self.rollout).write_text(''.join(json.dumps(row) + '\n' for row in records))

    def snapshot(self):
        return self.observer.snapshot(self.observation, backend=self.runtime)

    def verify(self, before):
        return self.observer.verify(self.observation, before, backend=self.runtime)

    def assert_private(self, report):
        serialized = json.dumps(report, ensure_ascii=False)
        for secret in (TITLE, PROMPT, ERROR):
            self.assertNotIn(secret, serialized)

    def assert_blocked(self, report, counts=(1, 1)):
        self.assertEqual(report['verdict'], 'BLOCKED')
        self.assertTrue(report['reasons'], 'Refusal must explain missing/invalid evidence')
        self.assertEqual((report['counts']['task_started'], report['counts']['task_complete']),
                         counts, 'Collect final rollout counters even on another refusal')
        self.assert_private(report)


class ObserverTests(ObserverFixture):
    def test_rm2_live_checkpoint_then_reconnect_reconciles_strict_raw_verdict(self):
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS')
        self.assertEqual(before['raw_verdict'], 'BLOCKED')
        self.log.close('tui-1')
        for direction, message in naming_exchange()[:3]:
            self.log.message('tui-2', direction, message)
        self.save_capture()
        after = self.verify(before)
        self.assertEqual(after['verdict'], 'PASS')
        self.assertEqual(after['raw_verdict'], 'BLOCKED')
        self.assertEqual([row['thread_id'] for row in after['auxiliary_threads']], [AUXILIARY])
        self.assertEqual(after['counts']['task_started'], 1)
        self.assertEqual(after['counts']['task_complete'], 1)
        self.assert_private(after)

    def test_rm2_plain_text_or_singleton_json_string_is_bound_to_applied_title(self):
        for output in (TITLE, json.dumps({'title': TITLE}, ensure_ascii=False)):
            with self.subTest(output_format='json' if output.startswith('{') else 'text'):
                self.log = capture_exchange(self.capture, naming_exchange(output))
                self.save_capture()
                report = self.verify(self.snapshot())
                self.assertEqual(report['verdict'], 'PASS')
                self.assert_private(report)
                self.assertIn(hashlib.sha256(TITLE.encode()).hexdigest(),
                              json.dumps(self.log.report()))

    def test_rm1_product_only_observation_keeps_both_verdicts_pass(self):
        self.runtime.loaded = [PRODUCT]
        self.log = capture_exchange(self.capture, naming_exchange()[:3])
        self.save_capture()
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS')
        after = self.verify(before)
        self.assertEqual((after['raw_verdict'], after['verdict']), ('PASS', 'PASS'))
        self.assertEqual(after['auxiliary_threads'], [])

    def test_rm2_incomplete_or_uncorrelated_naming_chain_is_blocked(self):
        variants = {}
        good = naming_exchange()
        variants['late capture'] = good[3:]
        variants['missing start response'] = good[:4] + good[5:]
        variants['missing turn response'] = good[:6] + good[7:]
        variants['missing final item'] = good[:8] + good[9:]
        variants['missing completed turn'] = good[:9] + good[10:]
        variants['missing name request'] = good[:10] + good[11:]
        variants['missing name response'] = good[:-1]
        variants['wrong order'] = good[:8] + good[10:] + good[8:10]
        for label, exchange in variants.items():
            with self.subTest(label=label):
                self.log = capture_exchange(self.capture, exchange)
                self.save_capture()
                self.assert_blocked(self.verify(self.snapshot()))

    def test_rm2_wrong_target_result_identity_or_ambiguous_output_is_blocked(self):
        variants = []
        for label, index, edit in (
            ('wrong client', 0, lambda m: m['params']['clientInfo'].update(name='other-client')),
            ('non temporary request', 3, lambda m: m.update(id='ordinary-request')),
            ('not ephemeral', 4, lambda m: m['result']['thread'].update(ephemeral=False)),
            ('unknown turn target', 5, lambda m: m['params'].update(threadId='unknown-aux')),
            ('wrong completed turn', 9, lambda m: m['params']['turn'].update(id=OTHER_TURN)),
            ('wrong naming target', 10, lambda m: m['params'].update(threadId=AUXILIARY)),
            ('different title', 10, lambda m: m['params'].update(name=TITLE + '!')),
            ('wrong response ID', 11, lambda m: m.update(id=999)),
            ('naming RPC failure', 11, lambda m: (m.pop('result'), m.update(
                error={'code': -1, 'message': ERROR}))),
        ):
            exchange = naming_exchange()
            edit(exchange[index][1])
            variants.append((label, exchange))
        for output in ('{"a":"one","b":"two"}', '{"title":123}', '["title"]'):
            variants.append(('ambiguous output ' + output, naming_exchange(output)))
        for label, exchange in variants:
            with self.subTest(label=label):
                self.log = capture_exchange(self.capture, exchange)
                self.save_capture()
                self.assert_blocked(self.verify(self.snapshot()))

    def test_rm2_matching_request_ids_on_other_connection_do_not_correlate(self):
        self.log = capture_exchange(self.capture, naming_exchange()[:10])
        for direction, message in naming_exchange()[:3] + naming_exchange()[10:]:
            self.log.message('unrelated-tui', direction, message)
        self.save_capture()
        self.assert_blocked(self.verify(self.snapshot()))

    def test_rm2_tool_requests_and_items_at_any_time_block_auxiliary(self):
        forbidden = [
            ('client', request(70, 'thread/shellCommand',
                               {'threadId': AUXILIARY, 'command': PROMPT})),
            ('server', request(71, 'item/tool/call',
                               {'threadId': AUXILIARY, 'turnId': AUXILIARY_TURN})),
            ('server', notification('item/completed', {'threadId': AUXILIARY,
                'turnId': AUXILIARY_TURN, 'completedAtMs': 101,
                'item': {'id': 'tool-119', 'type': 'commandExecution',
                         'command': PROMPT, 'status': 'completed'}})),
        ]
        for event in forbidden:
            with self.subTest(method=event[1]['method']):
                self.log = capture_exchange(self.capture, naming_exchange())
                before = self.snapshot()
                self.log.message('tui-1', *event)
                self.save_capture()
                self.assert_blocked(self.verify(before))

    def test_rm2_unknown_loaded_thread_and_new_auxiliary_after_snapshot_are_blocked(self):
        before = self.snapshot()
        for loaded in ([PRODUCT, AUXILIARY, 'unknown-thread'], [AUXILIARY], []):
            with self.subTest(loaded=loaded):
                self.runtime.loaded = loaded
                self.assert_blocked(self.verify(before))
        self.runtime.loaded = [PRODUCT]
        initialized = capture_exchange(self.capture, naming_exchange()[:3])
        self.save_capture(initialized.report())
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS')
        self.runtime.loaded = [PRODUCT, AUXILIARY]
        self.save_capture()
        self.assert_blocked(self.verify(before))

    def test_rm2_second_auxiliary_turn_is_not_naming_even_with_matching_title(self):
        before = self.snapshot()
        for direction, message in naming_exchange()[5:10]:
            message = copy.deepcopy(message)
            if 'id' in message:
                message['id'] = 'second-auxiliary-turn'
            self.log.message('tui-1', direction, message)
        self.save_capture()
        self.assert_blocked(self.verify(before))

    def test_rm2_lifecycle_causality_connection_and_uniqueness_are_required(self):
        before = self.snapshot()
        good = naming_exchange()
        variants = {
            'completion before turn request': good[:5] + good[8:10] + good[5:8] + good[10:],
            'duplicate turn started': good[:8] + [good[7]] + good[8:],
            'completion on uninitialized connection': good,
        }
        for label, exchange in variants.items():
            self.log = self.capture.CaptureLog()
            for index, (direction, message) in enumerate(exchange):
                other = label == 'completion on uninitialized connection' and index in (8, 9)
                self.log.message('other' if other else 'tui-1', direction, message)
            self.save_capture()
            for phase, observe in (('snapshot', self.snapshot),
                                   ('verify', lambda: self.verify(before))):
                with self.subTest(variant=label, phase=phase):
                    self.assert_blocked(observe())

    def test_rm2_started_notification_can_precede_response_after_turn_request(self):
        good = naming_exchange()
        self.log = capture_exchange(self.capture, good[:6] + [good[7], good[6]] + good[8:])
        self.save_capture()
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS')
        self.assertEqual(self.verify(before)['verdict'], 'PASS')

    def test_rm2_embedded_turn_tools_and_unknown_items_are_rejected_privately(self):
        before = self.snapshot()
        for location, index, container in (('start response', 6, 'result'),
                                            ('completed notification', 9, 'params')):
            for item_type in ('commandExecution', 'unknownFutureItem'):
                exchange = naming_exchange()
                exchange[index][1][container]['turn']['items'] = [{
                    'type': item_type, 'id': 'embedded-tool-119', 'status': 'completed',
                    'command': PROMPT, 'cwd': PROMPT, 'aggregatedOutput': ERROR}]
                self.log = capture_exchange(self.capture, exchange)
                self.save_capture()
                self.assert_private(self.log.report())
                for phase, observe in (('snapshot', self.snapshot),
                                       ('verify', lambda: self.verify(before))):
                    with self.subTest(location=location, item=item_type, phase=phase):
                        self.assert_blocked(observe())

    def test_rm5_malformed_capture_event_returns_blocked_without_losing_counts(self):
        before = self.snapshot()
        original = self.log.report()
        for label, malformed in (('null', None), ('string', PROMPT),
                                 ('array', []), ('missing fields', {})):
            report = copy.deepcopy(original)
            report['events'].append(malformed)
            self.save_capture(report)
            for phase, observe in (('snapshot', self.snapshot),
                                   ('verify', lambda: self.verify(before))):
                with self.subTest(event=label, phase=phase):
                    self.assert_blocked(observe())

    def test_rm2_repeated_final_summary_with_same_identity_and_output_is_consistent(self):
        for index, container in ((6, 'result'), (9, 'params')):
            orders = ('early response', 'late response') if index == 6 else ('notification',)
            for order in orders:
                with self.subTest(container=container, order=order):
                    exchange = naming_exchange()
                    final = copy.deepcopy(exchange[8][1]['params']['item'])
                    exchange[index][1][container]['turn']['items'] = [final]
                    if order == 'late response':
                        response = exchange.pop(index)
                        exchange.insert(9, response)
                    self.log = capture_exchange(self.capture, exchange)
                    self.save_capture()
                    self.assert_private(self.log.report())
                    before = self.snapshot()
                    self.assertEqual(before['verdict'], 'PASS')
                    after = self.verify(before)
                    self.assertEqual(after['verdict'], 'PASS')
                    self.assert_private(after)

    def test_rm2_conflicting_ambiguous_or_second_embedded_final_is_blocked(self):
        before = self.snapshot()
        variants = {
            'same item different output': {'text': TITLE + '!'},
            'same item ambiguous output': {'text': json.dumps({'a': TITLE, 'b': PROMPT})},
            'another final item': {'id': 'other-final-119', 'text': TITLE + '!'},
        }
        for index, container in ((6, 'result'), (9, 'params')):
            for label, changes in variants.items():
                exchange = naming_exchange()
                final = copy.deepcopy(exchange[8][1]['params']['item'])
                final.update(changes)
                exchange[index][1][container]['turn']['items'] = [final]
                self.log = capture_exchange(self.capture, exchange)
                self.save_capture()
                self.assert_private(self.log.report())
                for phase, observe in (('snapshot', self.snapshot),
                                       ('verify', lambda: self.verify(before))):
                    with self.subTest(container=container, variant=label, phase=phase):
                        self.assert_blocked(observe())

    def test_rm2_same_final_identity_cannot_change_phase_or_item_type(self):
        before = self.snapshot()
        for index, container in ((6, 'result'), (9, 'params')):
            final = copy.deepcopy(naming_exchange()[8][1]['params']['item'])
            variants = {
                'final becomes commentary': dict(final, phase='commentary'),
                'final becomes reasoning': {'id': final['id'], 'type': 'reasoning'},
            }
            for label, item in variants.items():
                exchange = naming_exchange()
                exchange[index][1][container]['turn']['items'] = [item]
                self.log = capture_exchange(self.capture, exchange)
                self.save_capture()
                self.assert_private(self.log.report())
                for phase, observe in (('snapshot', self.snapshot),
                                       ('verify', lambda: self.verify(before))):
                    with self.subTest(container=container, variant=label, phase=phase):
                        self.assert_blocked(observe())

    def test_rm2_distinct_nonfinal_items_can_accompany_consistent_final_summary(self):
        for index, container in ((6, 'result'), (9, 'params')):
            with self.subTest(container=container):
                exchange = naming_exchange()
                final = copy.deepcopy(exchange[8][1]['params']['item'])
                exchange[index][1][container]['turn']['items'] = [
                    {'id': 'reasoning-119', 'type': 'reasoning',
                     'summary': [PROMPT], 'content': [PROMPT]},
                    {'id': 'commentary-119', 'type': 'agentMessage',
                     'phase': 'commentary', 'text': PROMPT},
                    final,
                ]
                self.log = capture_exchange(self.capture, exchange)
                self.save_capture()
                self.assert_private(self.log.report())
                before = self.snapshot()
                self.assertEqual(before['verdict'], 'PASS')
                self.assert_private(before)
                after = self.verify(before)
                self.assertEqual(after['verdict'], 'PASS')
                self.assert_private(after)

    def test_rm2_capture_sequence_loss_cannot_hide_tools_or_initial_segment(self):
        before = self.snapshot()
        tool = notification('item/completed', {'threadId': AUXILIARY,
            'turnId': AUXILIARY_TURN, 'completedAtMs': 101,
            'item': {'id': 'removed-tool-119', 'type': 'commandExecution',
                     'command': PROMPT, 'cwd': PROMPT, 'aggregatedOutput': ERROR}})
        good = naming_exchange()
        log = capture_exchange(self.capture, good[:9] + [('server', tool)] + good[9:])
        missing_tool = log.report()
        del missing_tool['events'][9]  # Keep the collector's sequence numbers unchanged.
        log = capture_exchange(self.capture, good[:3], connection='preflight-tui', close=True)
        for direction, message in good:
            log.message('tui-1', direction, message)
        canonical = log.report()
        self.save_capture(canonical)
        self.assertEqual(self.snapshot()['verdict'], 'PASS')
        self.assertEqual(self.verify(before)['verdict'], 'PASS')
        missing_prefix = copy.deepcopy(canonical)
        del missing_prefix['events'][:3]
        for label, report in (('removed tool', missing_tool),
                              ('missing initial segment', missing_prefix)):
            self.save_capture(report)
            self.assert_private(report)
            for phase, observe in (('snapshot', self.snapshot),
                                   ('verify', lambda: self.verify(before))):
                with self.subTest(loss=label, phase=phase):
                    self.assert_blocked(observe())

    def test_rm2_auxiliary_persistence_is_rejected_in_sessions_and_archives(self):
        before = self.snapshot()
        for location in (self.sessions, self.home / 'archived_sessions'):
            with self.subTest(location=location.name):
                location.mkdir(parents=True, exist_ok=True)
                path = location / ('rollout-2026-11-16-' + AUXILIARY + '.jsonl')
                path.write_text(json.dumps({'type': 'session_meta',
                                            'payload': {'id': AUXILIARY}}) + '\n')
                self.assert_blocked(self.verify(before))
                path.unlink()

    def test_rm3_second_product_turn_same_or_different_id_is_counted_and_blocked(self):
        before = self.snapshot()
        for turn in (PRODUCT_TURN, OTHER_TURN):
            with self.subTest(second_turn=turn):
                self.write_rollout((PRODUCT_TURN, turn))
                self.assert_blocked(self.verify(before), counts=(2, 2))

    def test_rm3_rollout_invalid_json_wrong_turn_or_unfinished_task_is_blocked(self):
        before = self.snapshot()
        original = self.rollout.read_text()
        for label, content, counts in (
            ('malformed', original + '{not json}\n', (1, 1)),
            ('wrong turn', original.replace(PRODUCT_TURN, OTHER_TURN), (1, 1)),
            ('unfinished', '\n'.join(original.splitlines()[:-1]) + '\n', (1, 0)),
        ):
            with self.subTest(label=label):
                self.rollout.write_text(content)
                self.assert_blocked(self.verify(before), counts=counts)

    def test_rm3_rollout_beyond_old_read_window_and_unrelated_files(self):
        before = self.snapshot()
        # Read through long files; a tail turn must not disappear behind a byte limit.
        with self.rollout.open('a') as handle:
            for _ in range(80):
                handle.write(json.dumps({'type': 'event_msg', 'payload': {
                    'type': 'agent_message', 'message': PROMPT * 1024}}) + '\n')
        unrelated = self.sessions / 'rollout-unrelated.jsonl'
        unrelated.write_text('{unrelated corrupt file}\n')
        self.assertEqual(self.verify(before)['verdict'], 'PASS')
        with self.rollout.open('a') as handle:
            for event in ('task_started', 'task_complete'):
                handle.write(json.dumps({'type': 'event_msg', 'payload': {
                    'type': event, 'turn_id': OTHER_TURN}}) + '\n')
        self.assert_blocked(self.verify(before), counts=(2, 2))

    def test_rm4_executable_identity_distinguishes_wrappers_and_both_socket_endpoints(self):
        report = self.verify(self.snapshot())
        roles = {row['pid']: row['role'] for row in report['processes']}
        self.assertEqual(roles[45001], 'server')
        self.assertEqual(roles[45002], 'tui')
        for pid in (45003, 45004):
            self.assertNotIn(roles.get(pid), ('tui', 'server'))
        self.assertEqual(set(self.runtime.endpoints), {self.upstream, self.tui})

    def test_rm4_reused_or_replaced_server_is_blocked_and_counters_remain_final(self):
        before = self.snapshot()
        for field, changed in (('starttime', 'different'), ('pid', 45009),
                               ('exe', '/usr/bin/python3')):
            with self.subTest(field=field):
                records = copy.deepcopy(self.runtime.records)
                self.runtime.records[0][field] = changed
                self.assert_blocked(self.verify(before))
                self.runtime.records = records

    def test_rm5_receipt_mismatch_and_missing_capture_cannot_skip_rollout_counting(self):
        before = self.snapshot()
        self.receipt['turn_id'] = OTHER_TURN
        write_json(Path(self.observation['receipt']), self.receipt)
        self.assert_blocked(self.verify(before))
        Path(self.observation['capture']).write_text('{invalid capture json ' + ERROR)
        self.assert_blocked(self.verify(before))

    def test_rm1_cli_failure_is_json_blocked_and_contains_no_input_content(self):
        request_path = self.root / 'request.json'
        write_json(request_path, self.observation)
        # No real RPC/process boundary is permitted in CLI tests. Invalid input must
        # fail before attempting collection; successful CLI collection is a live recipe.
        Path(self.observation['state']).write_text('{invalid state ' + PROMPT)
        run = subprocess.run([sys.executable, str(OBSERVER), 'snapshot', '--request',
                              str(request_path)], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(json.loads(run.stdout)['verdict'], 'BLOCKED')
        for secret in (PROMPT, TITLE, ERROR):
            self.assertNotIn(secret, run.stdout + run.stderr)


def frame(payload, masked=False, opcode=1, final=True):
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    first = (0x80 if final else 0) | opcode
    size, mask_bit = len(payload), 0x80 if masked else 0
    if size < 126:
        header = bytes((first, mask_bit | size))
    elif size < 65536:
        header = bytes((first, mask_bit | 126)) + struct.pack('!H', size)
    else:
        header = bytes((first, mask_bit | 127)) + struct.pack('!Q', size)
    if not masked:
        return header + payload
    mask = b'\x01\x02\x03\x04'
    return header + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))


def receive_exact(connection, size):
    result = bytearray()
    while len(result) < size:
        part = connection.recv(size - len(result))
        if not part:
            raise AssertionError('Synthetic relay closed before byte-identical transfer')
        result.extend(part)
    return bytes(result)


class SocketRelayTests(ObserverFixture):
    """Use real local sockets and fake upstream, never a real Codex subprocess."""
    def run_wire_exchange(self, exchange, extra=b'', max_message=1048576,
                          live_checkpoint=None, continuation=b''):
        self.state['socket'] = self.upstream
        write_json(Path(self.observation['state']), self.state)
        previous_threads = set(threading.enumerate())
        upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(upstream.close)
        upstream.bind(self.upstream)
        upstream.listen(1)
        upstream.settimeout(3)
        key = base64.b64encode(b'0123456789abcdef').decode()
        handshake = ('GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n'
                     'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                     'Sec-WebSocket-Key: ' + key + '\r\n\r\n').encode()
        accept = base64.b64encode(hashlib.sha1((key +
            '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        response = ('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n'
                    'Connection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + '\r\n\r\n').encode()
        wires = []
        for index, (direction, message) in enumerate(exchange):
            payload = json.dumps(message, ensure_ascii=False).encode()
            masked = direction == 'client'
            # Continuations, interleaved control and split UTF-8/reads must be passive.
            split = max(1, len(payload) // 2)
            wire = (frame(payload[:split], masked, final=False) +
                    frame(b'control-119', masked, opcode=9) +
                    frame(payload[split:], masked, opcode=0)) if index % 2 else frame(payload, masked)
            wires.append((direction, wire))
        failures = []

        def serve():
            try:
                with upstream.accept()[0] as server:
                    server.settimeout(3)
                    self.assertEqual(receive_exact(server, len(handshake)), handshake)
                    server.sendall(response)
                    for direction, wire in wires:
                        if direction == 'client':
                            self.assertEqual(receive_exact(server, len(wire)), wire)
                        else:
                            for offset in range(0, len(wire), 7):
                                server.sendall(wire[offset:offset + 7])
                    if extra:
                        server.sendall(extra)
                    self.server_done.set()
                    if continuation:
                        if not self.continue_server.wait(3):
                            raise AssertionError('Synthetic continuation was not released')
                        server.sendall(continuation)
                    self.release_server.wait(3)
            except BaseException as error:
                failures.append(error)
                self.server_done.set()

        self.server_done, self.release_server = threading.Event(), threading.Event()
        self.continue_server = threading.Event()
        server_thread = threading.Thread(target=serve, name='synthetic-upstream-119')
        server_thread.start()
        try:
            with self.capture.CaptureProxy(self.upstream, self.tui, timeout=3,
                                           max_message=max_message) as proxy:
                self.assertEqual(stat.S_IMODE(Path(self.tui).stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(3)
                    client.connect(self.tui)
                    client.sendall(handshake)
                    self.assertEqual(receive_exact(client, len(response)), response)
                    for direction, wire in wires:
                        if direction == 'client':
                            for offset in range(0, len(wire), 11):
                                client.sendall(wire[offset:offset + 11])
                        else:
                            self.assertEqual(receive_exact(client, len(wire)), wire)
                    self.assertTrue(self.server_done.wait(3))
                    if extra:
                        # Invalid input may be relayed unchanged or close the connection.
                        if live_checkpoint:
                            self.assertEqual(receive_exact(client, len(extra)), extra)
                        else:
                            try:
                                client.recv(len(extra))
                            except (OSError, TimeoutError):
                                pass
                    report = proxy.report()
                    self.assert_private(report)
                    self.save_capture(report)
                    before = self.snapshot()  # Capture is live at the snapshot boundary.
                    if live_checkpoint:
                        live_checkpoint(before)
                    if continuation:
                        self.continue_server.set()
                        self.assertEqual(receive_exact(client, len(continuation)), continuation)
                        self.save_capture(proxy.report())
                        before = self.snapshot()
                self.release_server.set()
            self.save_capture(proxy.report())
            after = self.verify(before)
        finally:
            self.continue_server.set()
            self.release_server.set()
            server_thread.join(timeout=4)
        self.assertFalse(server_thread.is_alive(), 'Synthetic server thread was not joined')
        self.assertFalse(set(threading.enumerate()) - previous_threads,
                         'Capture context left an unjoined worker thread')
        if failures:
            raise failures[0]
        return after

    def test_rm1_rm2_socket_capture_report_feeds_observer_without_transcript_leak(self):
        self.assertEqual(self.run_wire_exchange(naming_exchange())['verdict'], 'PASS')

    def test_rm2_malformed_truncated_or_oversized_wire_cannot_prove_naming(self):
        malformed = (
            frame(b'{not JSON ' + PROMPT.encode()),
            frame(b'partial ' + PROMPT.encode(), final=False),
            frame(b'x' * 4096),
            b'\xc1\x01x',  # Unexpected RSV bit: unsupported wire format.
        )
        for wire in malformed:
            with self.subTest(kind=wire[:8].hex()):
                # Separate socket paths because collision handling is intentionally strict.
                self.upstream = str(self.root / ('up-' + str(len(wire)) + '.sock'))
                self.tui = str(self.root / ('tui-' + str(len(wire)) + '.sock'))
                self.runtime = RuntimeBoundary(self.upstream, self.tui)
                self.assert_blocked(self.run_wire_exchange(naming_exchange(), wire,
                                                           max_message=2048))

    def test_rm2_partial_live_wire_blocks_checkpoint_and_final_truncation(self):
        payload = json.dumps(notification('thread/status/changed', {
            'threadId': PRODUCT, 'status': {'type': 'idle'}, 'private': PROMPT})).encode()
        partials = {'fragment': frame(payload[:20], final=False),
                    'frame header': frame(payload)[:1]}
        for label, partial in partials.items():
            self.upstream = str(self.root / ('up-' + label.replace(' ', '-') + '.sock'))
            self.tui = str(self.root / ('tui-' + label.replace(' ', '-') + '.sock'))
            self.runtime = RuntimeBoundary(self.upstream, self.tui)
            checkpoints = []
            after = self.run_wire_exchange(naming_exchange(), partial,
                                           live_checkpoint=checkpoints.append)
            with self.subTest(partial=label, phase='live snapshot'):
                self.assert_blocked(checkpoints[0])
            with self.subTest(partial=label, phase='final verify'):
                self.assert_blocked(after)

    def test_rm2_completed_fragment_or_header_recovers_after_partial_checkpoint(self):
        payload = json.dumps(notification('thread/status/changed', {
            'threadId': PRODUCT, 'status': {'type': 'idle'}, 'private': PROMPT})).encode()
        variants = {
            'fragment': (frame(payload[:20], final=False), frame(payload[20:], opcode=0)),
            'frame header': (frame(payload)[:1], frame(payload)[1:]),
        }
        for label, (partial, completion) in variants.items():
            self.upstream = str(self.root / ('up-complete-' + label.replace(' ', '-') + '.sock'))
            self.tui = str(self.root / ('tui-complete-' + label.replace(' ', '-') + '.sock'))
            self.runtime = RuntimeBoundary(self.upstream, self.tui)
            checkpoints = []
            after = self.run_wire_exchange(naming_exchange(), partial,
                live_checkpoint=checkpoints.append, continuation=completion)
            with self.subTest(partial=label, phase='live snapshot'):
                self.assert_blocked(checkpoints[0])
            with self.subTest(partial=label, phase='completed verify'):
                self.assertEqual(after['verdict'], 'PASS',
                                 'Reading a partial checkpoint must not create a sticky error')
                self.assert_private(after)

    def test_rm2_proxy_refuses_existing_path_without_removing_or_chmodding_it(self):
        path = Path(self.tui)
        path.write_text(PROMPT)
        path.chmod(0o640)
        with self.assertRaises(Exception) as failure:
            with self.capture.CaptureProxy(self.upstream, self.tui, timeout=.2):
                pass
        self.assertNotIn(PROMPT, str(failure.exception))
        self.assertEqual(path.read_text(), PROMPT)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    def test_rm2_unresponsive_upstream_is_bounded_and_diagnosed_without_leak(self):
        previous_threads = set(threading.enumerate())
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
            upstream.bind(self.upstream)
            upstream.listen(1)
            upstream.settimeout(1)
            with self.capture.CaptureProxy(self.upstream, self.tui, timeout=.1) as proxy:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(1)
                    client.connect(self.tui)
                    client.sendall(b'GET / HTTP/1.1\r\nX-Private: ' + PROMPT.encode() + b'\r\n')
                    with upstream.accept()[0] as server:
                        server.settimeout(1)
                        self.assertTrue(server.recv(4096))
                        # No handshake response: the collector must reach its own deadline.
                        try:
                            self.assertEqual(client.recv(4096), b'')
                        except ConnectionResetError:
                            pass
            report = proxy.report()
        self.assertTrue(report['errors'])
        self.assert_private(report)
        self.assertFalse(set(threading.enumerate()) - previous_threads,
                         'Deadline left an unjoined capture worker')


# ---------------------------------------------------------------------------
# Correction 4: synthetic, sanitised model of the real TUI naming recipe, with
# product events interleaved, three additional auxiliary events (moderation
# metadata, thread/unsubscribe + ACK, thread/closed) and streaming deltas.
# Ids are synthetic; no payload text from any real capture is reused.
# ---------------------------------------------------------------------------
RECIPE_START = 'temporary-structured-0001'
RECIPE_TURN_REQUEST = 'temporary-structured-turn-0002'
RECIPE_UNSUBSCRIBE = 'temporary-structured-unsubscribe-0003'


def _step(label, direction, message, connection='tui-1'):
    return (label, connection, direction, message)


def _thread_event(method, thread, turn, **extra):
    return notification(method, dict({'threadId': thread, 'turnId': turn}, **extra))


def _product_item(method, item):
    return notification(method, {'threadId': PRODUCT, 'turnId': PRODUCT_TURN,
                                 'completedAtMs': 90, 'item': item})


def _aux_item(method, item):
    return notification(method, {'threadId': AUXILIARY, 'turnId': AUXILIARY_TURN,
                                 'completedAtMs': 100, 'item': item})


def _turn_event(method, thread, turn, status):
    return notification(method, {'threadId': thread, 'turn': {
        'id': turn, 'status': status, 'items': []}})


def recipe_steps(output=TITLE):
    """Labelled (label, connection, direction, message) steps in observed order."""
    final = {'id': 'aux-final-1', 'type': 'agentMessage', 'phase': 'final_answer'}
    return [
        _step('init', 'client', request(1, 'initialize', {
            'clientInfo': {'name': 'codex-tui', 'version': '0.169.0'},
            'capabilities': {'experimentalApi': True}})),
        _step('init-ack', 'server', {'id': 1, 'result': {'userAgent': 'synthetic-codex'}}),
        _step('initialized', 'client', notification('initialized', {})),
        _step('product-started', 'server', _turn_event(
            'turn/started', PRODUCT, PRODUCT_TURN, 'inProgress')),
        _step('cfg', 'client', request('config-1', 'config/read', {'includeLayers': False})),
        _step('cfg-ack', 'server', {'id': 'config-1', 'result': {'config': {}}}),
        _step('start', 'client', request(RECIPE_START, 'thread/start', {
            'ephemeral': True, 'dynamicTools': [], 'sandbox': 'read-only',
            'baseInstructions': PROMPT})),
        _step('start-ack', 'server', {'id': RECIPE_START, 'result': {
            'thread': {'id': AUXILIARY, 'ephemeral': True, 'turns': []}}}),
        _step('aux-thread-started', 'server', notification('thread/started', {
            'thread': {'id': AUXILIARY, 'ephemeral': True, 'turns': []}})),
        _step('turn-req', 'client', request(RECIPE_TURN_REQUEST, 'turn/start', {
            'threadId': AUXILIARY, 'input': [{'type': 'text', 'text': PROMPT}],
            'sandboxPolicy': {'type': 'readOnly', 'networkAccess': False}})),
        _step('settings', 'server', notification('thread/settings/updated', {
            'threadId': AUXILIARY, 'settings': {}})),
        _step('turn-ack', 'server', {'id': RECIPE_TURN_REQUEST, 'result': {'turn': {
            'id': AUXILIARY_TURN, 'status': 'inProgress', 'items': []}}}),
        _step('status-1', 'server', notification('thread/status/changed', {
            'threadId': AUXILIARY, 'status': {'type': 'active'}})),
        _step('turn-started', 'server', _turn_event(
            'turn/started', AUXILIARY, AUXILIARY_TURN, 'inProgress')),
        _step('user-started', 'server', _aux_item('item/started', {
            'id': 'aux-user-1', 'type': 'userMessage',
            'content': [{'type': 'text', 'text': PROMPT}]})),
        _step('user-completed', 'server', _aux_item('item/completed', {
            'id': 'aux-user-1', 'type': 'userMessage',
            'content': [{'type': 'text', 'text': PROMPT}]})),
        _step('prod-comment-started', 'server', _product_item('item/started', {
            'id': 'prod-comment-1', 'type': 'agentMessage', 'phase': 'commentary', 'text': ''})),
        _step('prod-comment-completed', 'server', _product_item('item/completed', {
            'id': 'prod-comment-1', 'type': 'agentMessage', 'phase': 'commentary',
            'text': 'synthetic commentary'})),
        _step('reason-started', 'server', _aux_item('item/started', {
            'id': 'aux-reason-1', 'type': 'reasoning', 'summary': [], 'content': []})),
        _step('reason-completed', 'server', _aux_item('item/completed', {
            'id': 'aux-reason-1', 'type': 'reasoning', 'summary': [], 'content': []})),
        _step('prod-moderation', 'server', _thread_event(
            'turn/moderationMetadata', PRODUCT, PRODUCT_TURN, metadata={'opaque': 1})),
        _step('prod-tool-started', 'server', _product_item('item/started', {
            'id': 'prod-tool-1', 'type': 'commandExecution', 'status': 'inProgress',
            'command': 'synthetic'})),
        _step('prod-tool-completed', 'server', _product_item('item/completed', {
            'id': 'prod-tool-1', 'type': 'commandExecution', 'status': 'completed',
            'command': 'synthetic'})),
        _step('prod-usage', 'server', _thread_event(
            'thread/tokenUsage/updated', PRODUCT, PRODUCT_TURN, tokenUsage={})),
        _step('rate-1', 'server', notification('account/rateLimits/updated', {'rateLimits': {}})),
        _step('final-started', 'server', _aux_item('item/started', dict(final, text=''))),
        _step('delta-1', 'server', _thread_event(
            'item/agentMessage/delta', AUXILIARY, AUXILIARY_TURN,
            itemId='aux-final-1', delta='synthetic delta one')),
        _step('delta-2', 'server', _thread_event(
            'item/agentMessage/delta', AUXILIARY, AUXILIARY_TURN,
            itemId='aux-final-1', delta='synthetic delta two')),
        _step('moderation', 'server', _thread_event(
            'turn/moderationMetadata', AUXILIARY, AUXILIARY_TURN, metadata={'opaque': PROMPT})),
        _step('final-completed', 'server', _aux_item('item/completed', dict(final, text=output))),
        _step('aux-usage', 'server', _thread_event(
            'thread/tokenUsage/updated', AUXILIARY, AUXILIARY_TURN, tokenUsage={})),
        _step('rate-2', 'server', notification('account/rateLimits/updated', {'rateLimits': {}})),
        _step('status-2', 'server', notification('thread/status/changed', {
            'threadId': AUXILIARY, 'status': {'type': 'idle'}})),
        _step('turn-completed', 'server', _turn_event(
            'turn/completed', AUXILIARY, AUXILIARY_TURN, 'completed')),
        _step('unsubscribe', 'client', request(RECIPE_UNSUBSCRIBE, 'thread/unsubscribe', {
            'threadId': AUXILIARY})),
        _step('unsubscribe-ack', 'server', {'id': RECIPE_UNSUBSCRIBE,
                                            'result': {'status': 'unsubscribed'}}),
        _step('read', 'client', request('read-1', 'thread/read', {
            'threadId': PRODUCT, 'includeTurns': False})),
        _step('read-ack', 'server', {'id': 'read-1', 'result': {
            'thread': {'id': PRODUCT, 'turns': []}}}),
        _step('name', 'client', request('name-1', 'thread/name/set', {
            'threadId': PRODUCT, 'name': TITLE})),
        _step('name-ack', 'server', {'id': 'name-1', 'result': {}}),
        _step('name-updated', 'server', notification('thread/name/updated', {
            'threadId': PRODUCT, 'threadName': TITLE})),
        _step('product-completed', 'server', _turn_event(
            'turn/completed', PRODUCT, PRODUCT_TURN, 'completed')),
        _step('exec', 'client', request('exec-1', 'command/exec', {'command': ['true']})),
        _step('exec-ack', 'server', {'id': 'exec-1', 'result': {'exitCode': 0}}),
        _step('rate-read', 'client', request('rate-1', 'account/rateLimits/read', {})),
        _step('rate-read-ack', 'server', {'id': 'rate-1', 'result': {'rateLimits': {}}}),
        _step('status-late', 'server', notification('thread/status/changed', {
            'threadId': AUXILIARY, 'status': {'type': 'notLoaded'}})),
        _step('closed', 'server', notification('thread/closed', {'threadId': AUXILIARY})),
    ]


def recipe_log(api, steps):
    log = api.CaptureLog()
    for _, connection, direction, message in steps:
        log.message(connection, direction, copy.deepcopy(message))
    return log


def _index(steps, label):
    return [row[0] for row in steps].index(label)


def recipe_without(steps, *labels):
    return [row for row in steps if row[0] not in labels]


def recipe_until(steps, label):
    return steps[:_index(steps, label)]


def recipe_edit(steps, label, edit):
    steps = copy.deepcopy(steps)
    edit(steps[_index(steps, label)][3])
    return steps


def recipe_replace(steps, label, **changes):
    """Change label/connection/direction/message of one step."""
    steps = list(steps)
    row = dict(zip(('label', 'connection', 'direction', 'message'), steps[_index(steps, label)]))
    row.update(changes)
    steps[_index(steps, label)] = (row['label'], row['connection'], row['direction'],
                                   copy.deepcopy(row['message']))
    return steps


def recipe_move(steps, label, before=None, after=None):
    steps = list(steps)
    row = steps.pop(_index(steps, label))
    anchor = _index(steps, before) if before else _index(steps, after) + 1
    steps.insert(anchor, row)
    return steps


def recipe_append(steps, *rows):
    return list(steps) + list(rows)


class PostNamingReadTests(ObserverFixture):
    """#124 AC1–4 / RM1–5: reads never substitute for positive naming proof."""
    METHODS = ('thread/read', 'thread/turns/list')

    def prefix(self, closed=False):
        steps = recipe_steps()
        return steps if closed else recipe_until(steps, 'status-late')

    def feed(self, steps):
        for _, connection, direction, message in steps:
            self.log.message(connection, direction, copy.deepcopy(message))
        self.assertEqual(self.log.report()['errors'], [], 'Use valid capture evidence')
        self.save_capture()

    def initialize_steps(self, connection='tui-2'):
        return [_step(label, direction, message, connection)
                for label, (direction, message) in zip(
                    ('read-init', 'read-init-ack', 'read-initialized'),
                    naming_exchange()[:3])]

    def read_steps(self, method, connection='tui-2', identifier='aux-read-124', items=None):
        if items is None:
            steps = recipe_steps()
            items = [dict(steps[_index(steps, 'final-completed')][3]['params']['item'])]
        # Turn ids are present in real protocol responses; reading one is not a new turn.
        turns = [{'id': AUXILIARY_TURN, 'status': 'completed', 'items': items}]
        result = {
            'thread/read': {'thread': {'id': AUXILIARY, 'ephemeral': True, 'turns': turns}},
            'thread/turns/list': {'data': turns, 'nextCursor': None},
        }[method]
        params = {'threadId': AUXILIARY}
        if method == 'thread/read':
            params['includeTurns'] = True
        return [
            _step('aux-read', 'client', request(identifier, method, params), connection),
            _step('aux-read-ack', 'server', {'id': identifier, 'result': result}, connection),
        ]

    def checkpoint(self, closed=False):
        self.log = recipe_log(self.capture, self.prefix(closed))
        self.runtime.loaded = [PRODUCT] if closed else [PRODUCT, AUXILIARY]
        self.save_capture()
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS', before['reasons'])
        return before

    def reconnect_reads(self, steps):
        self.log.close('tui-1')
        self.feed(steps)

    def assert_read_pass(self, before):
        after = self.verify(before)
        self.assertEqual(after['verdict'], 'PASS', after['reasons'])
        expected_raw = 'BLOCKED' if AUXILIARY in self.runtime.loaded else 'PASS'
        self.assertEqual(after['raw_verdict'], expected_raw, after['raw_reasons'])
        self.assertEqual(after['loaded_threads'], self.runtime.loaded)
        if expected_raw == 'BLOCKED':
            self.assertIn('loaded-set', after['raw_reasons'])
        self.assertEqual([row['thread_id'] for row in after['auxiliary_threads']], [AUXILIARY])
        self.assertEqual((after['counts']['task_started'], after['counts']['task_complete']),
                         (1, 1))
        self.assert_private(self.log.report())
        self.assert_private(after)

    def test_124_ac1_completed_unsubscribe_snapshot_reconnect_two_successful_reads(self):
        before = self.checkpoint()
        self.assertTrue(before['auxiliary_threads'][0]['loaded'])
        self.assertEqual(before['raw_verdict'], 'BLOCKED')
        self.reconnect_reads(self.initialize_steps()
                             + self.read_steps('thread/read', identifier='read-124')
                             + self.read_steps('thread/turns/list', identifier='turns-124'))
        self.assert_read_pass(before)

    def test_124_rm2_each_read_on_original_or_reconnected_tui_including_after_closed(self):
        for method in self.METHODS:
            for closed, connection in ((False, 'tui-1'), (False, 'tui-2'), (True, 'tui-2')):
                with self.subTest(method=method, closed=closed, connection=connection):
                    before = self.checkpoint(closed)
                    steps = self.read_steps(method, connection)
                    if connection == 'tui-2':
                        self.reconnect_reads(self.initialize_steps() + steps)
                    else:
                        self.feed(steps)
                    self.assert_read_pass(before)

    def test_124_rm2_successful_reads_accept_empty_or_consistent_nonfinal_item_summaries(self):
        final = self.read_steps('thread/read')[1][3]['result']['thread']['turns'][0]['items'][0]
        summaries = {
            'empty': [],
            'nonfinal and final': [
                {'id': 'read-reasoning-124', 'type': 'reasoning', 'summary': [PROMPT]},
                {'id': 'read-comment-124', 'type': 'agentMessage',
                 'phase': 'commentary', 'text': PROMPT}, final],
        }
        for method in self.METHODS:
            for label, items in summaries.items():
                with self.subTest(method=method, content=label):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps()
                                         + self.read_steps(method, items=items))
                    self.assert_read_pass(before)

    def test_124_ac4_real_recipe_read_success_then_turns_list_error_stays_blocked(self):
        before = self.checkpoint()
        steps = self.initialize_steps() + self.read_steps('thread/read', identifier='read-124')
        steps += self.read_steps('thread/turns/list', identifier='turns-124')
        # Edit the last response, reproducing #121's failed turns/list, not its private text.
        steps[-1] = _step('turns-error', 'server', {
            'id': 'turns-124', 'error': {'code': -32000, 'message': ERROR}}, 'tui-2')
        self.reconnect_reads(steps)
        self.assert_blocked(self.verify(before))
        self.assert_private(self.log.report())

    def test_124_rm3_each_read_requires_unique_later_server_success_same_id_and_connection(self):
        for method in self.METHODS:
            pair = self.read_steps(method)
            variants = {
                'missing response': pair[:1],
                'error response': recipe_replace(pair, 'aux-read-ack', message={
                    'id': 'aux-read-124', 'error': {'code': -1, 'message': ERROR}}),
                'wrong response id': recipe_edit(pair, 'aux-read-ack',
                                                  lambda m: m.update(id='wrong-id')),
                'wrong response connection': recipe_replace(pair, 'aux-read-ack',
                                                             connection='tui-3'),
                'wrong response direction': recipe_replace(pair, 'aux-read-ack',
                                                            direction='client'),
                'response before request': list(reversed(pair)),
                'duplicate response': pair + [pair[1]],
                'duplicate request id': [pair[0]] + pair,
                'server request': recipe_replace(pair, 'aux-read', direction='server'),
                'notification is not request': recipe_edit(pair, 'aux-read',
                                                            lambda m: m.pop('id')),
            }
            for label, steps in variants.items():
                with self.subTest(method=method, variant=label):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps()
                                         + self.initialize_steps('tui-3') + steps)
                    self.assert_blocked(self.verify(before))
                    self.assert_private(self.log.report())

    def test_124_rm3_same_read_id_on_two_initialized_connections_is_not_ambiguous(self):
        for method in self.METHODS:
            with self.subTest(method=method):
                before = self.checkpoint()
                self.reconnect_reads(self.initialize_steps('tui-2')
                                     + self.initialize_steps('tui-3')
                                     + self.read_steps(method, 'tui-2')[:1]
                                     + self.read_steps(method, 'tui-3')
                                     + self.read_steps(method, 'tui-2')[1:])
                self.assert_read_pass(before)

    def test_124_rm2_read_connection_must_initialize_as_tui_with_prior_success(self):
        init = self.initialize_steps()
        for method in self.METHODS:
            pair = self.read_steps(method)
            variants = {
                'no initialize': pair,
                'initialize unacknowledged': init[:1] + pair,
                'initialize other client': recipe_edit(init, 'read-init',
                    lambda m: m['params']['clientInfo'].update(name='observer')) + pair,
                'initialize without clientInfo': recipe_edit(init, 'read-init',
                    lambda m: m['params'].pop('clientInfo')) + pair,
                'initialize server direction': recipe_replace(init, 'read-init',
                                                               direction='server') + pair,
                'initialize notification': recipe_edit(init, 'read-init',
                                                         lambda m: m.pop('id')) + pair,
                'initialize error': recipe_replace(init, 'read-init-ack', message={
                    'id': 1, 'error': {'code': -1, 'message': ERROR}}) + pair,
                'initialize wrong ack id': recipe_edit(init, 'read-init-ack',
                                                        lambda m: m.update(id=999)) + pair,
                'initialize ack other connection': recipe_replace(init, 'read-init-ack',
                                                                  connection='tui-3') + pair,
                'initialize ack client direction': recipe_replace(init, 'read-init-ack',
                                                                  direction='client') + pair,
                'read before initialize': pair + init,
                'read before initialize ack': init[:1] + pair + init[1:],
                'initialize ack before request': [init[1], init[0], init[2]] + pair,
            }
            for label, steps in variants.items():
                with self.subTest(method=method, variant=label):
                    before = self.checkpoint()
                    self.reconnect_reads(steps)
                    self.assert_blocked(self.verify(before))

    def test_124_rm1_read_before_name_ack_cannot_be_retroactively_proven(self):
        for method in self.METHODS:
            for anchor in ('name', 'name-ack'):
                with self.subTest(method=method, before=anchor):
                    before = self.checkpoint()
                    steps = self.prefix()
                    offset = _index(steps, anchor)
                    steps[offset:offset] = self.read_steps(method, 'tui-1')
                    self.log = recipe_log(self.capture, steps)
                    self.save_capture()
                    self.assert_blocked(self.snapshot())
                    self.assert_blocked(self.verify(before))

    def test_124_rm1_read_never_replaces_missing_naming_evidence(self):
        for method in self.METHODS:
            for absent in ('start-ack', 'final-completed', 'turn-completed', 'name-ack'):
                with self.subTest(method=method, missing=absent):
                    before = self.checkpoint()
                    self.log = recipe_log(self.capture, recipe_without(self.prefix(), absent))
                    self.reconnect_reads(self.initialize_steps() + self.read_steps(method))
                    self.assert_blocked(self.snapshot())
                    self.assert_blocked(self.verify(before))

    def test_124_ac2_auxiliary_first_seen_after_snapshot_still_blocks_with_good_reads(self):
        self.log = capture_exchange(self.capture, naming_exchange()[:3])
        self.runtime.loaded = [PRODUCT]
        self.save_capture()
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS', before['reasons'])
        self.feed(recipe_without(self.prefix(), 'init', 'init-ack', 'initialized'))
        self.runtime.loaded = [PRODUCT, AUXILIARY]
        self.reconnect_reads(self.initialize_steps() + self.read_steps('thread/read'))
        self.assert_blocked(self.verify(before))

    def test_124_rm4_reads_do_not_authorize_other_methods_turns_or_tools(self):
        forbidden = [
            ('client', request('resume-124', 'thread/resume', {'threadId': AUXILIARY})),
            ('client', request('turn-124', 'turn/start', {'threadId': AUXILIARY})),
            ('client', request('subscribe-124', 'thread/subscribe', {'threadId': AUXILIARY})),
            ('client', request('other-124', 'thread/archive', {'threadId': AUXILIARY})),
            ('server', request('tool-124', 'item/tool/call', {'threadId': AUXILIARY})),
            ('server', _turn_event('turn/started', AUXILIARY, OTHER_TURN, 'inProgress')),
            ('server', _aux_item('item/completed', {'id': 'tool-124',
                'type': 'commandExecution', 'command': PROMPT, 'aggregatedOutput': ERROR})),
        ]
        for method in self.METHODS:
            for direction, message in forbidden:
                with self.subTest(read=method, forbidden=message['method']):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps() + self.read_steps(method)
                                         + [_step('forbidden', direction, message, 'tui-2')])
                    self.assert_blocked(self.verify(before))
                    self.assert_private(self.log.report())

    def test_124_rm4_reads_after_closed_do_not_reopen_subscription(self):
        for method in self.METHODS:
            for event in ('thread/status/changed', 'thread/tokenUsage/updated'):
                with self.subTest(read=method, event=event):
                    before = self.checkpoint(closed=True)
                    self.reconnect_reads(self.initialize_steps() + self.read_steps(method))
                    # Even formerly allowed lifecycle metadata cannot follow closed.
                    self.feed([_step('late-event', 'server', notification(event, {
                        'threadId': AUXILIARY, 'status': {'type': 'active'}}), 'tui-2')])
                    self.assert_blocked(self.verify(before))

    def test_124_rm4_reads_after_unsubscribe_still_allow_original_close(self):
        for method in self.METHODS:
            with self.subTest(method=method):
                before = self.checkpoint()
                self.feed(self.read_steps(method, 'tui-1'))
                steps = recipe_steps()
                self.feed(steps[_index(steps, 'status-late'):])
                self.runtime.loaded = [PRODUCT]
                self.assert_read_pass(before)

    def test_124_rm4_auxiliary_rollout_after_reads_is_still_forbidden(self):
        for method in self.METHODS:
            for location in (self.sessions, self.home / 'archived_sessions'):
                with self.subTest(method=method, location=location.name):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps() + self.read_steps(method))
                    location.mkdir(parents=True, exist_ok=True)
                    path = location / ('rollout-124-' + AUXILIARY + '.jsonl')
                    write_json(path, {'type': 'session_meta', 'payload': {'id': AUXILIARY}})
                    self.assert_blocked(self.verify(before))
                    path.unlink()

    def test_124_rm4_read_content_preserves_item_and_final_consistency_guards(self):
        final = self.read_steps('thread/read')[1][3]['result']['thread']['turns'][0]['items'][0]
        variants = {
            'tool': {'id': 'tool-124', 'type': 'commandExecution',
                     'command': PROMPT, 'aggregatedOutput': ERROR},
            'unknown item': {'id': 'unknown-124', 'type': 'futureItem', 'text': PROMPT},
            'contradictory output': dict(final, text=TITLE + '!'),
            'second final': dict(final, id='second-final-124'),
            'ambiguous final': dict(final, text=json.dumps({'a': TITLE, 'b': PROMPT})),
            'same id different phase': dict(final, phase='commentary', text=PROMPT),
            'same id different type': {'id': final['id'], 'type': 'reasoning', 'text': PROMPT},
        }
        for method in self.METHODS:
            for label, item in variants.items():
                with self.subTest(method=method, content=label):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps()
                                         + self.read_steps(method, items=[item]))
                    self.assert_blocked(self.verify(before))
                    self.assert_private(self.log.report())

    def test_124_rm4_rm5_capture_retains_read_item_metadata_and_hashes_without_text(self):
        final = self.read_steps('thread/read')[1][3]['result']['thread']['turns'][0]['items'][0]
        items = [final, {'id': 'read-tool-124', 'type': 'commandExecution',
                         'command': PROMPT, 'cwd': PROMPT, 'aggregatedOutput': ERROR}]
        for method in self.METHODS:
            with self.subTest(method=method):
                log = recipe_log(self.capture, self.initialize_steps()
                                 + self.read_steps(method, items=items))
                report = log.report()
                self.assertEqual(report['errors'], [])
                self.assert_private(report)
                response = report['events'][-1]
                embedded = {item['id']: item for item in response.get('turn_items', [])}
                self.assertEqual(set(embedded), {final['id'], 'read-tool-124'})
                self.assertEqual(embedded['read-tool-124']['type'], 'commandExecution')
                self.assertEqual(embedded[final['id']]['phase'], 'final_answer')
                self.assertEqual(embedded[final['id']]['output_sha256'],
                                 hashlib.sha256(TITLE.encode()).hexdigest())
                self.assertIs(embedded[final['id']]['output_ambiguous'], False)

    def test_124_rm5_turns_data_extraction_is_scoped_to_request_method_and_connection(self):
        pair = self.read_steps('thread/turns/list', identifier='shared-id-124')
        unrelated = request('shared-id-124', 'thread/list', {'cursor': PROMPT})
        response = copy.deepcopy(pair[1][3])
        log = recipe_log(self.capture, self.initialize_steps('tui-2')
                         + self.initialize_steps('tui-3') + pair[:1]
                         + [_step('unrelated', 'client', unrelated, 'tui-3'),
                            _step('unrelated-ack', 'server', response, 'tui-3')]
                         + pair[1:])
        report = log.report()
        self.assert_private(report)
        unrelated_ack, turns_ack = report['events'][-2:]
        self.assertFalse(unrelated_ack.get('turn_items'))
        self.assertTrue(turns_ack.get('turn_items'),
                        'Correlated turns/list must retain item safety evidence')

    # --- #124 correction 1 (M1/M2): a read must prove its structure and its single turn ---

    def mutated_read(self, method, edit, identifier='aux-read-124'):
        """Valid read pair whose response `result` (or request message) is changed by `edit`."""
        steps = self.read_steps(method, identifier=identifier)
        edit(method, steps[0][3], steps[1][3])
        return steps

    @staticmethod
    def read_turns(method, response):
        result = response['result']
        return result['thread']['turns'] if method == 'thread/read' else result['data']

    @staticmethod
    def read_container(method, response, value):
        if method == 'thread/read':
            response['result']['thread']['turns'] = value
        else:
            response['result']['data'] = value

    def blocked_reads(self, cases):
        for method in self.METHODS:
            for label, edit in cases.items():
                with self.subTest(method=method, read=label):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps()
                                         + self.mutated_read(method, edit))
                    self.assert_blocked(self.verify(before))
                    self.assert_private(self.log.report())

    def test_124_m1_malformed_read_bodies_are_invalid_proof_not_empty_turns(self):
        def turn(change):
            return lambda method, _, response: change(self.read_turns(method, response)[0])

        def drop(key):
            return turn(lambda t: t.pop(key))

        def put(key, value):
            return turn(lambda t: t.__setitem__(key, value))

        def result(value):
            return lambda method, _, response: response.__setitem__('result', value)

        def container(value):
            return lambda method, _, response: self.read_container(method, response, value)

        def listed(value):
            return lambda method, _, response: self.read_turns(method, response).append(value)

        self.blocked_reads({
            'turn without items': drop('items'), 'turn without id': drop('id'),
            'turn without status': drop('status'),
            'items null': put('items', None), 'items object': put('items', {}),
            'items boolean': put('items', True), 'items string': put('items', 'x'),
            'id null': put('id', None), 'id object': put('id', {}), 'id boolean': put('id', True),
            'status null': put('status', None), 'status object': put('status', {}),
            'status boolean': put('status', False),
            'result null': result(None), 'result empty object': result({}),
            'result array': result([]), 'result string': result('x'),
            'turns container null': container(None), 'turns container object': container({}),
            'turns container boolean': container(True), 'turns container string': container('x'),
            'turn element null': listed(None), 'turn element string': listed('x'),
            'turn element array': listed([]),
            'extra turn without items': listed({'id': AUXILIARY_TURN, 'status': 'completed'}),
        })
        # thread/read specifics: the thread object itself, then its identity.
        for label, thread in {'thread null': None, 'thread array': [], 'thread empty': {},
                              'thread without id': {'turns': []},
                              'thread without turns': {'id': AUXILIARY}}.items():
            with self.subTest(method='thread/read', read=label):
                before = self.checkpoint()
                self.reconnect_reads(self.initialize_steps() + self.mutated_read(
                    'thread/read', lambda m, _, r, t=thread: r['result'].__setitem__('thread', t)))
                self.assert_blocked(self.verify(before))
        # turns/list specifics: data absent.
        with self.subTest(method='thread/turns/list', read='data absent'):
            before = self.checkpoint()
            self.reconnect_reads(self.initialize_steps() + self.mutated_read(
                'thread/turns/list', lambda m, _, r: r['result'].pop('data')))
            self.assert_blocked(self.verify(before))

    def test_124_m2_read_turn_identity_status_and_extra_turns_must_match_naming_turn(self):
        def turn(change):
            return lambda method, _, response: change(self.read_turns(method, response)[0])

        def listed(value):
            return lambda method, _, response: self.read_turns(method, response).append(value)

        def response_turn(value):
            return lambda method, _, response: response['result'].__setitem__('turn', value)

        def request_params(**params):
            return lambda method, ask, _: ask['params'].update(params)

        self.blocked_reads({
            'other turn id': turn(lambda t: t.__setitem__('id', OTHER_TURN)),
            'in progress': turn(lambda t: t.__setitem__('status', 'inProgress')),
            'failed': turn(lambda t: t.__setitem__('status', 'failed')),
            'interrupted': turn(lambda t: t.__setitem__('status', 'interrupted')),
            'second other turn empty': listed(
                {'id': OTHER_TURN, 'status': 'completed', 'items': []}),
            'second other turn in progress': listed(
                {'id': OTHER_TURN, 'status': 'inProgress', 'items': []}),
            'second same turn in progress': listed(
                {'id': AUXILIARY_TURN, 'status': 'inProgress', 'items': []}),
            'second same turn duplicate': listed(
                {'id': AUXILIARY_TURN, 'status': 'completed', 'items': []}),
            'response turn other': response_turn(
                {'id': OTHER_TURN, 'status': 'completed', 'items': []}),
            'response turn in progress': response_turn(
                {'id': AUXILIARY_TURN, 'status': 'inProgress', 'items': []}),
            'response turn other and in progress': response_turn(
                {'id': OTHER_TURN, 'status': 'inProgress', 'items': []}),
            'request turn id other': request_params(turnId=OTHER_TURN),
            'request turn other': request_params(
                turn={'id': OTHER_TURN, 'status': 'completed', 'items': []}),
            'request turn in progress': request_params(
                turn={'id': AUXILIARY_TURN, 'status': 'inProgress', 'items': []}),
            'request tool item': request_params(
                item={'id': 'req-tool-124', 'type': 'commandExecution', 'command': PROMPT}),
            'request unknown embedded turn': request_params(
                turn={'id': AUXILIARY_TURN, 'status': 'completed', 'items': [
                    {'id': 'req-tool-125', 'type': 'commandExecution', 'command': PROMPT}]}),
        })

    def test_124_m1_m2_legitimate_reads_without_items_or_with_consistent_turn_stay_pass(self):
        def container(value):
            return lambda method, _, response: self.read_container(method, response, value)

        def response_turn(value):
            return lambda method, _, response: response['result'].__setitem__('turn', value)

        done = {'id': AUXILIARY_TURN, 'status': 'completed'}
        cases = {
            'empty turns': container([]),
            'original turn without items': container([dict(done, items=[])]),
            'original turn with final summary': lambda *_: None,
            'consistent response turn': response_turn(dict(done, items=[])),
        }
        for method in self.METHODS:
            for label, edit in cases.items():
                with self.subTest(method=method, read=label):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps()
                                         + self.mutated_read(method, edit))
                    self.assert_read_pass(before)

    def test_124_m2_capture_keeps_read_turn_metadata_and_observer_rejects_invalid_forms(self):
        for method in self.METHODS:
            with self.subTest(method=method, check='capture'):
                log = recipe_log(self.capture, self.initialize_steps()
                                 + self.read_steps(method))
                report = log.report()
                self.assert_private(report)
                response = report['events'][-1]
                self.assertEqual(response['read_turns'],
                                 [{'id': AUXILIARY_TURN, 'status': 'completed'}])
                self.assertFalse(response.get('read_invalid'))
                bad = self.mutated_read(
                    method, lambda m, _, r: self.read_turns(m, r)[0].pop('status'))
                invalid = recipe_log(self.capture, self.initialize_steps() + bad).report()
                self.assertIs(invalid['events'][-1].get('read_invalid'), True)
        marks = {
            'read_turns missing': lambda e: e.pop('read_turns'),
            'read_turns string': lambda e: e.__setitem__('read_turns', 'x'),
            'read_turns object': lambda e: e.__setitem__('read_turns', {}),
            'read_turns null': lambda e: e.__setitem__('read_turns', None),
            'read_turns other id': lambda e: e.__setitem__(
                'read_turns', [{'id': OTHER_TURN, 'status': 'completed'}]),
            'read_turns in progress': lambda e: e.__setitem__(
                'read_turns', [{'id': AUXILIARY_TURN, 'status': 'inProgress'}]),
            'read_turns without status': lambda e: e.__setitem__(
                'read_turns', [{'id': AUXILIARY_TURN}]),
            'read_turns element string': lambda e: e.__setitem__('read_turns', ['x']),
            'read_turns bad id type': lambda e: e.__setitem__(
                'read_turns', [{'id': {}, 'status': 'completed'}]),
            'read_invalid flag': lambda e: e.__setitem__('read_invalid', True),
            'read_invalid string': lambda e: e.__setitem__('read_invalid', 'no'),
        }
        for method in self.METHODS:
            for label, edit in marks.items():
                with self.subTest(method=method, mark=label):
                    before = self.checkpoint()
                    self.reconnect_reads(self.initialize_steps() + self.read_steps(method))
                    report = self.log.report()
                    edit(report['events'][-1])
                    self.save_capture(report)
                    self.assert_blocked(self.verify(before))


class RecipeObserverTests(ObserverFixture):
    """Real recipe: naming chain interleaved with product events (synthetic ids)."""
    def use(self, steps):
        self.log = recipe_log(self.capture, steps)
        self.save_capture()

    def reconnect(self):
        self.log.close('tui-1')
        for direction, message in naming_exchange()[:3]:
            self.log.message('tui-2', direction, message)
        self.save_capture()

    def test_rm2_recipe_helper_without_new_events_is_accepted_today(self):
        steps = recipe_without(recipe_steps(), 'moderation', 'unsubscribe',
                               'unsubscribe-ack', 'status-late', 'closed')
        self.use(steps)
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS', before['reasons'])
        self.assertEqual(self.verify(before)['verdict'], 'PASS')

    def test_rm2_recipe_full_lifecycle_with_unloaded_auxiliary_passes_raw_and_reconciled(self):
        self.runtime.loaded = [PRODUCT]
        self.use(recipe_steps())
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS', before['reasons'])
        self.assertEqual(before['raw_verdict'], 'PASS', before['raw_reasons'])
        self.assertEqual([row['thread_id'] for row in before['auxiliary_threads']], [AUXILIARY])
        self.assertFalse(before['auxiliary_threads'][0]['loaded'])
        self.assert_private(before)
        self.reconnect()
        after = self.verify(before)
        self.assertEqual(after['verdict'], 'PASS', after['reasons'])
        self.assertEqual(after['raw_verdict'], 'PASS', after['raw_reasons'])
        self.assertEqual((after['counts']['task_started'], after['counts']['task_complete']),
                         (1, 1))
        self.assertEqual([row['thread_id'] for row in after['auxiliary_threads']], [AUXILIARY])
        self.assert_private(after)

    def test_rm2_recipe_loaded_auxiliary_before_close_is_reconciled_then_unloaded(self):
        steps = recipe_steps()
        self.use(recipe_until(steps, 'status-late'))
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS', before['reasons'])
        self.assertEqual(before['raw_verdict'], 'BLOCKED')
        self.assertTrue(before['auxiliary_threads'][0]['loaded'])
        self.use(steps)
        self.runtime.loaded = [PRODUCT]
        self.reconnect()
        after = self.verify(before)
        self.assertEqual(after['verdict'], 'PASS', after['reasons'])
        self.assertEqual(after['raw_verdict'], 'PASS', after['raw_reasons'])
        self.assertFalse(after['auxiliary_threads'][0]['loaded'])
        self.assert_private(after)

    def test_rm2_recipe_moderation_without_unsubscribe_or_close_passes(self):
        self.use(recipe_without(recipe_steps(), 'unsubscribe', 'unsubscribe-ack',
                                'status-late', 'closed'))
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS', before['reasons'])
        after = self.verify(before)
        self.assertEqual(after['verdict'], 'PASS', after['reasons'])
        self.assert_private(after)

    def test_rm2_recipe_unsubscribe_without_close_passes(self):
        self.use(recipe_without(recipe_steps(), 'status-late', 'closed'))
        before = self.snapshot()
        self.assertEqual(before['verdict'], 'PASS', before['reasons'])
        self.assertEqual(self.verify(before)['verdict'], 'PASS')

    def assert_variants(self, variants):
        good = self.log
        before = self.snapshot()      # PASS baseline of the already supported chain
        self.assertEqual(before['verdict'], 'PASS')
        for label, steps in variants:
            with self.subTest(variant=label):
                self.use(steps)
                self.assert_blocked(self.snapshot())
                self.assert_blocked(self.verify(before))
        self.log = good

    def test_rm2_recipe_moderation_metadata_is_strictly_scoped_to_auxiliary_turn(self):
        steps = recipe_steps()
        moderation = lambda **changes: recipe_replace(steps, 'moderation', **changes)
        message = steps[_index(steps, 'moderation')][3]
        no_turn = copy.deepcopy(message)
        del no_turn['params']['turnId']
        other_turn = copy.deepcopy(message)
        other_turn['params']['turnId'] = OTHER_TURN
        self.assert_variants([
            ('other turn', moderation(message=other_turn)),
            ('missing turn', moderation(message=no_turn)),
            ('other connection', moderation(connection='tui-2')),
            ('client direction', moderation(direction='client')),
            ('before turn/start request', recipe_move(steps, 'moderation', before='turn-req')),
            ('after turn completion', recipe_move(steps, 'moderation', after='turn-completed')),
            ('after thread close', recipe_move(steps, 'moderation', after='closed')),
        ])

    def test_rm2_recipe_unsubscribe_is_single_positive_and_after_completion(self):
        steps = recipe_steps()
        again = [('unsubscribe-2', 'tui-1', 'client', request(
                      'temporary-structured-unsubscribe-0004', 'thread/unsubscribe',
                      {'threadId': AUXILIARY})),
                 ('unsubscribe-2-ack', 'tui-1', 'server', {
                      'id': 'temporary-structured-unsubscribe-0004',
                      'result': {'status': 'unsubscribed'}})]
        failed = recipe_edit(steps, 'unsubscribe-ack', lambda m: (
            m.pop('result'), m.update(error={'code': -1, 'message': ERROR})))
        moved = recipe_move(recipe_move(steps, 'unsubscribe', before='turn-completed'),
                            'unsubscribe-ack', before='turn-completed')
        self.assert_variants([
            ('error response', failed),
            ('no response', recipe_without(steps, 'unsubscribe-ack')),
            ('response on other connection',
             recipe_replace(steps, 'unsubscribe-ack', connection='tui-2')),
            ('duplicate', steps[:_index(steps, 'read')] + again + steps[_index(steps, 'read'):]),
            ('before turn completion', moved),
            ('other connection', recipe_replace(recipe_replace(
                steps, 'unsubscribe', connection='tui-2'), 'unsubscribe-ack', connection='tui-2')),
            ('server direction request', recipe_replace(steps, 'unsubscribe', direction='server')),
        ])

    def test_rm2_recipe_close_requires_acked_unsubscribe_once_on_same_connection(self):
        steps = recipe_steps()
        closed = steps[_index(steps, 'closed')]
        self.assert_variants([
            ('closed without unsubscribe',
             recipe_without(steps, 'unsubscribe', 'unsubscribe-ack')),
            ('closed with failed unsubscribe', recipe_edit(
                steps, 'unsubscribe-ack', lambda m: (m.pop('result'), m.update(
                    error={'code': -1, 'message': ERROR})))),
            ('closed before unsubscribe ack', recipe_move(steps, 'closed', before='unsubscribe-ack')),
            ('closed twice', recipe_append(steps, ('closed-2',) + closed[1:])),
            ('closed on other connection', recipe_replace(steps, 'closed', connection='tui-2')),
            ('closed from client', recipe_replace(steps, 'closed', direction='client')),
        ])

    def test_rm2_recipe_no_auxiliary_activity_after_close(self):
        steps = recipe_steps()
        after = lambda label, direction, message: recipe_append(
            steps, (label, 'tui-1', direction, message))
        item = {'id': 'late-1', 'type': 'agentMessage', 'phase': 'commentary', 'text': ''}
        variants = [
            ('status', after('x', 'server', notification('thread/status/changed', {
                'threadId': AUXILIARY, 'status': {'type': 'idle'}}))),
            ('token usage', after('x', 'server', _thread_event(
                'thread/tokenUsage/updated', AUXILIARY, AUXILIARY_TURN, tokenUsage={}))),
            ('thread started', after('x', 'server', notification('thread/started', {
                'thread': {'id': AUXILIARY, 'ephemeral': True, 'turns': []}}))),
            ('turn started', after('x', 'server', _turn_event(
                'turn/started', AUXILIARY, AUXILIARY_TURN, 'inProgress'))),
            ('turn completed', after('x', 'server', _turn_event(
                'turn/completed', AUXILIARY, AUXILIARY_TURN, 'completed'))),
            ('item started', after('x', 'server', _aux_item('item/started', item))),
            ('item completed', after('x', 'server', _aux_item('item/completed', item))),
            ('delta', after('x', 'server', _thread_event(
                'item/agentMessage/delta', AUXILIARY, AUXILIARY_TURN, itemId='late-1',
                delta='late'))),
            ('tool item', after('x', 'server', _aux_item('item/completed', {
                'id': 'late-tool', 'type': 'commandExecution', 'status': 'completed',
                'command': PROMPT}))),
            ('client request', after('x', 'client', request('late-req', 'thread/read', {
                'threadId': AUXILIARY, 'includeTurns': False}))),
            ('server request', after('x', 'server', request('late-srv', 'item/tool/call', {
                'threadId': AUXILIARY, 'turnId': AUXILIARY_TURN}))),
        ]
        self.assert_variants(variants)


    def test_rm2_recipe_server_requests_without_thread_cannot_masquerade_as_lifecycle(self):
        steps = recipe_steps()
        variants = []
        for method in ('thread/unsubscribe', 'thread/closed'):
            row = ('x', 'tui-1', 'server', request('srv-' + method[7:], method, {}))
            variants.append((method + ' server request',
                             steps[:_index(steps, 'unsubscribe')] + [row]
                             + steps[_index(steps, 'unsubscribe'):]))
            variants.append((method + ' server request at end', recipe_append(steps, row)))
        self.assert_variants(variants)


if __name__ == '__main__':
    unittest.main()
