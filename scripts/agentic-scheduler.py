#!/usr/bin/env python3
"""Cooperative scheduler. Runtime identities are observed by a trusted adapter.

No host tools or manifest shell commands are executed here. COMPLETED means an
execution handoff, not reviewed/merged. CLI attestations do not authenticate users.
"""
import argparse
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
import unicodedata
import uuid


def module(name, optional=False):
    path = Path(__file__).with_name('agentic-' + name + '.py')
    if optional and not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('scheduler_' + name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


BUILD, WORKSPACE = module('build'), module('workspace')
Blocked = BUILD.Blocked
require = BUILD._CHECK.require
STATES = {'PLANNED', 'ASSIGNED', 'RUNNING', 'COMPLETED', 'BLOCKED', 'INTEGRATED'}
AUTH_TERMS = (r'\b(auth|authent(?:icat|ifi)\w*|authori[sz]\w*|autoris\w*|'
              r'permissions?|tenants?|secrets?|security|secure|securite|securis\w*|'
              r'login|log[- ]?in|sign[- ]?in|oauth2?|jwt)\b')


def review_cycle_settings(raw):
    """An explicit launch/correction budget, never a monetary or quota estimate."""
    if raw is None:
        return {'enabled': False}
    allowed = {'enabled', 'max_attempts', 'max_corrections', 'max_cost_rank',
               'prefer_cross_provider', 'justification'}
    require(isinstance(raw, dict) and not set(raw) - allowed, 'invalid run.review_cycle fields')
    require(type(raw.get('enabled')) is bool, 'review_cycle.enabled must be boolean')
    if not raw['enabled']:
        return {'enabled': False}
    for key, minimum in (('max_attempts', 1), ('max_corrections', 0)):
        require(type(raw.get(key)) is int and raw[key] >= minimum,
                'review_cycle.' + key + ' requires an explicit integer budget')
    rank = raw.get('max_cost_rank')
    require(type(rank) in (int, float) and math.isfinite(rank) and rank >= 0,
            'review_cycle.max_cost_rank requires an explicit finite relative budget')
    require(type(raw.get('prefer_cross_provider', False)) is bool,
            'review_cycle.prefer_cross_provider must be boolean')
    if raw.get('prefer_cross_provider'):
        require(isinstance(raw.get('justification'), str) and raw['justification'].strip(),
                'cross-provider preference requires quota justification')
    return {**raw, 'prefer_cross_provider': raw.get('prefer_cross_provider', False)}


def snapshot(repo):
    """Use the shared content proof; missing Quality cannot downgrade acceptance."""
    quality = module('quality', True)
    require(quality is not None, 'Quality component not installed; acceptance blocked')
    return quality.snapshot(repo)


def file_hashes(repo):
    """Content and mode of tracked/untracked files; ignored runtime files stay local."""
    entries = BUILD.git(repo, 'ls-files', '--stage', '-z').split(b'\0')
    require(not any(entry.startswith(b'160000 ') for entry in entries),
            'mission pipelines do not support gitlinks; reconcile before launch')
    names = BUILD.git(repo, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
    result = {}
    for raw in set(names.split(b'\0')) - {b''}:
        name = raw.decode('utf-8', 'surrogateescape')
        path = Path(repo) / name
        if not path.exists() and not path.is_symlink():
            continue
        data = os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        result[name] = [path.lstat().st_mode, hashlib.sha256(data).hexdigest()]
    return result


class Scheduler:
    def __init__(self, manifest, repo='.', state_path=None, *, skill_roots=(), models=None,
                 attempts=None, routing_policy=None, missions=False, execution_context=None,
                 double_analysis=None, analysis_models=None, review_cycle=None):
        self.manifest = Path(manifest).resolve()
        self.repo = WORKSPACE.root(repo)
        common = BUILD.common_dir(self.repo)
        namespace = hashlib.sha256(str(self.manifest).encode()).hexdigest()
        self.path = Path(state_path) if state_path else common / 'agentic-scheduler' / namespace / 'state.json'
        self.skill_roots, self.models, self.attempts = skill_roots, models, attempts
        self.routing_policy = routing_policy
        self.missions = missions
        self.review_cycle = review_cycle_settings(review_cycle)
        require(not self.review_cycle['enabled'] or missions, 'review cycle requires missions')
        self.double_analysis = double_analysis or {'enabled': False}
        self.analysis_models = analysis_models or {}
        fingerprint = ({'policy': routing_policy, 'missions': True, 'runtime': execution_context}
                       if missions else routing_policy)
        if self.review_cycle['enabled']:
            fingerprint = {'context': fingerprint, 'review_cycle': self.review_cycle}
        if self.double_analysis['enabled']:
            require(missions, 'double analysis requires the mission pipeline')
            fingerprint = {'context': fingerprint, 'double_analysis': self.double_analysis,
                           'analysis_models': self.analysis_models}
        self.routing_fingerprint = hashlib.sha256(
            json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()

    def _save(self, state):
        fd, temporary = tempfile.mkstemp(dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(state, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @contextmanager
    def _state(self):
        require(not self.path.parent.is_symlink(), 'symlink state directory refused')
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(str(self.path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            require(not self.path.is_symlink(), 'symlink state refused')
            state = json.loads(self.path.read_text()) if self.path.exists() else {
                'version': 1, 'manifest': str(self.manifest), 'repo': str(self.repo),
                'tasks': {}, 'events': []}
            require(state.get('version') == 1 and state.get('manifest') == str(self.manifest)
                    and state.get('repo') == str(self.repo), 'state belongs to another plan/repository')
            require(isinstance(state.get('tasks'), dict) and isinstance(state.get('events'), list),
                    'invalid scheduler state')
            require(all(isinstance(task, dict) and task.get('state') in STATES
                        for task in state['tasks'].values()), 'invalid task state')
            try:
                yield state
            finally:
                self._save(state)

    def _event(self, state, task, event):
        state['events'].append({'pr': task['unit']['id'], 'event': event,
                                'state': task['state'], 'time': time.time(),
                                'agent_id': task.get('agent_id'),
                                'plan_sha256': task.get('plan_sha256')})

    def _block(self, state, task, reason):
        task['state'] = 'BLOCKED'
        if reason not in task['blockers']:
            task['blockers'].append(reason)
            self._event(state, task, 'blocked')

    def _sync(self, state):
        plan = BUILD._CHECK.load_json(self.manifest)
        units, _ = BUILD._CHECK.check_plan(plan, self.repo)
        digest = BUILD._CHECK.plan_hash(plan)
        old = state.get('plan')
        changed = {key for key, task in state['tasks'].items()
                   if units.get(key) != task['unit']}
        if old and any(old.get(k) != plan.get(k) for k in set(old) | set(plan) if k != 'prs'):
            changed.update(state['tasks'])
        while True:
            descendants = {key for key, unit in units.items()
                           if set(unit['depends_on']) & changed}
            if descendants <= changed:
                break
            changed.update(descendants)
        for key, unit in units.items():
            if key not in state['tasks']:
                state['tasks'][key] = {'unit': unit, 'state': 'PLANNED', 'blockers': [],
                                       'plan_sha256': digest, 'agent_id': None, 'active': False}
                if self.missions:
                    tests = any(module('gates').TEST_PATH.search(path) for path in unit['files'])
                    state['tasks'][key].update(
                        mission_roles=(['test-author'] if tests else []) + ['implementer', 'reviewer'],
                        mission_index=0, mission_history=[], mission_complete=False)
            elif key not in changed and not state['tasks'][key].get('owner'):
                state['tasks'][key]['plan_sha256'] = digest
        changed.update(key for key, task in state['tasks'].items()
                       if task.get('routing_fingerprint', self.routing_fingerprint)
                       != self.routing_fingerprint)
        changed.update(key for key, task in state['tasks'].items()
                       if task.get('analysis_required') and task.get('analysis_bundle')
                       and (task['analysis_bundle']['plan_sha256'] != digest
                            or task['analysis_bundle'].get('routing_fingerprint')
                            != self.routing_fingerprint))
        for key in changed:
            if key in state['tasks']:
                task = state['tasks'][key]
                if task.get('analysis_required'):
                    task.setdefault('analysis_stale', 'analysis contract or routing context changed; '
                                    'explicit renewed analysis required')
                self._block(state, task, 'plan changed; revalidation required')
        state.update(plan=plan, plan_sha256=digest)
        self._historical(state, units)
        return units

    def _done(self, state):
        return [key for key, task in state['tasks'].items()
                if (task['state'] == 'COMPLETED' and task.get('accepted'))
                or (task['state'] == 'INTEGRATED' and task.get('integration_proven'))]

    def _historical(self, state, units):
        """Prove declared historical integration; never fabricate runtime/Verify."""
        invalidated = set()
        for pr, unit in units.items():
            if 'merged_commit' not in unit:
                continue
            task = state['tasks'][pr]
            try:
                require(task.get('active') is False and 'owner' not in task,
                        'historical integration cannot replace an active reservation')
                commit = unit['merged_commit']
                require(isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit),
                        'exact historical merged_commit required')
                merged = BUILD._CHECK.resolve(str(self.repo), commit)
                target_ref = state['plan'].get('target', 'HEAD')
                target = BUILD._CHECK.resolve(str(self.repo), target_ref)
                require(BUILD._CHECK.ancestor(str(self.repo), merged, target),
                        'historical merged_commit not integrated in target')
                proof = {'merged_commit': merged, 'target_ref': target_ref, 'target': target,
                         'source': 'manifest PR/SHA attestation plus observed Git ancestry',
                         'verify': 'NOT_OBSERVED'}
                if task.get('agent_id') is not None or task['blockers']:
                    previous = {key: value for key, value in task.items() if key != 'history'}
                    task.setdefault('history', []).append({'task': copy.deepcopy(previous),
                                                           'historical_import': proof})
                changed = task.get('historical') != proof or task['state'] != 'INTEGRATED'
                task.update(unit=unit, state='INTEGRATED', integration_proven=True, historical=proof,
                            runtime='historical', agent_id=None, active=False, accepted=False,
                            blockers=[], plan_sha256=state['plan_sha256'])
                if changed:
                    self._event(state, task, 'historical_integration_observed')
            except (ValueError, OSError) as error:
                task['integration_proven'] = False
                self._block(state, task, str(error))
                invalidated.add(pr)
        self._block_descendants(state, invalidated)

    def _classification(self, unit, delegation):
        classification = dict(unit.get('routing', {}))
        description = delegation['objective'] + ' ' + ' '.join(delegation['files'])
        description = ''.join(char for char in unicodedata.normalize('NFKD', description)
                              if not unicodedata.combining(char)).lower().replace('_', ' ')
        if re.search(AUTH_TERMS, description):
            classification.update(type='authentication', risk='security_critical')
        elif re.search(r'\b(migrations?|schema)\b|\.sql\b', description):
            classification.update(type='migration', risk='critical')
        elif re.search(r'\b(refactor|refactoring|architecture|cross.module)\b', description):
            classification.setdefault('complexity', 'high')
        return classification

    def _context(self, delegation, unit):
        skills, models = module('skills', True), module('models', True)
        brief = module('brief', True)
        classification = dict(unit.get('routing', {}))
        allowed = {'type', 'risk', 'complexity', 'role', 'phase', 'modalities',
                   'routing_override', 'session_id', 'implementer_session_id'}
        require(set(classification) <= allowed, 'invalid routing metadata')
        role, phase = classification.get('role', 'implementer'), classification.get('phase', 'BUILD')
        specialized = role != 'implementer' or phase != 'BUILD'
        routing_needed = (specialized or self.models is not None or self.routing_policy is not None
                          or bool(set(classification) - {'type', 'risk', 'complexity', 'role', 'phase'}))
        require(models is not None or not routing_needed, 'Models component required for routing')
        require(brief is not None or not specialized, 'Brief component required for specialized role')
        if models:
            require(role in models.SELECTORS['role'], 'unknown task role')
            require(phase in models.SELECTORS['phase'], 'unknown task phase')
        require(self.routing_policy is None or self.models is not None,
                'model inventory required for configured routing policy')
        delegation.update(role=role, phase=phase)
        context = {'role': role, 'phase': phase,
                   'read_only': role in brief.READ_ONLY_ROLES if brief else False,
                   'routing_fingerprint': self.routing_fingerprint,
                   'skills': {'selected': [], 'loaded': [], 'applied': []},
                   'model_requested': None}
        if skills and self.skill_roots:
            context['skills']['selection'] = skills.select(
                delegation['objective'], delegation['files'], self.skill_roots)
            context['skills']['selected'] = context['skills']['selection']['selected']
        if models and self.models is not None:
            classification = self._classification(unit, delegation)
            classification.update(role=role, phase=phase)
            inventory = self.models
            if self.review_cycle['enabled']:
                inventory = {**inventory, 'models': [m for m in inventory['models']
                    if m['cost_rank'] <= self.review_cycle['max_cost_rank']]}
            if delegation.get('analysis'):
                allowed_models = self.analysis_models.get(delegation['analysis_provider'], [])
                inventory = {**inventory, 'models': [m for m in inventory['models']
                                                       if m['id'] in allowed_models]}
            routing_id = delegation['pr']
            if self.review_cycle['enabled']:
                require(not any(a.get('task_id') == routing_id for a in (self.attempts or [])),
                        'review cycle requires role-scoped attempt IDs (<PR>:<role>)')
                routing_id += ':' + role
            routing = models.route({'id': routing_id, **classification}, inventory,
                                   self.attempts, self.routing_policy)
            require(routing['verdict'] == 'PASS', routing['reason'])
            if delegation.get('review_author') and self.review_cycle.get('prefer_cross_provider'):
                provider = delegation['review_author'].get('provider')
                alternatives = {**inventory, 'models': [m for m in inventory['models']
                    if provider and m.get('provider') and m['provider'] != provider]}
                cross = models.route({'id': routing_id, **classification}, alternatives,
                                     self.attempts, self.routing_policy)
                routing['review_selection'] = {
                    'justification': self.review_cycle['justification'],
                    'alternative_available': cross['verdict'] == 'PASS',
                    'reason': cross['reason'], 'provider_provenance': 'model configuration'}
                if cross['verdict'] == 'PASS':
                    selection_proof = routing['review_selection']
                    routing = {**cross, 'review_selection': selection_proof}
            explicit_effort = False
            if self.routing_policy and self.routing_policy.get('enabled'):
                _, selection = models.policy_context(classification, self.routing_policy['rules'])
                explicit_effort = 'effort' in selection
            context.update(model_routing=routing, model_requested=routing['recommendation'],
                           model_effort_required=explicit_effort)
        return context

    def _prepare_analysis(self, task, unit, delegation, plan_sha256):
        if (self.double_analysis['enabled'] and task.get('mission_index') == 0
                and not task.get('analysis_required')):
            if module('models').classify(self._classification(unit, delegation)) >= 2:
                task.update(analysis_required=True, mission_roles=['explorer', 'explorer']
                            + task['mission_roles'])
                task['analysis_bundle'] = module('analysis').bundle(unit, delegation['worktree'], {
                    'plan_sha256': plan_sha256,
                    'routing_fingerprint': self.routing_fingerprint,
                    'base': WORKSPACE.git(delegation['worktree'], 'rev-parse', 'HEAD'),
                    'snapshot': snapshot(delegation['worktree'])})

    def _analysis_inputs(self, task, delegation, analyzing):
        if analyzing:
            provider = ('codex', 'claude')[task['mission_index']]
            task['analysis_provider'] = provider
            delegation.update(analysis=task['analysis_bundle'], analysis_provider=provider)
            self._analysis_sources(task, delegation['worktree'])
        elif task.get('analysis_required'):
            require(task.get('analysis_summary', {}).get('verdict') == 'PASS',
                    'two independent analyses and valid arbitration required before BUILD')
            self._analysis_sources(task, delegation['worktree'])

    def _assign(self, state, pr):
        task = state['tasks'][pr]
        require(task['state'] == 'PLANNED', 'task is not PLANNED; no redispatch')
        if self.review_cycle['enabled']:
            require(task.get('attempts_used', 0) < self.review_cycle['max_attempts'],
                    'review cycle attempt budget exhausted')
        require(not task.get('owner'), 'interrupted assignment; reconcile owner before dispatch')
        require(not self.missions or task.get('mission_roles'),
                'legacy task requires reviewed reconciliation before mission pipeline')
        delegation = BUILD.prepare(self.manifest, self.repo, pr, self._done(state))
        require(delegation['plan_sha256'] == state['plan_sha256'], 'plan changed during prepare')
        delegation['runtime_handshake'] = 'Remain read-only until orchestrator confirms launch receipt'
        unit = copy.deepcopy(task['unit'])
        self._prepare_analysis(task, unit, delegation, state['plan_sha256'])
        if task.get('mission_roles'):
            require(self.missions, 'mission pipeline disabled; reconciliation required')
            require(unit.get('routing', {}).get('role', 'implementer') == 'implementer'
                    and unit.get('routing', {}).get('phase', 'BUILD') == 'BUILD',
                    'mission pipeline requires an implementer BUILD PR entry')
            require(not task.get('mission_snapshot') or
                    task['mission_snapshot'] == snapshot(delegation['worktree']),
                    'mission input changed; revalidation required')
            role = task['mission_roles'][task['mission_index']]
            classification = unit.setdefault('routing', {})
            analyzing = task.get('analysis_required') and task['mission_index'] < 2
            phase = 'PREPARE' if analyzing else 'BUILD'
            classification.update(role=role, phase=phase, session_id='mission:' + uuid.uuid4().hex)
            self._analysis_inputs(task, delegation, analyzing)
            if role == 'reviewer':
                classification['complexity'] = 'high'  # Review floor also applies without a policy.
                writer = next(h['task'] for h in reversed(task['mission_history'])
                              if h['task']['role'] == 'implementer')
                classification['implementer_session_id'] = writer['agent_id']
                if self.review_cycle['enabled']:
                    delegation['review_author'] = self._review_actor(writer)
            hashes = file_hashes(delegation['worktree'])
            is_test = module('gates').TEST_PATH.search
            protected = {p: value for p, value in hashes.items()
                         if (not is_test(p) if role == 'test-author' else bool(is_test(p)))}
            task['mission_protected'] = protected
            if role == 'implementer':
                if task.get('correction'):
                    delegation['correction'] = task['correction']
                    if task['correction'].get('routing_override'):
                        classification['routing_override'] = task['correction']['routing_override']
                delegation['locked_tests'] = [p for p in hashes if is_test(p)]
            delegation['writable_files'] = [p for p in unit['files']
                                            if (bool(is_test(p)) if role == 'test-author'
                                                else not is_test(p))]
            if role == 'reviewer' or analyzing:
                delegation['writable_files'] = []
            if role == 'reviewer':
                delegation['verification'] = task['verify_evidence']
                if self.review_cycle['enabled']:
                    current = snapshot(delegation['worktree'])
                    require(task['verify_evidence']['snapshot'] == current
                            and task['verify_evidence']['plan_sha256'] == state['plan_sha256'],
                            'Verify evidence stale before review')
                    delegation['review_context'] = module('brief').review_context(
                        delegation, task.get('scope_base', task['starting_head']), current)
        context = self._context(delegation, unit)
        if self.review_cycle['enabled']:
            task.setdefault('scope_base', WORKSPACE.git(delegation['worktree'], 'rev-parse', 'HEAD'))
        owner = {'id': 'scheduler-' + uuid.uuid4().hex, 'task': pr,
                 'plan_sha256': delegation['plan_sha256']}
        resources = [{'type': 'file', 'name': file} for file in delegation['files']]
        resources += task['unit'].get('resources', [])
        reservation = {**owner, 'worktree': delegation['worktree'], 'resources': [
            WORKSPACE.normalize_resource(resource, Path(delegation['worktree']))
            for resource in resources]}
        task.update(delegation=delegation, owner=owner, reservation_status='INTENT',
                    reservation=reservation, **context,
                    result=None, model_observed=None, duration_seconds=None, accepted=False,
                    starting_head=WORKSPACE.git(delegation['worktree'], 'rev-parse', 'HEAD'),
                    assigned_snapshot=snapshot(delegation['worktree']))
        self._save(state)  # Durable intent reconciles a crash between the two registries.
        WORKSPACE.reserve(self.repo, owner, delegation['worktree'], resources)
        task.update(state='ASSIGNED', reservation_status='RESERVED')
        self._event(state, task, 'assigned')
        return task

    def prepare(self, pr):
        """Reserve assignment only. Host must launch and report a verified receipt."""
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            return copy.deepcopy(self._assign(state, pr))

    def _receipt(self, state, task, observation):
        blocked = task['state'] == 'BLOCKED'
        require(task['state'] == 'ASSIGNED' or (blocked and task.get('owner')
                                              and task.get('agent_id') is None),
                'launch receipt requires ASSIGNED or unresolved blocked launch')
        require({item['path'] for item in task['skills']['selected']}
                <= {item['path'] for item in task['skills']['loaded']},
                'selected skills must be loaded before launch')
        require(isinstance(observation, dict) and observation.get('launch_observed') is True
                and observation.get('identity_verified') is True,
                'orchestrator must verify observed runtime identity')
        identity, runtime = observation.get('agent_id'), observation.get('runtime')
        require(isinstance(identity, str) and identity.strip(), 'observed agent_id required')
        require(runtime in ('native', 'simulated', 'mono-agent', 'process'), 'unsupported runtime')
        require(not any(t.get('agent_id') == identity and t.get('active')
                        for t in state['tasks'].values()), 'runtime identity already active')
        task.update(agent_id=identity, runtime=runtime, active=True, launch_status='OBSERVED',
                    launched_at=time.time(), model_observed=observation.get('model_observed'),
                    identity_provenance='trusted orchestrator observation; not authenticated here',
                    independent_review=False)
        if 'model_execution' in observation:
            task['model_execution'] = copy.deepcopy(observation['model_execution'])
        task['model_applied'] = bool(task['model_requested'] and task['model_observed']
                                     == task['model_requested'])
        try:
            self._launch_guard(task)
            if task.get('mission_roles') and task['role'] == 'reviewer':
                writers = [h['task']['agent_id'] for h in task['mission_history']
                           if h['task']['role'] in ('test-author', 'implementer')]
                require(identity not in writers and runtime != 'simulated',
                        'review requires an independently observed runtime session')
                task['independent_review'] = True
        except (ValueError, OSError) as error:
            self._block(state, task, str(error))
            self._event(state, task, 'launch_observed_scope_invalid')
            raise
        if (not blocked and task.get('analysis_required') and task['mission_index'] == 2
                and task['phase'] == 'BUILD' and task['role'] in ('test-author', 'implementer')
                and runtime in ('native', 'process') and not task.get('analysis_consumption')):
            task['analysis_consumption'] = {'bundle_sha256': task['analysis_bundle']['bundle_sha256'],
                                            'role': task['role'], 'receipt': copy.deepcopy(observation)}
            self._event(state, task, 'analysis_consumption_authorized')
        task['state'] = 'BLOCKED' if blocked else 'RUNNING'
        self._event(state, task, 'launch_observed')

    def receipt(self, pr, observation):
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            self._receipt(state, state['tasks'][pr], observation)
            return copy.deepcopy(state['tasks'][pr])

    def handoff(self, pr, observation):
        """Release only after trusted runtime confirms completion or stop."""
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            task = state['tasks'][pr]
            require(task.get('owner'), 'task has no reservation')
            require(isinstance(observation, dict) and observation.get('stopped_confirmed') is True
                    and observation.get('identity_verified') is True, 'confirmed stop required')
            require(observation.get('agent_id') == task.get('agent_id'), 'handoff identity mismatch')
            outcome = observation.get('outcome')
            require(outcome in ('COMPLETED', 'BLOCKED'), 'invalid handoff outcome')
            require('result' in observation, 'handoff result required')
            try:
                self._scope(task)
            except (ValueError, OSError) as error:
                self._block(state, task, str(error))
            if outcome == 'COMPLETED':
                require(task.get('agent_id') and task.get('launched_at'), 'no observed launch')
                require(isinstance(observation.get('blockers', []), list)
                        and not observation.get('blockers'), 'completed handoff has blockers')
            applied = observation.get('skills_applied', [])
            require(isinstance(applied, list), 'skills_applied must be a list')
            loaded = {(item['path'], item['sha256']) for item in task['skills']['loaded']}
            require(all(isinstance(item, dict) and (item.get('path'), item.get('sha256')) in loaded
                        and isinstance(item.get('evidence'), str) and item['evidence'].strip()
                        for item in applied), 'skill application requires loaded hash and evidence')
            task['skills']['applied'] = applied
            if 'model_execution' in observation:
                task['model_execution'] = copy.deepcopy(observation['model_execution'])
            if task.get('read_only'):
                if snapshot(task['delegation']['worktree']) != task['assigned_snapshot']:
                    self._block(state, task, 'read-only mission modified worktree')
            if task.get('mission_roles'):
                task['result_snapshot'] = snapshot(task['delegation']['worktree'])
                if task['role'] == 'reviewer':
                    observed_session = task.get('model_execution', {}).get('cli_session_id')
                    writer_sessions = [h['task'].get('model_execution', {}).get('cli_session_id')
                                       for h in task['mission_history']]
                    if observed_session and observed_session in writer_sessions:
                        self._block(state, task, 'review reused a writer CLI session')
            task.update(active=False, result=observation['result'], stop_evidence=observation,
                        duration_seconds=max(0, time.time() - task['launched_at'])
                        if task.get('launched_at') else None)
            if outcome == 'BLOCKED' or task['blockers']:
                self._block(state, task, 'execution blocked or stale contract')
                task['blockers'].extend(observation.get('blockers', []))
            else:
                task['state'] = 'COMPLETED'
            # Confirmed stop is durable even if release fails; retry is safe.
            self._save(state)
            with WORKSPACE.registry(self.repo) as owners:
                reservation = owners.get(task['owner']['id'])
                require(reservation is None or reservation == task['reservation'],
                        'reservation changed; reconcile before release')
            if reservation is not None:
                WORKSPACE.release(self.repo, task['owner']['id'])
            task.pop('owner')
            self._event(state, task, 'handoff')
            return copy.deepcopy(task)

    def _scope(self, task):
        tree, unit = task['delegation']['worktree'], task['unit']
        info = WORKSPACE.inspect(self.repo, tree)
        require(info['branch'] == unit['branch'], 'assigned worktree has wrong branch')
        committed = BUILD.git(tree, 'diff', '--name-only', '--no-renames', '-z',
                              task.get('scope_base', task['starting_head']), 'HEAD').split(b'\0')
        changed = {path.decode('utf-8', 'surrogateescape') for path in committed if path}
        require(not (changed | BUILD.dirty_paths(tree)) - set(unit['files']),
                'committed/dirty paths outside scope')
        if task.get('mission_roles'):
            require(WORKSPACE.git(tree, 'rev-parse', 'HEAD') == task['starting_head'],
                    'mission must not commit or change HEAD')
            current = file_hashes(tree)
            is_test = module('gates').TEST_PATH.search
            protected = {p: value for p, value in current.items()
                         if (not is_test(p) if task['role'] == 'test-author' else bool(is_test(p)))}
            require(protected == task['mission_protected'],
                    'mission changed protected product/tests content')

    def _launch_guard(self, task):
        self._scope(task)
        require(task['assigned_snapshot'] == snapshot(task['delegation']['worktree']),
                'assignment content changed before launch receipt')
        if task.get('analysis_required'):
            self._analysis_sources(task, task['delegation']['worktree'])
        if task['delegation'].get('review_context'):
            require(task['delegation']['review_context']['snapshot'] == task['assigned_snapshot'],
                    'inline review context stale before launch')

    def accept(self, pr, evidence):
        """Trusted orchestrator accepts tests and contract for dependency readiness."""
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            task = state['tasks'][pr]
            require(task['state'] == 'COMPLETED' and not task.get('active'),
                    'acceptance requires completed stopped execution')
            self._scope(task)
            require(isinstance(evidence, dict) and evidence.get('status') == 'PASS'
                    and evidence.get('orchestrator_verified') is True, 'verified PASS required')
            require(isinstance(evidence.get('source'), str) and evidence['source'].strip(),
                    'validation source required')
            for key in ('criteria', 'tests'):
                require(isinstance(evidence.get(key), list) and evidence[key]
                        and all(isinstance(item, str) and item.strip() for item in evidence[key]),
                        key + ' validation evidence required')
            require(evidence.get('head') == WORKSPACE.git(task['delegation']['worktree'],
                                                        'rev-parse', 'HEAD')
                    and evidence.get('plan_sha256') == state['plan_sha256'],
                    'stale acceptance head/plan')
            require(evidence.get('snapshot') == snapshot(task['delegation']['worktree']),
                    'stale acceptance content snapshot')
            task.update(accepted=True, acceptance_evidence=evidence)
            self._event(state, task, 'contract_accepted')
            return copy.deepcopy(task)

    def finish_mission(self, pr, gate):
        """Advance one PR after fresh deterministic evidence and confirmed runtime stop."""
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            task = state['tasks'][pr]
            try:
                require(task['state'] == 'COMPLETED' and task.get('active') is False
                        and 'owner' not in task, 'mission requires stopped completed execution')
                require(task.get('stop_evidence', {}).get('stopped_confirmed') is True,
                        'mission stop evidence required')
                stop = task['stop_evidence']
                require(stop.get('identity_verified') is True
                        and stop.get('agent_id') == task.get('agent_id'),
                        'mission stop identity mismatch')
                self._scope(task)
                current = snapshot(task['delegation']['worktree'])
                require(task.get('result_snapshot') == current, 'mission output changed')
                require(gate.get('verdict') == 'PASS' and gate.get('snapshot') == current
                        and gate.get('plan_sha256') == state['plan_sha256']
                        and gate.get('base') == task.get('scope_base', task['starting_head']),
                        'mission gate failed or stale')
                handoff = task.get('result', {}).get('handoff')
                require(handoff and handoff['status'] == 'COMPLETED', 'mission handoff required')
                analyzing = task['phase'] == 'PREPARE' and task.get('analysis_required')
                if analyzing:
                    require(not handoff.get('blockers'), 'analysis handoff has unresolved blockers')
                    module('analysis').validate_opinion(handoff.get('analysis'), task['analysis_bundle'])
                if task['role'] == 'reviewer':
                    if self.review_cycle['enabled']:
                        task['review_identity'] = self._review_identity(task)
                    require(task.get('independent_review') is True
                            and module('brief').review_passes(handoff.get('review')),
                            'independent review missing or blocking findings')
                task['mission_gate'] = copy.deepcopy(gate)
                previous = {k: copy.deepcopy(v) for k, v in task.items() if k != 'mission_history'}
                task['mission_history'].append({'task': previous, 'gate': copy.deepcopy(gate)})
                task['mission_snapshot'] = current
                if task['role'] == 'implementer':
                    task['verify_evidence'] = copy.deepcopy(gate)
                if task['role'] == 'reviewer':
                    task['mission_complete'] = True
                elif analyzing and task['mission_index'] == 1:
                    self._finish_analysis(state, task)
                else:
                    task.update(state='PLANNED', mission_index=task['mission_index'] + 1,
                                agent_id=None, active=False, result=None, accepted=False)
                self._event(state, task, 'mission_verified')
            except (ValueError, OSError, KeyError, TypeError) as error:
                self._block(state, task, str(error))
            return copy.deepcopy(task)

    def _analysis_consumed(self, task):
        proof = task.get('analysis_consumption')
        if proof is None:
            return False
        receipt = proof.get('receipt') if isinstance(proof, dict) else None
        require(isinstance(receipt, dict) and receipt.get('launch_observed') is True
                and receipt.get('identity_verified') is True
                and receipt.get('runtime') in ('native', 'process')
                and isinstance(receipt.get('agent_id'), str) and receipt['agent_id'].strip()
                and proof.get('role') in ('test-author', 'implementer')
                and proof.get('bundle_sha256') == task['analysis_bundle']['bundle_sha256'],
                'analysis consumption requires the observed first-writer authorization')
        return True

    def _analysis_sources(self, task, tree, plan_sha256=None):
        """Bind every reuse to its contract; content may evolve only after authorization."""
        try:
            require(not task.get('analysis_stale'), 'analysis invalidated; renewed analysis required')
            contract = task['analysis_bundle']
            current = {'plan_sha256': plan_sha256 or task['plan_sha256'],
                       'routing_fingerprint': self.routing_fingerprint,
                       'base': WORKSPACE.git(tree, 'rev-parse', 'HEAD')}
            require(all(contract.get(k) == value for k, value in current.items()),
                    'analysis plan, base or routing context is stale; renewed analysis required')
            if not self._analysis_consumed(task):
                current['snapshot'] = snapshot(tree)
                require(contract['snapshot'] == current['snapshot'],
                        'analysis prewrite snapshot is stale; renewed analysis required')
                require(module('analysis').bundle(task['unit'], tree, current) == contract,
                        'analysis sources changed; renewed analysis required')
        except (ValueError, OSError, KeyError, TypeError) as error:
            task.setdefault('analysis_stale', str(error))
            raise

    def _finish_analysis(self, state, task):
        analysis = module('analysis')
        self._analysis_sources(task, task['delegation']['worktree'])
        histories = [h['task'] for h in task['mission_history'] if h['task']['phase'] == 'PREPARE']
        arbitration, arbitration_error = None, None
        try:
            arbitration = analysis.arbitration_for(self.double_analysis.get('arbitration_file'),
                                                   task['unit']['id'])
        except (ValueError, OSError) as error:
            arbitration_error = str(error)
        summary = analysis.synthesize(histories, task['analysis_bundle'], arbitration)
        if arbitration_error and summary['verdict'] == 'BLOCKED':
            summary['reason'] = arbitration_error
        task['analysis_summary'] = summary
        if summary['verdict'] == 'PASS':
            task.update(state='PLANNED', mission_index=2, agent_id=None, active=False,
                        result=None, accepted=False, analysis_pending=False, blockers=[])
        else:
            task['analysis_pending'] = True
            self._block(state, task, 'analysis arbitration required')

    def pending_analyses(self):
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            return [pr for pr, task in state['tasks'].items() if task.get('analysis_pending')]

    def resolve_analysis(self, pr):
        """Reconcile only pending arbitration; never redispatch missing analyses."""
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            task = state['tasks'][pr]
            if (not task.get('analysis_pending') or task['state'] != 'BLOCKED'
                    or task['blockers'] != ['analysis arbitration required']):
                return copy.deepcopy(task)
            try:
                require(task.get('active') is False and 'owner' not in task,
                        'analysis runtime stop required')
                self._scope(task)
                tree, contract = task['delegation']['worktree'], task['analysis_bundle']
                require(snapshot(tree) == contract['snapshot']
                        and state['plan_sha256'] == contract['plan_sha256']
                        and WORKSPACE.git(tree, 'rev-parse', 'HEAD') == contract['base'],
                        'analysis input evidence stale')
                self._analysis_sources(task, tree)
                self._finish_analysis(state, task)
            except (ValueError, OSError, KeyError, TypeError) as error:
                self._block(state, task, str(error))
            return copy.deepcopy(task)

    @staticmethod
    def _review_actor(task):
        execution = task.get('model_execution', {})
        return {'agent_id': task.get('agent_id'),
                'session_id': execution.get('session_id') or task.get('agent_id'),
                'cli_session_id': execution.get('cli_session_id'),
                'requested': execution.get('requested'),
                'observed': execution.get('observed', {'model': None, 'effort': None}),
                'provider': execution.get('provider'),
                'provider_provenance': execution.get('provenance', {}).get('provider')}

    def _review_identity(self, task):
        author = next(h['task'] for h in reversed(task['mission_history'])
                      if h['task']['role'] == 'implementer')
        writer, reviewer = self._review_actor(author), self._review_actor(task)
        return {'author': writer, 'reviewer': reviewer,
                'cross_provider': bool(writer['provider'] and reviewer['provider']
                                       and writer['provider'] != reviewer['provider']),
                'provider_verification': 'declared, not observed',
                'head': task['starting_head'], 'snapshot': task['result_snapshot'],
                'plan_sha256': task['plan_sha256']}

    def request_correction(self, pr, evidence):
        """Authorize a stopped review's correction; never launch or silently escalate."""
        require(self.review_cycle['enabled'], 'review cycle not enabled')
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            task = state['tasks'][pr]
            require(task['state'] in ('BLOCKED', 'COMPLETED') and not task.get('accepted')
                    and task.get('active') is False and 'owner' not in task,
                    'correction requires a stopped, unaccepted review without owner')
            require(task.get('role') == 'reviewer' and task.get('independent_review') is True,
                    'correction requires an independent review')
            self._requeue_evidence(task, evidence, state['plan_sha256'])
            require(not any('plan changed' in reason for reason in task.get('blockers', [])),
                    'stale correction plan/config')
            require(task.get('routing_fingerprint') == self.routing_fingerprint
                    and task['plan_sha256'] == state['plan_sha256'], 'stale correction plan/config')
            stop = task.get('stop_evidence', {})
            require(stop.get('stopped_confirmed') is True and stop.get('identity_verified') is True,
                    'correction stop evidence required')
            handoff = task.get('result', {}).get('handoff') or {}
            review = handoff.get('review')
            require(handoff.get('status') == 'COMPLETED' and isinstance(review, dict)
                    and isinstance(review.get('findings'), list) and review['findings']
                    and not module('brief').review_passes(review),
                    'correction requires precise blocking review findings; quota is not a review')
            require(all(isinstance(f, dict) and f.get('severity') in ('Critical', 'Major', 'Minor', 'Nit')
                        and isinstance(f.get('message'), str) and f['message'].strip()
                        for f in review['findings']), 'invalid correction findings')
            require(task.get('corrections', 0) < self.review_cycle['max_corrections']
                    and task.get('attempts_used', 0) + 2 <= self.review_cycle['max_attempts'],
                    'correction or attempt budget exhausted')
            require(evidence.get('diagnosis_kind') in ('implementation', 'capacity')
                    and isinstance(evidence.get('diagnosis'), str) and evidence['diagnosis'].strip(),
                    'concrete correction diagnosis required')
            override = evidence.get('routing_override')
            if override is not None:
                require(self.routing_policy and self.routing_policy.get('enabled'),
                        'correction override requires active routing policy')
                classification = self._classification(task['unit'], task['delegation'])
                classification.update(role='implementer', phase='BUILD', routing_override=override)
                inventory = {**self.models, 'models': [m for m in self.models['models']
                    if m['cost_rank'] <= self.review_cycle['max_cost_rank']]}
                routed = module('models').route({'id': pr + ':implementer', **classification}, inventory,
                                               self.attempts, self.routing_policy)
                require(routed['verdict'] == 'PASS', routed['reason'])
            require(override is None or evidence['diagnosis_kind'] == 'capacity',
                    'model/effort escalation requires concrete capacity diagnosis')
            tree = task['delegation']['worktree']
            current = snapshot(tree)
            require(evidence.get('snapshot') == current
                    and evidence.get('head') == WORKSPACE.git(tree, 'rev-parse', 'HEAD'),
                    'stale correction head/snapshot')
            # Commit reconciliation is explicit; complete PR scope remains relative to scope_base.
            reconciled = {**task, 'starting_head': current['head']}
            self._scope(reconciled)
            require(not task.get('analysis_required') or current['head'] == task['starting_head'],
                    'changed analysis HEAD requires renewed PREPARE analysis')
            with WORKSPACE.registry(self.repo) as owners:
                require(not any(o['worktree'] == tree for o in owners.values()),
                        'workspace still reserved')
            correction = {'findings': copy.deepcopy(review['findings']),
                          'reviewer': self._review_actor(task), 'previous_head': task['starting_head'],
                          'head': current['head'], 'diagnosis_kind': evidence['diagnosis_kind'],
                          'diagnosis': evidence['diagnosis'],
                          **({'routing_override': copy.deepcopy(override)} if override else {})}
            previous = {k: copy.deepcopy(v) for k, v in task.items() if k != 'mission_history'}
            task['mission_history'].append({'task': previous, 'gate': {'verdict': 'BLOCKED'}})
            task.update(state='PLANNED', mission_index=task['mission_roles'].index('implementer'),
                        role='implementer', starting_head=current['head'], mission_snapshot=current,
                        mission_complete=False, active=False, agent_id=None, accepted=False,
                        result=None, blockers=[], correction=correction,
                        corrections=task.get('corrections', 0) + 1)
            for key in ('verify_evidence', 'mission_gate', 'result_snapshot', 'review_identity'):
                task.pop(key, None)
            self._event(state, task, 'correction_authorized')
            return copy.deepcopy(task)

    def requeue(self, pr, evidence):
        """Reconcile a stopped attempt and plan a new one without launch or release."""
        with self._state() as state:
            units = self._sync(state)
            self._validate_owners(state)
            task = state['tasks'][pr]
            require(task['state'] in ('BLOCKED', 'COMPLETED') and not task.get('accepted'),
                    'requeue requires blocked or unaccepted completed execution')
            require(task.get('active') is False, 'runtime stop must be known before requeue')
            require('owner' not in task, 'reservation must be released by confirmed handoff')
            self._requeue_evidence(task, evidence, state['plan_sha256'])
            if self.review_cycle['enabled'] and task.get('role') == 'reviewer':
                review = (task.get('result', {}).get('handoff') or {}).get('review')
                require(not task.get('mission_complete'), 'completed review proceeds to SHIP')
                require(not (isinstance(review, dict) and review.get('findings')
                             and not module('brief').review_passes(review)),
                        'blocking findings require request_correction and renewed Verify')
            require(pr in units, 'task removed from current plan')
            delegation = BUILD.prepare(self.manifest, self.repo, pr, self._done(state))
            require(delegation['plan_sha256'] == state['plan_sha256'], 'plan changed during requeue')
            if task.get('analysis_required'):
                try:
                    self._analysis_sources(task, delegation['worktree'], state['plan_sha256'])
                except (ValueError, OSError, KeyError, TypeError) as error:
                    self._block(state, task, str(error))
                    raise
            reconciled = {**task, 'unit': units[pr], 'delegation': delegation}
            reconciled.setdefault('starting_head', WORKSPACE.git(delegation['worktree'],
                                                                 'rev-parse', 'HEAD'))
            self._scope(reconciled)
            require(evidence.get('snapshot') == snapshot(delegation['worktree']),
                    'stale requeue content snapshot')
            with WORKSPACE.registry(self.repo) as owners:
                require(not any(entry['worktree'] == delegation['worktree'] or
                                entry['id'] == task.get('reservation', {}).get('id')
                                for entry in owners.values()), 'workspace still reserved')
            previous = {key: value for key, value in task.items() if key != 'history'}
            history = task.get('history', []) + [{'task': copy.deepcopy(previous),
                                                 'requeue': copy.deepcopy(evidence), 'time': time.time()}]
            mission = {key: copy.deepcopy(task[key]) for key in (
                'mission_roles', 'mission_index', 'mission_history', 'mission_complete',
                'verify_evidence', 'starting_head', 'scope_base', 'role', 'mission_protected', 'delegation',
                'attempts_used', 'corrections', 'correction', 'review_identity',
                'analysis_required', 'analysis_bundle', 'analysis_summary',
                'analysis_pending', 'analysis_provider', 'analysis_consumption') if key in task}
            if mission:
                mission['mission_snapshot'] = evidence['snapshot']
            task.clear()
            task.update(unit=units[pr], state='PLANNED', blockers=[], active=False,
                        agent_id=None, accepted=False, plan_sha256=state['plan_sha256'],
                        history=history, result=None, **mission)
            self._event(state, task, 'requeued')
            return copy.deepcopy(task)

    def _requeue_evidence(self, task, evidence, digest):
        require(isinstance(evidence, dict) and evidence.get('orchestrator_verified') is True,
                'orchestrator-verified requeue evidence required')
        for key in ('reason', 'proof'):
            require(isinstance(evidence.get(key), str) and evidence[key].strip(),
                    key + ' required for requeue')
        require(evidence.get('plan_sha256') == digest, 'stale requeue plan')
        if task.get('agent_id') is not None or task.get('launch_status') == 'UNKNOWN':
            require(evidence.get('stopped_confirmed') is True
                    and evidence.get('identity_verified') is True
                    and evidence.get('agent_id') == task.get('agent_id'),
                    'verified stop and coherent runtime identity required')

    def _validate_owners(self, state):
        self._historical(state, {unit['id']: unit for unit in state['plan']['prs']})
        stale = set()
        for task in state['tasks'].values():
            if task.get('accepted'):
                evidence = task['acceptance_evidence']
                try:
                    current = snapshot(task['delegation']['worktree'])
                except (ValueError, OSError) as error:
                    self._block(state, task, str(error))
                    current = None
                if (evidence['plan_sha256'] != state['plan_sha256']
                        or evidence.get('snapshot') != current):
                    task['accepted'] = False
                    self._event(state, task, 'acceptance_stale')
                    stale.add(task['unit']['id'])
        self._block_descendants(state, stale)
        with WORKSPACE.registry(self.repo) as owners:
            for task in state['tasks'].values():
                if task.get('owner'):
                    if task['state'] == 'PLANNED':
                        self._block(state, task, 'interrupted assignment; reconcile owner')
                    if owners.get(task['owner']['id']) != task['reservation']:
                        self._block(state, task, 'reservation missing or changed')
                    else:
                        task['reservation_status'] = 'RESERVED'

    def _block_descendants(self, state, stale):
        """Changed dependency output invalidates consumers, including active ones."""
        affected = set(stale)
        while True:
            descendants = {key for key, task in state['tasks'].items()
                           if set(task['unit']['depends_on']) & affected}
            new = descendants - affected
            if not new:
                break
            for key in new:
                task = state['tasks'][key]
                task['accepted'] = False
                self._block(state, task, 'dependency acceptance stale; revalidation required')
            affected.update(new)

    def resume(self):
        """Inspect persisted tasks; never relaunch an assigned/running agent."""
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            for task in state['tasks'].values():
                if task['state'] == 'INTEGRATED' and task.get('integration_proven'):
                    continue
                try:
                    unit = task['unit']
                    tree = (self.repo / unit['worktree']).resolve()
                    info = WORKSPACE.inspect(self.repo, str(tree))
                    require(info['branch'] == unit['branch'], 'assigned worktree has wrong branch')
                    require(not BUILD.dirty_paths(tree) - set(unit['files']), 'dirty paths outside scope')
                    if task.get('analysis_bundle'):
                        self._analysis_sources(task, tree, state['plan_sha256'])
                    if task.get('starting_head'):
                        self._scope(task)
                    if task.get('mission_roles') and not task.get('owner'):
                        expected = (task.get('result_snapshot') if task['state'] == 'COMPLETED'
                                    else task.get('mission_snapshot'))
                        require(not expected or snapshot(tree) == expected,
                                'mission evidence stale; revalidation required')
                except (ValueError, OSError) as error:
                    self._block(state, task, str(error))
            return copy.deepcopy(state)

    def dispatch(self, adapter):
        """adapter.launch(task) -> receipt, wait(task) -> stopped handoff or None.

        Callbacks are a trusted runtime boundary. Errors have unknown launch/stop
        status, so retain ownership. All independent ready tasks launch before wait.
        """
        require(callable(getattr(adapter, 'launch', None))
                and callable(getattr(adapter, 'wait', None)), 'launch/wait callbacks required')
        launched = []
        with self._state() as state:
            units = self._sync(state)  # Invalid/cyclic plans fail before any callback.
            self._validate_owners(state)
            for pr in units:
                task = state['tasks'][pr]
                if task['state'] != 'PLANNED':
                    continue
                dependencies = [state['tasks'][key] for key in task['unit']['depends_on']]
                if any(dep['state'] == 'BLOCKED' for dep in dependencies):
                    self._block(state, task, 'dependency blocked')
                    continue
                if any(key not in self._done(state) for key in task['unit']['depends_on']):
                    continue
                try:
                    self._assign(state, pr)
                    loaded = self._load_skills(task)
                    self._validate_owners(state)
                    require(task['state'] == 'ASSIGNED', 'assignment changed before launch')
                    self._launch_guard(task)
                    if self.review_cycle['enabled'] and not getattr(adapter, 'dry_run', False):
                        task['attempts_used'] = task.get('attempts_used', 0) + 1
                    task.update(active=None, launch_status='UNKNOWN', launch_attempted_at=time.time())
                    self._save(state)  # Crash during launch leaves ASSIGNED + owner, not PLANNED.
                    launch_task = copy.deepcopy(task)
                    launch_task['skill_instructions'] = loaded
                    observation = adapter.launch(launch_task)
                    self._receipt(state, task, observation)
                    self._save(state)
                    launched.append(copy.deepcopy(task))
                except Exception as error:
                    self._block(state, task, 'prepare/launch failed: ' + str(error))
        for task in launched:
            try:
                observation = adapter.wait(task)
                if observation is not None:
                    self.handoff(task['unit']['id'], observation)
            except Exception as error:
                with self._state() as state:
                    self._block(state, state['tasks'][task['unit']['id']], 'wait failed: ' + str(error))
        return self.resume()

    def load_skills(self, pr):
        """Explicit instruction read; application is a separate handoff observation."""
        with self._state() as state:
            task = state['tasks'][pr]
            return self._load_skills(task)

    def _load_skills(self, task):
        selected = task['skills']['selected']
        if not selected:
            return []
        skills = module('skills', True)
        require(skills is not None, 'skills component unavailable')
        loaded = [skills.load(item['path']) for item in selected]
        task['skills']['loaded'] = [{k: v for k, v in item.items() if k != 'instructions'}
                                    for item in loaded]
        return loaded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'receipt', 'handoff', 'resume',
                                         'accept', 'load-skills', 'requeue'])
    parser.add_argument('manifest')
    parser.add_argument('--repo', default='.')
    parser.add_argument('--state')
    parser.add_argument('--pr')
    parser.add_argument('--observation', help='JSON file attested by trusted orchestrator')
    parser.add_argument('--skill-root', action='append', default=[])
    parser.add_argument('--models', help='JSON model capability inventory')
    args = parser.parse_args()
    try:
        models = json.loads(Path(args.models).read_text()) if args.models else None
        scheduler = Scheduler(args.manifest, args.repo, args.state,
                              skill_roots=args.skill_root, models=models)
        if args.action == 'resume':
            result = scheduler.resume()
        else:
            require(args.pr, '--pr required')
            if args.action in ('prepare', 'load-skills'):
                method = scheduler.prepare if args.action == 'prepare' else scheduler.load_skills
                result = method(args.pr)
            else:
                require(args.observation, '--observation required')
                result = getattr(scheduler, args.action)(args.pr,
                                                       json.loads(Path(args.observation).read_text()))
        print(json.dumps({'verdict': 'PASS', 'result': result, 'identity_authenticated': False}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'verdict': 'BLOCKED', 'reason': str(error), 'identity_authenticated': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
