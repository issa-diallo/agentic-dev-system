"""First-run RM/AC tests: fake CLIs, temporary Git repositories, no real accounts."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('onboard', SOURCE / 'scripts/agentic-onboard.py')
ONBOARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ONBOARD)

FAKE = r'''
import json, os, sys
from pathlib import Path
root, name, args = Path(__file__).parent, Path(__file__).name, sys.argv[1:]
login = (root / (name + '-login')).read_text().strip()
if args[:2] in (['login', 'status'], ['auth', 'status']):
    if name == 'codex':
        print('Logged in using ChatGPT' if login == 'ok' else 'Not logged in', file=sys.stderr)
    else:
        print(json.dumps({'loggedIn': login != 'missing', 'authMethod': 'claude.ai',
                          'apiProvider': 'firstParty', 'subscriptionType': login if login != 'ok'
                          else 'pro', 'email': 'secret-sentinel@example.invalid'}))
    sys.exit(1 if login == 'missing' else 0)
with (root / 'events').open('a') as stream:
    stream.write(json.dumps({'name': name, 'argv': args, 'cwd': str(Path.cwd())}) + '\n')
mode = (root / 'mode').read_text().strip()
if mode == 'fail':
    print('private-secret-sentinel', file=sys.stderr)
    sys.exit(2)
if mode == 'quota':
    print('usage limit reached', file=sys.stderr)
    sys.exit(1)
answer = 'wrong response' if mode == 'wrong' else 'AGENTIC_ONBOARDING_OK'
if name == 'claude':
    print(json.dumps({'type': 'result', 'is_error': mode == 'error-zero',
                      'result': answer, 'modelUsage': {'observed-test': {}}}))
else:
    print(answer)
'''


def model(harness='codex', **changes):
    return {'id': harness + '-account', 'harness': harness,
            'provider': {'codex': 'openai', 'claude': 'anthropic'}[harness],
            'model': harness + '-test', 'max_level': 'HIGH', 'efforts': ['high'],
            'cost_rank': 1, **changes}


class OnboardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo, self.home, self.bin = (self.root / n for n in ('repo', 'home', 'bin'))
        for directory in (self.repo, self.home, self.bin):
            directory.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / '.git/info/exclude').write_text('/.agentic-local/\n')
        self.config = self.repo / '.agentic-local/agentic.config.json'
        self.mode('ok')
        for name in ('codex', 'claude'):
            executable = self.bin / name
            executable.write_text('#!' + sys.executable + '\n' + FAKE)
            executable.chmod(0o755)
            (self.bin / (name + '-login')).write_text('ok')
        environment = {'HOME': str(self.home), 'LANG': 'C',
                       'PATH': str(self.bin) + os.pathsep + str(Path(shutil.which('git')).parent)}
        patch = mock.patch.dict(os.environ, environment, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(ONBOARD.RUN, 'CLAUDE_MANAGED_DIR', self.root / 'managed')
        patch.start()
        self.addCleanup(patch.stop)

    def mode(self, value):
        (self.bin / 'mode').write_text(value)

    def events(self):
        path = self.bin / 'events'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def answers(self, **changes):
        return {'claude': False, 'reviews': True, 'models': [model()], **changes}

    def configure(self, answers=None, **options):
        return ONBOARD.configure(self.repo, answers or self.answers(),
                                 config_path=self.config, **options)

    def saved(self):
        return json.loads(self.config.read_text())

    def write_config(self, data):
        self.config.parent.mkdir(exist_ok=True)
        self.config.write_text(json.dumps(data))
        return self.config.read_bytes()

    def test_RM4_pending_status_does_not_infer_or_write(self):
        before = subprocess.check_output(['git', '-C', str(self.repo), 'status', '--porcelain'])
        result = ONBOARD.status(self.repo, config_path=self.config)
        self.assertTrue(result['onboarding_required'])
        self.assertEqual(Path(result['config']), self.config)
        self.assertFalse(self.config.exists())
        self.assertEqual(self.events(), [])
        self.assertEqual(subprocess.check_output(
            ['git', '-C', str(self.repo), 'status', '--porcelain']), before)

    def test_RM1_codex_only_enables_review_with_seven_two_defaults(self):
        result = self.configure()
        config = self.saved()
        self.assertEqual(result['verdict'], 'PASS')
        self.assertTrue(config['onboarding']['completed'])
        self.assertTrue(config['run']['subscription_only'])
        self.assertTrue(config['run']['missions']['enabled'])
        self.assertEqual(config['run']['review_cycle']['max_attempts'], 7)
        self.assertEqual(config['run']['review_cycle']['max_corrections'], 2)
        self.assertEqual([entry['harness'] for entry in config['models']], ['codex'])
        self.assertEqual([event['name'] for event in self.events()], ['codex'])

    def test_AC5_selected_models_can_route_each_mission_and_high_reviewer(self):
        self.configure(self.answers(claude=True, models=[model(), model('claude', cost_rank=2)]))
        config = self.saved()
        inventory = ONBOARD.RUN.build_inventory(config)[0]
        for role in ('test-author', 'implementer', 'reviewer'):
            task = {'id': 'setup-' + role, 'role': role, 'phase': 'BUILD',
                    'complexity': 'medium', 'session_id': 'review',
                    'implementer_session_id': 'writer'}
            routed = ONBOARD.RUN.module('models').route(
                task, inventory, policy=config.get('routing_policy'))
            self.assertEqual(routed['verdict'], 'PASS', routed)
            if role == 'reviewer':
                self.assertIn(routed['level'], ('HIGH', 'EXTRA_HIGH'))
        self.assertEqual({event['name'] for event in self.events()}, {'codex', 'claude'})

    def test_RM1_declining_review_is_persisted_without_enabling_it(self):
        self.configure(self.answers(reviews=False))
        self.assertFalse(self.saved()['run']['review_cycle']['enabled'])
        self.assertTrue(self.saved()['onboarding']['completed'])

    def test_RM1_budgets_are_customizable_and_invalid_limits_never_activate(self):
        self.configure(self.answers(max_attempts=11, max_corrections=3))
        self.assertEqual(self.saved()['run']['review_cycle']['max_attempts'], 11)
        self.assertEqual(self.saved()['run']['review_cycle']['max_corrections'], 3)
        before = self.config.read_bytes()
        for invalid in ({'max_attempts': True}, {'max_attempts': 0}, {'max_corrections': -1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.configure(self.answers(**invalid), reconfigure=True)
            self.assertEqual(self.config.read_bytes(), before)

    def test_RM1_choices_require_explicit_boolean_answers(self):
        for changes in ({'claude': None}, {'reviews': 'yes'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.configure(self.answers(**changes))
        self.assertFalse(self.config.exists())
        self.assertEqual(self.events(), [])

    def test_RM4_completed_status_and_configure_do_not_repeat_inference(self):
        self.configure()
        before, events = self.config.read_bytes(), self.events()
        status = ONBOARD.status(self.repo, config_path=self.config)
        self.assertFalse(status['onboarding_required'])
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.events(), events)

    def test_RM4_explicit_reconfiguration_can_disable_reviews(self):
        self.configure()
        self.configure(self.answers(reviews=False), reconfigure=True)
        self.assertFalse(self.saved()['run']['review_cycle']['enabled'])
        self.assertEqual(len(self.events()), 2)

    def test_RM3_existing_models_limits_and_unrelated_config_are_preserved(self):
        original = {'version': 1, 'models': [model()], 'custom': {'keep': ['value']},
                    'gates': {'commands': [['python3', '-m', 'unittest']]},
                    'run': {'subscription_only': True, 'timeout_seconds': 777,
                            'double_analysis': {'enabled': False},
                            'review_cycle': {'enabled': True, 'max_attempts': 9,
                                             'max_corrections': 1, 'max_cost_rank': 2}}}
        self.write_config(original)
        self.configure({'claude': False, 'reviews': True})
        saved = self.saved()
        for key in ('models', 'custom', 'gates'):
            self.assertEqual(saved[key], original[key])
        self.assertEqual(saved['run']['timeout_seconds'], 777)
        self.assertEqual(saved['run']['double_analysis'], {'enabled': False})
        self.assertEqual(saved['run']['review_cycle']['max_attempts'], 9)
        self.assertEqual(saved['run']['review_cycle']['max_corrections'], 1)

    def test_RM5_missing_model_metadata_does_not_invent_a_name_or_capacity(self):
        for answers in ({'claude': False, 'reviews': True},
                        self.answers(models=[{k: v for k, v in model().items()
                                              if k != 'max_level'}]),
                        self.answers(models=[model(max_level='MEDIUM', efforts=['medium'])])):
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                self.configure(answers)
        self.assertFalse(self.config.exists())
        self.assertEqual(self.events(), [])

    def test_RM5_declining_claude_does_not_leave_an_enabled_claude_route(self):
        original = self.write_config({
            'version': 1, 'models': [model(), model('claude')],
            'routing_policy': {'version': 1, 'enabled': True, 'rules': [
                {'id': 'implementation', 'match': {'role': 'implementer', 'phase': 'BUILD'},
                 'prefer': [{'harness': 'claude'}], 'fallback': 'blocked'}]}})
        with self.assertRaises(ValueError):
            self.configure({'claude': False, 'reviews': True})
        self.assertEqual(self.config.read_bytes(), original)

    def test_RM5_existing_review_budget_cannot_be_raised_silently(self):
        original = self.write_config({
            'version': 1, 'models': [model(cost_rank=5)],
            'run': {'review_cycle': {'enabled': True, 'max_attempts': 7,
                                     'max_corrections': 2, 'max_cost_rank': 1}}})
        with self.assertRaises(ValueError):
            self.configure({'claude': False, 'reviews': True})
        self.assertEqual(self.config.read_bytes(), original)

    def test_RM5_existing_enabled_tdd_is_not_silently_disabled_to_enable_reviews(self):
        for tdd in (True, {'enabled': True, 'red_level': 'MEDIUM'}):
            with self.subTest(tdd=tdd):
                original = self.write_config({'version': 1, 'models': [model()],
                                               'run': {'tdd': tdd}})
                with self.assertRaisesRegex(ValueError, 'TDD'):
                    self.configure({'claude': False, 'reviews': True})
                self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.events(), [])

    def test_RM5_saved_phase_specific_routes_must_support_the_real_pipeline_contexts(self):
        for role, phase in (('lead-tech', 'SHIP'), ('explorer', 'PREPARE'),
                            ('orchestrator', 'PREPARE')):
            with self.subTest(role=role, phase=phase):
                original = self.write_config({
                    'version': 1, 'models': [model()],
                    'routing_policy': {'version': 1, 'enabled': True, 'rules': [
                        {'id': 'unavailable', 'match': {'role': role, 'phase': phase},
                         'prefer': [{'model': 'not-available'}], 'fallback': 'blocked'}]}})
                with self.assertRaises(ValueError):
                    self.configure({'claude': False, 'reviews': True})
                self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.events(), [])

    def test_RM5_double_analysis_requires_high_preparation_routes_for_both_providers(self):
        for claude, policy in ((model('claude', max_level='MEDIUM', efforts=['medium']), None),
                               (model('claude'), {'version': 1, 'enabled': True, 'rules': [
                                   {'id': 'codex-only-analysis',
                                    'match': {'role': 'explorer', 'phase': 'PREPARE'},
                                    'prefer': [{'harness': 'codex'}], 'fallback': 'blocked'}]})):
            with self.subTest(claude=claude, policy=policy):
                config = {'version': 1, 'models': [model(), claude],
                          'run': {'subscription_only': True, 'missions': {'enabled': True},
                                  'double_analysis': {'enabled': True, 'justification': 'Existing'}}}
                if policy:
                    config['routing_policy'] = policy
                original = self.write_config(config)
                with self.assertRaises(ValueError):
                    self.configure({'claude': True, 'reviews': True})
                self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.events(), [])

    def test_RM5_explicit_effort_that_claude_cannot_transmit_blocks_before_activation(self):
        original = self.write_config({
            'version': 1, 'models': [model(), model('claude')],
            'routing_policy': {'version': 1, 'enabled': True, 'rules': [
                {'id': 'forced-effort', 'match': {'role': 'implementer', 'phase': 'BUILD'},
                 'prefer': [{'harness': 'claude'}], 'effort': 'high', 'fallback': 'blocked'}]}})
        with self.assertRaises(ValueError):
            self.configure({'claude': True, 'reviews': True})
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.events(), [])

    def test_RM5_declining_review_preserves_existing_double_analysis_prerequisites(self):
        self.write_config({
            'version': 1, 'models': [model(), model('claude')],
            'run': {'subscription_only': True, 'missions': {'enabled': True},
                    'double_analysis': {'enabled': True, 'justification': 'Existing choice'}}})
        self.configure({'claude': True, 'reviews': False})
        self.assertTrue(self.saved()['run']['missions']['enabled'])
        self.assertTrue(self.saved()['run']['double_analysis']['enabled'])
        self.assertFalse(self.saved()['run']['review_cycle']['enabled'])

    def test_RM2_missing_binary_or_login_blocks_without_a_saved_completion(self):
        for mode in ('missing-binary', 'missing-login'):
            with self.subTest(mode=mode):
                if mode == 'missing-binary':
                    (self.bin / 'codex').rename(self.bin / 'codex.off')
                else:
                    (self.bin / 'codex.off').rename(self.bin / 'codex')
                    (self.bin / 'codex-login').write_text('missing')
                with self.assertRaises(ValueError):
                    self.configure()
                self.assertFalse(self.config.exists())
        self.assertEqual(self.events(), [])

    def test_RM2_failed_wrong_or_quota_smoke_keeps_old_config_and_does_not_retry(self):
        original = self.write_config({'version': 1, 'models': [model()], 'custom': 'keep'})
        for mode in ('fail', 'wrong', 'quota'):
            self.mode(mode)
            count = len(self.events())
            with self.subTest(mode=mode), self.assertRaises(ValueError) as caught:
                self.configure()
            self.assertNotIn('private-secret-sentinel', str(caught.exception))
            self.assertEqual(self.config.read_bytes(), original)
            self.assertEqual(len(self.events()), count + 1)

    def test_RM2_timeout_keeps_setup_pending(self):
        real_run = subprocess.run

        def run(argv, **kwargs):
            if argv[0] in ('codex', 'claude') and argv[1] not in ('login', 'auth'):
                raise subprocess.TimeoutExpired(argv, kwargs.get('timeout', 1))
            return real_run(argv, **kwargs)

        with self.assertRaises(ValueError):
            self.configure(run=run)
        self.assertFalse(self.config.exists())

    def test_RM2_real_timeout_stops_the_cli_and_its_child_before_returning(self):
        marker, started = self.root / 'child-escaped', self.root / 'child-started'
        child_code = 'import time; from pathlib import Path; time.sleep(0.7); Path(' + repr(
            str(marker)) + ').write_text("escaped")'
        prefix = ('import subprocess, sys, time\nfrom pathlib import Path\n'
                  'if sys.argv[1:2] == ["exec"]:\n'
                  '    child = subprocess.Popen([sys.executable, "-c", ' + repr(child_code) + '],\n'
                  '                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n'
                  '    Path(' + repr(str(started)) + ').write_text(str(child.pid))\n'
                  '    time.sleep(30)\n')
        (self.bin / 'codex').write_text('#!' + sys.executable + '\n' + prefix + FAKE)
        original = self.write_config({'version': 1, 'models': [model()]})
        with mock.patch.object(ONBOARD, 'SMOKE_TIMEOUT', 0.2), self.assertRaises(ValueError):
            self.configure()
        self.assertTrue(started.exists(), 'real descendant must have been started')
        time.sleep(0.9)
        self.assertFalse(marker.exists(), 'timed-out descendant must not continue working')
        self.assertEqual(self.config.read_bytes(), original)

    def test_RM5_subscription_environment_and_custom_harness_conflicts_are_not_overwritten(self):
        with mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'private-secret-sentinel'}):
            with self.assertRaises(ValueError):
                self.configure()
        self.assertEqual(self.events(), [])
        original = self.write_config({'version': 1, 'models': [model()],
                                      'harnesses': {'codex': {'preset': 'codex',
                                                              'extra_args': ['--unsafe']}}})
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.events(), [])

    def test_RM5_claude_review_smoke_uses_exact_isolated_preset_and_private_plan(self):
        self.configure(self.answers(claude=True, models=[model(), model('claude')]))
        event = next(event for event in self.events() if event['name'] == 'claude')
        args = event['argv']
        self.assertIn('--safe-mode', args)
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--strict-mcp-config', args)
        self.assertIn('--no-session-persistence', args)
        self.assertNotIn('--dangerously-skip-permissions', args)
        self.assertNotIn('secret-sentinel', self.config.read_text())

    def test_RM5_claude_managed_policy_or_unknown_plan_blocks_activation(self):
        managed = self.root / 'managed'
        managed.mkdir()
        (managed / 'managed-settings.json').write_text('{"hooks": {}}')
        answers = self.answers(claude=True, models=[model(), model('claude')])
        with self.assertRaises(ValueError):
            self.configure(answers)
        self.assertFalse(self.config.exists())
        (managed / 'managed-settings.json').unlink()
        (self.bin / 'claude-login').write_text('team')
        with self.assertRaises(ValueError):
            self.configure(answers)
        self.assertFalse(self.config.exists())

    def test_RM2_claude_structured_error_with_zero_exit_still_blocks(self):
        self.mode('error-zero')
        with self.assertRaises(ValueError):
            self.configure(self.answers(claude=True, models=[model(), model('claude')]))
        self.assertFalse(self.config.exists())

    def test_RM2_probes_are_isolated_from_project_and_codex_is_read_only(self):
        (self.repo / 'private-project.txt').write_text('private-project-sentinel')
        self.configure()
        event = self.events()[0]
        self.assertNotEqual(Path(event['cwd']), self.repo)
        self.assertFalse(Path(event['cwd']).exists())
        self.assertEqual(event['argv'][event['argv'].index('-s') + 1], 'read-only')
        self.assertNotIn('private-project-sentinel', json.dumps(event))

    def test_RM3_invalid_json_symlink_or_tracked_config_is_never_replaced(self):
        self.config.parent.mkdir()
        self.config.write_text('{broken')
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(self.config.read_text(), '{broken')
        self.config.unlink()
        foreign = self.root / 'foreign.json'
        foreign.write_text('{"keep": true}')
        self.config.symlink_to(foreign)
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual(foreign.read_text(), '{"keep": true}')
        self.config.unlink()
        self.write_config({'version': 1, 'models': [model()]})
        subprocess.run(['git', '-C', str(self.repo), 'add', '-f', str(self.config)], check=True)
        with self.assertRaises(ValueError):
            self.configure()
        self.assertNotIn('onboarding', self.saved())

    def test_RM3_concurrent_configuration_change_is_preserved(self):
        self.write_config({'version': 1, 'models': [model()]})
        real_run = subprocess.run

        def run(argv, **kwargs):
            result = real_run(argv, **kwargs)
            if argv[0] == 'codex' and argv[1] == 'exec':
                self.config.write_text('{"concurrent": true}')
            return result

        with self.assertRaises(ValueError):
            self.configure(run=run)
        self.assertEqual(self.saved(), {'concurrent': True})

    def test_RM3_failed_atomic_replace_keeps_previous_configuration(self):
        original = self.write_config({'version': 1, 'models': [model()]})
        with mock.patch.object(ONBOARD.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises((ValueError, OSError)):
                self.configure()
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse(any(self.config.parent.glob('*.tmp')))

    def test_RM3_saved_configuration_is_private_and_ignored(self):
        self.configure()
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        result = subprocess.run(['git', '-C', str(self.repo), 'check-ignore', '-q',
                                 str(self.config)])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(subprocess.check_output(
            ['git', '-C', str(self.repo), 'status', '--porcelain']), b'')

    def test_RM3_fresh_shared_setup_adds_only_the_exact_private_configuration_exclusion(self):
        exclude = self.repo / '.git/info/exclude'
        exclude.write_text('# team exclusions stay\n')
        self.configure()
        self.assertIn('# team exclusions stay', exclude.read_text())
        self.assertIn('/.agentic-local/agentic.config.json', exclude.read_text())
        self.assertEqual(subprocess.run(
            ['git', '-C', str(self.repo), 'check-ignore', '-q', str(self.config)]).returncode, 0)
        unrelated = self.config.parent / 'unrelated.json'
        unrelated.write_text('{}')
        self.assertEqual(subprocess.run(
            ['git', '-C', str(self.repo), 'check-ignore', '-q', str(unrelated)]).returncode, 1)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_AC4_configure_cli_reads_confirmed_answers_and_returns_structured_status(self):
        answers = self.root / 'answers.json'
        answers.write_text(json.dumps(self.answers()))
        command = [sys.executable, str(SOURCE / 'scripts/agentic-onboard.py'), 'configure',
                   '--repo', str(self.repo), '--config', str(self.config), '--answers', str(answers)]
        done = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertEqual(json.loads(done.stdout)['verdict'], 'PASS')
        self.assertTrue(self.saved()['onboarding']['completed'])
        self.mode('wrong')
        done = subprocess.run(command + ['--reconfigure'], capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 1, done.stderr + done.stdout)
        self.assertEqual(json.loads(done.stdout)['verdict'], 'BLOCKED')
        self.assertNotIn('secret-sentinel', done.stdout + done.stderr)

    def test_RM4_explicit_environment_config_path_is_respected(self):
        custom = self.repo / '.agentic-local/personal.json'
        with mock.patch.dict(os.environ, {'AGENTIC_CONFIG': str(custom)}):
            status = ONBOARD.status(self.repo)
        self.assertEqual(Path(status['config']), custom)

    def test_RM4_fresh_shared_project_uses_an_explicit_local_configuration_path(self):
        status = ONBOARD.status(self.repo)
        self.assertEqual(Path(status['config']), self.config)
        self.assertFalse((self.repo / 'agentic.config.json').exists())

    def test_AC4_mission_entrypoints_reference_onboarding_and_diagnostic_is_unchanged(self):
        for relative in ('docs/agentic/LOCAL.md', 'docs/agentic/README.md',
                         'skills/start-ticket/SKILL.md',
                         'scripts/agentic-codex.sh', 'scripts/agentic-claude.sh'):
            with self.subTest(relative=relative):
                self.assertIn('ONBOARDING.md', (SOURCE / relative).read_text())
        global_rules = (SOURCE / 'codex/global-AGENTS.md').read_text()
        self.assertIn('réponds exactement « Agentic Dev System prêt à commencer. »', global_rules)
        self.assertNotIn('onboard', global_rules.lower())


if __name__ == '__main__':
    unittest.main()
