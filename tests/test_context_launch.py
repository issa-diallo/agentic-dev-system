"""#113 L1–L7 / RM4, RM5, RM8, RM9: opt-in fresh terminal launch.

Public contract: launch(request, backend=None, reconnect=False) returns a receipt
with phase/thread_id/turn_id. LaunchError means BLOCKED. CLI: --request JSON
[--reconnect]. A backend replaces only process/RPC boundaries, never validation,
prompt construction, persistence, locking or transition decisions. No model runs.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import importlib.util
import json
import os
import select
from pathlib import Path
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from test_checkpoint import manual_handoff

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / 'scripts/agentic-context-launch.py'
SECRET = 'PRIVATE_HANDOFF_BODY_NEVER_PRINT_113'


def load_api():
    spec = importlib.util.spec_from_file_location('context_launch_113', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RuntimeBoundary:
    """Protocol-shaped runtime spy; asserts durable intent at actual effect boundaries."""
    def __init__(self, request):
        self.request = request
        self.calls = []
        self.processes = {}
        self.fail = None
        self.evidence = None
        self.stop_confirmed = True
        self.entered = None
        self.release = None
        self.config = {'model': 'gpt-6.1-sol', 'model_reasoning_effort': 'high',
                       'approval_policy': 'never', 'sandbox_mode': 'danger-full-access'}

    def state(self):
        return json.loads(Path(self.request['state']).read_text())

    def probe(self):
        self.calls.append(('probe',))
        return {'platform': 'linux', 'terminal': 'gnome-terminal', 'codex': '0.169.0'}

    def spawn(self, kind, argv, cwd, state_path):
        state = self.state()
        assert state['phase'] not in ('submitted', 'submitting')
        assert state['transition_id'] == self.request['transition_id']
        assert Path(state_path) == Path(self.request['state'])
        assert isinstance(argv, list) and all(isinstance(arg, str) for arg in argv)
        self.calls.append(('spawn', kind, list(argv), str(cwd)))
        if self.entered is not None:
            self.entered.set()
            assert self.release.wait(5)
        if self.fail == kind:
            raise OSError('private runtime error ' + SECRET)
        identity = {'pid': 70000 + len(self.processes), 'starttime': str(len(self.calls))}
        self.processes[identity['pid']] = identity
        return identity

    def rpc(self, endpoint, method, params):
        self.calls.append(('rpc', method, copy.deepcopy(params)))
        if self.fail == method:
            if method == 'turn/start':
                assert self.state()['phase'] == 'submitting'
            raise TimeoutError('private RPC error ' + SECRET)
        if method == 'thread/loaded/list':
            terminal = self.state().get('terminal')
            return {'data': ['fresh-thread-113'] if terminal and self.alive(terminal) else []}
        if method == 'thread/read':
            assert params['includeTurns'] is False
            return {'thread': {'id': 'fresh-thread-113', 'cwd': self.request['worktree'],
                               'turns': [], 'status': {'type': 'idle'}}}
        if method == 'config/read':
            return {'config': copy.deepcopy(self.config)}
        if method == 'turn/start':
            state = self.state()
            assert state['phase'] == 'submitting'
            assert state['thread_id'] == params['threadId'] == 'fresh-thread-113'
            assert state['nonce'] in json.dumps(params)
            return {'turn': {'id': 'turn-113'}}
        return {}

    def alive(self, identity):
        return self.processes.get(identity['pid']) == identity

    def stop(self, identity):
        self.calls.append(('stop', copy.deepcopy(identity)))
        assert self.processes.get(identity['pid']) == identity, 'Foreign/reused PID stopped'
        if self.stop_confirmed:
            del self.processes[identity['pid']]
        return self.stop_confirmed

    def submission_evidence(self, state):
        self.calls.append(('evidence', state['thread_id'], state['nonce']))
        return copy.deepcopy(self.evidence)

    def count(self, kind, value=None):
        return sum(call[0] == kind and (value is None or call[1] == value)
                   for call in self.calls)


class LaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCRIPT.is_file():
            raise AssertionError('L1–L6: scripts/agentic-context-launch.py absent (phase rouge)')
        cls.api = load_api()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='context-launch-113-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'worktree with spaces'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'feat/context-launch')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'product').write_text('preserved local work\n')
        self.git('add', 'product')
        self.git('commit', '-qm', 'Initial fixture')
        (self.repo / '.git/info/exclude').write_text('/.agentic-local/\n')
        self.local = self.repo / '.agentic-local'
        self.local.mkdir(mode=0o700)
        handoff = self.local / 'HANDOFF.md'
        handoff.write_text(manual_handoff(self.repo, note=SECRET))
        plan = self.local / 'pr-split.json'
        plan.write_text(json.dumps({'version': 1, 'story': 'fixture-113', 'prs': [
            {'id': '113-PR1', 'branch': 'feat/context-launch', 'files': ['product']}]}))
        config = self.local / 'agentic.config.json'
        config.write_text('{"version": 1}')
        skill = self.local / 'skills/start-ticket/SKILL.md'
        skill.parent.mkdir(parents=True)
        shutil.copyfile(SOURCE / 'skills/start-ticket/SKILL.md', skill)
        self.request = {
            'transition_id': '113-transition-1',
            'ticket_url': 'https://github.com/issa-diallo/agentic-dev-system/issues/113',
            'worktree': str(self.repo), 'branch': 'feat/context-launch',
            'head': self.git('rev-parse', 'HEAD'), 'handoff': str(handoff),
            'handoff_sha256': hashlib.sha256(handoff.read_bytes()).hexdigest(),
            'plan': str(plan), 'plan_sha256': hashlib.sha256(json.dumps(
                json.loads(plan.read_text()), sort_keys=True, separators=(',', ':'),
                ensure_ascii=False).encode()).hexdigest(),
            'config': str(config), 'skill': str(skill), 'phase': 'BUILD',
            'last_pass': 'PREPARE + PR_SPLIT PASS',
            'next_action': 'Lire product puis vérifier les AC restants.',
            'first_read': str(self.repo / 'product'), 'writers_stopped': True,
            'parent_permissions': {'approval_policy': 'never',
                                   'sandbox_mode': 'danger-full-access',
                                   'profile': None, 'writable_roots': []},
            'state': str(self.local / 'launch/transition.json'),
        }
        self.runtime = RuntimeBoundary(self.request)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def launch(self, **kwargs):
        return self.api.launch(self.request, backend=self.runtime, **kwargs)

    def blocked(self, **kwargs):
        with self.assertRaises(self.api.LaunchError) as caught:
            self.launch(**kwargs)
        self.assertNotIn(SECRET, str(caught.exception))
        return caught.exception

    def test_l1_l3_fresh_launch_validates_identity_then_submits_exact_compact_prompt(self):
        receipt = self.launch()
        self.assertEqual(receipt['phase'], 'submitted')
        self.assertEqual(receipt['thread_id'], 'fresh-thread-113')
        self.assertEqual(receipt['turn_id'], 'turn-113')
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 1)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)
        methods = [call[1] for call in self.runtime.calls if call[0] == 'rpc']
        for method in ('thread/loaded/list', 'thread/read', 'config/read'):
            self.assertLess(methods.index(method), methods.index('turn/start'))
        params = next(call[2] for call in self.runtime.calls
                      if call[:2] == ('rpc', 'turn/start'))
        prompt = '\n'.join(item['text'] for item in params['input'] if item['type'] == 'text')
        self.assertTrue(prompt.startswith('$start-ticket ' + self.request['ticket_url']))
        for key in ('worktree', 'branch', 'head', 'handoff', 'handoff_sha256', 'plan',
                    'plan_sha256', 'config', 'skill', 'phase', 'last_pass', 'next_action',
                    'first_read'):
            self.assertIn(self.request[key], prompt, key)
        self.assertNotIn(SECRET, prompt)
        self.assertLess(len(prompt.encode()), 8192)
        self.assertNotIn(SECRET, json.dumps(receipt))
        self.assertEqual((self.repo / 'product').read_text(), 'preserved local work\n')

    def test_l1_l2_argv_are_literal_no_shell_no_prompt_and_explicit_permissions(self):
        self.launch()
        calls = [call for call in self.runtime.calls if call[0] == 'spawn']
        server = next(call[2] for call in calls if call[1] == 'server')
        terminal = next(call[2] for call in calls if call[1] == 'terminal')
        self.assertIn('app-server', server)
        self.assertEqual(terminal[0], 'gnome-terminal')
        self.assertIn('--remote', terminal)
        self.assertIn('--wait', terminal)
        self.assertIn('gpt-6.1-sol', ' '.join(server + terminal))
        self.assertIn('high', ' '.join(server + terminal))
        for value in ('never', 'danger-full-access'):
            self.assertIn(value, ' '.join(server + terminal))
        for call in calls:
            self.assertEqual(call[3], self.request['worktree'])
            for forbidden in ('sh', 'bash', '--dangerously-bypass-approvals-and-sandbox',
                              '--yolo', 'resume', 'fork'):
                self.assertNotIn(forbidden, call[2])
            self.assertFalse(any('$start-ticket' in arg or SECRET in arg for arg in call[2]))
            self.assertFalse(any('trusted_hash' in arg for arg in call[2]))

    def test_l2_missing_unknown_or_unrepresentable_permissions_block_before_effect(self):
        variants = [None, {}, {'approval_policy': 'sometimes', 'sandbox_mode': 'read-only'},
                    {'approval_policy': 'never', 'sandbox_mode': 'unknown'},
                    dict(self.request['parent_permissions'], profile='custom-profile'),
                    dict(self.request['parent_permissions'], writable_roots=['/outside']),
                    dict(self.request['parent_permissions'], extra_permission=True)]
        for permissions in variants:
            with self.subTest(permissions=permissions):
                self.request['parent_permissions'] = permissions
                self.blocked()
                self.assertEqual(self.runtime.count('spawn'), 0)

    def test_l2_effective_permission_or_model_mismatch_never_submits(self):
        for key, value in [('approval_policy', 'on-request'), ('sandbox_mode', 'read-only'),
                           ('model', 'other'), ('model_reasoning_effort', 'low')]:
            with self.subTest(key=key):
                original = self.runtime.config[key]
                self.runtime.config[key] = value
                self.blocked()
                self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0)
                self.runtime.config[key] = original
                # Each mismatch has its own disposable transition, never retry an unknown one.
                self.request['transition_id'] += '-next'
                self.request['state'] = str(self.local / (self.request['transition_id'] + '.json'))

    def test_l2_no_ownership_transfer_without_explicit_old_writer_stop(self):
        self.request['writers_stopped'] = False
        self.blocked()
        self.assertEqual(self.runtime.count('spawn'), 0)

    def test_l3_hash_git_skill_and_checkpoint_failures_have_no_runtime_effect(self):
        mutations = [('handoff_sha256', '0' * 64), ('plan_sha256', 'f' * 64),
                     ('head', 'a' * 40), ('branch', 'main'),
                     ('skill', str(self.local / 'missing-skill')),
                     ('worktree', str(self.repo / 'missing'))]
        for key, value in mutations:
            old = self.request[key]
            with self.subTest(key=key):
                self.request[key] = value
                self.blocked()
                self.assertEqual(self.runtime.count('spawn'), 0)
            self.request[key] = old
        handoff = Path(self.request['handoff'])
        handoff.write_text('# malformed ' + SECRET)
        self.request['handoff_sha256'] = hashlib.sha256(handoff.read_bytes()).hexdigest()
        self.blocked()
        self.assertEqual(self.runtime.count('spawn'), 0)

    def test_l2_supported_restricted_snapshot_is_applied_without_widening(self):
        self.request['parent_permissions'].update(
            approval_policy='on-request', sandbox_mode='read-only')
        self.runtime.config.update(approval_policy='on-request', sandbox_mode='read-only')
        self.launch()
        argv = ' '.join(arg for call in self.runtime.calls if call[0] == 'spawn'
                        for arg in call[2])
        self.assertIn('on-request', argv)
        self.assertIn('read-only', argv)
        self.assertNotIn('danger-full-access', argv)

    def test_l3_same_transition_cannot_be_rebound_to_changed_request(self):
        self.launch()
        count = len(self.runtime.calls)
        self.request['next_action'] = 'Une autre action non approuvée.'
        self.blocked()
        self.assertEqual(len(self.runtime.calls), count)

    def test_l4_failed_atomic_intent_write_prevents_all_runtime_effects(self):
        with mock.patch.object(self.api.os, 'replace', side_effect=OSError('disk full')):
            self.blocked()
        self.assertEqual(self.runtime.count('spawn'), 0)
        path = Path(self.request['state'])
        if path.exists():
            self.assertIsInstance(json.loads(path.read_text()), dict)

    def test_l4_private_ignored_atomic_state_and_corruption_fail_closed(self):
        self.launch()
        path = Path(self.request['state'])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(self.git('check-ignore', str(path)), str(path))
        self.assertNotIn(SECRET, path.read_text())
        self.assertFalse(list(path.parent.glob('*.tmp*')))
        count = len(self.runtime.calls)
        path.write_text('{invalid ' + SECRET)
        self.blocked()
        self.assertEqual(len(self.runtime.calls), count)

    def test_l4_nonignored_or_symlink_state_refused_without_external_writes(self):
        external = self.root / 'outside.json'
        external.write_text('preserve')
        Path(self.request['state']).parent.mkdir(mode=0o700)
        Path(self.request['state']).symlink_to(external)
        self.blocked()
        self.assertEqual(external.read_text(), 'preserve')
        self.request['state'] = str(self.repo / 'tracked-state.json')
        self.blocked()
        self.assertEqual(self.runtime.count('spawn'), 0)

    def test_l4_exclusive_lock_blocks_concurrent_launch(self):
        self.runtime.entered = threading.Event()
        self.runtime.release = threading.Event()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.launch)
            self.assertTrue(self.runtime.entered.wait(5))
            try:
                self.blocked()
            finally:
                self.runtime.release.set()
            self.assertEqual(future.result(timeout=5)['phase'], 'submitted')
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)

    def test_l5_repeat_returns_same_receipt_without_terminal_thread_or_prompt(self):
        first = self.launch()
        counts = (self.runtime.count('spawn'), self.runtime.count('rpc', 'turn/start'))
        second = self.launch()
        self.assertEqual(first['thread_id'], second['thread_id'])
        self.assertEqual(first['turn_id'], second['turn_id'])
        self.assertEqual(counts, (self.runtime.count('spawn'),
                                  self.runtime.count('rpc', 'turn/start')))

    def test_l5_durable_submitting_unknown_result_never_retries(self):
        self.runtime.fail = 'turn/start'
        self.blocked()
        self.assertEqual(self.runtime.state()['phase'], 'submitting')
        self.runtime.fail = None
        self.blocked()
        self.blocked()
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 1)

    def test_l5_lost_response_requires_positive_same_thread_nonce_and_turn(self):
        self.runtime.fail = 'turn/start'
        self.blocked()
        state = self.runtime.state()
        self.runtime.fail = None
        for evidence in (None, {'thread_id': 'foreign', 'turn_id': 'turn-113',
                                'nonce': state['nonce']},
                         {'thread_id': state['thread_id'], 'turn_id': 'turn-113',
                          'nonce': 'foreign'},
                         {'thread_id': state['thread_id'], 'nonce': state['nonce']}):
            self.runtime.evidence = evidence
            self.blocked()
        self.runtime.evidence = {'thread_id': state['thread_id'], 'turn_id': 'turn-113',
                                 'nonce': state['nonce']}
        self.assertEqual(self.launch()['turn_id'], 'turn-113')
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)

    def test_l5_presubmit_recovery_requires_confirmed_owned_process_stop(self):
        self.runtime.fail = 'thread/read'
        self.blocked()
        self.runtime.fail = None
        self.runtime.stop_confirmed = False
        self.blocked()
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0)
        self.runtime.stop_confirmed = True
        self.assertEqual(self.launch()['phase'], 'submitted')
        self.assertEqual(self.runtime.count('spawn', 'server'), 2)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)

    def test_l5_recovery_is_bounded_before_submission(self):
        self.runtime.fail = 'thread/read'
        self.blocked()
        self.blocked()
        self.assertEqual(self.runtime.count('spawn', 'server'), 2)
        self.blocked()
        self.assertEqual(self.runtime.count('spawn', 'server'), 2)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0)

    def test_l5_reused_pid_does_not_authorize_kill_or_recovery(self):
        self.runtime.fail = 'thread/read'
        self.blocked()
        self.runtime.fail = None
        identity = self.runtime.state()['server']
        self.runtime.processes[identity['pid']] = dict(identity, starttime='foreign-reused')
        self.blocked()
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)
        self.assertEqual(self.runtime.count('stop'), 0)

    def test_l5_reconnect_same_materialized_thread_has_no_second_prompt(self):
        self.launch()
        terminal = self.runtime.state()['terminal']
        del self.runtime.processes[terminal['pid']]
        receipt = self.launch(reconnect=True)
        self.assertEqual(receipt['thread_id'], 'fresh-thread-113')
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 2)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)
        argv = [call[2] for call in self.runtime.calls if call[:2] == ('spawn', 'terminal')][-1]
        self.assertIn('fresh-thread-113', argv)

    def test_l6_terminal_rpc_failure_and_interrupt_remain_explicit_and_safe(self):
        self.runtime.fail = 'terminal'
        self.blocked()
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0)
        self.assertNotIn(SECRET, Path(self.request['state']).read_text())

    def test_l6_interrupt_after_identification_retains_recoverable_intent(self):
        rpc = self.runtime.rpc

        def interrupted(endpoint, method, params):
            if method == 'config/read':
                raise KeyboardInterrupt()
            return rpc(endpoint, method, params)

        self.runtime.rpc = interrupted
        try:
            self.launch()
        except (KeyboardInterrupt, self.api.LaunchError):
            pass
        else:
            self.fail('Interruption must not report a successful launch')
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0)
        self.assertEqual(self.runtime.state()['thread_id'], 'fresh-thread-113')
        self.runtime.rpc = rpc
        self.assertEqual(self.launch()['phase'], 'submitted')
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)

    def test_l6_unqualified_runtime_version_blocks_before_spawn(self):
        self.runtime.probe = lambda: {'platform': 'linux', 'terminal': 'gnome-terminal',
                                     'codex': '0.168.0'}
        self.blocked()
        self.assertEqual(self.runtime.count('spawn'), 0)

    def test_l6_cli_is_opt_in_and_missing_permissions_fail_without_process(self):
        request_path = self.local / 'request.json'
        del self.request['parent_permissions']
        request_path.write_text(json.dumps(self.request))
        result = subprocess.run([sys.executable, str(SCRIPT), '--request', str(request_path)],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((result.stdout + result.stderr).strip())
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        self.assertLess(len(result.stdout + result.stderr), 4096)
        self.assertFalse(Path(self.request['state']).exists())


class DistributionTests(unittest.TestCase):
    def test_l7_skill_accepts_targeted_checkpoint_and_preserves_valid_prepare(self):
        text = (SOURCE / 'skills/start-ticket/SKILL.md').read_text()
        for reference in ('agentic-context-launch.py', 'handoff', 'SHA', 'prochaine action'):
            self.assertIn(reference, text)
        self.assertRegex(text, r'(?i)reprise ciblée')
        self.assertRegex(text, r'(?i)réutiliser.{0,100}préparation')

    def test_l7_installer_distributes_and_checker_requires_launcher(self):
        with tempfile.TemporaryDirectory(prefix='distribution-launch-113-') as tmp:
            root = Path(tmp)
            target = root / 'target'
            target.mkdir()
            subprocess.run(['git', 'init', '-q', str(target)], check=True)
            codex_home = root / 'codex-home'
            codex_home.mkdir()
            result = subprocess.run(['bash', str(SOURCE / 'install-agentic.sh'),
                                     '--local', str(target)], capture_output=True, text=True,
                                    env=dict(os.environ, CODEX_HOME=str(codex_home)), timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target / '.agentic-local'
            launcher = installed / 'scripts/agentic-context-launch.py'
            self.assertTrue(launcher.is_file(), 'L7: le lanceur doit être distribué')
            self.assertEqual(launcher.read_bytes(), SCRIPT.read_bytes())
            check = ['bash', 'scripts/agentic-check.sh', '--existing']
            self.assertEqual(subprocess.run(check, cwd=installed, capture_output=True).returncode, 0)
            launcher.unlink()
            self.assertNotEqual(subprocess.run(check, cwd=installed,
                                               capture_output=True).returncode, 0)


class ReviewRegressionTests(unittest.TestCase):
    """Independent-review M1/M2/m1 regressions; original 25 tests stay unchanged."""
    setUpClass = classmethod(LaunchTests.setUpClass.__func__)
    setUp = LaunchTests.setUp
    git = LaunchTests.git
    launch = LaunchTests.launch
    blocked = LaunchTests.blocked

    def _unidentified_reconnect(self, fault):
        self.launch()
        old_terminal = self.runtime.state()['terminal']
        del self.runtime.processes[old_terminal['pid']]
        spawn = self.runtime.spawn
        spawned = []

        def interrupted_spawn(*args):
            identity = spawn(*args)
            spawned.append(identity)
            if fault == 'crash':
                raise KeyboardInterrupt()
            return identity

        def fail_after_spawn(original):
            def operation(*args, **kwargs):
                if spawned:
                    raise OSError('durability failure after terminal creation')
                return original(*args, **kwargs)
            return operation

        self.runtime.spawn = interrupted_spawn
        with mock.patch.object(self.api.os, 'replace', fail_after_spawn(self.api.os.replace)
                               if fault == 'replace' else self.api.os.replace), \
             mock.patch.object(self.api.os, 'fsync', fail_after_spawn(self.api.os.fsync)
                               if fault == 'fsync' else self.api.os.fsync):
            with self.assertRaises((KeyboardInterrupt, self.api.LaunchError)):
                self.launch(reconnect=True)
        self.runtime.spawn = spawn
        self.assertEqual(len(spawned), 1, 'Fault must occur after an actual boundary creation')
        self.assertTrue(self.runtime.alive(spawned[0]))
        self.assertEqual(self.runtime.state()['phase'], 'reconnecting')
        for reconnect in (False, True, True):
            with self.subTest(retry_reconnect=reconnect):
                self.blocked(reconnect=reconnect)
                self.assertEqual(self.runtime.count('spawn', 'terminal'), 2)
                self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)

    def test_m1_crash_after_reconnect_spawn_never_recreates_unknown_terminal(self):
        self._unidentified_reconnect('crash')

    def test_m1_replace_failure_after_reconnect_spawn_blocks_all_retries(self):
        self._unidentified_reconnect('replace')

    def test_m1_fsync_failure_after_reconnect_spawn_blocks_all_retries(self):
        self._unidentified_reconnect('fsync')

    def test_m2_same_transition_different_state_path_cannot_launch_twice(self):
        self.launch()
        original_state = Path(self.request['state']).read_bytes()
        self.request['state'] = str(self.local / 'launch/alternate.json')
        self.blocked()
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 1)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)
        self.assertEqual((self.local / 'launch/transition.json').read_bytes(), original_state)

    def test_m2_same_transition_concurrent_different_state_paths_has_one_owner(self):
        self.runtime.entered = threading.Event()
        self.runtime.release = threading.Event()
        alternate = dict(self.request, state=str(self.local / 'launch/alternate.json'))
        other = RuntimeBoundary(alternate)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.launch)
            self.assertTrue(self.runtime.entered.wait(5))
            try:
                with self.assertRaises(self.api.LaunchError):
                    self.api.launch(alternate, backend=other)
                self.assertEqual(other.count('spawn'), 0)
                self.assertEqual(other.count('rpc'), 0)
            finally:
                self.runtime.release.set()
            self.assertEqual(future.result(timeout=5)['phase'], 'submitted')

    def test_m2_server_must_be_initially_empty_before_terminal_creation(self):
        rpc = self.runtime.rpc
        observations = []

        def observed(endpoint, method, params):
            if method == 'thread/loaded/list':
                observations.append(self.runtime.count('spawn', 'terminal'))
            return rpc(endpoint, method, params)

        self.runtime.rpc = observed
        self.launch()
        self.assertTrue(observations)
        self.assertEqual(observations[0], 0,
                         'includeTurns:false on an existing thread cannot prove freshness')

    def test_m2_historical_loaded_thread_blocks_before_terminal_and_prompt(self):
        rpc = self.runtime.rpc

        def historical(endpoint, method, params):
            if method == 'thread/loaded/list':
                self.runtime.calls.append(('rpc', method, copy.deepcopy(params)))
                # The existing metadata-only read still returns turns=[]; that is no proof.
                return {'data': ['fresh-thread-113']}
            return rpc(endpoint, method, params)

        self.runtime.rpc = historical
        self.blocked()
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 0)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0)

    def test_m2_real_backend_refuses_preexisting_unix_endpoint_before_process(self):
        backend = self.api.RealBackend()
        directory = self.root / 'endpoint'
        directory.mkdir(mode=0o700)
        endpoint = directory / 'app.sock'
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(endpoint))
            listener.listen(1)
            with mock.patch.object(self.api.subprocess, 'Popen') as popen:
                with self.assertRaises(self.api.LaunchError):
                    backend.spawn('server', self.api.server_argv(
                        str(endpoint), {'approval_policy': 'never',
                                        'sandbox_mode': 'danger-full-access'}),
                        str(self.repo), self.request['state'])
                popen.assert_not_called()
        self.assertTrue(endpoint.is_socket(), 'Do not unlink or claim the foreign endpoint')

    def test_m2_dead_real_server_owner_blocks_before_rpc_or_terminal(self):
        backend = self.api.RealBackend()
        spawn = self.runtime.spawn
        alive = self.runtime.alive
        identities = []

        def dead_server(kind, argv, cwd, state_path):
            if kind != 'server':
                return spawn(kind, argv, cwd, state_path)
            # A real process boundary which exits without ever owning an RPC endpoint.
            identity = backend.spawn(kind, [sys.executable, '-c', 'import time; time.sleep(.1)',
                                            '--listen', 'unix://' + str(
                                                self.root / 'dead-server/app.sock')],
                                     cwd, state_path)
            identities.append(identity)
            backend.children[identity['pid']].wait(timeout=5)
            return identity

        self.runtime.spawn = dead_server
        self.runtime.alive = lambda identity: (backend.alive(identity) if identity in identities
                                                else alive(identity))
        self.blocked()
        self.assertEqual(len(identities), 1)
        self.assertFalse(backend.alive(identities[0]))
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 0)
        self.assertEqual(self.runtime.count('rpc'), 0,
                         'Do not connect a residual endpoint after the recorded server died')

    def test_m1_real_terminal_client_exit_alone_does_not_prove_tui_stopped(self):
        backend = self.api.RealBackend()
        marker = self.local / 'owned-descendant.pid'
        # Simulate gnome client/server separation with owned disposable Python processes.
        program = ('import pathlib,subprocess,sys,time; '
                   'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],'
                   'start_new_session=True); '
                   'pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)')
        identity = backend.spawn('terminal', [sys.executable, '-c', program, str(marker)],
                                 str(self.repo), self.request['state'])
        process = backend.children[identity['pid']]
        child_fd = None
        try:
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(marker.exists())
            child_pid = int(marker.read_text())
            child_fd = os.pidfd_open(child_pid)
            confirmed = backend.stop(identity)
            letter, _ = self.api._starttime(child_pid)
            descendant_running = letter is not None and letter not in ('Z', 'X')
            self.assertFalse(confirmed and descendant_running,
                             'A stopped --wait client cannot certify a surviving TUI stopped')
        finally:
            if child_fd is not None:
                try:
                    signal.pidfd_send_signal(child_fd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stopped, _, _ = select.select([child_fd], [], [], 5)
                os.close(child_fd)
                self.assertTrue(stopped, 'Owned dummy descendant cleanup must be confirmed')
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

    def test_minor_m1_missing_null_and_malformed_handoff_hash_fail_before_spawn(self):
        for variant in ('missing', None, '', 'not-a-sha256', 'a' * 63, 123):
            with self.subTest(hash=variant):
                self.setUp()  # Independent input validation, not a changed-request replay.
                if variant == 'missing':
                    self.request.pop('handoff_sha256', None)
                else:
                    self.request['handoff_sha256'] = variant
                self.blocked()
                self.assertEqual(self.runtime.count('spawn'), 0)

    def test_minor_m1_cli_missing_handoff_hash_is_bounded_without_traceback(self):
        self.request.pop('handoff_sha256')
        request_path = self.local / 'request.json'
        request_path.write_text(json.dumps(self.request))
        # Exercise the real CLI parser/error handler in a child interpreter, replacing only
        # its runtime boundary so a malformed request cannot launch Codex during this test.
        entrypoint = ('import json,sys; from pathlib import Path; '
                      'sys.path.insert(0,sys.argv.pop(1)); '
                      'from test_context_launch import load_api,RuntimeBoundary; '
                      'api=load_api(); request=json.loads(Path(sys.argv[2]).read_text()); '
                      'api.RealBackend=lambda:RuntimeBoundary(request); '
                      'sys.exit(api.main(sys.argv[1:]))')
        result = subprocess.run([sys.executable, '-c', entrypoint, str(SOURCE / 'tests'),
                                 '--request', str(request_path)],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stdout + result.stderr)
        self.assertLess(len(result.stdout + result.stderr), 4096)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        self.assertFalse(Path(self.request['state']).exists())


class RecoveryOwnershipTests(unittest.TestCase):
    """M3 and lifecycle review: a stopped parent cannot authorize unknown descendants."""
    setUpClass = classmethod(LaunchTests.setUpClass.__func__)
    setUp = LaunchTests.setUp
    git = LaunchTests.git
    launch = LaunchTests.launch
    blocked = LaunchTests.blocked

    def test_m3_known_old_thread_on_recovery_server_blocks_before_new_terminal(self):
        self.runtime.fail = 'config/read'
        self.blocked()
        self.assertEqual(self.runtime.state()['thread_id'], 'fresh-thread-113')
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0)
        self.runtime.fail = None
        rpc = self.runtime.rpc

        def stale_thread(endpoint, method, params):
            if (method == 'thread/loaded/list' and self.runtime.count('spawn', 'server') == 2
                    and not self.runtime.state().get('terminal')):
                self.runtime.calls.append(('rpc', method, copy.deepcopy(params)))
                return {'data': ['fresh-thread-113']}
            return rpc(endpoint, method, params)

        self.runtime.rpc = stale_thread
        self.blocked()
        self.assertEqual(self.runtime.count('spawn', 'server'), 2)
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 1)
        self.assertEqual(self.runtime.count('rpc', 'turn/start'), 0,
                         'A thread known to this transition is still historical')

    def _dead_parent_family(self, tagged):
        backend = self.api.RealBackend()
        marker_file = self.local / 'owned-family.json'
        command_marker = 'unix://' + str(self.local / 'owned-tui.sock')
        child_program = (
            'import json,os,pathlib,subprocess,sys,time; '
            'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],'
            'start_new_session=True); '
            'pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),p.pid])); '
            'time.sleep(30)')
        child_argv = [sys.executable, '-c', child_program, str(marker_file)]
        if tagged:
            child_argv += ['--remote', command_marker]
        parent_program = (
            'import json,pathlib,subprocess,sys,time; '
            'subprocess.Popen(json.loads(sys.argv[1]),start_new_session=True); '
            'marker=pathlib.Path(sys.argv[2]); '
            '\nwhile not marker.exists(): time.sleep(.01)\n')
        argv = [sys.executable, '-c', parent_program, json.dumps(child_argv), str(marker_file)]
        if tagged:
            argv += ['--remote', command_marker]
        identity = backend.spawn('terminal', argv, str(self.repo), self.request['state'])
        process = backend.children[identity['pid']]
        pinned = []
        try:
            process.wait(timeout=5)  # Parent is reaped BEFORE ownership/recovery decisions.
            self.assertTrue(marker_file.is_file())
            for pid in json.loads(marker_file.read_text()):
                letter, start = self.api._starttime(pid)
                self.assertNotIn(letter, (None, 'Z', 'X'))
                fd = os.pidfd_open(pid)
                pinned.append((pid, start, fd))
                self.assertEqual(self.api._starttime(pid)[1], start)
            transition = self.api._Transition(Path(self.request['state']), {
                'phase': 'identified', 'terminal': identity, 'server': None})
            try:
                self.api._stop_owned(backend, transition)
            except self.api.LaunchError:
                return  # Honest refusal is a valid alternative to proven complete stopping.
            for pid, _, fd in pinned:
                exited, _, _ = select.select([fd], [], [], 0)
                self.assertTrue(exited,
                                f'Recovery was permitted while owned descendant {pid} lives')
        finally:
            # PID reuse cannot redirect cleanup: only pinned, test-created processes are signalled.
            for _, _, fd in pinned:
                try:
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for _, _, fd in pinned:
                exited, _, _ = select.select([fd], [], [], 5)
                os.close(fd)
                self.assertTrue(exited, 'Owned family cleanup must be confirmed')
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

    def test_lifecycle_dead_parent_unmarked_detached_children_cannot_authorize_recovery(self):
        self._dead_parent_family(tagged=False)

    def test_lifecycle_marker_tui_descendants_cannot_be_missed_after_client_exit(self):
        self._dead_parent_family(tagged=True)


class UncertainFamilyTests(unittest.TestCase):
    """M4: unavailable discovery or lost lineage cannot certify family closure.

    Only /proc filesystem observations are replaced. RealBackend and _stop_owned
    make the recovery decision; no process, socket, runtime launch or signal exists.
    """
    setUpClass = classmethod(LaunchTests.setUpClass.__func__)
    setUp = LaunchTests.setUp
    git = LaunchTests.git

    def _unknown_family_blocks_recovery(self, environment_denied, parent_denied=False):
        backend = self.api.RealBackend()
        parent, child = 770000, 770001
        identity = {'pid': parent, 'starttime': '991', 'owner_token': 'fixture-owner-113'}
        transition = self.api._Transition(Path(self.request['state']), {
            'phase': 'identified', 'terminal': identity, 'server': None})
        original_text = Path.read_text
        original_bytes = Path.read_bytes
        original_listdir = os.listdir
        original_stat = os.stat
        same_owner = original_stat(self.local)
        # The formerly owned child is alive but already reparented, with no remaining
        # ancestry link to the lost client. An inherited environment is not a closed set.
        child_stat = f'{child} (fixture child) ' + ' '.join(
            ['S', '1'] + ['0'] * 17 + ['992'])

        def read_text(path, *args, **kwargs):
            if str(path) == f'/proc/{parent}/stat':
                if parent_denied:
                    raise PermissionError(errno.EACCES, 'fixture parent stat unavailable')
                raise FileNotFoundError(errno.ENOENT, 'fixture parent disappeared')
            if str(path) == f'/proc/{child}/stat':
                return child_stat
            return original_text(path, *args, **kwargs)

        def read_bytes(path, *args, **kwargs):
            if str(path) == f'/proc/{child}/environ':
                if environment_denied:
                    raise PermissionError(errno.EACCES, 'fixture environment unavailable')
                return b'PATH=/fixture\0'  # Child exec filtered its inherited ownership tag.
            if str(path) == f'/proc/{child}/cmdline':
                return b'python\0fixture-worker\0'
            return original_bytes(path, *args, **kwargs)

        def listdir(path):
            return [str(child)] if str(path) == '/proc' else original_listdir(path)

        def proc_stat(path, *args, **kwargs):
            if str(path) == f'/proc/{child}':
                return same_owner
            return original_stat(path, *args, **kwargs)

        with mock.patch.object(Path, 'read_text', read_text), \
             mock.patch.object(Path, 'read_bytes', read_bytes), \
             mock.patch.object(self.api.os, 'listdir', listdir), \
             mock.patch.object(self.api.os, 'stat', proc_stat), \
             mock.patch.object(self.api.os, 'pidfd_open',
                               side_effect=AssertionError('Synthetic PID must never be signalled')), \
             mock.patch.object(backend, 'spawn') as spawn, \
             mock.patch.object(backend, 'rpc') as rpc:
            with self.assertRaises(self.api.LaunchError):
                self.api._stop_owned(backend, transition)
            spawn.assert_not_called()
            rpc.assert_not_called()

    def test_m4_parent_missing_live_descendant_environ_eacces_blocks_recovery(self):
        self._unknown_family_blocks_recovery(environment_denied=True)

    def test_m4_filtered_environment_and_reparenting_do_not_prove_family_closed(self):
        self._unknown_family_blocks_recovery(environment_denied=False)

    def test_m4_unreadable_parent_stat_is_not_proven_parent_absence(self):
        self._unknown_family_blocks_recovery(environment_denied=True, parent_denied=True)


class ZombieFamilyTests(unittest.TestCase):
    """A zombie client and a negative scan still leave a filtered orphan unaccounted for."""
    setUpClass = classmethod(LaunchTests.setUpClass.__func__)
    setUp = LaunchTests.setUp
    git = LaunchTests.git

    def _zombie_family_cannot_authorize_recovery(self, scan_stop_first):
        backend = self.api.RealBackend()
        parent, child = 780000, 780001
        identity = {'pid': parent, 'starttime': '1000', 'owner_token': 'zombie-family-113'}
        transition = self.api._Transition(Path(self.request['state']), {
            'phase': 'identified', 'terminal': identity, 'server': None})
        original_text, original_bytes = Path.read_text, Path.read_bytes
        original_listdir, original_stat = os.listdir, os.stat
        same_owner = original_stat(self.local)
        observations = {
            f'/proc/{parent}/stat': f'{parent} (fixture zombie) ' + ' '.join(
                ['Z', '1'] + ['0'] * 17 + ['1000']),
            f'/proc/{child}/stat': f'{child} (fixture orphan) ' + ' '.join(
                ['S', '1'] + ['0'] * 17 + ['1001']),
        }

        def read_text(path, *args, **kwargs):
            if str(path) in observations:
                return observations[str(path)]
            return original_text(path, *args, **kwargs)

        def read_bytes(path, *args, **kwargs):
            if str(path) == f'/proc/{child}/environ':
                return b'PATH=/fixture\0'  # Live descendant filtered the inherited token.
            if str(path) == f'/proc/{child}/cmdline':
                return b'python\0reparented-worker\0'
            return original_bytes(path, *args, **kwargs)

        def listdir(path):
            return [str(parent), str(child)] if str(path) == '/proc' else original_listdir(path)

        def proc_stat(path, *args, **kwargs):
            if str(path) in (f'/proc/{parent}', f'/proc/{child}'):
                return same_owner
            return original_stat(path, *args, **kwargs)

        with mock.patch.object(Path, 'read_text', read_text), \
             mock.patch.object(Path, 'read_bytes', read_bytes), \
             mock.patch.object(self.api.os, 'listdir', listdir), \
             mock.patch.object(self.api.os, 'stat', proc_stat), \
             mock.patch.object(self.api.os, 'pidfd_open',
                               side_effect=AssertionError('Synthetic PID must never be signalled')), \
             mock.patch.object(self.api.signal, 'pidfd_send_signal',
                               side_effect=AssertionError('No synthetic process may be signalled')), \
             mock.patch.object(backend, 'spawn') as spawn, \
             mock.patch.object(backend, 'rpc') as rpc:
            if scan_stop_first:
                try:
                    backend.stop(identity)  # Real stop must not manufacture family closure.
                except self.api.LaunchError:
                    pass  # A conservative refusal of best-effort stopping is allowed too.
            with self.assertRaises(self.api.LaunchError):
                self.api._stop_owned(backend, transition)
            spawn.assert_not_called()
            rpc.assert_not_called()

    def test_zombie_exact_starttime_does_not_prove_filtered_orphan_stopped(self):
        self._zombie_family_cannot_authorize_recovery(scan_stop_first=False)

    def test_negative_stop_scan_cannot_certify_zombie_family_closed(self):
        self._zombie_family_cannot_authorize_recovery(scan_stop_first=True)


class UnidentifiedCreationTests(unittest.TestCase):
    """M5: successful Popen without a reliable identity remains durably uncertain."""
    setUpClass = classmethod(LaunchTests.setUpClass.__func__)
    setUp = LaunchTests.setUp
    git = LaunchTests.git

    def _creation_cannot_repeat(self, reconnect, unreadable):
        if reconnect:
            self.api.launch(self.request, backend=self.runtime)
            server = self.runtime.state()['server']
        else:
            server = None
        runtime_dir = tempfile.TemporaryDirectory(prefix='m5-', dir='/tmp')
        self.addCleanup(runtime_dir.cleanup)
        original_popen = subprocess.Popen
        original_text, original_listdir = Path.read_text, os.listdir
        successful_creations = []
        unknown_pid = 790000

        def popen(argv, *args, **kwargs):
            if argv[0] not in ('codex', 'gnome-terminal'):
                return original_popen(argv, *args, **kwargs)  # Disposable fixture Git only.
            successful_creations.append(list(argv))
            return mock.Mock(pid=unknown_pid + len(successful_creations) - 1,
                             poll=mock.Mock(return_value=None))

        def read_text(path, *args, **kwargs):
            if str(path) in {f'/proc/{unknown_pid + i}/stat'
                             for i in range(len(successful_creations))}:
                if unreadable:
                    raise PermissionError(errno.EACCES, 'post-creation identity unreadable')
                raise FileNotFoundError(errno.ENOENT, 'post-creation identity unknown')
            if server and str(path) == f'/proc/{server["pid"]}/stat':
                return f'{server["pid"]} (owned server) ' + ' '.join(
                    ['S', '1'] + ['0'] * 17 + [server['starttime']])
            return original_text(path, *args, **kwargs)

        def listdir(path):
            if str(path) == '/proc':
                return [str(server['pid'])] if server else []
            return original_listdir(path)

        def assert_blocked(backend, retry_reconnect):
            try:
                self.api.launch(self.request, backend=backend, reconnect=retry_reconnect)
            except AssertionError:
                raise  # Guard failures are never accepted as an operational BLOCKED result.
            except Exception:
                return  # No particular phase spelling or exception class is prescribed.
            self.fail('Unknown post-creation outcome must not report launch success')

        probe = {'platform': 'linux', 'terminal': 'gnome-terminal', 'codex': '0.169.0'}
        with mock.patch.dict(os.environ, XDG_RUNTIME_DIR=runtime_dir.name), \
             mock.patch.object(self.api.RealBackend, 'probe', return_value=probe), \
             mock.patch.object(self.api.subprocess, 'Popen', side_effect=popen), \
             mock.patch.object(Path, 'read_text', read_text), \
             mock.patch.object(self.api.os, 'listdir', listdir), \
             mock.patch.object(self.api.RealBackend, 'rpc',
                               side_effect=AssertionError('No RPC after unidentified creation')), \
             mock.patch.object(self.api.os, 'pidfd_open',
                               side_effect=AssertionError('Synthetic PID must never be pinned')), \
             mock.patch.object(self.api.signal, 'pidfd_send_signal',
                               side_effect=AssertionError('Synthetic PID must never be signalled')):
            backend = self.api.RealBackend()
            assert_blocked(backend, reconnect)
            self.assertEqual(len(successful_creations), 1,
                             'The first failure must follow one successful Popen boundary')
            # A new backend must obey the durable uncertainty too, independently of memory.
            for fresh_backend, retry_reconnect in ((False, reconnect), (True, reconnect),
                                                    (True, False), (True, True)):
                with self.subTest(fresh_backend=fresh_backend, reconnect=retry_reconnect):
                    current = self.api.RealBackend() if fresh_backend else backend
                    assert_blocked(current, retry_reconnect)
                    self.assertEqual(len(successful_creations), 1,
                                     'A successful but unidentified creation cannot be replayed')
        if reconnect:
            self.assertEqual(self.runtime.count('rpc', 'turn/start'), 1)

    def test_m5_fresh_post_popen_unknown_identity_is_not_retryable(self):
        self._creation_cannot_repeat(reconnect=False, unreadable=False)

    def test_m5_fresh_post_popen_unreadable_identity_is_not_retryable(self):
        self._creation_cannot_repeat(reconnect=False, unreadable=True)

    def test_m5_reconnect_post_popen_unknown_identity_is_not_retryable(self):
        self._creation_cannot_repeat(reconnect=True, unreadable=False)

    def test_m5_reconnect_post_popen_unreadable_identity_is_not_retryable(self):
        self._creation_cannot_repeat(reconnect=True, unreadable=True)


class CanonicalPlanPromptTests(unittest.TestCase):
    """M6: public launch distinguishes canonical plan and raw handoff digests."""
    setUpClass = classmethod(LaunchTests.setUpClass.__func__)
    git = LaunchTests.git

    def setUp(self):
        LaunchTests.setUp(self)
        plan_path = Path(self.request['plan'])
        plan = json.loads(plan_path.read_text())
        plan['story'] = 'régression-113-漢字'
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf-8')
        raw = plan_path.read_bytes()
        decoded = json.loads(raw.decode('utf-8'))
        canonical = json.dumps(decoded, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=False).encode('utf-8')
        self.raw_plan_sha256 = hashlib.sha256(raw).hexdigest()
        self.request['plan_sha256'] = hashlib.sha256(canonical).hexdigest()
        # RM-M6a: this fixture must distinguish formatting, key order and Unicode.
        self.assertIn(b'\n  ', raw)
        self.assertNotEqual(list(decoded), sorted(decoded))
        self.assertIn('régression-113-漢字'.encode('utf-8'), raw)
        self.assertNotEqual(raw, canonical)
        self.assertNotEqual(self.raw_plan_sha256, self.request['plan_sha256'])

    def _submitted_prompt(self):
        receipt = self.api.launch(self.request, backend=self.runtime)
        self.assertEqual(receipt['phase'], 'submitted')
        submissions = [call[2] for call in self.runtime.calls
                       if call[:2] == ('rpc', 'turn/start')]
        self.assertEqual(len(submissions), 1)
        return '\n'.join(item['text'] for item in submissions[0]['input']
                         if item['type'] == 'text')

    def test_m6a_m6b_formatted_unsorted_unicode_plan_accepts_canonical_digest(self):
        prompt = self._submitted_prompt()
        self.assertIn(self.request['plan_sha256'], prompt)
        self.assertEqual(self.runtime.count('spawn', 'server'), 1)
        self.assertEqual(self.runtime.count('spawn', 'terminal'), 1)

    def test_m6b_raw_plan_digest_rejected_before_creation_rpc_or_prompt(self):
        self.request['plan_sha256'] = self.raw_plan_sha256
        before = set(self.local.rglob('*'))
        with self.assertRaises(self.api.LaunchError):
            self.api.launch(self.request, backend=self.runtime)
        self.assertEqual(self.runtime.calls, [])
        self.assertEqual(set(self.local.rglob('*')), before)

    def test_m6c_prompt_identifies_canonical_pr_split_and_exact_hash_method(self):
        prompt = self._submitted_prompt()
        self.assertIn(self.request['plan_sha256'], prompt)
        checks = {
            'canonical PR_SPLIT': r'(?is)(?:PR_SPLIT.*canoni|canoni.*PR_SPLIT)',
            'sorted keys': r'(?i)sort_keys\s*=\s*True\b',
            'compact separators': r'''separators\s*=\s*\(\s*['"],['"]\s*,\s*['"]:['"]\s*\)''',
            'literal Unicode': r'(?i)ensure_ascii\s*=\s*False\b',
            'UTF-8 bytes': r'(?i)utf[-_]?8',
            'SHA256': r'(?i)sha[-_ ]?256',
        }
        for meaning, pattern in checks.items():
            with self.subTest(parameter=meaning):
                self.assertRegex(prompt, pattern)

    def test_m6d_prompt_omits_raw_plan_digest(self):
        self.assertNotIn(self.raw_plan_sha256, self._submitted_prompt())

    def test_m6d_prompt_qualifies_handoff_digest_as_raw_bytes(self):
        prompt = self._submitted_prompt()
        handoff_digest = hashlib.sha256(Path(self.request['handoff']).read_bytes()).hexdigest()
        self.assertEqual(self.request['handoff_sha256'], handoff_digest)
        self.assertIn(handoff_digest, prompt)
        handoff_line = next(line for line in prompt.splitlines() if handoff_digest in line)
        # Accept French/English prose or code, without prescribing a label or command.
        self.assertRegex(handoff_line, r'(?i)\bsha[-_ ]?256\b')
        self.assertRegex(handoff_line, r'(?i)\b(?:brut(?:e)?s?|raw)\b')
        self.assertRegex(handoff_line, r'(?i)octets|bytes|read_bytes\s*\(|[\'"]rb[\'"]')

    def test_m6e_canonical_prompt_preserves_compact_safe_resume_markers(self):
        prompt = self._submitted_prompt()
        self.assertTrue(prompt.startswith('$start-ticket ' + self.request['ticket_url']))
        for key in ('worktree', 'branch', 'head', 'handoff', 'handoff_sha256', 'plan',
                    'plan_sha256', 'config', 'skill', 'phase', 'last_pass', 'next_action',
                    'first_read'):
            with self.subTest(marker=key):
                self.assertIn(self.request[key], prompt)
        self.assertIn(self.runtime.state()['nonce'], prompt)
        self.assertLess(len(prompt.encode('utf-8')), 8192)
        self.assertNotIn(SECRET, prompt)


if __name__ == '__main__':
    unittest.main()
