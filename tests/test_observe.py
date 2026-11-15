"""Read-only observer behavior against an isolated fake Codex proxy."""
import importlib.util
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/agentic-observe.py'
SPEC = importlib.util.spec_from_file_location('observe', SCRIPT)
OBSERVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBSERVE)

FAKE = r'''import base64, hashlib, json, os, struct, sys, time
mode = os.environ.get('FAKE_MODE', 'normal')
if mode == 'dead':
    sys.exit(2)
headers = {}
while True:
    line = sys.stdin.buffer.readline()
    if line in (b'\r\n', b'\n', b''):
        break
    if b':' in line:
        key, value = line.decode().split(':', 1)
        headers[key.lower()] = value.strip()
if mode == 'oversizeheaders':
    sys.stdout.buffer.write(b'HTTP/1.1 101 Switching Protocols\r\nX: '+b'x'*20000)
    sys.stdout.buffer.flush(); time.sleep(10)
key = headers.get('sec-websocket-key', '')
accept = base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
if mode == 'badaccept':
    accept = 'invalid'
status = '200 OK' if mode=='badstatus' else '101 Switching Protocols'
upgrade = 'invalid' if mode=='badupgrade' else 'websocket'
connection = 'close' if mode=='badconnection' else 'Upgrade'
sys.stdout.buffer.write(('HTTP/1.1 '+status+'\r\nUpgrade: '+upgrade+'\r\nConnection: '+connection+'\r\nSec-WebSocket-Accept: '+accept+'\r\n\r\n').encode())
sys.stdout.buffer.flush()
if mode == 'notreading':
    time.sleep(1.2); sys.exit(0)
def exact(size):
    result = b''
    while len(result)<size:
        chunk = sys.stdin.buffer.read(size-len(result))
        if not chunk:
            sys.exit(0)
        result += chunk
    return result
def receive():
    first, second = exact(2)
    assert first & 128 and second & 128, 'client frame must be final and masked'
    length=second&127
    if length==126: length=struct.unpack('!H',exact(2))[0]
    elif length==127: length=struct.unpack('!Q',exact(8))[0]
    mask=exact(4); payload=exact(length)
    return first&15, bytes(c^mask[i%4] for i,c in enumerate(payload))
def frame(payload, opcode=1, final=True, masked=False):
    first=(128 if final else 0)|opcode
    length=len(payload)
    tag=128 if masked else 0
    header=bytes([first,tag|length]) if length<126 else (bytes([first,tag|126])+struct.pack('!H',length) if length<65536 else bytes([first,tag|127])+struct.pack('!Q',length))
    if masked:
        header+=b'abcd'; payload=bytes(c^b'abcd'[i%4] for i,c in enumerate(payload))
    sys.stdout.buffer.write(header+payload);sys.stdout.buffer.flush()
def reply(message):
    payload=json.dumps(message).encode()
    if mode=='fragmentping':
        middle=len(payload)//2
        frame(payload[:middle],final=False);frame(b'keepalive',opcode=9)
        opcode,pong=receive();assert opcode==10 and pong==b'keepalive'
        frame(payload[middle:],opcode=0)
    else:
        frame(payload)
while True:
    opcode,payload=receive()
    if opcode==10: continue
    assert opcode==1
    request=json.loads(payload)
    with open(os.environ['FAKE_LOG'],'a') as log:
        log.write(json.dumps({'argv':sys.argv[1:],'request':request})+'\n')
    if request['method']=='initialized': continue
    if mode=='fragment':
        sys.stdout.buffer.write(bytes([129,100])+b'{');sys.stdout.buffer.flush();time.sleep(10)
    elif mode=='oversize':
        sys.stdout.buffer.write(bytes([129,127])+struct.pack('!Q',1024*1024+1));sys.stdout.buffer.flush();time.sleep(10)
    elif mode=='maskedserver': frame(b'{}',masked=True)
    elif mode=='rsv':
        sys.stdout.buffer.write(bytes([0xc1,2])+b'{}');sys.stdout.buffer.flush()
    elif mode=='fragmentedcontrol': frame(b'ping',opcode=9,final=False)
    elif mode=='invalidutf8': frame(b'\xff')
    elif mode=='close': frame(b'',opcode=8)
    elif mode=='fragmentsoverflow':
        frame(b'x'*700000,final=False)
        sys.stdout.buffer.write(bytes([128,127])+struct.pack('!Q',400000));sys.stdout.buffer.flush();time.sleep(10)
    elif mode=='binary': frame(b'{}',opcode=2)
    elif mode=='continuation': frame(b'{}',opcode=0)
    elif mode=='badjson': frame(b'{')
    elif mode=='apierror': reply({'id':request['id'],'error':{'code':-99,'message':'SECRET SERVER DETAIL'}})
    elif request['method']=='initialize':
        reply({'method':'thread/status/changed','params':{}})
        reply({'id':999,'result':{'ignored':True}})
        reply({'id':request['id'],'result':{}})
    elif request['method']=='thread/list': reply({'id':request['id'],'result':json.loads(os.environ['FAKE_PAYLOAD'])})
    else: reply({'id':request['id'],'error':{'code':-32601}})
'''



def agent(cwd, **updates):
    row = {'id':'agent-1', 'cwd':str(cwd), 'agentRole':'agentic_explorer',
           'agentNickname':'Scout', 'status':{'type':'active','activeFlags':['waitingOnApproval']},
           'source':{'subAgent':{'thread_spawn':{'parent_thread_id':'parent-1','depth':1}}},
           'preview':'SECRET CONVERSATION', 'name':'SECRET TITLE', 'model':'SECRET MODEL'}
    row.update(updates)
    return row


class ObserverTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'project'
        self.repo.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        fake = self.bin / 'codex'
        fake.write_text('#!' + sys.executable + '\n' + FAKE)
        fake.chmod(0o755)
        self.log = self.root / 'requests.jsonl'
        self.env = {'PATH':str(self.bin)+os.pathsep+os.environ.get('PATH',os.defpath),
                    'FAKE_LOG':str(self.log),'FAKE_MODE':'normal'}

    def observe(self, rows=None, *, mode='normal', next_cursor=None, **options):
        payload = {'data':rows if rows is not None else [agent(self.repo)],
                   'nextCursor':next_cursor}
        with patch.dict(os.environ, {**self.env,'FAKE_MODE':mode,
                                    'FAKE_PAYLOAD':json.dumps(payload)}):
            return OBSERVE.snapshot(self.repo, **options)

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_only_observation_rpc_and_minimal_projection(self):
        snapshot = self.observe(socket_path='/tmp/specific.sock')
        self.assertEqual(snapshot['source'],'codex-app-server')
        self.assertEqual(snapshot['repo'],str(self.repo.resolve()))
        self.assertEqual(len(snapshot['agents']),1)
        row = snapshot['agents'][0]
        self.assertEqual(row, {'id':'agent-1','role':'agentic_explorer','nickname':'Scout',
                              'status':'active','active_flags':['waitingOnApproval'],
                              'cwd':str(self.repo),'parent_id':'parent-1'})
        self.assertNotIn('SECRET',json.dumps(snapshot))
        self.assertFalse(snapshot['truncated'])
        requests = self.requests()
        self.assertEqual([item['request']['method'] for item in requests],
                         ['initialize','initialized','thread/list'])
        self.assertEqual(requests[0]['argv'],['app-server','proxy','--sock','/tmp/specific.sock'])
        params = requests[-1]['request']['params']
        self.assertTrue(params['useStateDbOnly'])
        self.assertEqual(params['cwd'],[str(self.repo)])
        self.assertEqual(params['limit'],50)
        self.assertEqual(params['modelProviders'],[])
        self.assertEqual(set(params['sourceKinds']),
                         {'subAgent','subAgentReview','subAgentCompact','subAgentThreadSpawn','subAgentOther'})

    def test_filters_out_other_projects_and_primary_sessions(self):
        rows = [agent(self.repo),agent(self.root/'project-other',id='other'),
                agent(self.repo,id='primary',source='cli')]
        self.assertEqual([r['id'] for r in self.observe(rows)['agents']],['agent-1'])

    def test_includes_known_git_worktrees(self):
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=Test',
                        '-c','user.email=test@example.com','commit','--allow-empty','-qm','Init'],check=True)
        linked = self.root/'linked tree'
        subprocess.run(['git','-C',str(self.repo),'worktree','add','-qb','feature',str(linked)],
                       check=True,capture_output=True)
        snapshot = self.observe([agent(linked)])
        self.assertEqual(snapshot['agents'][0]['cwd'],str(linked))
        self.assertEqual(set(self.requests()[-1]['request']['params']['cwd']),
                         {str(self.repo),str(linked)})

    def test_role_falls_back_to_spawn_metadata_without_guessing(self):
        source={'subAgent':{'thread_spawn':{'agent_role':'unit-test-writer',
                                           'agent_nickname':'Writer','parent_thread_id':'p'}}}
        rows=[agent(self.repo,agentRole=None,agentNickname=None,source=source),
              agent(self.repo,id='unknown',agentRole=None,agentNickname=None,
                    status={'type':'future-state'},source={'subAgent':'review'})]
        result=self.observe(rows)['agents']
        self.assertEqual(result[0]['role'],'unit-test-writer')
        self.assertEqual(result[0]['nickname'],'Writer')
        self.assertEqual(result[1]['role'],'unknown')
        self.assertEqual(result[1]['status'],'future-state')

    def test_missing_state_is_unknown_not_completion(self):
        row=self.observe([agent(self.repo,status=None)])['agents'][0]
        self.assertEqual(row['status'],'unknown')
        self.assertEqual(row['active_flags'],[])

    def test_terminal_controls_are_neutralized_in_every_text_field(self):
        row=agent(self.repo,id='agent\x1b[31m',agentRole='explorer\nBAD',
                  agentNickname='Scout\r\u202eNAME',
                  status={'type':'active\x07','activeFlags':['wait\x1b]0;title\x07']})
        snapshot=self.observe([row])
        for value in snapshot['agents'][0].values():
            for text in value if isinstance(value,list) else [value]:
                if isinstance(text,str):
                    self.assertFalse(any(ord(c)<32 or 0x7f<=ord(c)<=0x9f or c=='\u202e' for c in text))

    def test_pagination_marks_truncation_without_extra_requests(self):
        result=self.observe(next_cursor='more',limit=2)
        self.assertTrue(result['truncated'])
        self.assertEqual(len(self.requests()),3)

    def test_no_agents_is_a_successful_empty_snapshot(self):
        self.assertEqual(self.observe([])['agents'],[])

    def test_error_does_not_expose_server_body(self):
        with self.assertRaises(OBSERVE.ObservationError) as caught:
            self.observe(mode='apierror')
        self.assertNotIn('SECRET',str(caught.exception))

    def test_broken_proxy_and_malformed_json_are_observation_errors(self):
        for mode in ('dead','badjson','badaccept','maskedserver','binary','continuation','oversizeheaders','badstatus','badupgrade','badconnection',
                     'rsv','fragmentedcontrol','invalidutf8','close','fragmentsoverflow'):
            with self.subTest(mode=mode),self.assertRaises(OBSERVE.ObservationError):
                self.observe(mode=mode,timeout=.5)

    def test_fragmented_response_with_ping_pong_is_reassembled(self):
        result=self.observe(mode='fragmentping')
        self.assertEqual(result['agents'][0]['id'],'agent-1')

    def test_fragment_without_newline_obeys_deadline(self):
        started=time.monotonic()
        with self.assertRaises(OBSERVE.ObservationError):
            self.observe(mode='fragment',timeout=.15)
        self.assertLess(time.monotonic()-started,2)

    def test_oversized_message_is_rejected_without_waiting_for_newline(self):
        started=time.monotonic()
        with self.assertRaises(OBSERVE.ObservationError):
            self.observe(mode='oversize',timeout=2)
        self.assertLess(time.monotonic()-started,2)

    def test_blocked_proxy_input_obeys_deadline(self):
        started=time.monotonic()
        with patch.dict(os.environ,{**self.env,'FAKE_MODE':'notreading'}):
            with self.assertRaises(OBSERVE.ObservationError):
                with OBSERVE._Proxy(None,time.monotonic()+.15) as proxy:
                    proxy._send({'large':'x'*900000})
        self.assertLess(time.monotonic()-started,1)

    def test_invalid_data_response_is_not_reported_as_empty(self):
        with patch.dict(os.environ,{**self.env,'FAKE_PAYLOAD':'{"data":"invalid"}'}):
            with self.assertRaises(OBSERVE.ObservationError):
                OBSERVE.snapshot(self.repo)

    def test_timeout_and_limit_bounds_are_validated(self):
        for options in ({'timeout':0},{'timeout':float('nan')},{'timeout':float('inf')},
                        {'limit':0},{'limit':201},{'limit':True}):
            with self.subTest(options=options),self.assertRaises(OBSERVE.ObservationError):
                self.observe(**options)
        self.assertFalse(self.log.exists())

    def test_excessive_timeout_is_rejected_before_proxy_launch(self):
        with patch.object(OBSERVE, '_Proxy', side_effect=AssertionError('proxy started')):
            with self.assertRaises(OBSERVE.ObservationError):
                self.observe(timeout=1e300)

    def test_interruption_during_handshake_reaps_only_the_proxy(self):
        for interruption in (KeyboardInterrupt, SystemExit):
            with self.subTest(interruption=interruption.__name__):
                transport = OBSERVE._WS.WebSocketProxy(None, time.monotonic() + 1)
                transport.command = [sys.executable, '-c', 'import time; time.sleep(30)']
                try:
                    with patch.object(transport, '_handshake', side_effect=interruption):
                        with self.assertRaises(interruption):
                            with transport:
                                self.fail('handshake unexpectedly succeeded')
                    alive = transport.process.poll() is None
                finally:
                    if transport.process and transport.process.poll() is None:
                        transport.process.terminate()
                        transport.process.wait(timeout=2)
                    if transport.process:
                        transport.process.stdin.close()
                        transport.process.stdout.close()
                    transport.selector.close()
                self.assertFalse(alive, 'interrupted handshake leaked a proxy process')

    def test_cli_json_and_nonzero_error_without_details(self):
        env={**os.environ,**self.env,'FAKE_PAYLOAD':json.dumps({'data':[agent(self.repo)]})}
        result=subprocess.run([sys.executable,str(SCRIPT),'--repo',str(self.repo)],
                              capture_output=True,text=True,env=env,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['agents']),1)
        env['FAKE_MODE']='apierror'
        result=subprocess.run([sys.executable,str(SCRIPT),'--repo',str(self.repo)],
                              capture_output=True,text=True,env=env,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('SECRET',result.stdout+result.stderr)


# Extend the isolated proxy for context tests without changing the historical fake.
CONTEXT_FAKE = FAKE.replace(
    "elif request['method']=='thread/list':",
    "elif request['method']=='thread/read': "
    "reply({'id':request['id'],'result':json.loads(os.environ['FAKE_PAYLOAD'])})\n"
    "    elif request['method']=='thread/list':")


class ContextObserverTests(unittest.TestCase):
    """108-PR1 M1–M5: current occupancy, evidence freshness and read-only boundaries."""

    def setUp(self):
        ObserverTests.setUp(self)
        (self.bin / 'codex').write_text('#!' + sys.executable + '\n' + CONTEXT_FAKE)
        self.thread_id = 'thread-context-111'
        self.rollout = self.root / 'rollout.jsonl'
        self.measured = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.metadata = {'type':'session_meta', 'timestamp':self.measured.isoformat(),
                         'payload':{'id':self.thread_id, 'cwd':str(self.repo)}}
        self.event = self.token_event()
        self.thread = {'id':self.thread_id, 'cwd':str(self.repo),
                       'path':str(self.rollout), 'preview':'SECRET CONVERSATION',
                       'name':'SECRET TITLE', 'turns':[{'text':'SECRET TRANSCRIPT'}]}
        self.write_rollout()

    def token_event(self, used=400, capacity=1000, *, measured=None):
        return {'type':'event_msg', 'timestamp':(measured or self.measured).isoformat(),
                'payload':{'type':'token_count', 'info':{
                    'last_token_usage':{'total_tokens':used},
                    'total_token_usage':{'total_tokens':9000},
                    'model_context_window':capacity}}}

    def write_rollout(self, records=None, suffix=''):
        records = [self.metadata, self.event] if records is None else records
        self.rollout.write_text(''.join(json.dumps(row) + '\n' for row in records)
                                + suffix, encoding='utf-8')

    def environment(self, mode='normal', payload=None):
        return {**os.environ, **self.env, 'FAKE_MODE':mode,
                'FAKE_PAYLOAD':json.dumps({'thread':self.thread} if payload is None else payload)}

    def observe_context(self, *, mode='normal', payload=None, **options):
        function = getattr(OBSERVE, 'snapshot_context', None)
        self.assertTrue(callable(function), 'M1 requires snapshot_context(repo, thread_id, ...)')
        with patch.dict(os.environ, self.environment(mode, payload)):
            return function(self.repo, self.thread_id, **options)

    def cli_context(self, *, mode='normal', timeout=5, bounded_memory=False):
        def limit_memory():
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)

        return subprocess.run(
            [sys.executable, str(SCRIPT), '--repo', str(self.repo),
             '--context-thread', self.thread_id, '--timeout', str(timeout)],
            capture_output=True, text=True, env=self.environment(mode), timeout=4,
            preexec_fn=limit_memory if bounded_memory else None)

    def assert_unavailable(self, **options):
        with self.assertRaises(OBSERVE.ObservationError) as caught:
            self.observe_context(**options)
        message = str(caught.exception)
        self.assertTrue(message.strip(), 'unavailable evidence needs an explicit diagnostic')
        self.assertNotIn('SECRET', message)

    def assert_cli_unavailable(self, *, timeout=5, mode='normal', bounded_memory=False):
        result = self.cli_context(timeout=timeout, mode=mode, bounded_memory=bounded_memory)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '', 'context errors must be JSON, without traceback')
        error = json.loads(result.stdout)
        self.assertIsInstance(error.get('error'), str)
        self.assertTrue(error['error'].strip())
        self.assertNotIn('SECRET', result.stdout)
        self.assertNotIn('used_tokens', error, 'an error must not fabricate an empty measurement')

    def test_current_last_usage_and_minimal_dated_projection(self):
        before = datetime.now(timezone.utc)
        result = self.observe_context(socket_path='/tmp/context-test.sock')
        after = datetime.now(timezone.utc)
        expected = {'source':'codex-rollout', 'thread_id':self.thread_id,
                    'repo':str(self.repo.resolve()), 'model_context_window':1000,
                    'used_tokens':400, 'used_percent':40, 'remaining_percent':60,
                    'basis':'last_total_tokens/model_context_window',
                    'threshold_state':'handoff_required'}
        for key, value in expected.items():
            self.assertEqual(result[key], value, key)
        measured = datetime.fromisoformat(result['measured_at'].replace('Z', '+00:00'))
        observed = datetime.fromisoformat(result['observed_at'].replace('Z', '+00:00'))
        self.assertEqual(measured, self.measured)
        self.assertLessEqual(before, observed)
        self.assertLessEqual(observed, after)
        self.assertNotIn('SECRET', json.dumps(result))
        for key in ('total_token_usage', 'turns', 'preview', 'name', 'payload', 'info'):
            self.assertNotIn(key, result)
        requests = ObserverTests.requests(self)
        self.assertEqual([row['request']['method'] for row in requests],
                         ['initialize', 'initialized', 'thread/read'])
        self.assertEqual(requests[0]['argv'],
                         ['app-server', 'proxy', '--sock', '/tmp/context-test.sock'])
        self.assertEqual(requests[-1]['request']['params']['threadId'], self.thread_id)
        self.assertFalse(requests[-1]['request']['params'].get('includeTurns', False))

    def test_thresholds_and_complement_use_the_raw_context_ratio(self):
        cases = {39:'below_threshold', 40:'handoff_required', 45:'handoff_required',
                 50:'target_exceeded', 53:'target_exceeded'}
        for percent, state in cases.items():
            with self.subTest(percent=percent):
                self.write_rollout([self.metadata, self.token_event(percent * 1000, 100000)])
                result = self.observe_context()
                self.assertEqual(result['used_percent'], percent)
                self.assertEqual(result['remaining_percent'], 100 - percent)
                self.assertEqual(result['threshold_state'], state)
                # This basis explicitly identifies the raw ratio, not the TUI baseline adjustment.
                self.assertEqual(result['basis'], 'last_total_tokens/model_context_window')

    def test_latest_token_event_wins_even_when_context_usage_decreases(self):
        self.write_rollout([self.metadata, self.token_event(530), self.token_event(390)])
        result = self.observe_context()
        self.assertEqual(result['used_tokens'], 390)
        self.assertEqual(result['threshold_state'], 'below_threshold')

    def test_cumulative_usage_is_neither_required_nor_a_fallback(self):
        info = self.event['payload']['info']
        del info['total_token_usage']
        self.write_rollout()
        self.assertEqual(self.observe_context()['used_tokens'], 400)
        info['total_token_usage'] = {'total_tokens':400}
        del info['last_token_usage']
        self.write_rollout()
        self.assert_unavailable()

    def test_explicit_zero_usage_is_valid_when_evidence_is_present(self):
        self.write_rollout([self.metadata, self.token_event(0)])
        result = self.observe_context()
        self.assertEqual(result['used_tokens'], 0)
        self.assertEqual(result['remaining_percent'], 100)
        self.assertEqual(result['threshold_state'], 'below_threshold')

    def test_default_freshness_rejects_121_second_old_event(self):
        old = datetime.now(timezone.utc) - timedelta(seconds=121)
        self.write_rollout([self.metadata, self.token_event(measured=old)])
        self.assert_unavailable()

    def test_max_age_is_configurable_without_refreshing_measured_at(self):
        old = datetime.now(timezone.utc) - timedelta(seconds=180)
        self.write_rollout([self.metadata, self.token_event(measured=old)])
        result = self.observe_context(max_age=240)
        self.assertEqual(datetime.fromisoformat(result['measured_at'].replace('Z', '+00:00')), old)
        self.assert_unavailable(max_age=60)

    def test_future_missing_and_invalid_timestamps_are_unavailable(self):
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        for stamp in (future, None, '', 'SECRET INVALID DATE', '2026-11-15T12:00:00', True):
            with self.subTest(timestamp=stamp):
                self.event['timestamp'] = stamp
                self.write_rollout()
                self.assert_unavailable()
        del self.event['timestamp']
        self.write_rollout()
        self.assert_unavailable()

    def test_no_token_event_or_missing_usage_never_becomes_zero(self):
        records = ([self.metadata], [], [self.metadata, {'type':'event_msg',
                   'timestamp':self.measured.isoformat(), 'payload':{'type':'token_count'}}])
        for rows in records:
            with self.subTest(rows=rows):
                self.write_rollout(rows)
                self.assert_unavailable()
        for info in (None, [], 'SECRET INVALID USAGE', {}, {'model_context_window':1000},
                     {'last_token_usage':{'total_tokens':400}},
                     {'last_token_usage':{}, 'model_context_window':1000},
                     {'last_token_usage':None, 'model_context_window':1000}):
            with self.subTest(info=info):
                self.event['payload']['info'] = info
                self.write_rollout()
                self.assert_unavailable()

    def test_invalid_token_counts_and_capacities_are_unavailable(self):
        invalid = {'used':(None, True, -1, 1.5, '400', float('nan'), float('inf')),
                   'capacity':(None, False, 0, -1000, '1000', float('nan'), float('inf'))}
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    event = self.token_event(**{field:value})
                    self.write_rollout([self.metadata, event])
                    self.assert_unavailable()

    def test_invalid_latest_event_cannot_fall_back_to_older_valid_usage(self):
        self.write_rollout([self.metadata, self.event, self.token_event(used=None)])
        self.assert_unavailable()

    def test_thread_read_requires_exact_id_and_authorized_cwd(self):
        original = dict(self.thread)
        for updates in ({'id':'other-thread'}, {'id':None}, {'cwd':str(self.root / 'other')},
                        {'cwd':str(self.repo / 'child')}, {'cwd':None}):
            with self.subTest(updates=updates):
                self.thread = {**original, **updates}
                self.assert_unavailable()
        for key in ('id', 'cwd'):
            with self.subTest(missing=key):
                self.thread = dict(original)
                del self.thread[key]
                self.assert_unavailable()

    def test_session_metadata_must_confirm_both_id_and_cwd(self):
        for payload in ({'id':'other-thread', 'cwd':str(self.repo)},
                        {'id':self.thread_id, 'cwd':str(self.root)},
                        {'id':self.thread_id}, {'cwd':str(self.repo)}, None):
            with self.subTest(payload=payload):
                self.write_rollout([{'type':'session_meta', 'payload':payload}, self.event])
                self.assert_unavailable()
        self.write_rollout([self.event])
        self.assert_unavailable()

    def test_known_git_worktree_is_authorized_in_both_sources(self):
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.com', 'commit', '--allow-empty',
                        '-qm', 'Init'], check=True)
        linked = self.root / 'linked tree'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-qb', 'feature',
                        str(linked)], check=True, capture_output=True)
        self.thread['cwd'] = str(linked)
        self.metadata['payload']['cwd'] = str(linked)
        self.write_rollout()
        self.assertEqual(self.observe_context()['repo'], str(self.repo.resolve()))
        # Authorization of both paths does not replace agreement between the two sources.
        self.metadata['payload']['cwd'] = str(self.repo)
        self.write_rollout()
        self.assert_unavailable()

    def test_missing_malformed_and_unreadable_rollout_are_unavailable(self):
        for payload in ({}, {'thread':None}, {'thread':[]}, {'thread':{}}):
            with self.subTest(payload=payload):
                self.assert_unavailable(payload=payload)
        for path in (None, '', str(self.root / 'missing.jsonl'), str(self.root)):
            with self.subTest(path=path):
                self.thread['path'] = path
                self.assert_unavailable()
        self.thread['path'] = str(self.rollout)
        for content in ('SECRET MALFORMED JSON\n', '\xff\n'):
            self.rollout.write_bytes(content.encode('latin-1'))
            self.assert_unavailable()

    def test_partial_concurrent_append_never_becomes_a_complete_measurement(self):
        partial = json.dumps(self.token_event(530))[:-10]
        self.write_rollout([self.metadata], suffix=partial)
        self.assert_unavailable()
        self.write_rollout(suffix=partial)
        # Either the previous complete, fresh event or explicit unavailability is safe.
        try:
            result = self.observe_context()
        except OBSERVE.ObservationError as error:
            self.assertNotIn('SECRET', str(error))
        else:
            self.assertEqual(result['used_tokens'], 400)
            self.assertEqual(result['threshold_state'], 'handoff_required')

    def test_non_regular_rollout_is_rejected_without_blocking(self):
        fifo = self.root / 'SECRET-fifo'
        os.mkfifo(fifo)
        self.thread['path'] = str(fifo)
        self.assert_cli_unavailable(timeout=.2)

    def test_oversized_sparse_rollout_is_bounded_without_a_full_scan(self):
        # A terabyte of sparse holes costs no transcript/disk allocation and cannot be scanned.
        with self.rollout.open('wb') as output:
            output.write((json.dumps(self.metadata) + '\n').encode())
            output.seek(1 << 40)
            output.write(b'SECRET UNTRUSTED TAIL\n')
        self.assert_cli_unavailable(timeout=.2, bounded_memory=True)

    def test_context_proxy_failure_obeys_timeout_and_does_not_leak(self):
        self.assert_unavailable(mode='apierror')
        started = time.monotonic()
        self.assert_unavailable(mode='fragment', timeout=.15)
        self.assertLess(time.monotonic() - started, 2)

    def test_cli_opt_in_success_and_json_errors_without_transcript(self):
        result = self.cli_context()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        value = json.loads(result.stdout)
        self.assertEqual(value['thread_id'], self.thread_id)
        self.assertEqual(value['used_tokens'], 400)
        self.assertEqual(value['basis'], 'last_total_tokens/model_context_window')
        self.assertNotIn('agents', value)
        self.assertNotIn('SECRET', result.stdout)
        self.assert_cli_unavailable(mode='apierror')
        for measured in (datetime.now(timezone.utc) - timedelta(seconds=121),
                         datetime.now(timezone.utc) + timedelta(minutes=5)):
            with self.subTest(measured=measured):
                self.write_rollout([self.metadata, self.token_event(measured=measured)])
                self.assert_cli_unavailable()
        self.write_rollout([self.metadata])
        self.assert_cli_unavailable()


if __name__=='__main__':
    unittest.main()


class ContextEdgeCaseTests(unittest.TestCase):
    """108-PR1 review findings: malformed tail, strict deadline, numeric bounds."""

    # Reuse the fixtures without re-running the inherited tests.
    tearDown = getattr(ObserverTests, 'tearDown', lambda self: None)
    setUp = ContextObserverTests.setUp
    token_event = ContextObserverTests.token_event
    write_rollout = ContextObserverTests.write_rollout
    environment = ContextObserverTests.environment
    observe_context = ContextObserverTests.observe_context
    cli_context = ContextObserverTests.cli_context
    assert_unavailable = ContextObserverTests.assert_unavailable
    assert_cli_unavailable = ContextObserverTests.assert_cli_unavailable

    def test_complete_malformed_line_after_counter_is_refused(self):
        for garbage in ('{broken SECRET}', '[1, 2]', '"SECRET"'):
            with self.subTest(garbage=garbage):
                self.write_rollout([self.metadata, self.token_event(390)],
                                   suffix=garbage + '\n')
                self.assert_unavailable()
                self.assert_cli_unavailable()

    def test_newest_valid_counter_wins_over_older_damage(self):
        self.write_rollout([self.metadata, self.token_event(390)], suffix='{broken\n')
        with self.rollout.open('a', encoding='utf-8') as output:
            output.write(json.dumps(self.token_event(530)) + '\n')
        self.assertEqual(self.observe_context()['used_tokens'], 530)

    def test_partial_final_fragment_without_newline_is_still_ignored(self):
        self.write_rollout([self.metadata, self.token_event(530)], suffix='{"type":"event_ms')
        self.assertEqual(self.observe_context()['used_tokens'], 530)

    def test_slow_journal_read_never_succeeds_after_the_deadline(self):
        real = os.pread

        def slow(*args):
            time.sleep(.15)
            return real(*args)

        started = time.monotonic()
        with patch.object(OBSERVE.os, 'pread', slow):
            self.assert_unavailable(timeout=.1)
        self.assertLess(time.monotonic() - started, 1)

    def test_slow_journal_parsing_never_succeeds_after_the_deadline(self):
        real = OBSERVE._json_line

        def slow(raw):
            time.sleep(.15)
            return real(raw)

        self.write_rollout([self.metadata] + [self.token_event(390)] * 5)
        started = time.monotonic()
        with patch.object(OBSERVE, '_json_line', slow):
            self.assert_unavailable(timeout=.1)
        self.assertLess(time.monotonic() - started, 1)

    def test_huge_token_count_is_refused_without_overflow(self):
        self.event['payload']['info']['last_token_usage']['total_tokens'] = 10 ** 1000
        self.write_rollout()
        self.assert_unavailable()
        self.assert_cli_unavailable()

    def test_extreme_dates_and_ages_are_refused_without_overflow(self):
        self.write_rollout([self.metadata, {**self.event,
                           'timestamp':'0001-01-01T00:00:00+01:00'}])
        for max_age in (10 ** 12, 120):
            with self.subTest(max_age=max_age):
                self.assert_unavailable(max_age=max_age)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--repo', str(self.repo),
             '--context-thread', self.thread_id, '--max-age', str(10 ** 12)],
            capture_output=True, text=True, env=self.environment(), timeout=4)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '')
        self.assertTrue(json.loads(result.stdout)['error'].strip())
        self.write_rollout()
        self.assert_unavailable(max_age=10 ** 12)
