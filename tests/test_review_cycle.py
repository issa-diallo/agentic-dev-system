"""#88: bounded, independent review and explicit corrections; local fake CLIs only."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

import test_missions as missions
import test_analysis as analyses

RUN = missions.RUN

CLI = r'''
import json, os, re, sys
from pathlib import Path
root, name, args = Path(__file__).parent, Path(__file__).name, sys.argv[1:]
if args[:2] in (['auth', 'status'], ['login', 'status']):
    if name == 'codex':
        print('Logged in using ChatGPT', file=sys.stderr)
    else:
        print(json.dumps({'loggedIn':True,'authMethod':'claude.ai',
                          'apiProvider':'firstParty','subscriptionType':'pro'}))
    sys.exit(0)
tree = Path(args[args.index('-C') + 1]) if name == 'codex' else Path.cwd()
prompt = args[-1] if name == 'codex' else args[args.index('-p') + 1]
role = re.search(r'Rôle : ([\w-]+)', prompt).group(1)
mode = (root / 'mode').read_text().strip()
with (root / 'events').open('a') as stream:
    stream.write(json.dumps({'event':'launch','role':role,'provider':name,
                            'prompt':prompt,'argv':args,'pid':os.getpid()}) + '\n')
reply = {'status':'COMPLETED','summary':'fake only','files':[],'blockers':[]}
if role == 'test-author':
    (tree / 'test_a.py').write_text('import unittest, a\nclass T(unittest.TestCase):\n'
                                  '    def test_RM1(self):\n        self.assertEqual(a.VALUE, 1)\n')
elif role == 'implementer':
    (tree / 'a.py').write_text('VALUE = 1\n' + ('# corrected\n' if mode == 'corrected' else ''))
elif role == 'reviewer':
    if mode == 'quota' and name == 'claude':
        print('usage limit reached', file=sys.stderr)
        sys.exit(1)
    reply['review'] = {'verdict':'PASS','findings':[]}
    if mode in ('major','critical'):
        reply['review']['findings'] = [{'severity':mode.title(),'message':'a.py:1 missing AC2 guard'}]
    if mode == 'review-missing':
        reply.pop('review')
text = '```handoff\n' + json.dumps(reply) + '\n```'
if name == 'claude':
    print(json.dumps({'type':'result','result':text,'session_id':'cli-' + str(os.getpid()),
                      'modelUsage':{'claude-review':{}}}))
else:
    print(text)
'''


class ReviewCycleTests(unittest.TestCase):
    setUp = missions.MissionTests.setUp
    git, mode, events, roles = missions.MissionTests.git, missions.MissionTests.mode, missions.MissionTests.events, missions.MissionTests.roles
    assert_blocked = missions.MissionTests.assert_blocked

    def configure(self, cross=False, **settings):
        for name in ('codex', 'claude'):
            executable = self.root / name
            executable.write_text('#!' + sys.executable + '\n' + CLI)
            executable.chmod(0o755)
        for entry in self.config['models']:
            entry['provider'] = 'openai'
        self.config['models'].append({'id':'claude-review','harness':'claude','provider':'anthropic',
                                     'model':'claude-review','max_level':'HIGH','efforts':['high'],
                                     'cost_rank':3})
        self.config['routing_policy']['rules'][-1]['prefer'] = [
            {'model':'reviewer'}, {'model':'claude-review'}]
        self.config['run'].update(subscription_only=True, review_cycle={
            'enabled':True,'max_attempts':7,'max_corrections':2,'max_cost_rank':3,
            'prefer_cross_provider':cross,
            **({'justification':'An independent supplier helps validate the contract'} if cross else {}),
            **settings})
        # Subscription tests must not inspect the developer's real account/configuration.
        home = self.root / 'home'
        home.mkdir(exist_ok=True)
        self.environ.stop()
        self.environ = mock.patch.dict(os.environ, {
            'PATH':str(self.root) + os.pathsep + os.environ['PATH'], 'HOME':str(home),
            'PYTHONDONTWRITEBYTECODE':'1'}, clear=True)
        self.environ.start()
        managed = mock.patch.object(RUN, 'CLAUDE_MANAGED_DIR', self.root / 'managed')
        managed.start()
        self.addCleanup(managed.stop)

    def delegate(self):
        return missions.MissionTests.delegate(self)

    def task(self):
        return json.loads(self.state.read_text())['tasks']['example']

    def scheduler(self):
        return RUN.module('scheduler').Scheduler(
            self.manifest, self.repo, self.state, models=RUN.build_inventory(self.config)[0],
            routing_policy=self.config['routing_policy'], missions=True,
            review_cycle=RUN.review_cycle_settings(self.config),
            execution_context={'config':self.config,
                               'commands':[[sys.executable,str(self.verify)]]})

    def evidence(self, **extra):
        task = self.task()
        return {'orchestrator_verified':True,'reason':'Correct the exact blocking finding',
                'proof':'AC2 reviewed against a.py:1', 'plan_sha256':task['plan_sha256'],
                'agent_id':task['agent_id'],'stopped_confirmed':True,'identity_verified':True,
                'head':self.git('rev-parse','HEAD',repo=self.tree),
                'snapshot':RUN.module('quality').snapshot(self.tree),
                'diagnosis_kind':'implementation','diagnosis':'The AC2 guard is missing at a.py:1',
                **extra}

    def test_AC1_RM1_same_provider_distinct_sessions_and_observed_unknown_model(self):
        self.configure()
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        review = report['example']['review_identity']
        self.assertNotEqual(review['author']['session_id'], review['reviewer']['session_id'])
        self.assertIsNone(review['author']['observed']['model'])
        self.assertIsNone(review['reviewer']['observed']['model'])
        self.assertFalse(review['cross_provider'])

    def test_AC1_RM1_cross_provider_with_complete_readonly_inline_context(self):
        self.configure(cross=True)
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report, False), report)
        event = next(e for e in self.events() if e.get('role') == 'reviewer')
        self.assertEqual(event['provider'], 'claude')
        self.assertEqual(event['argv'][event['argv'].index('--tools') + 1], '')
        self.assertIn('--bare',event['argv'])
        self.assertNotIn('acceptEdits',event['argv'])
        self.assertIn('VALUE = 1',event['prompt'])
        self.assertIn('test_RM1',event['prompt'])
        identity = report['example']['review_identity']
        self.assertTrue(identity['cross_provider'])
        self.assertEqual(identity['reviewer']['observed']['model'],'claude-review')

    def test_AC2_RM2_findings_require_explicit_correction_verify_and_fresh_review(self):
        self.configure()
        self.mode('major')
        self.assert_blocked(self.delegate())
        self.assertFalse(self.task().get('mission_complete',False))
        self.scheduler().request_correction('example',self.evidence())
        self.assertNotIn('verify_evidence',self.task())
        self.mode('corrected')
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        self.assertEqual(self.roles(),['test-author','implementer','reviewer','implementer','reviewer'])
        correction = [e for e in self.events() if e.get('role') == 'implementer'][-1]
        self.assertIn('a.py:1 missing AC2 guard',correction['prompt'])
        latest_review = max(i for i,e in enumerate(self.events()) if e.get('role') == 'reviewer')
        self.assertTrue(any(e.get('event') == 'verify' for e in self.events()[
            self.events().index(correction) + 1:latest_review]))
        self.assertEqual(self.task()['corrections'],1)

    def test_AC2_RM2_critical_blocks_even_with_pass_verdict(self):
        self.configure()
        self.mode('critical')
        self.assert_blocked(self.delegate())
        events = self.events()
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(),events)

    def test_AC2_RM2_committed_revision_keeps_original_diff_base(self):
        self.configure()
        self.mode('major')
        self.assert_blocked(self.delegate())
        self.git('add','a.py','test_a.py',repo=self.tree)
        self.git('commit','-qm','fixture revision',repo=self.tree)
        head = self.git('rev-parse','HEAD',repo=self.tree)
        self.scheduler().request_correction('example',self.evidence())
        self.mode('corrected')
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        self.assertEqual(self.task()['verify_evidence']['base'],self.initial)
        self.assertEqual(self.task()['verify_evidence']['snapshot']['head'],head)
        self.assertIn('test_a.py',self.task()['verify_evidence']['changed'])

    def test_AC2_RM2_stale_correction_evidence_and_mutated_locked_tests_rejected(self):
        self.configure()
        self.mode('major')
        self.assert_blocked(self.delegate())
        evidence = self.evidence()
        (self.tree / 'a.py').write_text('VALUE = 1\n# new content\n')
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',evidence)
        (self.tree / 'test_a.py').write_text('raise RuntimeError("changed expectation")\n')
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence())

    def test_AC3_RM3_escalation_requires_capacity_diagnosis_and_budget(self):
        self.configure()
        self.mode('major')
        self.assert_blocked(self.delegate())
        override={'model':'reviewer','effort':'high'}
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence(routing_override=override))
        self.scheduler().request_correction('example',self.evidence(
            routing_override=override,diagnosis_kind='capacity',
            diagnosis='The implementer failed to reason about AC2 after concrete guard reproduction'))
        self.mode('corrected')
        self.assertTrue(RUN.succeeded(self.delegate(),False))
        requested = [h['task'] for h in self.task()['mission_history']
                     if h['task']['role'] == 'implementer'][-1]['model_requested']
        self.assertEqual(requested,override)

    def test_AC3_RM3_attempt_limit_survives_reentry_and_requeue(self):
        self.configure(max_attempts=3)
        self.mode('major')
        self.assert_blocked(self.delegate())
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence())
        events = self.events()
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(),events)

    def test_AC3_RM3_correction_limit_and_blank_diagnosis_rejected(self):
        self.configure(max_corrections=0)
        self.mode('major')
        self.assert_blocked(self.delegate())
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence())
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence(diagnosis=''))

    def test_AC3_RM3_budget_filters_reviewer_and_forbids_override_outside_budget(self):
        self.configure(max_cost_rank=1)
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(),['test-author','implementer'])

    def test_AC4_RM4_quota_blocks_without_new_review_or_api_fallback(self):
        self.configure(cross=True)
        self.mode('quota')
        self.assert_blocked(self.delegate())
        launches=[e for e in self.events() if e['event']=='launch']
        self.assertEqual([e['provider'] for e in launches],['codex','codex','claude'])
        events=self.events()
        self.assert_blocked(self.delegate())
        self.assertEqual(self.events(),events)
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence())

    def test_AC4_RM4_option_is_strict_and_cross_preference_needs_justification(self):
        self.configure(cross=True)
        for invalid in ({'enabled':True}, {'enabled':True,'max_attempts':True},
                        {**self.config['run']['review_cycle'],'justification':''},
                        {**self.config['run']['review_cycle'],'unknown':1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                RUN.review_cycle_settings({'run':{'review_cycle':invalid}})
        self.assertEqual(self.roles(),[])

    def test_AC1_RM1_unavailable_alternative_and_unknown_provider_are_explicit(self):
        self.configure(cross=True)
        self.config['models'][-1]['available'] = False
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        selection = self.task()['model_routing']['review_selection']
        self.assertFalse(selection['alternative_available'])
        self.assertTrue(selection['reason'])
        self.assertFalse(report['example']['review_identity']['cross_provider'])

    def test_AC1_RM1_unknown_author_provider_is_not_inferred_from_model_name(self):
        self.configure(cross=True)
        self.config['models'][1].pop('provider')
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        self.assertFalse(report['example']['review_identity']['cross_provider'])
        self.assertFalse(self.task()['model_routing']['review_selection']['alternative_available'])

    def test_AC1_RM1_explicit_override_is_not_replaced_by_cross_preference(self):
        self.configure(cross=True)
        self.plan['prs'][0]['routing'] = {'routing_override':{'model':'reviewer','effort':'high'}}
        self.manifest.write_text(json.dumps(self.plan))
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        self.assertEqual(self.task()['model_requested']['model'],'reviewer')
        self.assertFalse(report['example']['review_identity']['cross_provider'])

    def test_AC2_RM2_changed_plan_cannot_be_rehabilitated_by_correction(self):
        self.configure()
        self.mode('major')
        self.assert_blocked(self.delegate())
        self.plan['prs'][0]['acceptance'].append('AC2 changed')
        self.manifest.write_text(json.dumps(self.plan))
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence())
        self.assertEqual(self.roles(),['test-author','implementer','reviewer'])

    def test_AC2_RM2_stale_verify_does_not_launch_a_reviewer(self):
        self.configure()
        scheduler_module = RUN.module('scheduler')
        original, original_module = scheduler_module.Scheduler.finish_mission, RUN.module
        def stale(scheduler, pr, gate):
            result = original(scheduler,pr,gate)
            if result.get('role') == 'implementer' and result['state'] == 'PLANNED':
                (self.tree / 'a.py').write_text('VALUE = 1\n# changed after Verify\n')
            return result
        with mock.patch.object(RUN,'module',side_effect=lambda name: (
                scheduler_module if name == 'scheduler' else original_module(name))):
            with mock.patch.object(scheduler_module.Scheduler,'finish_mission',stale):
                self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(),['test-author','implementer'])

    def test_AC3_RM3_effort_only_override_also_needs_capacity_diagnosis(self):
        self.configure()
        self.config['models'][1]['efforts'].append('high')
        self.mode('major')
        self.assert_blocked(self.delegate())
        with self.assertRaises(ValueError):
            self.scheduler().request_correction('example',self.evidence(
                routing_override={'model':'implementer','effort':'high'}))
        self.assertEqual(self.task().get('corrections',0),0)

    def test_AC3_RM3_out_of_budget_override_rejected_before_transition(self):
        self.configure()
        self.config['models'].append({'id':'expensive','harness':'codex','model':'expensive',
                                     'max_level':'HIGH','efforts':['high'],'cost_rank':99})
        self.mode('major')
        self.assert_blocked(self.delegate())
        scheduler = self.scheduler()
        with self.assertRaises(ValueError):
            scheduler.request_correction('example',self.evidence(
                routing_override={'model':'expensive','effort':'high'},diagnosis_kind='capacity'))
        self.assertEqual(self.task().get('corrections',0),0)

    def test_AC3_RM3_requeue_does_not_reset_attempt_budget(self):
        self.configure(max_attempts=3)
        self.mode('review-missing')
        self.assert_blocked(self.delegate())
        self.scheduler().requeue('example',self.evidence())
        self.mode('ok')
        self.assert_blocked(self.delegate())
        self.assertEqual(self.task()['attempts_used'],3)
        self.assertEqual(self.roles(),['test-author','implementer','reviewer'])

    def test_AC1_RM1_same_model_in_distinct_sessions_is_valid(self):
        self.configure()
        self.config['routing_policy']['rules'][1]['prefer'] = [{'model':'reviewer'}]
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        identity = report['example']['review_identity']
        self.assertEqual(identity['author']['requested'],identity['reviewer']['requested'])
        self.assertNotEqual(identity['author']['session_id'],identity['reviewer']['session_id'])

    def test_AC1_RM1_cross_provider_cannot_reuse_observed_writer_cli_session(self):
        self.configure(cross=True)
        original = RUN.ProcessAdapter.wait
        writer = {}
        def reused(adapter, task):
            observation = original(adapter,task)
            if task['role'] == 'implementer':
                observation['model_execution']['cli_session_id'] = 'reused-cli'
            elif task['role'] == 'reviewer':
                observation['model_execution']['cli_session_id'] = 'reused-cli'
            return observation
        with mock.patch.object(RUN.ProcessAdapter,'wait',reused):
            self.assert_blocked(self.delegate())
        self.assertIn('review reused a writer CLI session',self.task()['blockers'])

    def test_AC2_RM2_requeue_cannot_skip_correction_of_blocking_findings(self):
        self.configure()
        self.mode('major')
        self.assert_blocked(self.delegate())
        with self.assertRaises(ValueError):
            self.scheduler().requeue('example',self.evidence())
        self.assertEqual(self.task()['attempts_used'],3)

    def test_AC3_RM3_capacity_attempts_are_scoped_to_their_role(self):
        self.configure()
        self.config['models'][1].update(max_level='EXTRA_HIGH',efforts=['medium','high','xhigh'])
        RUN.record_attempt(self.repo,{'task_id':'example:implementer','outcome':'FAIL','level':'HIGH',
            'diagnosis_kind':'capacity','diagnosis':'AC2 reasoning failed at HIGH on a reproduced guard'})
        report=self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        histories=self.task()['mission_history']
        writer=next(h['task'] for h in histories if h['task']['role']=='implementer')
        self.assertEqual(writer['model_requested']['effort'],'xhigh')
        self.assertEqual(self.task()['model_requested']['effort'],'high')

    def test_AC3_RM3_unscoped_attempt_history_is_not_silently_reinterpreted(self):
        self.configure()
        RUN.record_attempt(self.repo,{'task_id':'example','outcome':'FAIL','level':'MEDIUM',
            'diagnosis_kind':'capacity','diagnosis':'Concrete writer failure with unspecified role'})
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(),[])

    def ignored_context_attempt(self, exists):
        self.configure(cross=True)
        name = 'ignored-context.txt'
        self.plan['prs'][0]['files'].append(name)
        self.manifest.write_text(json.dumps(self.plan))
        ignored = self.tree / name
        if exists:
            ignored.write_text('safe initial context')
        exclude = Path(self.git('rev-parse','--git-common-dir',repo=self.tree)) / 'info/exclude'
        with exclude.open('a') as stream:
            stream.write('\n' + name + '\n')
        scheduler_module = RUN.module('scheduler')
        brief_module = scheduler_module.module('brief')
        original_context = brief_module.review_context
        original_run_module, original_scheduler_module = RUN.module, scheduler_module.module
        observed = {'called':False,'mutated':False}
        def mutate_after_bundle(*args):
            observed['called'] = True
            context = original_context(*args)
            ignored.write_text('changed after context bundle')
            observed['mutated'] = True
            return context
        with mock.patch.object(RUN,'module',side_effect=lambda name: (
                scheduler_module if name == 'scheduler' else original_run_module(name))):
            with mock.patch.object(scheduler_module,'module',side_effect=lambda name,optional=False: (
                    brief_module if name == 'brief' else original_scheduler_module(name,optional))):
                with mock.patch.object(brief_module,'review_context',mutate_after_bundle):
                    report = self.delegate()
        self.assert_blocked(report)
        self.assertTrue(observed['called'])
        self.assertFalse(observed['mutated'])
        self.assertEqual(self.roles(),['test-author','implementer'])
        self.assertIn('ignored untracked review source',json.dumps(report))

    def test_AC2_RM2_ignored_untracked_source_cannot_mutate_after_context_bundle(self):
        self.ignored_context_attempt(exists=True)

    def test_AC2_RM2_absent_ignored_source_cannot_be_created_after_context_bundle(self):
        self.ignored_context_attempt(exists=False)

    def test_AC2_RM2_tracked_source_is_allowed_even_when_ignore_pattern_matches(self):
        self.configure(cross=True)
        exclude = Path(self.git('rev-parse','--git-common-dir',repo=self.tree)) / 'info/exclude'
        with exclude.open('a') as stream:
            stream.write('\na.py\n')
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        event = next(e for e in self.events() if e.get('role') == 'reviewer')
        self.assertIn('VALUE = 1',event['prompt'])
        self.assertIn('test_RM1',event['prompt'])  # A new non-ignored source is still supplied.

    def test_AC2_RM2_deleted_tracked_source_stays_in_review_diff(self):
        self.configure(cross=True)
        retired = self.tree / 'retired.txt'
        retired.write_text('retired source line\n')
        self.git('add','retired.txt',repo=self.tree)
        self.git('commit','-qm','tracked source fixture',repo=self.tree)
        retired.unlink()
        self.plan['prs'][0]['files'].append('retired.txt')
        self.manifest.write_text(json.dumps(self.plan))
        report = self.delegate()
        self.assertTrue(RUN.succeeded(report,False),report)
        event = next(e for e in self.events() if e.get('role') == 'reviewer')
        self.assertIn('-retired source line',event['prompt'])

    def test_AC4_RM4_large_inline_context_blocks_instead_of_truncating(self):
        self.configure()
        self.plan['prs'][0]['files'].append('large.txt')
        self.manifest.write_text(json.dumps(self.plan))
        (self.tree / 'large.txt').write_text('x' * 100_001)
        self.assert_blocked(self.delegate())
        self.assertEqual(self.roles(),['test-author','implementer'])

    def test_AC4_RM4_absent_or_disabled_keeps_existing_flow(self):
        self.configure()
        self.config['run']['review_cycle']={'enabled':False}
        self.assertTrue(RUN.succeeded(self.delegate(),False))
        self.assertNotIn('review_identity',self.delegate()['example'])


class CombinedReviewCycleTests(unittest.TestCase):
    setUp = analyses.DualAnalysisTests.setUp
    git = analyses.DualAnalysisTests.git
    delegate = analyses.DualAnalysisTests.delegate
    events = analyses.DualAnalysisTests.events

    def test_AC4_RM4_review_cycle_composes_with_optional_dual_analysis(self):
        for entry in self.config['models']:
            entry['provider'] = {'codex':'openai','claude':'anthropic'}[entry['harness']]
        self.config['run']['review_cycle'] = {
            'enabled':True,'max_attempts':7,'max_corrections':1,'max_cost_rank':1,
            'prefer_cross_provider':True,'justification':'Confront the prepared contract'}
        report=self.delegate()
        self.assertTrue(analyses.RUN.succeeded(report,False),report)
        self.assertEqual([event['role'] for event in self.events()],
                         ['explorer','explorer','test-author','implementer','reviewer'])
        self.assertEqual(self.events()[-1]['provider'],'claude')
        self.assertTrue(report['example']['review_identity']['cross_provider'])
