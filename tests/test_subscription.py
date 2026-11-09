"""Subscription-only: launch only official CLIs logged in with a subscription, never an API."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('subscription_run', SOURCE / 'scripts/agentic-run.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)

# Fake CLI: answers login probes from the `login` file; anything else is an inference
# call, recorded with its environment and answered from the `run` file.
FAKE = '''#!{python}
import json, os, sys
from pathlib import Path
root, name, args = Path(__file__).parent, Path(__file__).name, sys.argv[1:]
login = (root / 'login').read_text()
if args[:2] in (['auth', 'status'], ['login', 'status']):
    with (root / 'probes').open('a') as stream:
        stream.write(json.dumps([name] + args) + '\\n')
    if name == 'codex':
        print({{'ok': 'Logged in using ChatGPT', 'apikey': 'Logged in using an API key - sk-***',
               'missing': 'Not logged in'}}.get(login, 'garbage'), file=sys.stderr)
        sys.exit(1 if login == 'missing' else 0)
    status = {{'ok': {{'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty',
                     'subscriptionType': 'pro', 'email': 'secret-sentinel@example.invalid'}},
              'apikey': {{'loggedIn': True, 'authMethod': 'api_key', 'apiProvider': 'firstParty'}},
              'bedrock': {{'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'bedrock'}},
              'missing': {{'loggedIn': False}}}}.get(login)
    print(json.dumps(status) if status else 'not json')
    sys.exit(1 if login == 'missing' else 0)
with (root / 'inference').open('a') as stream:
    stream.write(json.dumps({{'argv': args, 'env': sorted(os.environ)}}) + '\\n')
run = (root / 'run').read_text()
if run == 'quota':
    print('Error: usage limit reached, try again later', file=sys.stderr)
    sys.exit(1)
if run == 'fail':
    print('boom', file=sys.stderr)
    sys.exit(2)
if run == 'transcript':
    print('Fixed the rate limit and the quota exhausted handler; usage limit tests fail')
    sys.exit(1)
if run in ('claude-error', 'claude-error-zero'):
    print(json.dumps({{'type': 'result', 'is_error': True, 'result': 'Claude usage limit reached'}}))
    sys.exit(0 if run == 'claude-error-zero' else 1)
print(json.dumps({{'type': 'result', 'result': 'done'}}) if name == 'claude' else 'done')
'''


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin, self.home, self.work = (self.root / n for n in ('bin', 'home', 'work'))
        for directory in (self.bin, self.home, self.work):
            directory.mkdir()
        for name in ('codex', 'claude'):
            executable = self.bin / name
            executable.write_text(FAKE.format(python=sys.executable))
            executable.chmod(0o755)
        self.managed = self.root / 'managed'
        managed_path = patch.object(RUN, 'CLAUDE_MANAGED_DIR', self.managed, create=True)
        managed_path.start()
        self.addCleanup(managed_path.stop)
        self.set_login('ok')
        self.set_run('ok')
        path = str(self.bin) + os.pathsep + str(Path(shutil.which('git')).parent)
        self.environment = patch.dict(os.environ, {'PATH': path, 'HOME': str(self.home), 'LANG': 'C'},
                                      clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def set_login(self, mode):
        (self.bin / 'login').write_text(mode)

    def set_run(self, mode):
        (self.bin / 'run').write_text(mode)

    def lines(self, name):
        path = self.bin / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def adapter(self, preset='claude', enabled=True, popen=None, **harness):
        config = {'run': {'subscription_only': enabled}}
        index = {'m': {'id': 'm', 'harness': preset, 'model': 'test',
                       'harness_config': {'preset': preset, **harness}}}
        adapter = RUN.ProcessAdapter(config, index, self.root / 'runs', popen=popen or self.forbidden)
        adapter.brief.render = lambda *args: 'prompt'
        return adapter

    @staticmethod
    def forbidden(*args, **kwargs):
        raise AssertionError('inference must never start')

    def task(self):
        return {'unit': {'id': 't'}, 'model_requested': {'model': 'm', 'effort': 'low'},
                'delegation': {'worktree': str(self.work)}}

    def launch_blocked(self, adapter=None, reason=None):
        with self.assertRaises(RUN.Blocked) as raised:
            (adapter or self.adapter()).launch(self.task())
        message = str(raised.exception)
        if reason:
            self.assertIn(reason, message)
        self.assertNotIn('secret-sentinel', message)
        self.assertFalse((self.root / 'runs').exists())
        self.assertEqual(self.lines('inference'), [])
        return message

    def run_to_end(self, preset):
        adapter = self.adapter(preset, popen=subprocess.Popen)
        receipt = adapter.launch(self.task())
        self.assertEqual(receipt['runtime'], 'process')
        try:
            return adapter.wait(self.task())
        finally:
            adapter.close()

    def test_AC1_api_keys_tokens_endpoints_and_proxies_refused_before_any_cli_call(self):
        for name in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                     'OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL', 'AZURE_OPENAI_ENDPOINT',
                     'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_OAUTH_TOKEN', 'HTTPS_PROXY'):
            for preset in ('claude', 'codex'):
                with self.subTest(name=name, preset=preset), \
                        patch.dict(os.environ, {name: 'secret-sentinel'}):
                    before = dict(os.environ)
                    self.launch_blocked(self.adapter(preset), 'environment')
                    self.assertEqual(dict(os.environ), before)
        self.assertEqual(self.lines('probes'), [])

    def test_AC1_custom_harnesses_and_overrides_refused(self):
        for preset, options in [('opencode', {}), ('claude', {'argv': ['/custom']}),
                                ('codex', {'extra_args': ['--config=secret-sentinel']}),
                                ('claude', {'env_passthrough': ['CUSTOM']})]:
            with self.subTest(preset=preset, options=options):
                self.launch_blocked(self.adapter(preset, **options), 'harness')
        self.assertEqual(self.lines('probes'), [])

    def test_AC4_custom_endpoint_in_cli_settings_refused_without_leaking_values(self):
        codex = self.home / '.codex' / 'config.toml'
        claude_user = self.home / '.claude' / 'settings.json'
        claude_project = self.work / '.claude' / 'settings.local.json'
        cases = [
            ('codex', codex, 'model_provider = "azure"\n', 'model_provider'),
            ('codex', codex, 'openai_base_url = "https://secret-sentinel"\n', 'openai_base_url'),
            ('codex', codex, '[model_providers.x]\nbase_url = "https://secret-sentinel"\n',
             'model_providers'),
            ('codex', codex, '[profiles.p]\nmodel_provider = "x"\n', 'model_provider'),
            ('codex', codex, 'not = [toml', 'unreadable'),
            ('codex', self.work / '.codex' / 'config.toml', 'openai_base_url = "x"\n',
             'openai_base_url'),
            ('codex', self.root / 'codex-home' / 'config.toml', 'chatgpt_base_url = "x"\n',
             'chatgpt_base_url'),
            ('claude', self.work / '.claude' / 'settings.json', '{"env": {"HTTPS_PROXY": "x"}}',
             'HTTPS_PROXY'),
            ('claude', claude_user, '{"apiKeyHelper": "secret-sentinel"}', 'apiKeyHelper'),
            ('claude', claude_user, '{"env": {"ANTHROPIC_BASE_URL": "secret-sentinel"}}',
             'ANTHROPIC_BASE_URL'),
            ('claude', claude_project, '{"env": {"CLAUDE_CODE_USE_VERTEX": "1"}}',
             'CLAUDE_CODE_USE_VERTEX'),
            ('claude', claude_user, '{not json', 'unreadable'),
        ]
        for preset, path, content, reason in cases:
            with self.subTest(path=str(path), content=content), \
                    patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'codex-home')}
                               if 'codex-home' in str(path) else {}):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                try:
                    self.launch_blocked(self.adapter(preset), reason)
                finally:
                    path.unlink()
        self.assertEqual(self.lines('probes'), [])

    def test_AC1_managed_fragments_and_main_settings_refused_before_probe(self):
        fragments = self.managed / 'managed-settings.d'
        fragments.mkdir(parents=True)
        cases = [('managed-settings.json', {'env': {'HTTPS_PROXY': 'secret-sentinel'}},
                  'HTTPS_PROXY'),
                 ('managed-settings.d/20-routing.json',
                  {'env': {'ANTHROPIC_BASE_URL': 'secret-sentinel'}}, 'ANTHROPIC_BASE_URL'),
                 ('managed-settings.d/20-routing.json', {'policyHelper': 'secret-sentinel'},
                  'policyHelper'),
                 ('managed-settings.d/20-routing.json',
                  {'forceLoginGatewayUrl': 'secret-sentinel'}, 'forceLoginGatewayUrl')]
        for relative, settings, reason in cases:
            with self.subTest(relative=relative, settings=settings):
                target = self.managed / relative
                target.write_text(json.dumps(settings))
                try:
                    self.launch_blocked(reason=reason)
                finally:
                    target.unlink()
        self.assertEqual(self.lines('probes'), [])

    def test_AC1_invalid_unreadable_or_broken_managed_sources_block_before_probe(self):
        fragments = self.managed / 'managed-settings.d'
        fragments.mkdir(parents=True)
        target = fragments / '20-policy.json'
        for content in ('{invalid', '[]', '{"env": []}'):
            with self.subTest(content=content):
                target.write_text(content)
                self.launch_blocked(reason='settings')
                target.unlink()
        target.symlink_to(fragments / 'missing')
        self.launch_blocked(reason='settings')
        target.unlink()
        original_read = Path.read_text
        def unreadable_file(path, *args, **kwargs):
            if path == target:
                raise PermissionError('secret-sentinel')
            return original_read(path, *args, **kwargs)
        target.write_text('{}')
        with patch.object(Path, 'read_text', unreadable_file):
            self.launch_blocked(reason='settings')
        target.unlink()
        original_iterdir = Path.iterdir
        def unreadable_directory(path):
            if path == fragments:
                raise PermissionError('secret-sentinel')
            return original_iterdir(path)
        with patch.object(Path, 'iterdir', unreadable_directory):
            self.launch_blocked(reason='managed settings')
        self.assertEqual(self.lines('probes'), [])

    def test_AC1_all_nonhidden_json_fragments_are_read_in_order(self):
        fragments = self.managed / 'managed-settings.d'
        fragments.mkdir(parents=True)
        for filename in ('20-settings.json', '10-settings.json'):
            (fragments / filename).write_text('{"env": {"LANG": "C"}}')
        for filename in ('.hidden.json', 'backup.json.disabled', 'UPPER.JSON'):
            (fragments / filename).write_text('{invalid')
        reads, original_read = [], Path.read_text
        def track_reads(path, *args, **kwargs):
            if path.parent == fragments:
                reads.append(path.name)
            return original_read(path, *args, **kwargs)
        adapter = self.adapter()
        adapter.dry_run = True
        with patch.object(Path, 'read_text', track_reads):
            self.assertEqual(adapter.launch(self.task())['runtime'], 'simulated')
        self.assertEqual(reads, ['10-settings.json', '20-settings.json'])
        self.assertEqual(len(self.lines('probes')), 1)

    def test_AC1_uninspected_os_managed_sources_are_blocked_before_probe(self):
        for platform_name in ('darwin', 'win32'):
            with self.subTest(platform=platform_name), patch.object(RUN.sys, 'platform', platform_name):
                self.launch_blocked(reason='managed settings')
        release = type('Uname', (), {'release': 'microsoft-standard-WSL2'})()
        with patch.object(RUN.os, 'uname', return_value=release):
            self.launch_blocked(reason='managed settings')
        self.assertEqual(self.lines('probes'), [])

    def test_AC4_official_openai_provider_setting_is_allowed(self):
        (self.home / '.codex').mkdir()
        (self.home / '.codex' / 'config.toml').write_text(
            'model = "gpt-5"\nmodel_provider = "openai"\n[profiles.p]\nmodel_provider = "openai"\n')
        self.assertEqual(self.run_to_end('codex')['outcome'], 'COMPLETED')

    def test_AC2_AC4_login_absent_api_key_or_unknown_status_blocked_without_inference(self):
        for preset, modes in (('claude', ('missing', 'apikey', 'bedrock', 'garbage')),
                              ('codex', ('missing', 'apikey', 'garbage'))):
            for mode in modes:
                with self.subTest(preset=preset, mode=mode):
                    self.set_login(mode)
                    self.launch_blocked(self.adapter(preset), 'not logged in with')
        probes = self.lines('probes')
        self.assertEqual(len(probes), 7)
        self.assertIn(['claude', 'auth', 'status', '--json'], probes)
        self.assertIn(['codex', 'login', 'status'], probes)

    def test_AC4_success_runs_with_subscription_and_reports_unverified_limits(self):
        for preset, plan in (('claude', 'pro'), ('codex', None)):
            with self.subTest(preset=preset):
                done = self.run_to_end(preset)
                self.assertEqual(done['outcome'], 'COMPLETED', done)
                self.assertEqual(done['result']['subscription'],
                                 {'auth': 'claude.ai' if preset == 'claude' else 'chatgpt',
                                  'plan': plan, 'quota': 'not_verified', 'overage': 'not_verified'})
                self.assertNotIn('secret-sentinel', json.dumps(done))
        calls = self.lines('inference')
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertFalse([name for name in call['env'] if RUN.billing_name(name)])

    def test_AC2_AC4_quota_exhausted_blocks_without_retry(self):
        self.set_run('quota')
        done = self.run_to_end('claude')
        self.assertEqual(done['outcome'], 'BLOCKED')
        self.assertEqual(done['blockers'], ['subscription-only: quota exhausted; no automatic retry'])
        self.assertEqual(len(self.lines('inference')), 1)

    def test_AC2_claude_json_usage_limit_blocks_without_retry(self):
        for mode in ('claude-error', 'claude-error-zero'):
            with self.subTest(mode=mode):
                self.set_run(mode)
                done = self.run_to_end('claude')
                self.assertEqual(done['outcome'], 'BLOCKED')
                self.assertEqual(done['blockers'],
                                 ['subscription-only: quota exhausted; no automatic retry'])
        self.assertEqual(len(self.lines('inference')), 2)

    def test_other_failures_and_agent_transcript_are_not_reported_as_quota(self):
        for preset, run, code in (('codex', 'fail', 2), ('codex', 'transcript', 1),
                                  ('claude', 'transcript', 1)):
            with self.subTest(preset=preset, run=run):
                self.set_run(run)
                self.assertEqual(self.run_to_end(preset)['blockers'], ['exit code %d' % code])

    def test_AC2_missing_executable_blocked(self):
        with patch.object(RUN.shutil, 'which', return_value=None):
            self.launch_blocked(reason='executable not found')

    def quick(self, task_id, dry_run):
        repo = self.root / ('repo-' + task_id)
        repo.mkdir()
        def git(*args):
            subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
        git('init', '-q', '-b', 'main')
        git('config', 'user.email', 'test@example.invalid')
        git('config', 'user.name', 'Test')
        (repo / 'base.txt').write_text('base')
        git('add', 'base.txt')
        git('commit', '-qm', 'base')
        config = {'version': 1, 'models': [{'id': 'm', 'harness': 'claude', 'model': 'm',
                   'max_level': 'EXTRA_HIGH', 'cost_rank': 1,
                   'efforts': ['low', 'medium', 'high', 'xhigh']}],
                  'run': {'subscription_only': True}}
        path = self.root / 'config.json'
        path.write_text(json.dumps(config))
        report = RUN.quick(repo, task_id, 'Change a', ['a.py', 'test_a.py'], ['A'], [],
                           worktree_root=self.root / ('wt-' + task_id), config_path=path,
                           dry_run=dry_run)
        return report, repo

    def test_AC2_scheduler_propagates_blocked_without_brief_and_dry_run_checks_login(self):
        self.set_login('missing')
        for task_id, dry_run in (('t', False), ('dry', True)):
            with self.subTest(dry_run=dry_run):
                report, repo = self.quick(task_id, dry_run)
                self.assertEqual(list(repo.rglob('brief.md')), [])
                task = report['tasks'][task_id]
                self.assertEqual(task['state'], 'BLOCKED')
                self.assertTrue(any('not logged in' in reason for reason in task['blockers']), task)
                self.assertFalse(RUN.succeeded(report['tasks'], dry_run))
        self.set_login('ok')
        report, _ = self.quick('dry-ok', True)
        self.assertTrue(RUN.succeeded(report['tasks'], True), report['tasks'])
        self.assertEqual(self.lines('inference'), [])

    def test_AC3_invalid_policy_values_block_config_and_direct_adapter(self):
        for value in ('true', 'false', 0, 1, None, [], {}):
            with self.subTest(value=value):
                config = {'version': 1, 'models': [{'id': 'm', 'harness': 'claude', 'model': 'm'}],
                          'run': {'subscription_only': value}}
                path = self.root / 'config.json'
                path.write_text(json.dumps(config))
                with self.assertRaises(RUN.Blocked):
                    RUN.load_config(path)
                self.launch_blocked(self.adapter(enabled=value), 'boolean')

    def test_AC3_absent_or_false_policy_preserves_existing_flow_and_keys(self):
        for run in ({}, {'subscription_only': False}):
            with self.subTest(run=run), patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'legacy'}):
                adapter = self.adapter()
                adapter.config['run'] = run
                adapter.dry_run = True
                self.assertEqual(adapter.launch(self.task())['runtime'], 'simulated')
        self.assertEqual(self.lines('probes'), [])
        self.assertEqual(RUN.child_env({'preset': 'claude'}, {'ANTHROPIC_API_KEY': 'legacy'}),
                         {'ANTHROPIC_API_KEY': 'legacy'})


if __name__ == '__main__':
    unittest.main()
