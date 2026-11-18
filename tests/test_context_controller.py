"""#114 C1–C6 / RM1–10: durable, opt-in context renewal (unit contracts).

Public API fixed before product implementation:
  Controller(request, backend=None, clock=None).step() -> status dict;
  Controller(...).status() -> persisted, read-only status dict.
  ControllerError is the explicit invalid-request/storage/ownership error.
  Expected operational failures return phase='blocked', diagnostic and checkpoint.
  CLI: run --request JSON [--once]; status --request JSON (no runtime effects).

Request = the existing context-launch request, plus mission_id; transition_id and
writers_stopped are not authority to adopt an existing session. Each generation,
including zero, must be created by the managed controller. Module-level launch,
snapshot_context, save_checkpoint and validate_checkpoint are the existing APIs,
not replacements for their validation or persistence. clock() returns UTC datetime.
step is bounded: observe/advance until waiting, working, recovering, or blocked;
it owns a canonical worktree/mission lock for the entire step. Runtime waits must
return, never kill or transfer on timeout. Generation numbers start at zero.

Backend boundary (all methods concern actual RPC/process/rollout IO):
  probe() -> Linux/gnome-terminal/Codex 0.169.0 + systemd_user/cgroup_v2 booleans;
  prepare_generation(mission_id, generation, worktree) -> boundary identity;
  session_state(session) -> {status: idle|active, turn_id, tools_running};
  rpc(endpoint, method, params) -> existing app-server response;
  submission_evidence(operation) -> {thread_id, turn_id, nonce} or None;
  handoff_source(session) -> path to draft written by that session;
  close_admission(identity), quiescent(identity), retire(identity), closure(identity);
  bootstrap_receipt(session, expected) -> {**expected, instructions_read: True,
      handoff_read: True, reconciled: True}, or None while not ready.
  These receipts must be verified runtime evidence, not agent claims of PASS.
  launch(request, backend=...) is idempotent per transition, as in #113. Its
  request.next_action includes BOOTSTRAP_ONLY and awaits explicit dispatch;
  the existing start-ticket prompt must not authorize business work immediately.
  Sessions
  contain its receipt plus socket and boundary; permissions are checked before
  dispatch. Bootstrap expected binds thread, worktree, branch, head, plan hash,
  handoff_sha256, parent_permissions, and dirty (relative path -> content SHA256,
  null for deletion). No business dispatch
  until receipt and fresh <40% measurement. Work fingerprint and next action,
  not nonce/time/generation, determine progress.

Durable status fields used here: mission_id, generation, phase, checkpoint
  {path, sha256}, diagnostic, measurement, operations (list). Each mutation is
  recorded BEFORE RPC as {kind: handoff|correction|dispatch, method, nonce,
  thread_id, phase: sending}; outcome unknown is reconciled, never re-sent.

SystemdBoundary(state_path, run=None, cgroup_root='/sys/fs/cgroup') is the real
subprocess/filesystem adapter: reserve(mission_id,generation,role,worktree),
spawn(identity,argv,cwd), admit(identity), close_admission(identity),
inspect(identity), closure(identity), retire(identity). Identities bind unit,
owner_token, invocation_id, control_group. reserve persists before spawn;
spawn wraps the command after GNOME '--', not merely the GNOME client.
spawn requires ExitType=cgroup, RemainAfterExit=yes and SendSIGKILL=no.
Closure requires closed admission and the exact unit/InvocationID, plus either
regular cgroup.events populated=0 under the recorded ControlGroup, or a loaded
active/exited unit with ExitType=cgroup, RemainAfterExit=yes, SendSIGKILL=no and
an explicitly empty ControlGroup. Missing unit/PID/events alone are not proof.
A positive closure receipt may be persisted before final unit cleanup.
admit-exec --state PATH --unit UNIT --token TOKEN -- ARGV rechecks durable
admission before exec. Missing/changed identities cannot authorize closure.

No real Codex, terminal, service manager or external action is started here.
These deterministic tests do not satisfy the required two-cycle real recipe.
"""
import contextlib
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from test_checkpoint import manual_handoff

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / 'scripts/agentic-context.py'
SECRET = 'PRIVATE_CONTROLLER_FIXTURE_114_NEVER_PRINT'


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


class RuntimeBoundary:
    """IO spy, with durable-effect assertions; never decides controller phases."""
    def __init__(self, fixture):
        self.fixture = fixture
        self.calls = []
        self.boundaries = {}
        self.sessions = {}
        self.last_turn = {}
        self.percent = 39
        self.bootstrap_percent = 5
        self.measured_delta = 0
        self.safe = True
        self.closed = True
        self.active = False
        self.rpc_failure = None
        self.evidence = None
        self.bootstrap_change = {}
        self.bootstrap_ready = True
        self.fail_launch = 0
        self.crash_after_launch = False
        self.crash_after_close = False

    def state(self):
        return json.loads(Path(self.fixture.request['state']).read_text())

    def probe(self):
        self.calls.append(('probe',))
        return {'platform': 'linux', 'terminal': 'gnome-terminal', 'codex': '0.169.0',
                'systemd_user': True, 'cgroup_v2': True}

    def prepare_generation(self, mission_id, generation, worktree):
        self.calls.append(('prepare', generation))
        identity = {'unit': f'agentic-fixture-114-g{generation}.service',
                    'invocation_id': f'{generation + 1:032x}',
                    'control_group': f'/fixture/g{generation}',
                    'owner_token': f'private-token-{generation}', 'generation': generation,
                    'admission_open': True}
        self.boundaries[generation] = identity
        return copy.deepcopy(identity)

    def launch(self, request, backend=None, **kwargs):
        self.calls.append(('launch', copy.deepcopy(request)))
        assert backend is self
        # Keep the actual #113 request validator and prompt contract in this test:
        # replacing process/RPC IO must not silently replace that integration.
        self.fixture.launch_api.validate_request(request)
        assert Path(request['state']) != Path(self.fixture.request['state'])
        assert 'BOOTSTRAP_ONLY' in request['next_action']
        prompt = self.fixture.launch_api.build_prompt(request, 'bootstrap-fixture-nonce')
        assert prompt.startswith('$start-ticket ' + self.fixture.request['ticket_url'])
        assert 'BOOTSTRAP_ONLY' in prompt
        state = self.state()
        assert request['transition_id'] in json.dumps(state), 'Launch intent not durable'
        assert self.fixture.request['mission_id'] in json.dumps(state)
        if self.fail_launch:
            self.fail_launch -= 1
            raise OSError('temporary launch unavailable ' + SECRET)
        transition = request['transition_id']
        if transition not in self.sessions:
            generation = len(self.sessions)
            assert generation == 0 or not self.boundaries[generation - 1]['admission_open']
            assert generation == 0 or self.closed, 'New writer before authoritative closure'
            receipt = {'phase': 'submitted', 'thread_id': f'thread-114-{generation}',
                       'turn_id': f'bootstrap-114-{generation}', 'transition_id': transition,
                       'socket': f'/fixture/g{generation}.sock',
                       'boundary': copy.deepcopy(self.boundaries[generation]),
                       'model': 'gpt-6.1-sol', 'effort': 'high'}
            self.sessions[transition] = receipt
        if self.crash_after_launch:
            self.crash_after_launch = False
            raise KeyboardInterrupt('simulated controller crash after idempotent launch')
        return copy.deepcopy(self.sessions[transition])

    def measure(self, repo, thread_id, **kwargs):
        self.calls.append(('measure', thread_id))
        dispatched = any(c[0] == 'rpc' and c[3] == thread_id and c[2] == 'dispatch'
                         for c in self.calls)
        percent = self.percent if dispatched else self.bootstrap_percent
        now = self.fixture.now
        return {'source': 'codex-rollout', 'repo': str(repo), 'thread_id': thread_id,
                'observed_at': now.isoformat(),
                'measured_at': (now + timedelta(seconds=self.measured_delta)).isoformat(),
                'model_context_window': 100000, 'used_tokens': percent * 1000,
                'used_percent': percent, 'remaining_percent': 100 - percent,
                'basis': 'last_total_tokens/model_context_window',
                'threshold_state': ('below_threshold' if percent < 40 else
                                    'handoff_required' if percent < 50 else 'target_exceeded')}

    def session_state(self, session):
        return {'status': 'active' if self.active else 'idle',
                'turn_id': self.last_turn.get(session['thread_id'], session['turn_id']),
                'turn_status': 'inProgress' if self.active else 'completed',
                'tools_running': not self.safe}

    def owns_session(self, session, request):
        return self.sessions[request['transition_id']]['thread_id'] == session['thread_id']

    def rpc(self, endpoint, method, params):
        if method not in ('turn/start', 'turn/steer'):
            self.calls.append(('read_rpc', method))
            return {}
        operations = self.state()['operations']
        operation = operations[-1]
        assert operation['phase'] == 'sending', 'Mutation intent must precede RPC'
        assert operation['method'] == method
        assert operation['thread_id'] == params['threadId']
        assert operation['nonce'] in json.dumps(params), 'No nonce in actual RPC input'
        self.calls.append(('rpc', method, operation['kind'], params['threadId'],
                           copy.deepcopy(params)))
        if self.rpc_failure == operation['kind']:
            raise TimeoutError('RPC response lost ' + SECRET)
        turn_id = f'turn-{len(self.calls)}'
        self.last_turn[params['threadId']] = turn_id
        return {'turn': {'id': turn_id}}

    def submission_evidence(self, operation):
        self.calls.append(('evidence', operation['kind']))
        if self.evidence is True:
            return {'thread_id': operation['thread_id'], 'nonce': operation['nonce'],
                    'turn_id': 'positively-reconciled-turn'}
        return copy.deepcopy(self.evidence)

    def handoff_source(self, session):
        return str(self.fixture.draft)

    def bootstrap_receipt(self, session, expected):
        self.calls.append(('bootstrap', session['thread_id'], copy.deepcopy(expected)))
        for key in ('thread_id', 'worktree', 'branch', 'head', 'plan_sha256',
                    'handoff_sha256', 'parent_permissions', 'dirty'):
            assert key in expected, 'Bootstrap must bind ' + key
        assert expected['thread_id'] == session['thread_id']
        assert expected['parent_permissions'] == self.fixture.request['parent_permissions']
        for name in ('product', 'new-file'):
            path = self.fixture.repo / name
            if path.exists() and (name == 'new-file' or 'local uncommitted' in path.read_text()):
                assert expected['dirty'][name] == hashlib.sha256(path.read_bytes()).hexdigest()
        if not self.bootstrap_ready:
            return None
        return {**copy.deepcopy(expected), 'instructions_read': True, 'handoff_read': True,
                'reconciled': True, **self.bootstrap_change}

    def close_admission(self, identity):
        self.calls.append(('close', identity['generation']))
        assert identity['unit'] in json.dumps(self.state()), 'Ownership not durable'
        self.boundaries[identity['generation']]['admission_open'] = False
        if self.crash_after_close:
            self.crash_after_close = False
            raise KeyboardInterrupt('simulated controller crash after admission close')
        return True

    def quiescent(self, identity):
        self.calls.append(('quiescent', identity['generation']))
        return self.safe

    def retire(self, identity):
        self.calls.append(('retire', identity['generation']))
        assert not self.boundaries[identity['generation']]['admission_open']
        assert self.safe, 'Never terminate processes on a safe-point timeout'
        return True

    def closure(self, identity):
        self.calls.append(('closure', identity['generation']))
        return self.closed

    def count(self, name, kind=None):
        return sum(c[0] == name and (kind is None or c[2] == kind) for c in self.calls)


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_script('context_controller_114', SCRIPT)
        cls.launch_api = load_script('controller_launcher_114',
                                     SOURCE / 'scripts/agentic-context-launch.py')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='context-controller-114-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'worktree with spaces'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'feat/context-controller')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'product').write_text('initial\n')
        self.git('add', 'product')
        self.git('commit', '-qm', 'Initial fixture')
        (self.repo / '.git/info/exclude').write_text('/.agentic-local/\n')
        self.local = self.repo / '.agentic-local'
        self.local.mkdir(mode=0o700)
        self.draft = self.local / 'draft.md'
        self.draft.write_text(manual_handoff(self.repo, note=(
            SECRET + '; décision: garder stdlib; erreur ouverte E114; '
            'action externe déjà réalisée: PR#77; prochaine action: vérifier product')))
        self.handoff = self.local / 'HANDOFF.md'
        shutil.copyfile(self.draft, self.handoff)
        self.plan = self.local / 'pr-split.json'
        self.plan.write_text(json.dumps({'version': 1, 'story': 'fixture-114', 'prs': [
            {'id': '114-PR1', 'branch': 'feat/context-controller', 'files': ['product']}]}))
        self.config = self.local / 'agentic.config.json'
        self.config.write_text('{"version":1}')
        self.skill = self.local / 'skills/start-ticket/SKILL.md'
        self.skill.parent.mkdir(parents=True)
        shutil.copyfile(SOURCE / 'skills/start-ticket/SKILL.md', self.skill)
        self.request = {
            'mission_id': 'mission-114', 'transition_id': 'mission-114-g0',
            'ticket_url': 'https://github.com/issa-diallo/agentic-dev-system/issues/114',
            'worktree': str(self.repo), 'branch': 'feat/context-controller',
            'head': self.git('rev-parse', 'HEAD'), 'handoff': str(self.handoff),
            'handoff_sha256': hashlib.sha256(self.handoff.read_bytes()).hexdigest(),
            'plan': str(self.plan), 'plan_sha256': canonical_hash(json.loads(self.plan.read_text())),
            'config': str(self.config), 'skill': str(self.skill), 'phase': 'BUILD',
            'last_pass': 'PREPARE + PR_SPLIT PASS', 'next_action': 'Vérifier product',
            'first_read': str(self.repo / 'product'), 'writers_stopped': True,
            'parent_permissions': {'approval_policy': 'never',
                                   'sandbox_mode': 'danger-full-access',
                                   'profile': None, 'writable_roots': []},
            'state': str(self.local / 'controller/state.json')}
        self.now = datetime.now(timezone.utc)
        self.runtime = RuntimeBoundary(self)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(self.api, 'snapshot_context', side_effect=self.runtime.measure).start()
        mock.patch.object(self.api, 'launch', side_effect=self.runtime.launch).start()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def controller(self, request=None):
        return self.api.Controller(request or self.request, backend=self.runtime,
                                   clock=lambda: self.now)

    def step(self):
        return self.controller().step()

    def start(self):
        result = self.step()
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(result['generation'], 0)
        return result

    def blocked(self, result):
        self.assertEqual(result['phase'], 'blocked', result)
        self.assertTrue(result['diagnostic'])
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(Path(result['checkpoint']['path']).read_bytes(),
                         self.handoff.read_bytes())

    def progress(self, number):
        (self.repo / 'product').write_text(f'local uncommitted progress {number}\n')
        (self.repo / 'new-file').write_text(f'untracked {number}\n')
        self.draft.write_text(manual_handoff(self.repo, note=(
            f'{SECRET}; completed step {number}; décision stdlib; erreur E114 ouverte; '
            f'PR#77 déjà réalisée; prochaine action étape {number + 1}')))

    def renew(self, number=1):
        self.progress(number)
        self.runtime.percent = 40
        return self.step()

    def test_c3_initial_session_is_created_managed_never_adopted_from_boolean(self):
        self.start()
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertEqual(self.runtime.count('prepare'), 1)
        calls = [c[0] for c in self.runtime.calls]
        self.assertLess(calls.index('prepare'), calls.index('launch'))
        self.assertLess(calls.index('bootstrap'), calls.index('rpc'))
        self.assertLess(calls.index('measure'), calls.index('rpc'))
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 1)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 0)

    def test_c1_thresholds_39_40_45_50_53_and_repeated_observation(self):
        for percent in (39, 40, 45, 50, 53):
            with self.subTest(percent=percent):
                # Separate fixture mission: no state editing to reset a controller.
                if percent != 39:
                    self.doCleanups()
                    self.setUp()
                self.start()
                self.progress(1)
                self.runtime.percent = percent
                result = self.step()
                expected = int(percent >= 40)
                self.assertEqual(result['generation'], expected)
                self.assertEqual(self.runtime.count('rpc', 'handoff'), expected)
                if percent >= 50:
                    self.assertTrue(result['target_exceeded'])
                self.runtime.percent = 39
                self.step()
                self.assertEqual(self.runtime.count('rpc', 'handoff'), expected)

    def test_c1_missing_stale_future_measurements_have_persisted_bounded_recovery(self):
        self.start()
        self.runtime.measured_delta = -121
        first = self.step()
        self.assertIn(first['phase'], ('recovering', 'blocked'))
        for _ in range(4):
            last = self.step()
        self.blocked(last)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 0)
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertLessEqual(sum(c[0] == 'measure' for c in self.runtime.calls), 3)

    def test_c1_future_measurement_never_authorizes_a_dispatch_or_handoff(self):
        self.runtime.measured_delta = 1
        for _ in range(3):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('rpc'), 0)

    def test_c1_measurement_exception_is_explicit_never_replaced_with_zero(self):
        self.start()
        with mock.patch.object(self.api, 'snapshot_context', side_effect=OSError(SECRET)):
            for _ in range(3):
                result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 0)

    def test_c1_measurement_recovers_automatically_on_next_fresh_read(self):
        self.start()
        self.runtime.measured_delta = -121
        first = self.step()
        self.assertEqual(first['phase'], 'recovering', first)
        self.runtime.measured_delta = 0
        result = self.step()
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 0)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c1_real_rollout_last_tokens_timestamp_and_60_percent_remaining(self):
        self.start()
        self.progress(1)
        observer = load_script('controller_observe_114', SOURCE / 'scripts/agentic-observe.py')
        rollout = self.local / 'rollout.jsonl'
        rows = [{'type': 'session_meta', 'payload': {
            'id': 'thread-114-0', 'cwd': str(self.repo)}}]
        for used in (39000, 40000):
            rows.append({'timestamp': self.now.isoformat(), 'type': 'event_msg', 'payload': {
                'type': 'token_count', 'info': {'model_context_window': 100000,
                    'last_token_usage': {'total_tokens': used},
                    'total_token_usage': {'total_tokens': 9000000}}}})
        rollout.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        proxy = mock.MagicMock()
        proxy.__enter__.return_value = proxy
        proxy.request.return_value = {'thread': {
            'id': 'thread-114-0', 'cwd': str(self.repo), 'path': str(rollout)}}

        def actual_measure(repo, thread_id, **kwargs):
            if thread_id != 'thread-114-0':
                return self.runtime.measure(repo, thread_id, **kwargs)
            return observer.snapshot_context(repo, thread_id, **kwargs)

        with mock.patch.object(observer, '_Proxy', return_value=proxy), \
             mock.patch.object(self.api, 'snapshot_context', side_effect=actual_measure):
            result = self.step()
        self.assertEqual(result['generation'], 1, result)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 1)
        persisted = Path(self.request['state']).read_text()
        self.assertNotIn('9000000', persisted, 'Cumulative tokens are not occupancy')

    def test_c2_c5_two_renewals_preserve_dirty_decision_error_and_external_action(self):
        head = self.git('rev-parse', 'HEAD')
        self.start()
        for number in (1, 2):
            result = self.renew(number)
            self.assertEqual(result['phase'], 'working', result)
            self.assertEqual(result['generation'], number)
            self.assertEqual(self.git('rev-parse', 'HEAD'), head, 'No forced commit')
            self.assertEqual((self.repo / 'product').read_text(),
                             f'local uncommitted progress {number}\n')
            self.assertEqual((self.repo / 'new-file').read_text(), f'untracked {number}\n')
            checkpoint = Path(result['checkpoint']['path']).read_text()
            for preserved in ('stdlib', 'E114', 'PR#77', f'étape {number + 1}'):
                self.assertIn(preserved, checkpoint)
        self.assertEqual(len(self.runtime.sessions), 3)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 2)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 3)
        self.assertTrue(self.git('status', '--porcelain'))
        prompts = [c[4] for c in self.runtime.calls if c[0] == 'rpc' and c[2] == 'dispatch']
        self.assertNotIn(SECRET, json.dumps(prompts), 'Use references, not outgoing transcript')
        for launch_call in [c for c in self.runtime.calls if c[0] == 'launch']:
            req = launch_call[1]
            self.assertEqual(req['worktree'], str(self.repo))
            self.assertEqual(req['parent_permissions'], self.request['parent_permissions'])
            self.assertEqual(req['skill'], str(self.skill))
            self.assertEqual(req['ticket_url'], self.request['ticket_url'])

    def test_c5_nonce_timestamp_or_generation_changes_alone_are_not_progress(self):
        self.start()
        self.runtime.percent = 40
        original_draft = self.draft.read_text()
        self.step()
        count = len(self.runtime.sessions)
        for attempt in range(3):
            self.now += timedelta(seconds=5)
            self.draft.write_text(original_draft + (
                f'\n<!-- timestamp={self.now.isoformat()} nonce=attempt-{attempt} -->\n'))
            result = self.step()
        self.blocked(result)
        self.assertLessEqual(len(self.runtime.sessions), max(2, count))
        self.assertRegex(result['diagnostic'].lower(), r'progr|progress')

    def test_c2_admission_closed_before_retirement_and_new_launch(self):
        self.start()
        self.renew()
        calls = [c[0] for c in self.runtime.calls]
        close = calls.index('close')
        retire = calls.index('retire')
        closure = calls.index('closure')
        last_launch = max(i for i, name in enumerate(calls) if name == 'launch')
        self.assertLess(close, retire)
        self.assertLess(retire, closure)
        self.assertLess(closure, last_launch)

    def test_c2_live_background_writer_never_killed_on_timeout_or_restart(self):
        self.start()
        self.progress(1)
        self.runtime.percent = 53
        self.runtime.safe = False
        for _ in range(5):
            result = self.step()
            self.now += timedelta(minutes=5)
        self.assertIn(result['phase'], ('waiting_safe_point', 'blocked'))
        self.assertEqual(self.runtime.count('retire'), 0)
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 1)

    def test_c2_unknown_boundary_closure_blocks_ownership_transfer(self):
        self.start()
        self.runtime.closed = False
        result = self.renew()
        for _ in range(3):
            if result['phase'] == 'blocked':
                break
            result = self.step()
        self.blocked(result)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c2_active_turn_steered_once_without_starting_another_business_turn(self):
        self.start()
        self.runtime.active = True
        self.runtime.safe = False
        self.progress(1)
        self.runtime.percent = 40
        self.step()
        self.step()
        requests = [c for c in self.runtime.calls if c[0] == 'rpc' and c[2] == 'handoff']
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][1], 'turn/steer')
        self.assertIn('expectedTurnId', requests[0][4])
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c2_invalid_handoff_has_only_two_corrections_and_keeps_last_valid(self):
        self.start()
        old = self.handoff.read_bytes()
        self.draft.write_text('# incomplete handoff\n' + SECRET)
        self.runtime.percent = 40
        for _ in range(5):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.handoff.read_bytes(), old)
        self.assertEqual(self.runtime.count('rpc', 'correction'), 2)
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertEqual(self.runtime.count('retire'), 0)

    def final_draft(self, valid=False):
        text = manual_handoff(self.repo, state='IMPLEMENTATION_COMPLETE')
        self.draft.write_text(text if valid else text.replace(
            '## Tests exécutés', '## Tests exécutés / preuves factuelles'))
        return text

    def test_final_document_repaired_then_saved_and_closed_without_more_business(self):
        self.start()
        previous = self.handoff.read_bytes()
        valid = self.final_draft()
        self.runtime.measured_delta = -300
        self.assertEqual(self.step()['stored_phase'], 'finalizing')
        self.assertEqual(self.handoff.read_bytes(), previous)
        rpc = [c for c in self.runtime.calls if c[0] == 'rpc' and c[2] == 'final_correction']
        self.assertEqual(len(rpc), 1)
        prompt = rpc[0][4]['input'][0]['text']
        for name in (*self.api._checkpoint.SECTIONS, *self.api._checkpoint.CHECKPOINT_LABELS):
            self.assertIn(name, prompt)
        self.draft.write_text(valid)
        self.runtime.active = True
        self.assertEqual(self.step()['phase'], 'waiting_safe_point')
        self.assertEqual(self.handoff.read_bytes(), previous)
        self.runtime.active = False
        result = self.step()
        self.assertEqual(result['phase'], 'completed', result)
        self.assertEqual(self.handoff.read_text(), valid)
        self.assertEqual(result['generation'], 0)
        self.assertIn('0', self.runtime.state()['closed'])
        self.assertEqual(self.runtime.count('closure'), 1)
        self.assertEqual(self.step()['phase'], 'completed')
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 1)
        self.assertEqual(self.runtime.count('launch'), 1)

    def test_invalid_final_corrections_exhaust_budget_and_preserve_checkpoint(self):
        self.start()
        original = self.handoff.read_bytes()
        self.final_draft()
        self.step()
        self.draft.write_text(manual_handoff(self.repo, state='IN_PROGRESS'))
        self.step()
        self.blocked(self.step())
        self.assertEqual(self.runtime.count('rpc', 'final_correction'), 2)
        self.assertEqual(self.handoff.read_bytes(), original)
        self.assertEqual(self.runtime.count('close'), 0)

    def test_lost_final_correction_receipt_never_resends_or_accepts_foreign_turn(self):
        self.start()
        previous = self.handoff.read_bytes()
        self.final_draft()
        self.runtime.rpc_failure = 'final_correction'
        self.assertEqual(self.step()['phase'], 'recovering')
        self.runtime.evidence = True
        self.final_draft(valid=True)
        self.runtime.last_turn['thread-114-0'] = 'unrelated-turn'
        result = self.step()
        self.assertIn(result['phase'], ('waiting_safe_point', 'blocked'))
        self.assertEqual(self.runtime.count('rpc', 'final_correction'), 1)
        self.assertEqual(self.handoff.read_bytes(), previous)
        self.assertFalse(self.runtime.count('close'))

    def test_reconciled_final_correction_completes_only_after_its_own_turn(self):
        self.start()
        self.final_draft()
        self.runtime.rpc_failure = 'final_correction'
        self.assertEqual(self.step()['phase'], 'recovering')
        self.runtime.evidence = True
        self.runtime.last_turn['thread-114-0'] = 'positively-reconciled-turn'
        self.final_draft(valid=True)
        self.assertEqual(self.step()['phase'], 'completed')
        self.assertEqual(self.runtime.count('rpc', 'final_correction'), 1)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 1)

    def test_quoted_example_of_final_state_cannot_end_active_mission(self):
        self.start()
        previous = self.handoff.read_bytes()
        self.draft.write_text('~~~md\n## État\nIMPLEMENTATION_COMPLETE\n~~~\n' +
                              manual_handoff(self.repo, state='IN_PROGRESS'))
        self.assertEqual(self.step()['phase'], 'working')
        self.assertEqual(self.handoff.read_bytes(), previous)
        self.assertFalse(self.runtime.count('close'))

    def test_final_retirement_skips_a_proven_closed_tui_and_requires_all_identities(self):
        backend = self.api.ManagedBackend(self.request)
        old = {'unit': 'old-tui', 'invocation_id': 'old'}
        current = {'unit': 'current-tui', 'invocation_id': 'current'}
        with mock.patch.object(backend, '_generation', return_value=[old, current]) as units, \
                mock.patch.object(backend.boundary, 'closure', side_effect=lambda u: u == old), \
                mock.patch.object(backend.boundary, 'retire', return_value=True) as retire:
            self.assertTrue(backend.retire({}))
            retire.assert_called_once_with(current)
            units.return_value = [old, {'unit': 'unknown', 'invocation_id': None}]
            self.assertFalse(backend.closure({}))
            self.assertFalse(backend.quiescent({}))

    def test_final_closure_resumes_after_save_and_never_claims_unknown_closure(self):
        self.start()
        self.final_draft(valid=True)
        save = self.api.save_checkpoint
        def crash_after_save(*args):
            save(*args)
            raise KeyboardInterrupt
        with mock.patch.object(self.api, 'save_checkpoint', side_effect=crash_after_save):
            with self.assertRaises(KeyboardInterrupt):
                self.step()
        self.runtime.crash_after_close = True
        with self.assertRaises(KeyboardInterrupt):
            self.step()
        self.runtime.closed = False
        self.assertEqual(self.step()['phase'], 'recovering')
        self.blocked(self.step())
        self.assertFalse(self.runtime.state()['closed'])
        self.assertEqual(self.runtime.count('launch'), 1)

    def test_legacy_measurement_block_recovers_only_the_exact_owned_final_draft(self):
        self.start()
        self.final_draft()
        state = self.runtime.state()
        reason = 'Mesure du contexte indisponible (2 tentatives épuisées).'
        state.update(phase='blocked', diagnostic=reason,
                     draft_seen=hashlib.sha256(self.draft.read_bytes()).hexdigest())
        state.pop('finalization', None)
        state['attempts']['measure_io'] = 2
        path = Path(self.request['state'])
        def persist(**fields):
            path.write_text(json.dumps({**state, **fields}))
        persist(diagnostic='Fermeture de la frontière non prouvée.')
        self.blocked(self.step())
        persist(draft_seen='0' * 64)
        self.blocked(self.step())
        persist()
        with mock.patch.object(self.runtime, 'owns_session', return_value=False):
            self.blocked(self.step())
        self.assertFalse(self.runtime.count('rpc', 'final_correction'))
        self.assertEqual(self.step()['stored_phase'], 'finalizing')
        self.assertEqual(self.runtime.state()['finalization']['previous_diagnostic'], reason)
        self.assertEqual(self.runtime.count('rpc', 'final_correction'), 1)

    def test_final_correction_cannot_change_business_files_or_close_over_a_writer(self):
        self.start()
        self.final_draft()
        self.runtime.safe = False
        self.assertEqual(self.step()['phase'], 'waiting_safe_point')
        self.assertFalse(self.runtime.count('rpc', 'final_correction'))
        self.runtime.safe = True
        self.step()
        self.final_draft(valid=True)
        (self.repo / 'product').write_text('unrelated change during formatting')
        self.blocked(self.step())
        self.assertEqual(self.runtime.count('close'), 0)

    def test_c2_symlink_draft_is_never_followed_or_promoted_as_checkpoint(self):
        self.start()
        previous = self.handoff.read_bytes()
        target = self.root / 'foreign-draft.md'
        target.write_text(manual_handoff(self.repo, note='foreign document ' + SECRET))
        self.draft.unlink()
        self.draft.symlink_to(target)
        self.runtime.percent = 40
        for _ in range(5):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.handoff.read_bytes(), previous)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c2_corrected_handoff_is_revalidated_before_transfer(self):
        self.start()
        self.progress(1)
        valid = self.draft.read_text()
        self.draft.write_text('# incomplete\n')
        self.runtime.percent = 40
        rpc = self.runtime.rpc

        def corrected(endpoint, method, params):
            result = rpc(endpoint, method, params)
            if self.runtime.calls[-1][0] == 'rpc' and self.runtime.calls[-1][2] == 'correction':
                self.draft.write_text(valid)
            return result

        with mock.patch.object(self.runtime, 'rpc', side_effect=corrected):
            for _ in range(3):
                result = self.step()
                if result['generation'] == 1:
                    break
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(result['generation'], 1)
        self.assertEqual(self.runtime.count('rpc', 'correction'), 1)
        self.assertEqual(self.handoff.read_text(), valid)

    def test_c2_disk_failure_preserves_previous_checkpoint_and_stops_transfer(self):
        self.start()
        old = self.handoff.read_bytes()
        self.progress(1)
        self.runtime.percent = 40
        with mock.patch.object(self.api, 'save_checkpoint', side_effect=OSError(SECRET)):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.handoff.read_bytes(), old)
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertEqual(self.runtime.count('retire'), 0)

    def test_c3_bootstrap_context_at_40_blocks_before_first_business_dispatch(self):
        self.runtime.bootstrap_percent = 40
        for _ in range(3):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 0)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c3_bootstrap_receipt_must_confirm_instructions_handoff_and_reconciliation(self):
        self.runtime.bootstrap_change = {'instructions_read': False, 'reconciled': False}
        for _ in range(3):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 0)

    def test_c3_bootstrap_mismatched_identity_git_plan_checkpoint_or_permissions(self):
        mismatches = (('head', '0' * 40), ('plan_sha256', 'f' * 64),
                      ('handoff_sha256', 'e' * 64), ('worktree', '/foreign/worktree'),
                      ('thread_id', 'foreign-thread'), ('dirty', {'product': '0' * 64}),
                      ('parent_permissions', {'approval_policy': 'never'}))
        for field, value in mismatches:
            with self.subTest(field=field):
                if field != 'head':
                    self.doCleanups()
                    self.setUp()
                self.runtime.bootstrap_change = {field: value}
                for _ in range(3):
                    result = self.step()
                self.blocked(result)
                self.assertEqual(self.runtime.count('rpc', 'dispatch'), 0)

    def test_c3_no_business_turn_until_positive_bootstrap_receipt(self):
        self.runtime.bootstrap_ready = False
        self.step()
        self.assertEqual(self.runtime.count('rpc'), 0)
        self.runtime.bootstrap_ready = True
        self.assertEqual(self.step()['phase'], 'working')
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c4_lost_mutation_response_never_resends_after_restart(self):
        self.start()
        self.runtime.rpc_failure = 'handoff'
        self.progress(1)
        self.runtime.percent = 40
        for _ in range(3):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 1)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c4_lost_first_business_dispatch_never_replays_business_action(self):
        self.runtime.rpc_failure = 'dispatch'
        for _ in range(4):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 1)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c4_positive_nonce_evidence_reconciles_lost_response_without_second_send(self):
        self.start()
        self.runtime.rpc_failure = 'handoff'
        self.runtime.evidence = True
        self.progress(1)
        self.runtime.percent = 40
        result = self.step()
        if result['phase'] != 'working':
            result = self.step()
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(result['generation'], 1)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 1)

    def test_c4_foreign_nonce_evidence_does_not_authorize_recovery(self):
        self.start()
        self.runtime.rpc_failure = 'handoff'
        self.runtime.evidence = {'thread_id': 'other-thread', 'turn_id': 'other-turn',
                                 'nonce': 'other-nonce'}
        self.progress(1)
        self.runtime.percent = 40
        for _ in range(3):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 1)

    def test_c4_crash_after_checkpoint_and_admission_close_reconciles_once(self):
        self.start()
        self.progress(1)
        self.runtime.percent = 40
        self.runtime.crash_after_close = True
        with self.assertRaises(KeyboardInterrupt):
            self.step()
        self.assertIn('completed step 1', self.handoff.read_text())
        result = self.step()
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(result['generation'], 1)
        self.assertEqual(self.runtime.count('rpc', 'handoff'), 1)
        self.assertEqual(len(self.runtime.sessions), 2)

    def test_c4_crash_after_launch_reuses_identified_generation_not_another_session(self):
        self.start()
        self.progress(1)
        self.runtime.percent = 40
        self.runtime.crash_after_launch = True
        with self.assertRaises(KeyboardInterrupt):
            self.step()
        self.assertEqual(len(self.runtime.sessions), 2)
        result = self.step()
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(result['generation'], 1)
        self.assertEqual(len(self.runtime.sessions), 2)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 2)

    def test_c4_launch_retries_are_bounded_across_controller_restarts(self):
        self.runtime.fail_launch = 99
        for _ in range(5):
            result = self.step()
        self.blocked(result)
        self.assertEqual(self.runtime.count('launch'), 2)
        self.assertEqual(len(self.runtime.sessions), 0)

    def test_c4_temporary_launch_error_recovers_without_an_extra_session(self):
        self.runtime.fail_launch = 1
        for _ in range(3):
            result = self.step()
            if result['phase'] == 'working':
                break
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(self.runtime.count('launch'), 2)
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 1)

    def test_c4_reconnection_error_during_bootstrap_reuses_created_session(self):
        receipt = self.runtime.bootstrap_receipt
        failed = False

        def reconnect(session, expected):
            nonlocal failed
            if not failed:
                failed = True
                raise ConnectionError(SECRET)
            return receipt(session, expected)

        with mock.patch.object(self.runtime, 'bootstrap_receipt', side_effect=reconnect):
            for _ in range(3):
                result = self.step()
                if result['phase'] == 'working':
                    break
        self.assertEqual(result['phase'], 'working', result)
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 1)

    def test_c4_runtime_incompatibility_blocks_without_spawning(self):
        with mock.patch.object(self.runtime, 'probe', return_value={
                'platform': 'linux', 'terminal': 'gnome-terminal', 'codex': '0.169.0',
                'systemd_user': False, 'cgroup_v2': False}):
            self.blocked(self.step())
        self.assertEqual(self.runtime.count('launch'), 0)
        self.assertEqual(self.runtime.count('prepare'), 0)

    def test_c4_status_is_read_only_private_and_contains_recovery_information(self):
        self.start()
        state_path = Path(self.request['state'])
        before = state_path.read_bytes()
        calls = copy.deepcopy(self.runtime.calls)
        result = self.controller().status()
        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(self.runtime.calls, calls)
        self.assertEqual(result['mission_id'], 'mission-114')
        self.assertIn('checkpoint', result)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn('private-token-', json.dumps(result))
        self.assertEqual(stat.S_IMODE(state_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(state_path.parent.stat().st_mode), 0o700)

    def test_c4_failed_state_fsync_preserves_parseable_previous_state_and_checkpoint(self):
        self.start()
        previous = Path(self.request['state']).read_bytes()
        checkpoint = self.handoff.read_bytes()
        self.progress(1)
        self.runtime.percent = 40
        with mock.patch.object(self.api.os, 'fsync', side_effect=OSError(SECRET)):
            with self.assertRaises(self.api.ControllerError) as caught:
                self.step()
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertEqual(Path(self.request['state']).read_bytes(), previous)
        json.loads(previous)
        self.assertEqual(self.handoff.read_bytes(), checkpoint)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c4_corrupt_state_is_not_reset_into_a_new_writer(self):
        self.start()
        Path(self.request['state']).write_text('{truncated')
        with self.assertRaises(self.api.ControllerError):
            self.step()
        self.assertEqual(len(self.runtime.sessions), 1)
        self.assertEqual(Path(self.request['state']).read_text(), '{truncated')

    def test_c4_state_symlink_and_outside_repo_paths_refused_before_runtime(self):
        outside = self.root / 'outside.json'
        outside.write_text('preserve me')
        state = Path(self.request['state'])
        state.parent.mkdir(mode=0o700)
        state.symlink_to(outside)
        with self.assertRaises(self.api.ControllerError):
            self.step()
        self.assertEqual(outside.read_text(), 'preserve me')
        changed = {**self.request, 'state': str(self.root / 'external/state.json')}
        with self.assertRaises(self.api.ControllerError):
            self.controller(changed).step()
        self.assertEqual(self.runtime.calls, [])

    def test_c4_parent_symlink_and_nested_repository_are_refused(self):
        other = self.root / 'other'
        other.mkdir()
        state = Path(self.request['state'])
        state.parent.symlink_to(other, target_is_directory=True)
        with self.assertRaises(self.api.ControllerError):
            self.step()
        state.parent.unlink()
        state.parent.mkdir()
        subprocess.run(['git', '-C', str(state.parent), 'init', '-q'], check=True,
                       capture_output=True)
        with self.assertRaises(self.api.ControllerError):
            self.step()
        self.assertEqual(self.runtime.calls, [])

    def test_c4_tracked_or_unexcluded_state_is_refused(self):
        (self.repo / '.git/info/exclude').write_text('')
        with self.assertRaises(self.api.ControllerError):
            self.step()
        self.assertEqual(self.runtime.calls, [])

    def test_c4_force_tracked_private_state_is_not_accepted_as_local_storage(self):
        self.start()
        self.git('add', '-f', self.request['state'])
        before = copy.deepcopy(self.runtime.calls)
        with self.assertRaises(self.api.ControllerError):
            self.step()
        self.assertEqual(self.runtime.calls, before)

    def test_c4_private_checkpoint_history_is_retained_across_two_renewals(self):
        self.start()
        initial = self.handoff.read_bytes()
        self.renew(1)
        first = self.handoff.read_bytes()
        self.renew(2)
        saved = [path.read_bytes() for path in self.local.rglob('*') if path.is_file()]
        self.assertIn(initial, saved, 'Previous checkpoint history was purged')
        self.assertIn(first, saved, 'Earlier renewal checkpoint was purged')

    def test_c4_unrepresentable_parent_permissions_are_rejected_without_effect(self):
        self.request['parent_permissions']['writable_roots'] = ['/tmp']
        with self.assertRaises(self.api.ControllerError):
            self.step()
        self.assertEqual(self.runtime.calls, [])

    def test_c4_real_head_plan_or_config_changes_require_reconciliation_before_dispatch(self):
        for changed in ('plan', 'config', 'head'):
            with self.subTest(changed=changed):
                if changed != 'plan':
                    self.doCleanups()
                    self.setUp()
                self.start()
                if changed == 'head':
                    self.git('commit', '--allow-empty', '-qm', 'Concurrent fixture head change')
                else:
                    getattr(self, changed).write_text('{"version":1,"changed":true}')
                before = self.runtime.count('rpc')
                result = self.step()
                self.blocked(result)
                self.assertEqual(self.runtime.count('rpc'), before)
                self.assertEqual(len(self.runtime.sessions), 1)

    def test_c4_concurrent_step_has_single_canonical_mission_owner(self):
        entered, release = threading.Event(), threading.Event()
        original = self.runtime.probe
        errors = []

        def held_probe():
            entered.set()
            if not release.wait(5):
                raise AssertionError('Test release timeout')
            return original()

        def first_step():
            try:
                self.step()
            except BaseException as error:
                errors.append(error)

        with mock.patch.object(self.runtime, 'probe', side_effect=held_probe):
            thread = threading.Thread(target=first_step)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                second = {**self.request, 'state': str(self.local / 'other/state.json')}
                with self.assertRaises(self.api.ControllerError):
                    self.controller(second).step()
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_c6_cli_status_has_no_runtime_effect_and_run_requires_explicit_request(self):
        self.start()
        request_path = self.local / 'request.json'
        request_path.write_text(json.dumps(self.request))
        before = copy.deepcopy(self.runtime.calls)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.api.main(['status', '--request', str(request_path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['mission_id'], 'mission-114')
        self.assertEqual(self.runtime.calls, before)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.api.main(['run', '--once'])


    def _review_second_mission_is_refused(self):
        """An independent backend must never inspect the first fixture's request."""
        second = {**self.request, 'mission_id': 'second-mission-114',
                  'transition_id': 'second-mission-114-g0',
                  'state': str(self.local / 'second-controller/state.json')}
        self.launch_api.validate_request({k: v for k, v in second.items() if k != 'mission_id'})
        backend = self.api.ManagedBackend(second)
        identity = {'mission_id': second['mission_id'], 'generation': 0,
                    'worktree': second['worktree'], 'unit': 'second-owned-generation',
                    'admission_open': True}
        receipt = {'phase': 'submitted', 'thread_id': 'second-thread-114',
                   'turn_id': 'second-bootstrap-114', 'socket': '/fixture/second.sock',
                   'transition_id': second['transition_id'],
                   'model': 'gpt-6.1-sol', 'effort': 'high'}
        with mock.patch.object(backend, 'probe', return_value={
                'platform': 'linux', 'terminal': 'gnome-terminal', 'codex': '0.169.0',
                'systemd_user': True, 'cgroup_v2': True}), \
             mock.patch.object(backend, 'prepare_generation', return_value=identity) as prepare, \
             mock.patch.object(backend, 'bootstrap_receipt', return_value=None), \
             mock.patch.object(backend, 'rpc') as rpc, \
             mock.patch.object(self.api, 'launch', return_value=receipt) as launch:
            with self.assertRaises(self.api.ControllerError,
                                   msg='An active worktree cannot admit a second mission'):
                self.api.Controller(second, backend=backend, clock=lambda: self.now).step()
            prepare.assert_not_called()
            launch.assert_not_called()
            rpc.assert_not_called()

    def test_review_m1_second_mission_refused_after_original_step_returns(self):
        self.start()
        self.assertEqual(self.runtime.count('closure'), 0)
        self.assertTrue(self.runtime.boundaries[0]['admission_open'])
        self._review_second_mission_is_refused()

    def test_review_m1_worktree_binding_survives_controller_reinstantiation(self):
        self.start()
        self.assertEqual(self.controller().step()['phase'], 'working')
        self.assertEqual(len(self.runtime.sessions), 1, 'Same mission resumes without a launch')
        self.assertEqual(self.runtime.count('closure'), 0)
        self._review_second_mission_is_refused()

    def _review_bootstrap_claim(self):
        """A matching agent message/file is evidence of a claim, not of file reads."""
        directory = Path(self.request['state']).parent
        directory.mkdir(mode=0o700, exist_ok=True)
        session = {'thread_id': 'claimed-thread-114', 'turn_id': 'bootstrap-current-114',
                   'socket': '/fixture/claimed.sock', 'generation': 0,
                   'worktree': str(self.repo), 'transition_id': self.request['transition_id'],
                   'bootstrap_receipt': str(directory / 'bootstrap-g0.json')}
        expected = {key: copy.deepcopy(self.request[key]) for key in (
            'worktree', 'branch', 'head', 'plan_sha256', 'handoff_sha256', 'parent_permissions')}
        expected.update(thread_id=session['thread_id'], dirty={})
        claimed = {**expected, 'instructions_read': True, 'handoff_read': True,
                   'reconciled': True}
        path = Path(session['bootstrap_receipt'])
        path.write_text(json.dumps(claimed))
        path.chmod(0o600)
        rollout = directory / 'claim-only-rollout.jsonl'
        rollout.write_text(json.dumps({'type': 'session_meta', 'payload': {
            'id': session['thread_id'], 'cwd': str(self.repo)}}) + '\n' + json.dumps({
                'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': json.dumps(claimed)}]}}) + '\n')
        thread = {'id': session['thread_id'], 'cwd': str(self.repo), 'path': str(rollout),
                  'status': {'type': 'idle'}, 'turns': [{
                      'id': session['turn_id'], 'status': 'completed', 'items': [{
                          'type': 'agentMessage', 'id': 'claim-only-message',
                          'text': json.dumps(claimed)}]}]}
        return session, expected, thread

    def _review_bootstrap_rpc(self, thread, mutations):
        def rpc(endpoint, method, params, **kwargs):
            if method == 'thread/read':
                return {'thread': copy.deepcopy(thread)}
            if method == 'thread/loaded/list':
                return {'data': [thread['id']]}
            if method == 'config/read':
                return {'config': {'model': 'gpt-6.1-sol', 'model_reasoning_effort': 'high',
                                   'approval_policy': 'never',
                                   'sandbox_mode': 'danger-full-access'}}
            if method in ('turn/start', 'turn/steer'):
                mutations.append((method, copy.deepcopy(params)))
                return {'turn': {'id': 'business-turn-must-not-be-dispatched'}}
            return {}  # no runtime read evidence exists for any other query either
        return rpc

    def test_review_m2_real_backend_rejects_agent_claim_without_runtime_read_evidence(self):
        session, expected, original = self._review_bootstrap_claim()
        backend = self.api.ManagedBackend(self.request)
        for provenance in ('current-claim-only', 'foreign-thread', 'previous-turn'):
            with self.subTest(provenance=provenance):
                thread = copy.deepcopy(original)
                if provenance == 'foreign-thread':
                    thread['id'] = 'foreign-thread-114'
                if provenance == 'previous-turn':
                    thread['turns'][0]['id'] = 'previous-bootstrap-turn-114'
                mutations = []
                with mock.patch.object(backend, 'rpc', side_effect=self._review_bootstrap_rpc(
                        thread, mutations)), mock.patch.object(backend.boundary, 'run'):
                    try:
                        receipt = backend.bootstrap_receipt(session, expected)
                    except (self.api.ControllerError, self.api._launcher.LaunchError):
                        receipt = None
                self.assertIsNone(receipt, 'Matching JSON and flags do not prove runtime reads')
                self.assertEqual(mutations, [])

    def test_review_m2_real_backend_claim_cannot_authorize_business_dispatch(self):
        session, expected, thread = self._review_bootstrap_claim()
        backend = self.api.ManagedBackend(self.request)
        mutations = []
        launch_receipt = {key: session[key] for key in (
            'thread_id', 'turn_id', 'socket', 'transition_id')}
        launch_receipt.update(phase='submitted', model='gpt-6.1-sol', effort='high')
        identity = {'mission_id': self.request['mission_id'], 'generation': 0,
                    'worktree': str(self.repo), 'unit': 'owned-bootstrap-generation',
                    'admission_open': True}
        with mock.patch.object(backend, 'probe', return_value={
                'platform': 'linux', 'terminal': 'gnome-terminal', 'codex': '0.169.0',
                'systemd_user': True, 'cgroup_v2': True}), \
             mock.patch.object(backend, 'prepare_generation', return_value=identity), \
             mock.patch.object(backend.boundary, 'run'), \
             mock.patch.object(backend, 'rpc', side_effect=self._review_bootstrap_rpc(
                 thread, mutations)), \
             mock.patch.object(self.api, 'launch', return_value=launch_receipt):
            try:
                for _ in range(2):
                    result = self.api.Controller(self.request, backend=backend,
                                                 clock=lambda: self.now).step()
            except self.api.ControllerError:
                result = None  # explicit rejection is as safe as waiting for valid evidence
        self.assertEqual(mutations, [], 'Unverified read claims authorized a business turn')
        if result is not None:
            self.assertNotIn(result['phase'], ('working', 'dispatching', 'completed'))

    def test_review_m4_identified_server_creation_recovers_before_launch_journal_promotion(self):
        """Real controller/launcher/backend; interrupt only the launch-state write IO."""
        backend = self.api.ManagedBackend(self.request)
        resumed = self.api.ManagedBackend(self.request)
        cgroups = self.local / 'simulated-cgroup'
        backend.boundary.root = resumed.boundary.root = str(cgroups)
        created, mutations = {}, []
        thread_id = 'managed-recovery-thread-114'

        def systemd(argv, **kwargs):
            if argv[0] == 'systemctl' and 'show' in argv:
                unit = next(arg for arg in argv if arg.endswith('.service'))
                properties = created[unit]
                text = ''.join(f'{key}={value}\n' for key, value in properties.items()
                               if key != 'kind')
                return subprocess.CompletedProcess(argv, 0, stdout=text, stderr='')
            unit = next(arg.split('=', 1)[1] for arg in argv if arg.startswith('--unit='))
            self.assertNotIn(unit, created, 'An existing unit was created a second time')
            group = '/fixture/' + unit
            directory = cgroups / group.lstrip('/')
            directory.mkdir(parents=True)
            (directory / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
            (directory / 'cgroup.procs').write_text('')
            created[unit] = {
                'Id': unit, 'LoadState': 'loaded', 'ActiveState': 'active',
                'SubState': 'running', 'InvocationID': hashlib.sha256(unit.encode()).hexdigest()[:32],
                'ControlGroup': group, 'MainPID': '0', 'ExitType': 'cgroup',
                'RemainAfterExit': 'yes', 'SendSIGKILL': 'no',
                'kind': 'terminal' if argv[0] == 'gnome-terminal' else 'server'}
            return subprocess.CompletedProcess(argv, 0, stdout='', stderr='')

        def rpc(endpoint, method, params, **kwargs):
            terminal = any(unit['kind'] == 'terminal' for unit in created.values())
            if method == 'thread/loaded/list':
                return {'data': [thread_id] if terminal else []}
            if method == 'thread/read':
                return {'thread': {'id': thread_id, 'cwd': str(self.repo), 'turns': [],
                                   'status': {'type': 'idle'}}}
            if method == 'config/read':
                return {'config': {'model': 'gpt-6.1-sol', 'model_reasoning_effort': 'high',
                                   'approval_policy': 'never',
                                   'sandbox_mode': 'danger-full-access'}}
            if method in ('turn/start', 'turn/steer'):
                mutations.append((method, copy.deepcopy(params)))
                return {'turn': {'id': 'managed-bootstrap-turn-114'}}
            return {}

        write_state = self.api._launcher._write_state

        def interrupted_write(path, state):
            if state.get('phase') == 'server_started':
                raise KeyboardInterrupt('Identified server, launch journal not promoted')
            return write_state(path, state)

        qualified = {'platform': 'linux', 'terminal': 'gnome-terminal', 'codex': '0.169.0',
                     'systemd_user': True, 'cgroup_v2': True}
        with mock.patch.object(self.api, 'launch', self.api._launcher.launch), \
             mock.patch.object(backend, 'probe', return_value=qualified), \
             mock.patch.object(resumed, 'probe', return_value=qualified), \
             mock.patch.object(backend.boundary, 'run', side_effect=systemd), \
             mock.patch.object(resumed.boundary, 'run', side_effect=systemd), \
             mock.patch.object(backend, 'rpc', side_effect=rpc), \
             mock.patch.object(resumed, 'rpc', side_effect=rpc), \
             mock.patch.object(self.api._launcher, '_short_socket', side_effect=(
                 lambda transition, nonce, attempt: str(
                     self.local / 'runtime' / f'attempt-{attempt}' / 'app.sock'))):
            with mock.patch.object(self.api._launcher, '_write_state', side_effect=interrupted_write):
                with self.assertRaises(KeyboardInterrupt):
                    first = self.api.Controller(self.request, backend=backend,
                                                clock=lambda: self.now).step()
                    self.fail('Durable-create interruption not reached: ' + json.dumps(first))
            known = backend.boundary.units(self.request['mission_id'], 0)
            self.assertEqual(len(known), 1)
            self.assertTrue(known[0]['invocation_id'])
            self.assertTrue(known[0]['control_group'])
            state = json.loads(Path(self.request['state']).read_text())
            launch_state = json.loads(Path(state['launch']['0']['state']).read_text())
            self.assertEqual(launch_state['phase'], 'server_spawning')
            for _ in range(3):
                result = self.api.Controller(self.request, backend=resumed,
                                             clock=lambda: self.now).step()
                if result['phase'] in ('blocked', 'waiting_bootstrap'):
                    break
        self.assertEqual(result['phase'], 'waiting_bootstrap',
                         'Identified runtime creation must be reconciled: ' +
                         str(result.get('diagnostic')))
        self.assertEqual(sum(unit['kind'] == 'terminal' for unit in created.values()), 1)
        self.assertEqual(len(mutations), 1, 'Only the initial bootstrap may be submitted once')
        self.assertEqual(mutations[0][0], 'turn/start')
        self.assertIn('BOOTSTRAP_ONLY', json.dumps(mutations[0][1]))


    def _correction2_read_output(self):
        session, expected, thread = self._review_bootstrap_claim()
        instructions = Path(session['bootstrap_receipt']).with_suffix('.md')
        instructions.write_text('Read these current bootstrap instructions, then await dispatch.\n')
        argv = ['bootstrap-read', '--worktree', str(self.repo), '--instructions', str(instructions),
                '--handoff', str(self.handoff), '--nonce', session['transition_id']]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.api.main(argv)
        self.assertEqual(code, 0)
        return session, expected, thread, instructions, argv, output.getvalue()

    def test_correction2_m2_reader_supplies_actual_material_and_current_turn_receipt(self):
        from shlex import join
        session, expected, thread, instructions, argv, output = self._correction2_read_output()
        payload = json.loads(output)

        def strings(value):
            if isinstance(value, str):
                return [value]
            values = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
            return [text for item in values for text in strings(item)]

        supplied = '\n'.join(strings(payload))
        self.assertIn(instructions.read_text(), supplied, 'Instructions were hashed but not supplied')
        self.assertIn(self.handoff.read_text(), supplied, 'Handoff was hashed but not supplied')
        thread['turns'][0]['items'] = [{
            'type': 'commandExecution', 'id': 'reader-material-12', 'status': 'completed',
            'exitCode': 0, 'command': join([sys.executable, str(SCRIPT), *argv]),
            'aggregatedOutput': output}]
        backend = self.api.ManagedBackend(self.request)
        with mock.patch.object(backend, 'rpc', return_value={'thread': thread}):
            receipt = backend.bootstrap_receipt(session, expected)
        self.assertIsInstance(receipt, dict)
        self.assertEqual({key: receipt[key] for key in expected}, expected)

    def test_grouped_code_mode_reads_bind_each_complete_output_to_its_runtime_command(self):
        import shlex
        session, _, _ = self._review_bootstrap_claim()
        tid, turn, cwd = session['thread_id'], session['turn_id'], str(self.repo)
        def row(kind, **data):
            return {'type': kind, 'payload': data}
        def message(**data):
            return row('response_item', **data)
        def result(call, values):
            return message(type='custom_tool_call_output', call_id=call, output=[
                {'type': 'input_text', 'text': json.dumps({'exit_code': 0, 'output': value})}
                for value in values])
        items, events = [], []
        for part in (1, 2):
            command = f'python3 reader.py --part {part}'
            output = json.dumps({'part': part, 'nonce': session['transition_id']}) + '\n'
            argv = ['/bin/bash', '-lc', command]
            item_id = f'exec-{part}'
            items.append({'id': item_id, 'command': shlex.join(argv), 'cwd': cwd,
                          'aggregatedOutput': output})
            events.append(row('event_msg', type='item_completed', thread_id=tid, turn_id=turn,
                              item={'type': 'CommandExecution', 'source': 'unified_exec_startup',
                                    'id': item_id, 'command': argv, 'cwd': cwd,
                                    'status': 'completed', 'exit_code': 0,
                                    'aggregated_output': output}))
        outputs = [item['aggregatedOutput'] for item in items]
        call = message(type='custom_tool_call', name='exec', call_id='read-parts',
                       input='text(await tools.exec_command(a)); text(await tools.exec_command(b));')
        records = [row('session_meta', id=tid, cwd=cwd),
                   row('event_msg', type='task_started', turn_id=turn), call,
                   *events, result('read-parts', outputs)]
        target = self.local / 'sessions/2026/11/17'
        target.mkdir(parents=True)
        path = target / f'rollout-runtime-{tid}.jsonl'
        backend = self.api.ManagedBackend(self.request)

        def check(rows):
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            return backend._reads_visible(session, items)

        with mock.patch.dict(os.environ, {'CODEX_HOME': str(self.local)}):
            self.assertTrue(check(records))
            uri_records = copy.deepcopy(records)
            for entry in uri_records[3:5]:
                entry['payload']['item']['cwd'] = self.repo.as_uri()
            self.assertTrue(check(uri_records))
            uri_records[3]['payload']['item']['cwd'] = 'file://another-host' + str(self.repo)
            self.assertFalse(check(uri_records))
            self.assertFalse(check(records[:-1] + [result('read-parts', outputs[:1])]))
            self.assertFalse(check(records[:-1] + [result('read-parts', [outputs[0], outputs[1][:-1]])]))
            self.assertFalse(check(records[:-1] + [result('other-call', outputs)]))
            self.assertFalse(check(records[:3] + events[:1] + records[-1:]))
            for field in ('thread_id', 'turn_id'):
                foreign = copy.deepcopy(records)
                foreign[3]['payload'][field] = 'foreign'
                self.assertFalse(check(foreign))
            self.assertFalse(check(records[:3] + [dict(call, payload=dict(call['payload'],
                                                                           call_id='overlap'))]
                                   + records[3:]))
            self.assertFalse(check(records[:4] + [records[3]] + records[4:]))
            wrong = copy.deepcopy(records)
            wrong[3]['payload']['item']['command'][-1] = 'some other command'
            self.assertFalse(check(wrong))
            wrong[3] = message(type='message', role='assistant', content=outputs)
            self.assertFalse(check(wrong))

    def test_permission_format_recovery_requires_verified_reads_config_and_matching_claim(self):
        import shlex
        session, expected, thread, _, argv, output = self._correction2_read_output()
        command = shlex.join([sys.executable, str(SCRIPT), *argv])
        thread['turns'][0]['items'] = [{
            'type': 'commandExecution', 'id': 'command-id', 'status': 'completed', 'exitCode': 0,
            'command': shlex.join(['/bin/bash', '-lc', command]), 'cwd': str(self.repo),
            'source': 'unifiedExecStartup', 'aggregatedOutput': output}]
        backend = self.api.ManagedBackend(self.request)
        path = Path(session['bootstrap_receipt'])
        claim = json.loads(path.read_text())
        alternate = {'permission_profile': 'disabled', 'file_system': 'unrestricted'}
        config = {'model': 'gpt-6.1-sol', 'model_reasoning_effort': 'high',
                  'approval_policy': 'never', 'sandbox_mode': 'danger-full-access'}
        def read(endpoint, method, params):
            return {'config': config} if method == 'config/read' else {'thread': thread}
        with mock.patch.object(backend, 'rpc', side_effect=read), \
             mock.patch.object(backend, '_reads_visible', return_value=True):
            path.write_text(json.dumps(dict(claim, parent_permissions=alternate)))
            self.assertIs(backend.bootstrap_receipt(session, expected),
                          self.api.PERMISSION_FORMAT_REQUIRED)
            for invalid in (dict(claim, thread_id='elsewhere', parent_permissions=alternate),
                            dict(claim, reconciled=False, parent_permissions=alternate),
                            dict(claim, parent_permissions={'file_system': 'restricted'}),
                            dict(claim, parent_permissions={}),
                            dict(claim, parent_permissions=dict(expected['parent_permissions'],
                                                                approval_policy='on-request'))):
                path.write_text(json.dumps(invalid))
                self.assertIsNot(backend.bootstrap_receipt(session, expected),
                                 self.api.PERMISSION_FORMAT_REQUIRED)
            path.write_text(json.dumps(dict(claim, parent_permissions=alternate)))
            config['approval_policy'] = 'on-request'
            with self.assertRaises(self.api.ControllerError):
                backend.bootstrap_receipt(session, expected)
            config['approval_policy'] = 'never'
            with mock.patch.object(backend, '_reads_visible', return_value=False):
                self.assertIsNone(backend.bootstrap_receipt(session, expected))

    def test_incomplete_runtime_proven_permission_receipt_is_corrected_once_on_same_thread(self):
        original = self.runtime.bootstrap_receipt
        corrections = []
        def claim(session, expected):
            value = original(session, expected)
            if not corrections:
                return self.api.PERMISSION_FORMAT_REQUIRED
            return value
        self.runtime.rpc_failure = 'bootstrap_receipt'
        with mock.patch.object(self.runtime, 'bootstrap_receipt', side_effect=claim):
            self.step()
            self.assertEqual(self.runtime.count('rpc', 'bootstrap_receipt'), 1)
            self.assertEqual(self.runtime.count('rpc', 'dispatch'), 0)
            self.runtime.evidence = True
            corrections.append('fixed')
            with mock.patch.object(self.runtime, 'session_state', return_value={
                    'status': 'active', 'tools_running': True,
                    'turn_id': 'positively-reconciled-turn'}):
                self.assertEqual(self.step()['phase'], 'waiting_bootstrap')
                self.assertEqual(self.runtime.count('rpc', 'dispatch'), 0)
            with mock.patch.object(self.runtime, 'session_state', return_value={
                    'status': 'idle', 'tools_running': False, 'turn_id': 'positively-reconciled-turn',
                    'turn_status': 'completed'}):
                self.assertEqual(self.step()['phase'], 'working')
        self.assertEqual(self.runtime.count('rpc', 'bootstrap_receipt'), 1)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 1)
        self.assertEqual(len(self.runtime.sessions), 1)

    def test_unfixed_permission_format_cannot_trigger_a_second_correction(self):
        with mock.patch.object(self.runtime, 'bootstrap_receipt',
                               return_value=self.api.PERMISSION_FORMAT_REQUIRED):
            self.assertEqual(self.step()['phase'], 'waiting_bootstrap')
            op = self.runtime.state()['operations'][-1]
            with mock.patch.object(self.runtime, 'session_state', return_value={
                    'status': 'idle', 'tools_running': False, 'turn_id': op['turn_id'],
                    'turn_status': 'completed'}):
                self.blocked(self.step())
        self.assertEqual(self.runtime.count('rpc', 'bootstrap_receipt'), 1)
        self.assertEqual(self.runtime.count('rpc', 'dispatch'), 0)

    def test_correction2_m2_correct_hashes_without_material_are_not_bootstrap_read_proof(self):
        from shlex import join
        session, expected, thread, instructions, argv, _ = self._correction2_read_output()
        hashes_only = {'nonce': session['transition_id'], 'worktree': str(self.repo),
                       'branch': expected['branch'], 'head': expected['head'], 'dirty': {},
                       'handoff_sha256': hashlib.sha256(self.handoff.read_bytes()).hexdigest(),
                       'instructions_sha256': hashlib.sha256(instructions.read_bytes()).hexdigest()}
        thread['turns'][0]['items'] = [{
            'type': 'commandExecution', 'id': 'hashes-only-12', 'status': 'completed', 'exitCode': 0,
            'command': join([sys.executable, str(SCRIPT), *argv]),
            'aggregatedOutput': json.dumps(hashes_only)}]
        backend = self.api.ManagedBackend(self.request)
        with mock.patch.object(backend, 'rpc', return_value={'thread': thread}):
            try:
                receipt = backend.bootstrap_receipt(session, expected)
            except (self.api.ControllerError, self.api._launcher.LaunchError):
                receipt = None
        self.assertIsNone(receipt, 'Matching hashes alone never supplied either document to the model')

    @contextlib.contextmanager
    def _correction2_managed_runtime(self):
        from shlex import join
        self.config.write_text(json.dumps({'version': 1, 'models': [
            {'id': 'fixture-codex', 'harness': 'codex', 'model': 'gpt-6.1-sol'}],
            'run': {'subscription_only': True}}))
        system = _Correction2SystemIO(self.api, self.local / 'system-12')
        backend = self.api.ManagedBackend(self.request)
        backend.boundary.run, backend.boundary.root = system.command, str(system.cgroups)
        thread_id, turns, mutations = 'native-managed-thread-12', [], []

        def rpc(endpoint, method, params, **kwargs):
            if method == 'thread/loaded/list':
                return {'data': [thread_id] if any(
                    unit['kind'] == 'terminal' for unit in system.units.values()) else []}
            if method == 'thread/read':
                return {'thread': {'id': thread_id, 'cwd': str(self.repo),
                                   'status': {'type': 'idle'}, 'turns': copy.deepcopy(turns)}}
            if method == 'config/read':
                return {'config': {'model': 'gpt-6.1-sol', 'model_reasoning_effort': 'high',
                                   'approval_policy': 'never', 'sandbox_mode': 'danger-full-access'}}
            if method in ('turn/start', 'turn/steer'):
                mutations.append((method, copy.deepcopy(params)))
                turn_id = f'native-turn-12-{len(mutations)}'
                items = []
                if 'BOOTSTRAP_ONLY' in json.dumps(params):
                    directory = Path(self.request['state']).parent
                    instructions = directory / 'bootstrap-g0.md'
                    argv = ['bootstrap-read', '--worktree', str(self.repo),
                            '--instructions', str(instructions), '--handoff', str(self.handoff),
                            '--nonce', self.request['transition_id']]
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        code = self.api.main(argv)
                    self.assertEqual(code, 0)
                    claimed = {key: copy.deepcopy(self.request[key]) for key in (
                        'worktree', 'branch', 'head', 'plan_sha256', 'handoff_sha256',
                        'parent_permissions')}
                    claimed.update(thread_id=thread_id, dirty={}, instructions_read=True,
                                   handoff_read=True, reconciled=True)
                    receipt = directory / 'bootstrap-g0.json'
                    receipt.write_text(json.dumps(claimed))
                    receipt.chmod(0o600)
                    items = [{'type': 'commandExecution', 'id': 'actual-reader-12',
                              'status': 'completed', 'exitCode': code,
                              'command': join([sys.executable, str(SCRIPT), *argv]),
                              'aggregatedOutput': output.getvalue()}]
                turns.append({'id': turn_id, 'status': 'completed', 'items': items})
                return {'turn': {'id': turn_id}}
            return {}

        def measure(repo, observed_thread, **kwargs):
            return {'thread_id': observed_thread, 'source': 'codex-rollout', 'repo': str(repo),
                    'model_context_window': 100000, 'used_tokens': 39000, 'used_percent': 39,
                    'remaining_percent': 61, 'basis': 'last_total_tokens/model_context_window',
                    'observed_at': self.now.isoformat(), 'measured_at': self.now.isoformat()}

        with system.active(), \
             mock.patch.object(self.api, 'launch', self.api._launcher.launch), \
             mock.patch.object(backend, 'rpc', side_effect=rpc), \
             mock.patch.object(self.api, 'snapshot_context', side_effect=measure), \
             mock.patch.object(self.api._launcher, '_short_socket', side_effect=(
                 lambda transition, nonce, attempt: str(
                     self.local / 'runtime-12' / f'attempt-{attempt}' / 'app.sock'))):
            yield backend, system, mutations

    def test_correction2_m5_working_step_reconnects_lost_tui_same_generation_without_prompt(self):
        with self._correction2_managed_runtime() as (backend, system, mutations):
            initial = self.api.Controller(self.request, backend=backend, clock=lambda: self.now).step()
            self.assertEqual(initial['phase'], 'working', initial)
            before = copy.deepcopy(mutations)
            server = next(unit for unit in system.units.values() if unit['kind'] == 'server')
            terminal = next(unit for unit in system.units.values() if unit['kind'] == 'terminal')
            self.assertIn(server['pid'], system.processes)
            system.exit_process(terminal['pid'])
            self.assertEqual(terminal['properties']['SubState'], 'exited')
            for _ in range(3):
                result = self.api.Controller(self.request, backend=backend, clock=lambda: self.now).step()
                if sum(unit['kind'] == 'terminal' for unit in system.units.values()) == 2:
                    break
            self.assertEqual(sum(unit['kind'] == 'terminal' for unit in system.units.values()), 2,
                             'Public working step never engaged TUI reconnection')
            self.assertEqual(result['generation'], 0)
            self.assertEqual(result['phase'], 'working', result)
            self.assertEqual(mutations, before, 'Reconnection re-sent a bootstrap/business prompt')
            journal = json.loads(Path(json.loads(Path(self.request['state']).read_text())[
                'launch']['0']['state']).read_text())
            self.assertEqual(journal['phase'], 'submitted')
            self.assertEqual(journal['thread_id'], 'native-managed-thread-12')
            self.assertEqual(sum(unit['kind'] == 'server' for unit in system.units.values()), 1)

    def test_correction2_m5_public_reconnection_crash_reuses_durably_created_tui(self):
        with self._correction2_managed_runtime() as (backend, system, mutations):
            self.assertEqual(self.api.Controller(
                self.request, backend=backend, clock=lambda: self.now).step()['phase'], 'working')
            before = copy.deepcopy(mutations)
            terminal = next(unit for unit in system.units.values() if unit['kind'] == 'terminal')
            system.exit_process(terminal['pid'])
            write_state = self.api._launcher._write_state

            def interrupt(path, state):
                if state.get('phase') == 'submitted' and state.get('prior_terminal'):
                    raise KeyboardInterrupt('Reconnected TUI identified before journal promotion')
                return write_state(path, state)

            with mock.patch.object(self.api._launcher, '_write_state', side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt,
                                       msg='Public working step did not begin reconnection'):
                    self.api.Controller(self.request, backend=backend, clock=lambda: self.now).step()
            for _ in range(3):
                result = self.api.Controller(self.request, backend=backend, clock=lambda: self.now).step()
                if result['phase'] == 'working':
                    break
            self.assertEqual(result['phase'], 'working', result)
            self.assertEqual(result['generation'], 0)
            self.assertEqual(sum(unit['kind'] == 'terminal' for unit in system.units.values()), 2)
            self.assertEqual(mutations, before)

    def test_correction2_m5_reconnect_failures_remain_bounded_after_reinstantiation(self):
        with self._correction2_managed_runtime() as (backend, system, mutations):
            self.assertEqual(self.api.Controller(
                self.request, backend=backend, clock=lambda: self.now).step()['phase'], 'working')
            before = copy.deepcopy(mutations)
            system.exit_process(next(unit['pid'] for unit in system.units.values()
                                     if unit['kind'] == 'terminal'))
            command, attempted = system.command, []

            def unavailable(argv, **kwargs):
                if argv[0] == 'gnome-terminal':
                    attempted.append(list(argv))
                    raise OSError('simulated temporary terminal outage')
                return command(argv, **kwargs)

            backend.boundary.run = unavailable
            for _ in range(6):
                result = self.api.Controller(self.request, backend=backend, clock=lambda: self.now).step()
            self.assertGreater(len(attempted), 0, 'No recovery was attempted by the public path')
            self.assertLessEqual(len(attempted), 2, 'Re-instantiation reset the reconnect budget')
            self.assertEqual(result['phase'], 'blocked', result)
            self.assertEqual(mutations, before)

    def test_correction2_m6_wrapper_effective_environment_cannot_bypass_subscription_gate(self):
        self.config.write_text(json.dumps({'version': 1, 'models': [
            {'id': 'fixture-codex', 'harness': 'codex', 'model': 'gpt-6.1-sol'}],
            'run': {'subscription_only': True}}))
        system = _Correction2SystemIO(self.api, self.local / 'wrapper-env-12')
        backend = self.api.ManagedBackend(self.request)
        backend.boundary.run, backend.boundary.root = system.command, str(system.cgroups)
        with system.active():
            self.assertNotIn('OPENAI_API_KEY', os.environ)
            self.assertTrue(backend.probe()['systemd_user'])  # real subscription gate, IO mocked
            backend.prepare_generation(self.request['mission_id'], 0, str(self.repo))
            for name in ('OPENAI_API_KEY', 'OPENAI_BASE_URL'):
                with self.subTest(manager_variable=name):
                    system.manager_environment = {name: 'DUMMY_114_NEVER_A_REAL_CREDENTIAL'}
                    first = len(system.executions)
                    try:
                        backend.spawn('server', self.api._launcher.server_argv(
                            str(self.local / ('effective-' + name) / 'app.sock'),
                            {'approval_policy': 'never', 'sandbox_mode': 'danger-full-access'}),
                            str(self.repo), self.request['state'])
                    except (self.api.ControllerError, self.api._launcher.LaunchError):
                        pass  # explicit refusal before inference is allowed
                    self.assertNotIn(name, os.environ, 'The controller environment stayed clean')
                    for execution in system.executions[first:]:
                        self.assertNotIn(name, execution['environment'],
                                         'Manager-only auth/route input reached actual exec')


class SystemdAdapterTests(unittest.TestCase):
    """Exercise real adapter argv/identity/fs checks, not the workflow spy above."""
    @classmethod
    def setUpClass(cls):
        cls.api = load_script('context_systemd_114', SCRIPT)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='context-boundary-114-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / 'boundary/state.json'
        self.cgroups = self.root / 'cgroup'
        self.events = self.cgroups / 'user.slice/agentic-fixture/cgroup.events'
        self.events.parent.mkdir(parents=True)
        self.events.write_text('populated 1\nfrozen 0\n')
        self.calls = []
        self.missing = False
        self.invocation = 'a' * 32
        self.control_group = '/user.slice/agentic-fixture'
        self.active_state = 'active'
        self.sub_state = 'running'
        self.load_state = 'loaded'
        self.exit_type = 'cgroup'
        self.remain_after_exit = 'yes'
        self.send_sigkill = 'no'
        self.reported_unit = None
        self.omit_properties = set()
        self.boundary = self.api.SystemdBoundary(str(self.state), run=self.run_command,
                                                cgroup_root=str(self.cgroups))

    def run_command(self, argv, **kwargs):
        self.assertIsInstance(argv, list)
        self.assertFalse(kwargs.get('shell', False))
        self.calls.append(list(argv))
        if argv[0] == 'systemctl' and 'show' in argv:
            properties = {
                'Id': self.identity['unit'] if self.reported_unit is None else self.reported_unit,
                'LoadState': self.load_state, 'ActiveState': self.active_state,
                'SubState': self.sub_state, 'InvocationID': self.invocation,
                'ControlGroup': self.control_group, 'MainPID': '0',
                'ExitType': self.exit_type, 'RemainAfterExit': self.remain_after_exit,
                'SendSIGKILL': self.send_sigkill}
            text = ''.join(f'{key}={value}\n' for key, value in properties.items()
                           if key not in self.omit_properties)
            return subprocess.CompletedProcess(argv, 1 if self.missing else 0,
                                               stdout=text, stderr='')
        serialized = self.state.read_text()
        self.assertIn(self.identity['unit'], serialized, 'Unit not durable before spawn')
        self.assertIn(self.identity['owner_token'], serialized, 'Token not durable before spawn')
        return subprocess.CompletedProcess(argv, 0, stdout='', stderr='')

    def reserve(self, mission='mission-114', generation=0, role='server'):
        self.identity = self.boundary.reserve(mission, generation, role, str(self.root))
        return self.identity

    def test_recovered_unused_reservation_does_not_block_final_closure_of_live_units(self):
        backend = self.api.ManagedBackend({'state': str(self.state)})
        backend.boundary = self.boundary
        group = {'mission_id': 'mission-114', 'generation': 0}
        first = self.reserve(role='server1')
        self.assertEqual(self.boundary.recover('mission-114', 0, 'server', set()), 'none')
        second = self.reserve(role='server2')
        live = self.boundary.spawn(second, ['codex', 'app-server'], str(self.root))
        self.assertEqual(len(self.boundary.units('mission-114', 0)), 2)
        self.assertNotEqual(first['unit'], live['unit'])
        self.assertEqual(backend._generation(group), [live])
        pending = self.reserve(role='terminal1')
        self.assertFalse(backend.quiescent(group))
        self.assertFalse(backend.closure(group))
        self.assertIn(pending, backend._generation(group))

    def spawn(self, argv=None):
        self.reserve()
        self.identity = self.boundary.spawn(self.identity, argv or [
            'codex', 'app-server', '--listen', 'unix:///fixture.sock'], str(self.root))
        return self.identity

    def assert_no_destructive_effects(self, calls):
        """SendSIGKILL=no disables escalation; it is not a destructive signal."""
        for argv in calls:
            for argument in argv:
                self.assertNotIn(Path(argument).name, ('kill', 'pkill', 'killall'), argv)
                self.assertNotIn('cgroup.kill', argument, argv)
                if 'SendSIGKILL=' in argument:
                    self.assertEqual(argument.split('SendSIGKILL=', 1)[1], 'no', argv)
                    continue
                self.assertNotIn(argument.upper(), ('-9', '-KILL', '-SIGKILL'), argv)
                self.assertNotIn(argument.rsplit('=', 1)[-1].upper(), ('SIGKILL', 'KILL'), argv)
                if argument.startswith('--signal=') or 'KillSignal=' in argument:
                    self.assertNotEqual(argument.rsplit('=', 1)[1], '9', argv)
            self.assertFalse(any(argv[i:i + 2] == ['--signal', '9']
                                 for i in range(len(argv) - 1)), argv)

    def test_c2_unit_and_token_durable_before_actual_subprocess_and_no_collect(self):
        identity = self.spawn()
        self.assertEqual(identity['invocation_id'], self.invocation)
        self.assertEqual(identity['control_group'], self.control_group)
        actual = [c for c in self.calls if 'systemd-run' in c][0]
        self.assertIn('--user', actual)
        self.assertNotIn('--collect', actual)
        self.assertIn('SendSIGKILL=no', ' '.join(actual),
                      'systemd defaults would kill remaining writers on stop timeout')
        self.assertIn('ExitType=cgroup', ' '.join(actual))
        self.assertIn('RemainAfterExit=yes', ' '.join(actual))
        self.assert_no_destructive_effects(self.calls)
        properties = ' '.join(actual)
        if 'RuntimeMaxSec=' in properties:
            self.assertIn(properties.split('RuntimeMaxSec=', 1)[1].split()[0], ('0', 'infinity'))
        self.assertIn('codex', actual)
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.state.parent.stat().st_mode), 0o700)

    def test_c2_actual_tui_after_gnome_separator_is_inside_unit_and_admission_wrapper(self):
        self.reserve(role='terminal')
        argv = ['gnome-terminal', '--wait', '--', 'codex', '--remote', 'unix:///fixture.sock']
        self.identity = self.boundary.spawn(self.identity, argv, str(self.root))
        terminal = [c for c in self.calls if c[0] == 'gnome-terminal'][0]
        child = terminal[terminal.index('--') + 1:]
        self.assertIn('systemd-run', child, 'Wrapping only gnome-terminal is insufficient')
        self.assertIn('admit-exec', child)
        self.assertIn(self.identity['unit'], ' '.join(child))
        self.assertIn(self.identity['owner_token'], child)
        self.assertLess(child.index('systemd-run'), child.index('codex'))
        self.assertIn('--remote', child)
        self.assertNotIn('resume', child)

    def test_c2_late_admission_is_refused_after_durable_close_even_with_same_token(self):
        identity = self.reserve()
        self.assertTrue(self.boundary.admit(identity))
        self.assertFalse(self.boundary.admit({**identity, 'owner_token': 'foreign-token'}))
        self.boundary.close_admission(identity)
        restarted = self.api.SystemdBoundary(str(self.state), run=self.run_command,
                                             cgroup_root=str(self.cgroups))
        self.assertFalse(restarted.admit(identity))
        before = copy.deepcopy(self.calls)
        with self.assertRaises(self.api.ControllerError):
            restarted.spawn(identity, ['codex'], str(self.root))
        self.assertEqual(self.calls, before)

    def test_c2_cli_late_wrapper_refuses_before_exec_or_subprocess(self):
        identity = self.reserve()
        self.boundary.close_admission(identity)
        with mock.patch.object(os, 'execvp') as execute, \
             mock.patch.object(subprocess, 'run') as run, \
             contextlib.redirect_stderr(io.StringIO()):
            result = self.api.main(['admit-exec', '--state', str(self.state),
                                    '--unit', identity['unit'], '--token', identity['owner_token'],
                                    '--', 'codex', '--version'])
        self.assertNotEqual(result, 0)
        execute.assert_not_called()
        run.assert_not_called()

    def test_c2_mainpid_zero_is_not_closure_while_cgroup_populated(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.active_state, self.sub_state = 'active', 'running'
        self.events.write_text('populated 1\nfrozen 0\n')
        self.assertFalse(self.boundary.closure(identity))
        self.events.write_text('populated 0\nfrozen 0\n')
        self.assertTrue(self.boundary.closure(identity))

    def test_c2_retained_cgroup_service_proves_closure_after_control_group_disappears(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.events.unlink()
        self.active_state, self.sub_state = 'active', 'exited'
        self.control_group = ''
        self.assertEqual(identity['invocation_id'], self.invocation)
        self.assertTrue(self.boundary.closure(identity))

    def test_c2_retained_exited_service_requires_closed_admission(self):
        identity = self.spawn()
        self.events.unlink()
        self.active_state, self.sub_state = 'active', 'exited'
        self.control_group = ''
        self.assertFalse(self.boundary.closure(identity))

    def test_c2_exited_receipt_rejects_main_lifetime_wrong_properties_identity_or_state(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.events.unlink()
        self.active_state, self.sub_state = 'active', 'exited'
        self.control_group = ''
        invalid = (('exit_type', 'main'), ('remain_after_exit', 'no'),
                   ('send_sigkill', 'yes'), ('load_state', 'not-found'),
                   ('active_state', 'inactive'), ('sub_state', 'running'),
                   ('sub_state', 'dead'), ('invocation', 'b' * 32),
                   ('reported_unit', 'foreign.service'))
        for attribute, value in invalid:
            with self.subTest(attribute=attribute, value=value):
                previous = getattr(self, attribute)
                setattr(self, attribute, value)
                try:
                    self.assertFalse(self.boundary.closure(identity))
                finally:
                    setattr(self, attribute, previous)

    def test_c2_exited_receipt_requires_each_positive_property_explicitly_present(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.events.unlink()
        self.active_state, self.sub_state = 'active', 'exited'
        self.control_group = ''
        for name in ('Id', 'LoadState', 'ActiveState', 'SubState', 'InvocationID',
                     'ControlGroup', 'ExitType', 'RemainAfterExit', 'SendSIGKILL'):
            with self.subTest(missing=name):
                self.omit_properties = {name}
                self.assertFalse(self.boundary.closure(identity))
        self.omit_properties.clear()

    def test_c2_running_service_without_control_group_or_events_is_not_closed(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.events.unlink()
        self.active_state, self.sub_state = 'active', 'running'
        self.control_group = ''
        self.assertFalse(self.boundary.closure(identity))

    def test_c2_unit_absence_changed_invocation_or_cgroup_never_proves_closure(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.events.write_text('populated 0\nfrozen 0\n')
        self.missing = True
        self.assertFalse(self.boundary.closure(identity))
        self.missing = False
        self.invocation = 'b' * 32
        self.assertFalse(self.boundary.closure(identity))
        self.invocation = identity['invocation_id']
        self.control_group = '/foreign/cgroup'
        self.assertFalse(self.boundary.closure(identity))

    def test_c2_open_admission_prevents_closure_even_if_cgroup_is_empty(self):
        identity = self.spawn()
        self.events.write_text('populated 0\nfrozen 0\n')
        self.assertFalse(self.boundary.closure(identity))

    def test_c2_missing_or_symlink_cgroup_events_is_not_evidence_of_empty_boundary(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.events.unlink()
        self.assertFalse(self.boundary.closure(identity))
        other = self.root / 'foreign.events'
        other.write_text('populated 0\n')
        self.events.symlink_to(other)
        self.assertFalse(self.boundary.closure(identity))

    def test_c2_retirement_refuses_foreign_identity_and_never_uses_kill(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        self.events.write_text('populated 0\nfrozen 0\n')
        foreign = {**identity, 'invocation_id': 'b' * 32}
        before = len(self.calls)
        with self.assertRaises(self.api.ControllerError):
            self.boundary.retire(foreign)
        self.assertFalse(any('stop' in c for c in self.calls[before:]))
        self.assert_no_destructive_effects(self.calls)

    def test_c2_graceful_retirement_targets_only_verified_owned_user_unit(self):
        identity = self.spawn()
        self.events.write_text('populated 0\nfrozen 0\n')
        self.boundary.close_admission(identity)
        self.assertTrue(self.boundary.retire(identity))
        stops = [c for c in self.calls if 'stop' in c]
        for argv in stops:
            self.assertEqual(argv[0], 'systemctl')
            self.assertIn('--user', argv)
            self.assertIn(identity['unit'], argv)
        self.assert_no_destructive_effects(self.calls)

    def test_c2_injection_or_path_tokens_never_reach_systemd(self):
        for mission in ('../../foreign', 'mission;touch /tmp/114', 'bad\nunit'):
            with self.subTest(mission=mission), self.assertRaises(self.api.ControllerError):
                self.reserve(mission=mission)
        self.assertEqual(self.calls, [])

    def test_review_m3_unattested_business_child_cannot_be_retired_by_unix_cli_flags(self):
        identity = self.spawn()
        self.boundary.close_admission(identity)
        child = 701140
        self.events.with_name('cgroup.procs').write_text(f'{child}\n')
        real_read_bytes, real_read_text = Path.read_bytes, Path.read_text
        descriptors = []

        def pin(pid):
            self.assertEqual(pid, child)
            fd = os.open(os.devnull, os.O_RDONLY)
            descriptors.append(fd)
            return fd

        def process_group(path, *args, **kwargs):
            if str(path) == f'/proc/{child}/cgroup':
                return f'0::{self.control_group}\n'
            return real_read_text(path, *args, **kwargs)

        try:
            for flag in ('--listen', '--remote'):
                with self.subTest(flag=flag):
                    command = [b'/usr/bin/python3', b'-c', b'local business operation',
                               flag.encode(), b'unix:///business-114-fixture.sock']

                    def command_line(path, *args, **kwargs):
                        if str(path) == f'/proc/{child}/cmdline':
                            return b'\0'.join(command) + b'\0'
                        return real_read_bytes(path, *args, **kwargs)

                    with mock.patch.object(Path, 'read_bytes', autospec=True,
                                           side_effect=command_line), \
                         mock.patch.object(Path, 'read_text', autospec=True,
                                           side_effect=process_group), \
                         mock.patch.object(os, 'pidfd_open', side_effect=pin), \
                         mock.patch.object(self.api.signal, 'pidfd_send_signal') as signal_pid, \
                         mock.patch.object(os, 'kill') as kill, \
                         mock.patch.object(os, 'killpg') as killpg:
                        refused, outcome = False, None
                        try:
                            outcome = self.boundary.retire(identity)
                        except self.api.ControllerError:
                            refused = True
                        signal_pid.assert_not_called()
                        kill.assert_not_called()
                        killpg.assert_not_called()
                        self.assertTrue(refused or outcome is False,
                                        'CLI flags alone cannot attest infrastructure ownership')
        finally:
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except OSError:
                    pass  # the real adapter closes its pinned descriptor on return


    def _correction2_native_boundary(self, system, command):
        boundary = self.api.SystemdBoundary(str(system.root / 'boundary/state.json'),
                                            run=system.command, cgroup_root=str(system.cgroups))
        identity = boundary.reserve('native-12', 0, 'server', str(self.root))
        identity = boundary.spawn(identity, command, str(self.root))
        return boundary, identity

    def test_correction2_m3_native_attested_argv_with_final_nul_is_retirable(self):
        system = _Correction2SystemIO(self.api, self.root / 'native-12')
        with system.active():
            boundary, identity = self._correction2_native_boundary(system, [
                'codex', 'app-server', '--listen', 'unix:///native-fixture-12.sock'])
            self.assertEqual(len(system.executions), 1, 'The actual wrapper must attest before exec')
            self.assertEqual(boundary.foreign_members(identity), [],
                             'The native terminating NUL is not an extra empty argument')
            boundary.close_admission(identity)
            self.assertTrue(boundary.retire(identity))
            self.assertEqual(system.processes, {})  # only the attested infrastructure exited

    def test_correction2_m3_real_empty_argument_preserved_and_missing_empty_is_foreign(self):
        system = _Correction2SystemIO(self.api, self.root / 'native-empty-12')
        command = [sys.executable, '-c', 'pass', '', 'argument-12']
        with system.active():
            boundary, identity = self._correction2_native_boundary(system, command)
            pid = next(iter(system.processes))
            with self.subTest(argv='legitimate empty argument remains'):
                self.assertEqual(boundary.foreign_members(identity), [])
            system.processes[pid]['argv'] = [sys.executable, '-c', 'pass', 'argument-12']
            with self.subTest(argv='empty argument was removed'):
                self.assertEqual(boundary.foreign_members(identity), [pid],
                                 'Normalizing the final separator must not erase real arguments')

    @contextlib.contextmanager
    def _correction2_descendant_writer(self):
        system = _Correction2SystemIO(self.api, self.root / 'descendant-12')
        with system.active():
            boundary, identity = self._correction2_native_boundary(system, [
                'codex', 'app-server', '--listen', 'unix:///descendant-fixture-12.sock'])
            unit = system.units[identity['unit']]
            system.processes.pop(unit['pid'])  # native parent exited; its descendant remains
            unit['properties']['MainPID'] = '0'
            directory = system.cgroups / unit['group'].lstrip('/')
            (directory / 'cgroup.procs').write_text('')
            child_directory = directory / 'business-child'
            child_directory.mkdir()
            (child_directory / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
            child = 801999
            (child_directory / 'cgroup.procs').write_text(f'{child}\n')
            system.processes[child] = {'pid': child, 'starttime': '801999114',
                                       'group': unit['group'] + '/business-child',
                                       'argv': [sys.executable, '-c', 'business write in progress']}
            backend = self.api.ManagedBackend({'state': str(system.root / 'controller.json'),
                                                'mission_id': 'native-12',
                                                'worktree': str(self.root)})
            backend.boundary = boundary
            yield backend, boundary, identity, child_directory

    def test_correction2_m7_subgroup_writer_or_unreadable_membership_prevents_quiescence(self):
        with self._correction2_descendant_writer() as (backend, boundary, identity, child_directory):
            original_read = Path.read_text
            for unreadable in (False, True):
                with self.subTest(unreadable=unreadable):
                    def read(path, *args, **kwargs):
                        if unreadable and path == child_directory / 'cgroup.procs':
                            raise PermissionError('simulated inaccessible descendant membership')
                        return original_read(path, *args, **kwargs)

                    with mock.patch.object(Path, 'read_text', new=read):
                        self.assertFalse(backend.quiescent(identity),
                                         'An empty root cgroup.procs does not close its descendants')
                        self.assertFalse(boundary.closure(identity))

    def test_correction2_m7_subgroup_writer_or_unreadable_membership_prevents_retirement(self):
        with self._correction2_descendant_writer() as (_, boundary, identity, child_directory):
            boundary.close_admission(identity)
            original_read = Path.read_text
            for unreadable in (False, True):
                with self.subTest(unreadable=unreadable):
                    def read(path, *args, **kwargs):
                        if unreadable and path == child_directory / 'cgroup.procs':
                            raise PermissionError('simulated inaccessible descendant membership')
                        return original_read(path, *args, **kwargs)

                    with mock.patch.object(Path, 'read_text', new=read), \
                         mock.patch.object(self.api.signal, 'pidfd_send_signal',
                                           wraps=self.api.signal.pidfd_send_signal) as signal_pid:
                        refused, result = False, None
                        try:
                            result = boundary.retire(identity)
                        except self.api.ControllerError:
                            refused = True
                        signal_pid.assert_not_called()
                        self.assertTrue(refused or result is False,
                                        'Retirement ignored a populated/unreadable sub-cgroup')


    def test_correction2_m7_membership_loss_after_initial_check_never_means_empty(self):
        with self._correction2_descendant_writer() as (_, boundary, identity, child_directory):
            boundary.close_admission(identity)
            root_members = child_directory.parent / 'cgroup.procs'
            original_read, observed = Path.read_text, []

            def lost(path, *args, **kwargs):
                if path == root_members:
                    observed.append(str(path))
                    if len(observed) >= 2:
                        raise PermissionError('membership became unreadable before retirement')
                return original_read(path, *args, **kwargs)

            with mock.patch.object(Path, 'read_text', new=lost), \
                 mock.patch.object(self.api.signal, 'pidfd_send_signal',
                                   wraps=self.api.signal.pidfd_send_signal) as signal_pid:
                refused, result = False, None
                try:
                    result = boundary.retire(identity)
                except self.api.ControllerError:
                    refused = True
                signal_pid.assert_not_called()
                self.assertTrue(refused or result is False,
                                f'Indeterminate membership accepted after {len(observed)} reads')


class _Correction2SystemIO:
    """OS fixture: real admit-exec attestation, native argv bytes, populated cgroups.

    This fixture simulates execution/exit, never classification, admission, closure,
    bootstrap validation, controller phases or reconnect decisions.
    """
    def __init__(self, api, root):
        self.api, self.root = api, Path(root)
        self.cgroups = self.root / 'native-cgroup'
        self.processes, self.units, self.executions, self.pins = {}, {}, [], {}
        self.manager_environment = {}
        self.current_pid = None
        self.next_pid = 801212

    @contextlib.contextmanager
    def active(self):
        read_text, read_bytes, readlink = Path.read_text, Path.read_bytes, os.readlink
        run, which, exists = subprocess.run, shutil.which, os.path.exists

        def proc_path(path, filename):
            parts = str(path).split('/')
            if len(parts) == 4 and parts[1] == 'proc' and parts[3] == filename:
                return self.processes.get(int(parts[2])) if parts[2].isdigit() else None
            return None

        def text(path, *args, **kwargs):
            process = proc_path(path, 'stat')
            if process:
                return f'{process["pid"]} (codex native) ' + ' '.join(
                    ['S', *(['0'] * 18), process['starttime'], *(['0'] * 10)])
            process = proc_path(path, 'cgroup')
            if process:
                return f'0::{process["group"]}\n'
            if str(path) == '/etc/codex/config.toml':
                return ''  # synthetic empty settings; never inspect machine credentials
            if str(path).startswith('/proc/'):
                raise FileNotFoundError(str(path))
            return read_text(path, *args, **kwargs)

        def binary(path, *args, **kwargs):
            process = proc_path(path, 'cmdline')
            if process:
                return b'\0'.join(arg.encode() for arg in process['argv']) + b'\0'
            if str(path).startswith('/proc/'):
                raise FileNotFoundError(str(path))
            return read_bytes(path, *args, **kwargs)

        def link(path, *args, **kwargs):
            process = proc_path(path, 'exe')
            if process:
                return process['argv'][0] if process['argv'][0] != 'codex' else (
                    '/home/issa/.codex/packages/standalone/releases/'
                    '0.169.0-x86_64-unknown-linux-musl/bin/codex')
            return readlink(path, *args, **kwargs)

        def execute(program, argv, environ=None):
            process = self.processes[self.current_pid]
            process['argv'] = list(argv)
            self.executions.append({'pid': self.current_pid, 'argv': list(argv),
                                    'environment': dict(os.environ if environ is None else environ)})

        def pin(pid):
            if pid not in self.processes:
                raise ProcessLookupError(pid)
            descriptor = os.open(os.devnull, os.O_RDONLY)
            self.pins[descriptor] = pid
            return descriptor

        def signal_process(descriptor, sig, *args):
            if sig != self.api.signal.SIGTERM:
                raise AssertionError('Only graceful infrastructure exit is simulated')
            self.exit_process(self.pins[descriptor])

        def command(argv, **kwargs):
            if argv[0] == 'git':
                return run(argv, **kwargs)  # disposable fixture repository only
            if argv[:2] == ['codex', '--version']:
                return subprocess.CompletedProcess(argv, 0, stdout='codex-cli 0.169.0\n', stderr='')
            if argv[:3] == ['codex', 'login', 'status']:
                return subprocess.CompletedProcess(argv, 0, stdout='Logged in using ChatGPT', stderr='')
            return self.command(argv, **kwargs)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ, {
                'HOME': str(self.root / 'dummy-home'), 'PATH': '/usr/bin:/bin',
                'DISPLAY': ':114'}, clear=True))
            for owner, name, replacement in (
                    (Path, 'read_text', text), (Path, 'read_bytes', binary),
                    (os, 'readlink', link), (os, 'execvp', execute), (os, 'execve', execute),
                    (os, 'execvpe', execute), (os, 'pidfd_open', pin),
                    (self.api.signal, 'pidfd_send_signal', signal_process),
                    (subprocess, 'run', command)):
                stack.enter_context(mock.patch.object(owner, name, side_effect=replacement,
                                                     autospec=owner is Path))
            stack.enter_context(mock.patch.object(shutil, 'which', side_effect=(
                lambda name, *a, **k: '/fixture/bin/' + name
                if name in ('codex', 'gnome-terminal') else which(name, *a, **k))))
            stack.enter_context(mock.patch.object(os.path, 'exists', side_effect=(
                lambda path: True if str(path) == '/sys/fs/cgroup/cgroup.controllers'
                else exists(path))))
            stack.enter_context(mock.patch.object(os, 'kill', side_effect=AssertionError('real kill')))
            stack.enter_context(mock.patch.object(os, 'killpg', side_effect=AssertionError('real killpg')))
            yield self

    def command(self, argv, **kwargs):
        if argv[0] == 'systemctl':
            if '--property=Version' in argv:
                return subprocess.CompletedProcess(argv, 0, stdout='Version=255\n', stderr='')
            unit = next(arg for arg in argv if arg.endswith('.service'))
            info = self.units[unit]
            text = ''.join(f'{key}={value}\n' for key, value in info['properties'].items())
            return subprocess.CompletedProcess(argv, 0, stdout=text, stderr='')
        if argv[0] not in ('systemd-run', 'gnome-terminal'):
            raise AssertionError('Unexpected external process: ' + str(argv))
        unit = next(arg.split('=', 1)[1] for arg in argv if arg.startswith('--unit='))
        if unit in self.units:
            raise AssertionError('Duplicate creation of an existing unit')
        pid, self.next_pid = self.next_pid, self.next_pid + 1
        group = '/fixture/' + unit
        directory = self.cgroups / group.lstrip('/')
        directory.mkdir(parents=True)
        (directory / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
        (directory / 'cgroup.procs').write_text(f'{pid}\n')
        wrapper = argv[argv.index('admit-exec') + 1:]
        self.processes[pid] = {'pid': pid, 'starttime': str(pid + 114), 'group': group,
                               'argv': [sys.executable, str(SCRIPT), 'admit-exec', *wrapper]}
        self.units[unit] = {'pid': pid, 'kind': 'terminal' if argv[0] == 'gnome-terminal' else 'server',
                            'group': group, 'properties': {
                                'Id': unit, 'LoadState': 'loaded', 'ActiveState': 'active',
                                'SubState': 'running', 'MainPID': str(pid), 'ControlGroup': group,
                                'InvocationID': hashlib.sha256(unit.encode()).hexdigest()[:32],
                                'ExitType': 'cgroup', 'RemainAfterExit': 'yes', 'SendSIGKILL': 'no'}}
        self.current_pid = pid
        with mock.patch.object(os, 'getpid', return_value=pid), \
             mock.patch.dict(os.environ, self.manager_environment), \
             contextlib.redirect_stderr(io.StringIO()):
            code = self.api.main(['admit-exec', *wrapper])
        self.current_pid = None
        if code:
            self.exit_process(pid)
        return subprocess.CompletedProcess(argv, code, stdout='', stderr='')

    def exit_process(self, pid):
        process = self.processes.pop(pid)
        directory = self.cgroups / process['group'].lstrip('/')
        (directory / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
        (directory / 'cgroup.procs').write_text('')
        for unit in self.units.values():
            if unit['pid'] == pid:
                unit['properties'].update(MainPID='0', ControlGroup='', SubState='exited')


if __name__ == '__main__':
    unittest.main()
