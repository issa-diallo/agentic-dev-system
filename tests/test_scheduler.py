"""Simulated runtime callbacks over real Git worktrees; no native-runtime proof."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / 'scripts/agentic-scheduler.py'
SPEC = importlib.util.spec_from_file_location('agentic_scheduler', SCRIPT)
SCHEDULER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCHEDULER)


class SimulatedAdapter:
    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = outcomes or {}

    def launch(self, task):
        pr = task['unit']['id']
        self.calls.append(('launch', pr))
        return {'agent_id': 'simulated-' + pr, 'runtime': 'simulated',
                'launch_observed': True, 'identity_verified': True}

    def wait(self, task):
        pr = task['unit']['id']
        self.calls.append(('wait', pr))
        return {'agent_id': task['agent_id'], 'identity_verified': True,
                'stopped_confirmed': True, 'outcome': self.outcomes.get(pr, 'COMPLETED'),
                'result': {'validation': 'simulation only'}}


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'base').write_text('base\n')
        self.git('add', 'base')
        self.git('commit', '-qm', 'fixture')
        self.plan = {'version': 1, 'story': 'runtime', 'capabilities': [], 'prs': []}
        self.manifest = self.root / 'plan.json'
        self.path = self.root / 'scheduler.json'
        self.add('a')
        self.scheduler = SCHEDULER.Scheduler(self.manifest, self.repo, self.path)

    def git(self, *args, repo=None):
        return subprocess.run(['git', '-C', str(repo or self.repo), *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def add(self, name, dependencies=()):
        tree = self.root / name
        self.git('worktree', 'add', '-q', '-b', 'feat/' + name, str(tree))
        unit = {'id': name, 'reason': 'Deliver ' + name, 'capabilities': [name],
                'files': [name + '.py'], 'acceptance': ['Expected behavior'],
                'tests': ['Behavior tests'], 'contracts': [], 'depends_on': list(dependencies),
                'branch': 'feat/' + name, 'worktree': str(tree), 'implementer': 'writer-' + name}
        self.plan['capabilities'].append(name)
        self.plan['prs'].append(unit)
        self.write()
        return unit

    def write(self):
        self.manifest.write_text(json.dumps(self.plan))

    def owners(self):
        with SCHEDULER.WORKSPACE.registry(self.repo) as owners:
            return dict(owners)

    def receipt(self, pr='a'):
        return self.scheduler.receipt(pr, {'agent_id': 'simulated-' + pr,
                                         'runtime': 'simulated', 'launch_observed': True,
                                         'identity_verified': True})

    def handoff(self, pr='a', **extras):
        observation = {'agent_id': 'simulated-' + pr, 'identity_verified': True,
                       'stopped_confirmed': True, 'outcome': 'COMPLETED', 'result': 'tested'}
        observation.update(extras)
        return self.scheduler.handoff(pr, observation)

    def accept(self, pr='a'):
        state = self.scheduler.resume()
        return self.scheduler.accept(pr, {'status': 'PASS', 'orchestrator_verified': True,
                                          'source': 'simulated orchestrator validation',
                                          'criteria': ['Expected behavior verified'],
                                          'tests': ['Fixture behavior test passed'],
                                          'head': self.git('rev-parse', 'HEAD', repo=self.root / pr),
                                          'snapshot': SCHEDULER.snapshot(self.root / pr),
                                          'plan_sha256': state['plan_sha256']})

    def requeue_evidence(self, pr='a', **extras):
        state = self.scheduler.resume()
        evidence = {'orchestrator_verified': True, 'reason': 'Corrected failed attempt',
                    'proof': 'Fixture scope reconciled and runtime stopped',
                    'snapshot': SCHEDULER.snapshot(self.root / pr),
                    'plan_sha256': state['plan_sha256'], 'identity_verified': True,
                    'stopped_confirmed': True, 'agent_id': state['tasks'][pr]['agent_id']}
        evidence.update(extras)
        return evidence

    def test_prepare_is_assignment_not_launch_and_reserves_all_files(self):
        self.plan['prs'][0]['files'].append('other.py')
        self.plan['prs'][0]['resources'] = [{'type': 'api', 'name': 'public'}]
        self.write()
        task = self.scheduler.prepare('a')
        self.assertEqual(task['state'], 'ASSIGNED')
        self.assertIsNone(task['agent_id'])
        self.assertEqual(task['reservation']['resources'], [
            {'type': 'file', 'name': 'a.py'}, {'type': 'file', 'name': 'other.py'},
            {'type': 'api', 'name': 'public'}])
        for key in ('objective', 'acceptance', 'files', 'tests', 'dependencies',
                    'worktree', 'deliverable', 'prohibitions'):
            self.assertIn(key, task['delegation'])
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'no redispatch'):
            self.scheduler.prepare('a')

    def test_multiple_independent_launches_before_collection(self):
        self.add('b')
        adapter = SimulatedAdapter()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [('launch', 'a'), ('launch', 'b'),
                                         ('wait', 'a'), ('wait', 'b')])
        for task in state['tasks'].values():
            self.assertEqual(task['state'], 'COMPLETED')
            self.assertEqual(task['runtime'], 'simulated')
            self.assertIsNone(task['model_requested'])
            self.assertIsNone(task['model_observed'])
            self.assertGreaterEqual(task['duration_seconds'], 0)
            self.assertFalse(task['independent_review'])
        self.assertEqual(self.owners(), {})
        self.scheduler.dispatch(adapter)
        self.assertEqual(len(adapter.calls), 4)

    def test_blocked_branch_isolated_and_dependency_waits(self):
        self.add('b', ['a'])
        self.add('c')
        adapter = SimulatedAdapter({'a': 'BLOCKED'})
        self.scheduler.dispatch(adapter)
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(state['tasks']['a']['state'], 'BLOCKED')
        self.assertEqual(state['tasks']['b']['state'], 'BLOCKED')
        self.assertEqual(state['tasks']['c']['state'], 'COMPLETED')
        self.assertNotIn(('launch', 'b'), adapter.calls)

    def test_completed_dependency_can_dispatch_next_round(self):
        self.add('b', ['a'])
        adapter = SimulatedAdapter()
        first = self.scheduler.dispatch(adapter)
        self.assertEqual(first['tasks']['b']['state'], 'PLANNED')
        self.scheduler.dispatch(adapter)
        self.assertNotIn(('launch', 'b'), adapter.calls)
        self.accept('a')
        second = self.scheduler.dispatch(adapter)
        self.assertEqual(second['tasks']['b']['state'], 'COMPLETED')

    def test_cycle_invalid_and_wrong_branch_before_adapter(self):
        self.add('b', ['a'])
        self.plan['prs'][0]['depends_on'] = ['b']
        self.write()
        adapter = SimulatedAdapter()
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'cycle'):
            self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.plan['prs'][0]['depends_on'] = []
        self.plan['prs'][0]['branch'] = 'feat/wrong'
        self.write()
        self.scheduler.dispatch(adapter)
        self.assertNotIn(('launch', 'a'), adapter.calls)

    def test_resource_conflict_before_adapter(self):
        task = self.scheduler.prepare('a')
        other = self.add('b')
        other['resources'] = [{'type': 'file', 'name': 'a.py'}]
        self.write()
        adapter = SimulatedAdapter()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(state['tasks']['b']['state'], 'BLOCKED')
        self.assertIn(task['owner']['id'], self.owners())

    def test_callback_failure_never_fabricates_launch_or_releases(self):
        class Failed(SimulatedAdapter):
            def launch(self, task):
                raise RuntimeError('runtime disconnected')
        state = self.scheduler.dispatch(Failed())
        task = state['tasks']['a']
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertIsNone(task['agent_id'])
        self.assertIsNone(task['active'])
        self.assertEqual(task['launch_status'], 'UNKNOWN')
        self.assertIn(task['owner']['id'], self.owners())
        self.assertNotIn('launch_observed', [event['event'] for event in state['events']])

    def test_timeout_and_restart_retain_owner_without_relaunch(self):
        class Timeout(SimulatedAdapter):
            def wait(self, task):
                return None
        adapter = Timeout()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(state['tasks']['a']['state'], 'RUNNING')
        self.assertTrue(state['tasks']['a']['active'])
        restarted = SCHEDULER.Scheduler(self.manifest, self.repo, self.path)
        restarted.dispatch(adapter)
        self.assertEqual(adapter.calls, [('launch', 'a')])
        self.assertEqual(len(self.owners()), 1)
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'confirmed stop'):
            self.handoff(stopped_confirmed=False)
        self.assertEqual(len(self.owners()), 1)
        self.handoff()
        self.assertEqual(self.owners(), {})

    def test_wait_exception_keeps_active_identity_and_reservation(self):
        class Failed(SimulatedAdapter):
            def wait(self, task):
                raise TimeoutError('still active')
        state = self.scheduler.dispatch(Failed())
        self.assertTrue(state['tasks']['a']['active'])
        self.assertEqual(state['tasks']['a']['agent_id'], 'simulated-a')
        self.assertEqual(len(self.owners()), 1)

    def test_stale_plan_blocks_affected_tasks_without_relaunch(self):
        self.add('b', ['a'])
        self.add('c')
        self.scheduler.prepare('a')
        self.receipt()
        self.plan['prs'][0]['reason'] = 'Changed contract'
        self.write()
        adapter = SimulatedAdapter()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(state['tasks']['a']['state'], 'BLOCKED')
        self.assertTrue(state['tasks']['a']['active'])
        self.assertEqual(state['tasks']['b']['state'], 'BLOCKED')
        self.assertEqual(state['tasks']['c']['state'], 'COMPLETED')
        self.assertEqual(adapter.calls, [('launch', 'c'), ('wait', 'c')])
        self.assertEqual(self.handoff()['state'], 'BLOCKED')

    def test_resume_checks_git_and_missing_owner(self):
        task = self.scheduler.prepare('a')
        self.receipt()
        (self.root / 'a' / 'outside').write_text('preserve')
        SCHEDULER.WORKSPACE.release(self.repo, task['owner']['id'])
        state = self.scheduler.resume()
        blockers = state['tasks']['a']['blockers']
        self.assertIn('reservation missing or changed', blockers)
        self.assertIn('dirty paths outside scope', blockers)
        self.assertTrue(state['tasks']['a']['active'])

    def test_cli_receipt_is_no_autonomous_identity_proof(self):
        self.scheduler.prepare('a')
        observation = self.root / 'observation.json'
        data = {'agent_id': 'claimed', 'runtime': 'native', 'launch_observed': True}
        observation.write_text(json.dumps(data))
        argv = ['python3', str(SCRIPT), 'receipt', str(self.manifest), '--repo', str(self.repo),
                '--state', str(self.path), '--pr', 'a', '--observation', str(observation)]
        rejected = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn('orchestrator must verify', rejected.stdout)
        data['identity_verified'] = True
        observation.write_text(json.dumps(data))
        accepted = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stdout)
        self.assertFalse(json.loads(accepted.stdout)['identity_authenticated'])

    def test_two_processes_cannot_double_assign(self):
        argv = ['python3', str(SCRIPT), 'prepare', str(self.manifest), '--repo', str(self.repo),
                '--state', str(self.path), '--pr', 'a']
        processes = [subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for _ in range(2)]
        results = [process.communicate() for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1], results)
        self.assertEqual(len(self.owners()), 1)

    def test_duplicate_active_runtime_identity_keeps_second_reservation(self):
        self.add('b')
        self.scheduler.prepare('a')
        self.receipt()
        self.scheduler.prepare('b')
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'identity already active'):
            self.scheduler.receipt('b', {'agent_id': 'simulated-a', 'runtime': 'simulated',
                                         'launch_observed': True, 'identity_verified': True})
        self.assertEqual(len(self.owners()), 2)

    def test_interrupted_assignment_preserves_intent_and_cannot_launch(self):
        reserve = SCHEDULER.WORKSPACE.reserve
        def crash(*args):
            reserve(*args)
            raise SystemExit('simulate process death after registry write')
        with mock.patch.object(SCHEDULER.WORKSPACE, 'reserve', side_effect=crash):
            with self.assertRaises(SystemExit):
                self.scheduler.prepare('a')
        owner = json.loads(self.path.read_text())['tasks']['a']['owner']['id']
        adapter = SimulatedAdapter()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(state['tasks']['a']['owner']['id'], owner)
        self.assertIn(owner, self.owners())
        self.handoff(agent_id=None, outcome='BLOCKED')
        self.assertEqual(self.owners(), {})

    def test_skill_selection_loading_application_and_model_observation(self):
        skill = self.root / 'skills' / 'test-patterns' / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: test-patterns\ndescription: Unit testing patterns\n'
                         'agentic_tier: CORE\n---\nApply assertions.\n')
        models = {'runtime_overrides': True, 'models': [
            {'id': 'test-model', 'max_level': 'MEDIUM', 'efforts': ['medium'], 'cost_rank': 1}]}
        scheduler = SCHEDULER.Scheduler(self.manifest, self.repo, self.path,
                                        skill_roots=[str(skill.parent.parent)], models=models)
        task = scheduler.prepare('a')
        self.assertEqual(len(task['skills']['selected']), 1)
        self.assertEqual(task['skills']['loaded'], [])
        self.assertEqual(task['skills']['applied'], [])
        self.assertEqual(task['model_requested'], {'model': 'test-model', 'effort': 'medium'})
        self.assertIsNone(task['model_observed'])
        loaded = scheduler.load_skills('a')
        self.assertIn('Apply assertions.', loaded[0]['instructions'])
        task = scheduler.receipt('a', {'agent_id': 'simulated-a', 'runtime': 'mono-agent',
                                      'launch_observed': True, 'identity_verified': True,
                                      'model_observed': {'model': 'other', 'effort': 'medium'}})
        self.assertFalse(task['model_applied'])
        self.assertFalse(task['independent_review'])
        applied = {'path': str(skill), 'sha256': loaded[0]['sha256'], 'evidence': 'handoff example'}
        result = self.handoff(skills_applied=[applied])
        self.assertEqual(result['skills']['applied'], [applied])

    def test_unloaded_application_is_rejected_without_releasing(self):
        self.scheduler.prepare('a')
        self.receipt()
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'loaded hash'):
            self.handoff(skills_applied=[{'path': 'fake', 'sha256': 'fake', 'evidence': 'claimed'}])
        self.assertEqual(len(self.owners()), 1)

    def test_fictitious_launch_receipt_is_rejected(self):
        self.scheduler.prepare('a')
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'orchestrator must verify'):
            self.scheduler.receipt('a', {'agent_id': 'fake', 'runtime': 'simulated',
                                         'identity_verified': True, 'launch_observed': False})
        self.assertIsNone(self.scheduler.resume()['tasks']['a']['agent_id'])

    def test_default_state_namespaces_independent_manifests(self):
        first = SCHEDULER.Scheduler(self.manifest, self.repo)
        other = self.root / 'other-plan.json'
        other.write_text(self.manifest.read_text())
        second = SCHEDULER.Scheduler(other, self.repo)
        self.assertNotEqual(first.path, second.path)
        first.resume()
        second.resume()
        self.assertTrue(first.path.exists() and second.path.exists())

    def test_committed_outside_scope_blocks_handoff_and_dependents(self):
        self.add('b', ['a'])
        self.scheduler.prepare('a')
        self.receipt()
        (self.root / 'a' / 'outside.py').write_text('unauthorized\n')
        self.git('add', 'outside.py', repo=self.root / 'a')
        self.git('commit', '-qm', 'outside scope', repo=self.root / 'a')
        result = self.handoff()
        self.assertEqual(result['state'], 'BLOCKED')
        self.assertIn('committed/dirty paths outside scope', result['blockers'])
        adapter = SimulatedAdapter()
        self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(self.owners(), {})

    def test_conservative_routing_requires_auth_and_sql_strong_model(self):
        models = {'runtime_overrides': True, 'models': [
            {'id': 'cheap', 'max_level': 'MEDIUM', 'efforts': ['medium'], 'cost_rank': 1},
            {'id': 'strong', 'max_level': 'EXTRA_HIGH', 'efforts': ['xhigh'], 'cost_rank': 2}]}
        for name, description in [('a', 'Add authentication'), ('sql', 'Apply SQL migration')]:
            if name != 'a':
                self.add(name)
            unit = next(unit for unit in self.plan['prs'] if unit['id'] == name)
            unit['reason'] = description
        high = self.add('high')
        high['routing'] = {'complexity': 'high'}
        self.write()
        scheduler = SCHEDULER.Scheduler(self.manifest, self.repo, self.path, models=models)
        for name in ('a', 'sql', 'high'):
            task = scheduler.prepare(name)
            self.assertEqual(task['model_requested']['model'], 'strong')
        state = scheduler.resume()
        self.assertEqual(state['tasks']['a']['model_routing']['level'], 'EXTRA_HIGH')
        self.assertEqual(state['tasks']['sql']['model_routing']['level'], 'EXTRA_HIGH')
        self.assertEqual(state['tasks']['high']['model_routing']['level'], 'HIGH')

    def test_dispatch_loads_selected_skills_before_callback(self):
        skill = self.root / 'SKILL.md'
        skill.write_text('---\nname: tests\ndescription: Testing\nagentic_tier: CORE\n---\nRead me.')
        scheduler = SCHEDULER.Scheduler(self.manifest, self.repo, self.path, skill_roots=[str(skill)])
        class Loaded(SimulatedAdapter):
            def launch(adapter, task):
                self.assertEqual(task['skills']['loaded'][0]['state'], 'LOADED')
                self.assertIn('Read me.', task['skill_instructions'][0]['instructions'])
                self.assertEqual(task['skills']['applied'], [])
                return super().launch(task)
        scheduler.dispatch(Loaded())

    def test_stale_acceptance_after_commit_waits_for_revalidation(self):
        self.add('b', ['a'])
        adapter = SimulatedAdapter()
        self.scheduler.dispatch(adapter)
        self.accept('a')
        (self.root / 'a' / 'a.py').write_text('changed\n')
        self.git('add', 'a.py', repo=self.root / 'a')
        self.git('commit', '-qm', 'after acceptance', repo=self.root / 'a')
        self.scheduler.dispatch(adapter)
        self.assertNotIn(('launch', 'b'), adapter.calls)
        self.assertEqual(self.scheduler.resume()['tasks']['b']['state'], 'BLOCKED')

    def test_accepted_parent_content_changes_invalidate_without_head_change(self):
        self.add('b', ['a'])
        for mode in ('untracked', 'tracked', 'staged'):
            with self.subTest(mode=mode):
                # Isolate the persisted graph for each content mutation.
                path = self.root / ('state-' + mode + '.json')
                scheduler = SCHEDULER.Scheduler(self.manifest, self.repo, path)
                tree = self.root / 'a'
                file = tree / 'a.py'
                file.write_text('initial-' + mode + '\n')
                if mode != 'untracked':
                    self.git('add', 'a.py', repo=tree)
                    self.git('commit', '-qm', 'in scope baseline', repo=tree)
                adapter = SimulatedAdapter()
                scheduler.dispatch(adapter)
                state = scheduler.resume()
                evidence = {'status': 'PASS', 'orchestrator_verified': True,
                            'source': 'fixture test result', 'criteria': ['verified'], 'tests': ['passed'],
                            'head': self.git('rev-parse', 'HEAD', repo=tree),
                            'snapshot': SCHEDULER.snapshot(tree), 'plan_sha256': state['plan_sha256']}
                scheduler.accept('a', evidence)
                file.write_text('changed after validation\n')
                if mode == 'staged':
                    self.git('add', 'a.py', repo=tree)
                self.assertEqual(self.git('rev-parse', 'HEAD', repo=tree), evidence['head'])
                state = scheduler.resume()
                self.assertFalse(state['tasks']['a']['accepted'])
                self.assertEqual(state['tasks']['b']['state'], 'BLOCKED')
                scheduler.dispatch(adapter)
                self.assertNotIn(('launch', 'b'), adapter.calls)
                with self.assertRaisesRegex(SCHEDULER.Blocked, 'content snapshot'):
                    scheduler.accept('a', evidence)

    def test_stale_parent_blocks_active_descendant_without_releasing(self):
        self.add('b', ['a'])
        self.scheduler.dispatch(SimulatedAdapter())
        self.accept('a')
        self.scheduler.prepare('b')
        self.receipt('b')
        owner = self.scheduler.resume()['tasks']['b']['owner']['id']
        (self.root / 'a' / 'a.py').write_text('parent changed\n')
        state = self.scheduler.resume()
        self.assertFalse(state['tasks']['a']['accepted'])
        self.assertEqual(state['tasks']['b']['state'], 'BLOCKED')
        self.assertTrue(state['tasks']['b']['active'])
        self.assertEqual(state['tasks']['b']['agent_id'], 'simulated-b')
        self.assertIn(owner, self.owners())
        adapter = SimulatedAdapter()
        self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])

    def test_author_word_does_not_trigger_auth_but_french_security_does(self):
        models = {'runtime_overrides': True, 'models': [
            {'id': 'cheap', 'max_level': 'MEDIUM', 'efforts': ['medium'], 'cost_rank': 1},
            {'id': 'strong', 'max_level': 'EXTRA_HIGH', 'efforts': ['xhigh'], 'cost_rank': 2}]}
        self.plan['prs'][0]['reason'] = 'Update author profile'
        other = self.add('b')
        other['reason'] = 'Sécuriser permissions et authentification'
        self.write()
        scheduler = SCHEDULER.Scheduler(self.manifest, self.repo, self.path, models=models)
        self.assertEqual(scheduler.prepare('a')['model_requested']['model'], 'cheap')
        self.assertEqual(scheduler.prepare('b')['model_routing']['level'], 'EXTRA_HIGH')

    def test_receipt_after_branch_change_blocks_observed_agent_without_stop(self):
        self.scheduler.prepare('a')
        self.git('switch', '-qc', 'feat/wrong', repo=self.root / 'a')
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'wrong branch'):
            self.receipt()
        task = self.scheduler.resume()['tasks']['a']
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertTrue(task['active'])
        self.assertEqual(task['agent_id'], 'simulated-a')
        self.assertEqual(len(self.owners()), 1)

    def test_receipt_after_committed_scope_change_blocks(self):
        self.scheduler.prepare('a')
        (self.root / 'a' / 'outside.py').write_text('outside\n')
        self.git('add', 'outside.py', repo=self.root / 'a')
        self.git('commit', '-qm', 'unexpected change', repo=self.root / 'a')
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'outside scope'):
            self.receipt()
        self.assertEqual(len(self.owners()), 1)

    def test_dispatch_rechecks_scope_after_skill_loading_before_launch(self):
        def change(task):
            self.git('switch', '-qc', 'feat/wrong', repo=self.root / 'a')
            return []
        adapter = SimulatedAdapter()
        with mock.patch.object(self.scheduler, '_load_skills', side_effect=change):
            state = self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(state['tasks']['a']['state'], 'BLOCKED')
        self.assertEqual(len(self.owners()), 1)

    def test_receipt_rejects_changed_assignment_even_in_scope(self):
        self.scheduler.prepare('a')
        (self.root / 'a' / 'a.py').write_text('early worker edit\n')
        self.git('add', 'a.py', repo=self.root / 'a')
        self.git('commit', '-qm', 'early edit', repo=self.root / 'a')
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'assignment content changed'):
            self.receipt()
        task = self.scheduler.resume()['tasks']['a']
        self.assertTrue(task['active'])
        self.assertEqual(task['state'], 'BLOCKED')
        self.assertEqual(len(self.owners()), 1)

    def test_missing_quality_blocks_instead_of_downgrading_snapshot(self):
        original = SCHEDULER.module
        with mock.patch.object(SCHEDULER, 'module',
                               side_effect=lambda name, optional=False:
                               None if name == 'quality' else original(name, optional)):
            with self.assertRaisesRegex(SCHEDULER.Blocked, 'Quality component not installed'):
                self.scheduler.prepare('a')
        self.assertEqual(self.owners(), {})

    def test_authentication_word_families_and_file_indicators_require_strong_model(self):
        models = {'runtime_overrides': True, 'models': [
            {'id': 'cheap', 'max_level': 'MEDIUM', 'efforts': ['medium'], 'cost_rank': 1},
            {'id': 'strong', 'max_level': 'EXTRA_HIGH', 'efforts': ['xhigh'], 'cost_rank': 2}]}
        objectives = [
            'Add authenticated API access', 'Ajouter une API authentifiée',
            'Add authorized API requests', 'Ajouter un accès autorisé',
            'Authenticate requests', 'Authentifier les appels',
            'Authorise API calls', 'API réservée aux utilisateurs autorisés',
            'Add login form', 'Implement sign-in flow', 'Validate OAuth tokens', 'Verify JWT claims']
        file_indicators = ['api/authenticated_access.py', 'api/authentifiee.py',
                           'api/authorized.py', 'api/autorise.py', 'api/login.py',
                           'api/sign_in.py', 'api/oauth2.py', 'api/jwt.py']
        cases = [('Update author profile', 'a.py', 'MEDIUM')]
        cases += [(objective, 'a.py', 'EXTRA_HIGH') for objective in objectives]
        cases += [('Add API endpoint', file, 'EXTRA_HIGH') for file in file_indicators]
        for index, (objective, file, expected) in enumerate(cases):
            with self.subTest(objective=objective, file=file):
                unit = self.plan['prs'][0]
                # Conservative inference overrides an explicit insufficient classification.
                unit.update(reason=objective, files=[file], routing={
                    'risk': 'low', 'complexity': 'simple', 'type': 'implementation'})
                self.write()
                scheduler = SCHEDULER.Scheduler(self.manifest, self.repo,
                                                self.root / ('case-' + str(index) + '.json'),
                                                models=models)
                task = scheduler.prepare('a')
                self.assertEqual(task['model_routing']['level'], expected)
                self.assertEqual(task['model_requested']['model'],
                                 'cheap' if expected == 'MEDIUM' else 'strong')
                # No runtime was launched; confirm the unused assignment stopped.
                scheduler.handoff('a', {'agent_id': None, 'identity_verified': True,
                                       'stopped_confirmed': True, 'outcome': 'BLOCKED',
                                       'result': 'routing fixture; no runtime started'})

    def test_failed_attempt_stop_fix_requeue_dispatch_preserves_history(self):
        self.scheduler.dispatch(SimulatedAdapter({'a': 'BLOCKED'}))
        prior = self.scheduler.resume()['tasks']['a']
        (self.root / 'a' / 'a.py').write_text('corrected implementation\n')
        evidence = self.requeue_evidence()
        queued = self.scheduler.requeue('a', evidence)
        self.assertEqual(queued['state'], 'PLANNED')
        self.assertIsNone(queued['agent_id'])
        self.assertEqual(queued['history'][0]['task']['result'], prior['result'])
        self.assertEqual(queued['history'][0]['task']['agent_id'], 'simulated-a')
        self.assertEqual(queued['history'][0]['requeue'], evidence)
        self.assertEqual(self.owners(), {})
        class Retry(SimulatedAdapter):
            def launch(self, task):
                observation = super().launch(task)
                observation['agent_id'] = 'simulated-retry-a'
                return observation
        adapter = Retry()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(state['tasks']['a']['state'], 'COMPLETED')
        self.assertEqual(state['tasks']['a']['agent_id'], 'simulated-retry-a')
        self.assertEqual(len(state['tasks']['a']['history']), 1)
        self.assertEqual(adapter.calls, [('launch', 'a'), ('wait', 'a')])

    def test_descendant_requires_explicit_requeue_after_fresh_parent_acceptance(self):
        self.add('b', ['a'])
        self.scheduler.dispatch(SimulatedAdapter({'a': 'BLOCKED'}))
        self.scheduler.dispatch(SimulatedAdapter())  # Propagate the failed parent.
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'dependencies not completed'):
            self.scheduler.requeue('b', self.requeue_evidence('b'))
        self.scheduler.requeue('a', self.requeue_evidence())
        self.scheduler.dispatch(SimulatedAdapter())
        self.assertEqual(self.scheduler.resume()['tasks']['b']['state'], 'BLOCKED')
        self.accept('a')
        queued = self.scheduler.requeue('b', self.requeue_evidence('b'))
        self.assertIsNone(queued['history'][0]['task']['agent_id'])
        adapter = SimulatedAdapter()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(state['tasks']['b']['state'], 'COMPLETED')
        self.assertEqual(adapter.calls, [('launch', 'b'), ('wait', 'b')])

    def test_requeue_refuses_active_runtime_and_unknown_launch(self):
        class Unknown(SimulatedAdapter):
            def launch(self, task):
                raise TimeoutError('launch identity unavailable')
        self.scheduler.dispatch(Unknown())
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'runtime stop must be known'):
            self.scheduler.requeue('a', self.requeue_evidence())
        self.assertEqual(len(self.owners()), 1)
        self.handoff(agent_id=None, outcome='BLOCKED')
        self.scheduler.requeue('a', self.requeue_evidence())
        self.scheduler.prepare('a')
        self.receipt()
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'requeue requires blocked'):
            self.scheduler.requeue('a', self.requeue_evidence())
        self.assertEqual(len(self.owners()), 1)

    def test_requeue_never_releases_owner_even_when_no_runtime_started(self):
        with mock.patch.object(self.scheduler, '_load_skills', side_effect=ValueError('read failed')):
            self.scheduler.dispatch(SimulatedAdapter())
        self.assertIs(self.scheduler.resume()['tasks']['a']['active'], False)
        owners = self.owners()
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'reservation must be released'):
            self.scheduler.requeue('a', self.requeue_evidence())
        self.assertEqual(self.owners(), owners)

    def test_requeue_refuses_accepted_execution_and_wrong_identity_or_evidence(self):
        self.scheduler.dispatch(SimulatedAdapter({'a': 'BLOCKED'}))
        for extras, message in [({'agent_id': 'wrong'}, 'coherent runtime identity'),
                                ({'stopped_confirmed': False}, 'verified stop'),
                                ({'proof': ''}, 'proof required'),
                                ({'orchestrator_verified': False}, 'orchestrator-verified'),
                                ({'snapshot': {}}, 'stale requeue content'),
                                ({'plan_sha256': 'stale'}, 'stale requeue plan')]:
            with self.subTest(extras=extras):
                with self.assertRaisesRegex(SCHEDULER.Blocked, message):
                    self.scheduler.requeue('a', self.requeue_evidence(**extras))
        self.scheduler.requeue('a', self.requeue_evidence())
        self.scheduler.dispatch(SimulatedAdapter())
        self.accept()
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'unaccepted completed'):
            self.scheduler.requeue('a', self.requeue_evidence())

    def test_requeue_rechecks_branch_and_committed_scope(self):
        self.scheduler.dispatch(SimulatedAdapter({'a': 'BLOCKED'}))
        self.git('switch', '-qc', 'feat/wrong', repo=self.root / 'a')
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'wrong branch'):
            self.scheduler.requeue('a', self.requeue_evidence())
        self.git('switch', '-q', 'feat/a', repo=self.root / 'a')
        (self.root / 'a' / 'outside.py').write_text('out of scope\n')
        self.git('add', 'outside.py', repo=self.root / 'a')
        self.git('commit', '-qm', 'out of scope', repo=self.root / 'a')
        with self.assertRaisesRegex(SCHEDULER.Blocked, 'outside scope'):
            self.scheduler.requeue('a', self.requeue_evidence())
        self.assertEqual(self.owners(), {})

    def test_cli_requeue_before_launch_requires_no_fictitious_runtime_identity(self):
        self.plan['prs'][0]['branch'] = 'feat/wrong'
        self.write()
        self.scheduler.resume()
        self.plan['prs'][0]['branch'] = 'feat/a'
        self.write()
        evidence = self.requeue_evidence()
        for key in ('agent_id', 'identity_verified', 'stopped_confirmed'):
            evidence.pop(key)
        observation = self.root / 'requeue.json'
        observation.write_text(json.dumps(evidence))
        result = subprocess.run(['python3', str(SCRIPT), 'requeue', str(self.manifest),
                                 '--repo', str(self.repo), '--state', str(self.path), '--pr', 'a',
                                 '--observation', str(observation)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        task = json.loads(result.stdout)['result']
        self.assertEqual(task['state'], 'PLANNED')
        self.assertIsNone(task['history'][0]['task']['agent_id'])
        self.assertEqual(self.owners(), {})

    def historical_parent(self, integrated=True):
        self.add('b', ['a'])
        tree = self.root / 'a'
        (tree / 'a.py').write_text('delivered parent\n')
        self.git('add', 'a.py', repo=tree)
        self.git('commit', '-qm', 'historical parent', repo=tree)
        merged = self.git('rev-parse', 'HEAD', repo=tree)
        if integrated:
            self.git('merge', '--ff-only', 'feat/a')
        self.git('worktree', 'remove', str(tree))
        self.plan['prs'][0]['merged_commit'] = merged
        self.write()
        return merged

    def test_historical_merged_parent_without_worktree_allows_child(self):
        merged = self.historical_parent()
        adapter = SimulatedAdapter()
        state = self.scheduler.dispatch(adapter)
        parent = state['tasks']['a']
        self.assertEqual(parent['state'], 'INTEGRATED')
        self.assertEqual(parent['runtime'], 'historical')
        self.assertIsNone(parent['agent_id'])
        self.assertNotIn('launched_at', parent)
        self.assertEqual(parent['historical']['merged_commit'], merged)
        self.assertEqual(parent['historical']['verify'], 'NOT_OBSERVED')
        self.assertEqual(parent['blockers'], [])
        self.assertEqual(adapter.calls, [('launch', 'b'), ('wait', 'b')])
        self.assertEqual(state['tasks']['b']['state'], 'COMPLETED')
        self.assertEqual(self.scheduler.resume()['tasks']['a']['state'], 'INTEGRATED')

    def test_historical_unknown_or_unintegrated_commit_cannot_dispatch_child(self):
        self.historical_parent(integrated=False)
        adapter = SimulatedAdapter()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(state['tasks']['a']['state'], 'BLOCKED')
        self.assertFalse(state['tasks']['a']['integration_proven'])
        self.plan['prs'][0]['merged_commit'] = 'f' * 40
        self.write()
        state = self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])
        self.assertFalse(state['tasks']['a']['integration_proven'])

    def test_historical_ancestry_rechecked_and_active_child_keeps_owner(self):
        base = self.git('rev-parse', 'HEAD')
        merged = self.historical_parent()
        self.git('branch', 'delivery', merged)
        self.plan['target'] = 'delivery'
        self.write()
        self.scheduler.prepare('b')
        self.receipt('b')
        owner = self.scheduler.resume()['tasks']['b']['owner']['id']
        # Move only a disposable fixture target; the delivered commit still exists.
        self.git('update-ref', 'refs/heads/delivery', base)
        state = self.scheduler.resume()
        self.assertEqual(state['tasks']['a']['state'], 'BLOCKED')
        self.assertFalse(state['tasks']['a']['integration_proven'])
        self.assertEqual(state['tasks']['b']['state'], 'BLOCKED')
        self.assertTrue(state['tasks']['b']['active'])
        self.assertIn(owner, self.owners())
        adapter = SimulatedAdapter()
        self.scheduler.dispatch(adapter)
        self.assertEqual(adapter.calls, [])

    def test_explicit_target_proves_merge_outside_orchestration_head(self):
        merged = self.historical_parent(integrated=False)
        self.git('branch', 'delivery', merged)
        self.plan['target'] = 'delivery'
        self.write()
        state = self.scheduler.dispatch(SimulatedAdapter())
        self.assertEqual(state['tasks']['a']['state'], 'INTEGRATED')
        self.assertEqual(state['tasks']['b']['state'], 'COMPLETED')


if __name__ == '__main__':
    unittest.main()
