"""Offline native Claude agent discovery; sends initialize, never a user turn."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class NativeDiscoveryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('claude'), 'Claude CLI unavailable; discovery not observed')
    def test_claude_discovers_native_profiles_without_model_request(self):
        binary = shutil.which('claude')
        expected = {'agentic-explorer', 'agentic-implementer', 'agentic-reviewer'}
        for native in (False, True):
            with self.subTest(native=native), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project, home = root / 'project', root / 'home'
                project.mkdir()
                home.mkdir()
                config = home / '.claude'
                config.mkdir()
                # Empty HOME/config and an explicit environment exclude real credentials.
                env = {
                    'PATH': os.environ.get('PATH', os.defpath),
                    'HOME': str(home),
                    'CLAUDE_CONFIG_DIR': str(config),
                    'XDG_CONFIG_HOME': str(home / '.config'),
                    'XDG_CACHE_HOME': str(home / '.cache'),
                    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
                    'DISABLE_AUTOUPDATER': '1',
                    'NO_COLOR': '1',
                    'TERM': 'dumb',
                }
                subprocess.run(['git', 'init', '-q', str(project)], check=True,
                               capture_output=True, env=env, timeout=5)
                folder = project / ('.claude/agents' if native else 'claude/agents')
                folder.mkdir(parents=True)
                for role in ('explorer', 'implementer', 'reviewer'):
                    source = SOURCE / f'claude/agents/{role}.md'
                    (folder / f'agentic-{role}.md').write_bytes(source.read_bytes())
                request = {
                    'type': 'control_request',
                    'request_id': 'native-discovery',
                    'request': {'subtype': 'initialize'},
                }
                # EOF after initialize exits cleanly: no user message, no model turn.
                result = subprocess.run(
                    [binary, '--print', '--input-format', 'stream-json',
                     '--output-format', 'stream-json', '--verbose',
                     '--no-session-persistence', '--strict-mcp-config'],
                    cwd=project, env=env, input=json.dumps(request) + '\n',
                    capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0,
                                 'Offline Claude initialization failed; no output containing account data is printed.')
                messages = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
                replies = [m for m in messages if m.get('type') == 'control_response'
                           and m.get('response', {}).get('request_id') == 'native-discovery']
                self.assertEqual(len(replies), 1, 'Missing initialize response')
                self.assertFalse(any(m.get('type') in ('assistant', 'result') for m in messages),
                                 'Unexpected model-turn output during initialization')
                envelope = replies[0]['response']
                self.assertEqual(envelope.get('subtype'), 'success')
                names = {agent['name'] for agent in envelope['response'].get('agents', [])}
                observed = expected & names
                self.assertEqual(observed, expected if native else set())


if __name__ == '__main__':
    unittest.main()
