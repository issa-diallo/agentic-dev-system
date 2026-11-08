"""Observable panel behavior, with an offline observer and a real pseudo terminal."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/agentic-panel.py'
SPEC = importlib.util.spec_from_file_location('agentic_panel', SCRIPT)
PANEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PANEL)
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def sample():
    return {'source': 'codex-app-server', 'observed_at': '2026-11-08T10:00:00Z',
            'repo': '/project', 'truncated': False, 'agents': [
                {'id': 'one123456789', 'role': 'agentic_explorer', 'nickname': 'chercheur',
                 'status': 'active', 'active_flags': [], 'cwd': '/project', 'parent_id': 'root'},
                {'id': 'two123456789', 'role': 'agentic-implementer', 'nickname': '',
                 'status': 'idle', 'active_flags': [], 'cwd': '/project', 'parent_id': 'root'},
                {'id': 'three123456789', 'role': 'reviewer', 'nickname': 'lecteur',
                 'status': 'notLoaded', 'active_flags': [], 'cwd': '/project', 'parent_id': 'root'}]}


def observer(payload=None, error=None):
    class ObservationError(Exception):
        pass
    module = types.SimpleNamespace(ObservationError=ObservationError)
    module.calls = []
    def snapshot(**kwargs):
        module.calls.append(kwargs)
        if error:
            raise ObservationError(error)
        return copy.deepcopy(payload if payload is not None else sample())
    module.snapshot = snapshot
    return module


class PanelTests(unittest.TestCase):
    def test_rm2_states_have_observed_meanings_without_gate_verdicts(self):
        rendered = PANEL.render(sample(), width=100, height=24)
        self.assertIn('actif', rendered)
        self.assertIn('au repos', rendered)
        self.assertIn('non chargé', rendered)
        self.assertNotIn('terminé', rendered)
        self.assertNotIn('PASS', rendered)

    def test_rm2_approval_input_error_and_unknown_states(self):
        self.assertIn('approbation', PANEL.state_text({'status': 'active', 'active_flags': ['waitingOnApproval']}))
        self.assertIn('réponse', PANEL.state_text({'status': 'active', 'active_flags': ['waitingOnUserInput']}))
        self.assertEqual(PANEL.state_text({'status': 'systemError'}), 'erreur')
        self.assertEqual(PANEL.state_text({'status': 'future-status'}), 'inconnu')
        self.assertEqual(PANEL.state_text({}), 'inconnu')
        self.assertEqual(PANEL.state_text({'status': {'future': 'shape'}}), 'inconnu')

    def test_column_headers_align_with_their_values(self):
        lines = PANEL.render(sample(), width=100, height=24).splitlines()
        self.assertEqual(lines[3].index('ÉTAT'), lines[5].index('actif'))

    def test_rm3_three_roles_receive_distinct_colors(self):
        rendered = PANEL.render(sample(), width=100, height=24, color=True)
        for code in ('\x1b[34m', '\x1b[32m', '\x1b[35m'):
            self.assertIn(code, rendered)
        self.assertEqual(ANSI.sub('', rendered), PANEL.render(sample(), width=100, height=24))

    def test_rm3_unknown_role_is_not_inferred_from_nickname(self):
        data = sample()
        data['agents'] = [dict(data['agents'][0], role='unknown', nickname='reviewer')]
        rendered = PANEL.render(data, color=True)
        self.assertNotIn('\x1b[35m', rendered)
        self.assertIn('unknown', rendered)

    def test_no_color_and_dumb_terminal_disable_automatic_colors(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(PANEL.colors_enabled('auto', True))
            self.assertFalse(PANEL.colors_enabled('auto', False))
        with patch.dict(os.environ, {'NO_COLOR': '', 'TERM': 'xterm'}, clear=True):
            self.assertFalse(PANEL.colors_enabled('auto', True))
            self.assertTrue(PANEL.colors_enabled('always', True))
        with patch.dict(os.environ, {'TERM': 'dumb'}, clear=True):
            self.assertFalse(PANEL.colors_enabled('auto', True))
        self.assertFalse(PANEL.colors_enabled('never', True))

    def test_rm4_untrusted_terminal_sequences_and_conversation_fields_not_rendered(self):
        data = sample()
        data['repo'] = '/project\x1b]0;evil\x07\nnext\u202e'
        data['preview'] = 'PRIVATE_CONVERSATION'
        data['agents'][0].update(role='explorer\x1b[31m', nickname='hello\nworld\t\x1b]52;secret\x07\u202e')
        rendered = PANEL.render(data, width=120, height=24)
        for unsafe in ('\x1b', '\x07', '\t', '\u202e', 'PRIVATE_CONVERSATION'):
            self.assertNotIn(unsafe, rendered)
        self.assertEqual(len(rendered.splitlines()), len(PANEL.render(sample()).splitlines()))

    def test_height_width_and_unicode_are_bounded_with_truncation_notice(self):
        data = sample()
        data['agents'] = [dict(data['agents'][0], nickname='界' * 100) for _ in range(20)]
        data['truncated'] = True
        rendered = PANEL.render(data, width=40, height=8)
        self.assertLessEqual(len(rendered.splitlines()), 8)
        for line in rendered.splitlines():
            width = sum(2 if __import__('unicodedata').east_asian_width(c) in 'WF' else 1
                        for c in line if not __import__('unicodedata').combining(c))
            self.assertLessEqual(width, 40)
        self.assertIn('tronqu', rendered)

    def test_rm5_empty_and_unavailable_are_distinct_and_unavailable_has_no_old_agents(self):
        data = sample()
        data['agents'] = []
        self.assertIn('Aucun sous-agent', PANEL.render(data))
        failed = PANEL.render(sample(), unavailable=True)
        self.assertIn('indisponible', failed)
        self.assertNotIn('chercheur', failed)
        self.assertNotIn('actif', failed)

    def call_main(self, args, backend):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(PANEL, 'load_observer', return_value=backend), \
             patch('sys.stdout', output), patch('sys.stderr', errors):
            result = PANEL.main(args)
        return result, output.getvalue(), errors.getvalue()

    def test_non_tty_defaults_to_one_snapshot_without_terminal_controls(self):
        backend = observer()
        code, out, err = self.call_main([], backend)
        self.assertEqual(code, 0)
        self.assertEqual(len(backend.calls), 1)
        self.assertNotIn('\x1b', out)
        self.assertEqual(err, '')

    def test_json_is_snapshot_only_and_forwards_observation_options(self):
        backend = observer()
        args = ['--json', '--color', 'always', '--repo', '/work', '--socket', '/sock',
                '--timeout', '1.5', '--limit', '7']
        code, out, err = self.call_main(args, backend)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), sample())
        self.assertNotIn('\x1b', out)
        self.assertEqual(backend.calls, [{'repo': '/work', 'socket_path': '/sock', 'timeout': 1.5, 'limit': 7}])
        self.assertEqual(err, '')

    def test_rm4_json_does_not_export_undeclared_conversation_fields(self):
        data = sample()
        data['preview'] = 'PRIVATE_CONVERSATION'
        data['agents'][0]['messages'] = ['PRIVATE_CONVERSATION']
        code, out, err = self.call_main(['--json'], observer(payload=data))
        self.assertEqual(code, 0)
        self.assertNotIn('PRIVATE_CONVERSATION', out + err)
        self.assertEqual(json.loads(out), sample())

    def test_rm5_error_is_redacted_and_json_failure_is_structured(self):
        for args in (['--once'], ['--json']):
            code, out, err = self.call_main(args, observer(error='SECRET_RAW_SERVER_ERROR'))
            self.assertNotEqual(code, 0)
            self.assertIn('indisponible', out.lower())
            self.assertNotIn('SECRET', out + err)
            self.assertNotIn('Traceback', out + err)
            if '--json' in args:
                self.assertIn('error', json.loads(out))

    def test_missing_observer_api_fails_without_traceback(self):
        code, out, err = self.call_main(['--once'], types.SimpleNamespace())
        self.assertEqual(code, 1)
        self.assertIn('indisponible', out)
        self.assertNotIn('Traceback', err)

    def test_argument_validation_rejects_nonfinite_and_unbounded_values(self):
        for args in (['--interval', 'nan'], ['--timeout', 'inf'], ['--interval', '0.1'],
                     ['--timeout', '0'], ['--limit', '0'], ['--limit', '201']):
            with self.subTest(args=args), patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    PANEL.main(args)
                self.assertEqual(caught.exception.code, 2)

    def test_excessive_delays_are_rejected_before_observer_load(self):
        for flag in ('--timeout', '--interval'):
            with self.subTest(flag=flag), patch('sys.stderr', io.StringIO()), \
                    patch.object(PANEL, 'load_observer', side_effect=AssertionError('observer loaded')):
                with self.assertRaises(SystemExit) as caught:
                    PANEL.main([flag, '1e300'])
                self.assertEqual(caught.exception.code, 2)

    def fixture(self, directory):
        root = Path(directory)
        shutil.copy2(SCRIPT, root / SCRIPT.name)
        stub = '''import json, os, time
class ObservationError(Exception): pass
calls = 0
def snapshot(**kwargs):
    global calls
    calls += 1
    if os.environ.get('FAIL_AFTER_FIRST') and calls > 1: raise ObservationError('PRIVATE_FAILURE')
    return json.loads(os.environ['PANEL_SAMPLE'])
'''
        (root / 'agentic-observe.py').write_text(stub)
        return root / SCRIPT.name

    def test_cli_help_without_observer_or_server(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / SCRIPT.name
            shutil.copy2(SCRIPT, target)
            result = subprocess.run([sys.executable, str(target), '--help'], capture_output=True,
                                    text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--once', result.stdout)

    def test_cli_pipe_uses_one_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.fixture(directory)
            result = subprocess.run([sys.executable, str(target), '--json'], capture_output=True,
                                    text=True, timeout=5, env={**os.environ, 'PANEL_SAMPLE': json.dumps(sample())})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), sample())

    @unittest.skipUnless(os.name == 'posix', 'Pseudo terminal requires POSIX')
    def test_live_pty_replaces_stale_rows_and_restores_terminal_on_interrupt(self):
        import pty
        master, slave = pty.openpty()
        with tempfile.TemporaryDirectory() as directory:
            target = self.fixture(directory)
            env = {**os.environ, 'PANEL_SAMPLE': json.dumps(sample()), 'FAIL_AFTER_FIRST': '1', 'TERM': 'xterm'}
            process = subprocess.Popen([sys.executable, str(target), '--interval', '0.2'],
                                       stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            captured = b''
            try:
                deadline = time.monotonic() + 5
                with selectors.DefaultSelector() as selector:
                    selector.register(master, selectors.EVENT_READ)
                    while time.monotonic() < deadline and b'indisponible' not in captured:
                        if selector.select(0.2):
                            captured += os.read(master, 65536)
                self.assertIn(b'indisponible', captured)
                process.send_signal(signal.SIGINT)
                process.wait(timeout=5)
                with selectors.DefaultSelector() as selector:
                    selector.register(master, selectors.EVENT_READ)
                    while selector.select(0.1):
                        try:
                            part = os.read(master, 65536)
                        except OSError:
                            break
                        if not part:
                            break
                        captured += part
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                os.close(master)
        self.assertEqual(process.returncode, 0)
        self.assertIn(b'\x1b[?1049h', captured)
        self.assertIn(b'\x1b[?1049l', captured)
        self.assertIn(b'\x1b[?25h', captured)
        self.assertNotIn(b'PRIVATE_FAILURE', captured)
        error_frame = captured.split(b'\x1b[2J')[-1]
        self.assertNotIn(b'chercheur', error_frame)


if __name__ == '__main__':
    unittest.main()
