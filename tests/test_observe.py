"""Read-only observer behavior against an isolated fake Codex proxy."""
import importlib.util
import json
import os
from pathlib import Path
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


if __name__=='__main__':
    unittest.main()
