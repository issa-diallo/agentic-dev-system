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
import os
from pathlib import Path
import re
import tempfile
import time
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
STATES = {'PLANNED', 'ASSIGNED', 'RUNNING', 'COMPLETED', 'BLOCKED'}


class Scheduler:
    def __init__(self, manifest, repo='.', state_path=None, *, skill_roots=(), models=None):
        self.manifest = Path(manifest).resolve()
        self.repo = WORKSPACE.root(repo)
        common = BUILD.common_dir(self.repo)
        namespace = hashlib.sha256(str(self.manifest).encode()).hexdigest()
        self.path = Path(state_path) if state_path else common / 'agentic-scheduler' / namespace / 'state.json'
        self.skill_roots, self.models = skill_roots, models

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
            elif key not in changed and not state['tasks'][key].get('owner'):
                state['tasks'][key]['plan_sha256'] = digest
        for key in changed:
            if key in state['tasks']:
                self._block(state, state['tasks'][key], 'plan changed; revalidation required')
        state.update(plan=plan, plan_sha256=digest)
        return units

    def _done(self, state):
        return [key for key, task in state['tasks'].items()
                if task['state'] == 'COMPLETED' and task.get('accepted')]

    def _context(self, delegation, unit):
        context = {'skills': {'selected': [], 'loaded': [], 'applied': []},
                   'model_requested': None}
        skills, models = module('skills', True), module('models', True)
        if skills and self.skill_roots:
            context['skills']['selection'] = skills.select(
                delegation['objective'], delegation['files'], self.skill_roots)
            context['skills']['selected'] = context['skills']['selection']['selected']
        if models and self.models is not None:
            description = delegation['objective'] + ' ' + ' '.join(delegation['files'])
            classification = dict(unit.get('routing', {}))
            require(set(classification) <= {'type', 'risk', 'complexity'}, 'invalid routing metadata')
            if re.search(r'auth|permission|tenant|secret|security', description, re.I):
                classification.update(type='authentication', risk='security_critical')
            elif re.search(r'migration|\.sql\b|schema', description, re.I):
                classification.update(type='migration', risk='critical')
            elif re.search(r'refactor|architecture|cross.module', description, re.I):
                classification.setdefault('complexity', 'high')
            routing = models.route({'id': delegation['pr'], **classification}, self.models)
            require(routing['verdict'] == 'PASS', routing['reason'])
            context.update(model_routing=routing, model_requested=routing['recommendation'])
        return context

    def _assign(self, state, pr):
        task = state['tasks'][pr]
        require(task['state'] == 'PLANNED', 'task is not PLANNED; no redispatch')
        require(not task.get('owner'), 'interrupted assignment; reconcile owner before dispatch')
        delegation = BUILD.prepare(self.manifest, self.repo, pr, self._done(state))
        require(delegation['plan_sha256'] == state['plan_sha256'], 'plan changed during prepare')
        context = self._context(delegation, task['unit'])
        owner = {'id': 'scheduler-' + uuid.uuid4().hex, 'task': pr,
                 'plan_sha256': delegation['plan_sha256']}
        resources = [{'type': 'file', 'name': file} for file in delegation['files']]
        resources += task['unit'].get('resources', [])
        reservation = {**owner, 'worktree': delegation['worktree'], 'resources': [
            WORKSPACE.normalize_resource(resource, Path(delegation['worktree']))
            for resource in resources]}
        task.update(delegation=delegation, owner=owner, reservation_status='INTENT',
                    reservation=reservation, **context, role='implementer',
                    result=None, model_observed=None, duration_seconds=None, accepted=False,
                    starting_head=WORKSPACE.git(delegation['worktree'], 'rev-parse', 'HEAD'))
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
        require(task['state'] == 'ASSIGNED', 'launch receipt requires ASSIGNED')
        require({item['path'] for item in task['skills']['selected']}
                <= {item['path'] for item in task['skills']['loaded']},
                'selected skills must be loaded before launch')
        require(isinstance(observation, dict) and observation.get('launch_observed') is True
                and observation.get('identity_verified') is True,
                'orchestrator must verify observed runtime identity')
        identity, runtime = observation.get('agent_id'), observation.get('runtime')
        require(isinstance(identity, str) and identity.strip(), 'observed agent_id required')
        require(runtime in ('native', 'simulated', 'mono-agent'), 'unsupported runtime')
        require(not any(t.get('agent_id') == identity and t.get('active')
                        for t in state['tasks'].values()), 'runtime identity already active')
        task.update(state='RUNNING', agent_id=identity, runtime=runtime, active=True,
                    launched_at=time.time(), model_observed=observation.get('model_observed'),
                    identity_provenance='trusted orchestrator observation; not authenticated here',
                    independent_review=False)
        task['model_applied'] = bool(task['model_requested'] and task['model_observed']
                                     == task['model_requested'])
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
            task.update(active=False, result=observation['result'],
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
                              task['starting_head'], 'HEAD').split(b'\0')
        changed = {path.decode('utf-8', 'surrogateescape') for path in committed if path}
        require(not (changed | BUILD.dirty_paths(tree)) - set(unit['files']),
                'committed/dirty paths outside scope')

    def accept(self, pr, evidence):
        """Trusted orchestrator accepts tests and contract for dependency readiness."""
        with self._state() as state:
            self._sync(state)
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
            task.update(accepted=True, acceptance_evidence=evidence)
            self._event(state, task, 'contract_accepted')
            return copy.deepcopy(task)

    def _validate_owners(self, state):
        for task in state['tasks'].values():
            if task.get('accepted'):
                evidence = task['acceptance_evidence']
                try:
                    head = WORKSPACE.git(task['delegation']['worktree'], 'rev-parse', 'HEAD')
                except (ValueError, OSError) as error:
                    self._block(state, task, str(error))
                    head = None
                if evidence['plan_sha256'] != state['plan_sha256'] or evidence['head'] != head:
                    task['accepted'] = False
                    self._event(state, task, 'acceptance_stale')
        with WORKSPACE.registry(self.repo) as owners:
            for task in state['tasks'].values():
                if task.get('owner'):
                    if task['state'] == 'PLANNED':
                        self._block(state, task, 'interrupted assignment; reconcile owner')
                    if owners.get(task['owner']['id']) != task['reservation']:
                        self._block(state, task, 'reservation missing or changed')
                    else:
                        task['reservation_status'] = 'RESERVED'

    def resume(self):
        """Inspect persisted tasks; never relaunch an assigned/running agent."""
        with self._state() as state:
            self._sync(state)
            self._validate_owners(state)
            for task in state['tasks'].values():
                try:
                    unit = task['unit']
                    tree = (self.repo / unit['worktree']).resolve()
                    info = WORKSPACE.inspect(self.repo, str(tree))
                    require(info['branch'] == unit['branch'], 'assigned worktree has wrong branch')
                    require(not BUILD.dirty_paths(tree) - set(unit['files']), 'dirty paths outside scope')
                    if task.get('starting_head'):
                        self._scope(task)
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
                if any(dep['state'] != 'COMPLETED' or not dep.get('accepted') for dep in dependencies):
                    continue
                try:
                    self._assign(state, pr)
                    loaded = self._load_skills(task)
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
                                         'accept', 'load-skills'])
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
