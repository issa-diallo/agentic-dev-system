#!/usr/bin/env python3
"""Opt-in runner: route a delegation to a CLI harness, then apply mechanical gates.

Adapter for Scheduler.dispatch: launch() starts the routed harness (claude, codex,
opencode or any command) as a child process in the assigned worktree; wait() joins
it and returns the handoff. The observed identity is a real child PID, not a
native-harness event. Environment filtering is hygiene, not a sandbox: run agents
in a container for untrusted models. Nothing here merges, commits or publishes.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

METHOD_ROOT = Path(__file__).resolve().parents[1]
BASE_ENV = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TERM', 'TMPDIR', 'USER', 'SHELL')
ENV_PRESET = {'claude': ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL'),
              'codex': ('OPENAI_API_KEY', 'CODEX_HOME')}
DEFAULT_TOOLS = ('Read', 'Edit', 'Write', 'Glob', 'Grep')
# The harness is exec'd only after the scheduler confirmed the launch receipt: the
# contract requires a read-only agent until then. EOF without "go" means abort.
GATE = ('import os, sys\n'
        'if sys.stdin.readline().strip() != "go":\n    sys.exit(125)\n'
        'os.execvp(sys.argv[1], sys.argv[1:])\n')


class Blocked(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Blocked(message)


def module(name):
    path = Path(__file__).with_name('agentic-' + name + '.py')
    spec = importlib.util.spec_from_file_location('run_' + name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def claude(v):
    argv = ['claude', '-p', v['prompt'], '--model', v['model'], '--output-format', 'json',
            '--permission-mode', 'acceptEdits', '--max-turns', str(v['max_turns'])] + v['extra']
    return argv + (['--allowedTools', *v['tools']] if v['tools'] else [])  # variadic: keep last


def codex(v):
    return (['codex', 'exec', '-m', v['model'], '-s', 'workspace-write', '-C', v['worktree'],
             '-c', 'model_reasoning_effort=' + json.dumps(v['effort'])] + v['extra'] + [v['prompt']])


def opencode(v):
    return ['opencode', 'run', '-m', v['model']] + v['extra'] + [v['prompt']]


PRESETS = {'claude': claude, 'codex': codex, 'opencode': opencode}


def load_config(path):
    config = json.loads(Path(path).read_text())
    require(isinstance(config, dict) and config.get('version') == 1, 'config version must be 1')
    models = config.get('models')
    require(isinstance(models, list) and models, 'config models: nonempty list required')
    for entry in models:
        require(isinstance(entry, dict) and all(isinstance(entry.get(k), str) and entry[k].strip()
                                                for k in ('id', 'harness', 'model')),
                'model entry needs id, harness, model')
        require(not entry['model'].startswith('<'), 'model placeholder not filled: ' + entry['id'])
    return config


def default_config():
    return Path(os.environ.get('AGENTIC_CONFIG') or METHOD_ROOT / 'agentic.config.json')


def harness_of(config, name):
    harness = config.get('harnesses', {}).get(name) or ({'preset': name} if name in PRESETS else None)
    require(harness, 'unknown harness: ' + name)
    require('argv' in harness or harness.get('preset') in PRESETS, 'harness needs preset or argv')
    return harness


def binary(harness):
    return harness['argv'][0] if 'argv' in harness else harness['preset']


def build_inventory(config, which=shutil.which):
    """Inventory for agentic-models.route; unavailable or disabled models are left out."""
    index, models = {}, []
    ids = [entry['id'] for entry in config['models']]
    require(len(ids) == len(set(ids)), 'duplicate model id')
    for entry in config['models']:
        harness = harness_of(config, entry['harness'])
        if entry.get('enabled', True) is False or not which(binary(harness)):
            continue
        keep = {k: entry[k] for k in ('id', 'efforts', 'cost_rank', 'tiers', 'max_level') if k in entry}
        models.append(keep)
        index[entry['id']] = {**entry, 'harness_config': harness}
    return {'models': models, 'runtime_overrides': True}, index


def build_argv(harness, values):
    if 'argv' in harness:
        tokens = [('{%s}' % k, v) for k, v in values.items() if isinstance(v, str)]
        result = []
        for token in harness['argv']:
            for key, value in tokens:
                token = token.replace(key, value)
            result.append(token)
        return result
    return PRESETS[harness['preset']]({**values, 'extra': list(harness.get('extra_args', []))})


def child_env(harness, environ=None):
    environ = os.environ if environ is None else environ
    names = set(BASE_ENV) | set(ENV_PRESET.get(harness.get('preset'), ())) | set(
        harness.get('env_passthrough', []))
    return {name: environ[name] for name in names if name in environ}


def tool_rules(config, commands):
    run = config.get('run', {})
    return list(run.get('allowed_tools', DEFAULT_TOOLS)) + [
        'Bash(%s)' % shlex.join(command) for command in commands]


def parse_output(harness, text):
    """Return (reply_text, usage, cost, models). Only Claude's JSON carries metrics."""
    if harness.get('preset') != 'claude':
        return text, None, None, None
    try:
        data = json.loads(text)
    except ValueError:
        return text, None, None, None
    if isinstance(data, list):
        data = next((i for i in reversed(data) if isinstance(i, dict) and i.get('type') == 'result'), {})
    if not isinstance(data, dict):
        return text, None, None, None
    models = data.get('modelUsage')
    return (data.get('result') if isinstance(data.get('result'), str) else text,
            data.get('usage'), data.get('total_cost_usd'),
            sorted(models) if isinstance(models, dict) else None)


class ProcessAdapter:
    """Scheduler adapter: launch() spawns, wait() joins. dry_run spawns nothing."""

    def __init__(self, config, index, run_dir, commands=(), dry_run=False, popen=subprocess.Popen):
        self.config, self.index, self.run_dir = config, index, Path(run_dir)
        self.commands, self.dry_run, self.popen = list(commands), dry_run, popen
        self.jobs, self.finished = {}, []
        self.brief = module('brief')

    def launch(self, task):
        pr = task['unit']['id']
        request = task.get('model_requested')
        require(request and request['model'] in self.index, 'routed model not in inventory')
        entry = self.index[request['model']]
        harness, run = entry['harness_config'], self.config.get('run', {})
        directory = self.run_dir / pr / time.strftime('%Y%m%dT%H%M%S')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        prompt = self.brief.render(task['delegation'], self.commands, task.get('skill_instructions'))
        (directory / 'brief.md').write_text(prompt)
        argv = build_argv(harness, {
            'prompt': prompt, 'model': entry['model'], 'effort': request['effort'],
            'worktree': task['delegation']['worktree'], 'max_turns': run.get('max_turns', 40),
            'tools': tool_rules(self.config, self.commands)})
        job = {'pr': pr, 'dir': directory, 'harness': harness, 'entry': entry, 'request': request,
               'argv': [a if a != prompt else '<brief.md>' for a in argv],
               'timeout': run.get('timeout_seconds', 1800), 'started': time.time()}
        if self.dry_run:
            job['agent_id'] = 'dry-run:' + pr
            self.jobs[pr] = job
            return {'agent_id': job['agent_id'], 'runtime': 'simulated', 'launch_observed': True,
                    'identity_verified': True}
        require(shutil.which(argv[0]), 'harness binary not found: ' + argv[0])
        with open(directory / 'stdout.log', 'wb') as out, open(directory / 'stderr.log', 'wb') as err:
            try:
                process = self.popen([sys.executable, '-c', GATE, *argv],
                                     cwd=task['delegation']['worktree'], stdin=subprocess.PIPE,
                                     stdout=out, stderr=err, env=child_env(harness),
                                     start_new_session=True)
            except OSError as error:
                raise Blocked('cannot start %s: %s' % (argv[0], error))
        job.update(process=process, agent_id='%s:pid:%d' % (argv[0], process.pid), released=False)
        self.jobs[pr] = job
        return {'agent_id': job['agent_id'], 'runtime': 'process', 'launch_observed': True,
                'identity_verified': True, 'model_observed': None}

    def release(self):
        """Let every receipted agent start. dispatch() calls wait() only after all receipts."""
        for job in self.jobs.values():
            if not job.get('released') and 'process' in job:
                job['released'] = True
                try:
                    job['process'].stdin.write(b'go\n')
                    job['process'].stdin.close()
                except OSError:
                    pass

    def close(self):
        """Stop agents that never reached wait(), e.g. after a failed receipt."""
        for job in self.jobs.values():
            process = job.get('process')
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()

    def wait(self, task):
        self.release()
        job = self.jobs.pop(task['unit']['id'])
        self.finished.append(job['pr'])
        base = {'agent_id': job['agent_id'], 'identity_verified': True, 'stopped_confirmed': True}
        if self.dry_run:
            return {**base, 'outcome': 'COMPLETED', 'blockers': [],
                    'result': {'dry_run': True, 'model': job['request'], 'argv': job['argv']}}
        process, timed_out = job['process'], False
        try:
            process.wait(timeout=job['timeout'])
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        base['stopped_confirmed'] = process.poll() is not None
        raw = (job['dir'] / 'stdout.log').read_bytes()[:2_000_000]
        reply, usage, cost, reported = parse_output(job['harness'], raw.decode('utf-8', 'replace'))
        handoff = self.brief.parse_handoff(reply)
        blockers = []
        if timed_out:
            blockers.append('timeout after %ss' % job['timeout'])
        elif process.returncode != 0:
            blockers.append('exit code %s' % process.returncode)
        if handoff and handoff['status'] == 'BLOCKED':
            blockers += handoff['blockers'] or ['agent reported BLOCKED']
        result = {'exit_code': process.returncode, 'handoff': handoff, 'usage': usage,
                  'cost_usd': cost, 'models_reported': reported, 'model_requested': job['request'],
                  'log': str(job['dir']), 'duration_seconds': round(time.time() - job['started'], 1)}
        with open(self.run_dir / 'runs.jsonl', 'a') as stream:
            stream.write(json.dumps({'pr': job['pr'], 'harness': job['entry']['harness'],
                                     'model': job['entry']['id'], 'blocked': bool(blockers),
                                     **{k: result[k] for k in ('usage', 'cost_usd', 'duration_seconds')}})
                         + '\n')
        return {**base, 'outcome': 'BLOCKED' if blockers else 'COMPLETED', 'blockers': blockers,
                'result': result}


def claude_agents(directory=None):
    """Definitions for `claude --agents`, read from claude/agents/*.md (frontmatter + prompt)."""
    agents = {}
    for path in sorted(Path(directory or METHOD_ROOT / 'claude' / 'agents').glob('*.md')):
        parts = path.read_text().split('---', 2)
        require(len(parts) == 3 and not parts[0].strip(), 'frontmatter required: ' + path.name)
        meta = {}
        for line in parts[1].strip().splitlines():
            key, _, value = line.partition(':')
            meta[key.strip()] = value.strip()
        require(meta.get('name') and meta.get('description'), 'name and description required')
        agents[meta['name']] = {'description': meta['description'], 'prompt': parts[2].strip()}
        if meta.get('tools'):
            agents[meta['name']]['tools'] = [tool.strip() for tool in meta['tools'].split(',')]
        if meta.get('model'):
            agents[meta['name']]['model'] = meta['model']
    require(agents, 'no Claude agent definitions found')
    return agents


def attempts_file(repo):
    return module('build').common_dir(module('workspace').root(repo)) / 'agentic-runs' / 'attempts.json'


def load_attempts(repo):
    path = attempts_file(repo)
    return json.loads(path.read_text()) if path.exists() else []


def record_attempt(repo, entry):
    """Append an observation for agentic-models.route; escalation still needs a diagnosis."""
    require(isinstance(entry.get('task_id'), str) and entry['task_id'].strip(), 'task_id required')
    require(entry.get('outcome') in ('PASS', 'FAIL'), 'outcome must be PASS or FAIL')
    require(entry.get('level') in module('models').LEVELS, 'unknown level')
    path = attempts_file(repo)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    attempts = load_attempts(repo) + [entry]
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        json.dump(attempts, stream)
    os.replace(temporary, path)
    return attempts


def delegate(manifest, repo, config_path=None, state=None, accept=False, dry_run=False,
             commands=None, which=shutil.which, popen=subprocess.Popen):
    config = load_config(config_path or default_config())
    inventory, index = build_inventory(config, which)
    require(index, 'no available model: check config models, "enabled" flags and installed harnesses')
    repo = module('workspace').root(repo)
    gates_config = config.get('gates', {})
    commands = commands or gates_config.get('commands', [])
    run_dir = attempts_file(repo).parent
    if dry_run and not state:
        state = str(Path(tempfile.mkdtemp(prefix='agentic-dry-')) / 'state.json')
    scheduler = module('scheduler').Scheduler(
        manifest, repo, state, skill_roots=[str(METHOD_ROOT / 'skills')], models=inventory,
        attempts=load_attempts(repo))
    adapter = ProcessAdapter(config, index, run_dir, commands, dry_run, popen)
    try:
        final = scheduler.dispatch(adapter)
    finally:
        adapter.close()
    gates, report = module('gates'), {}
    for pr, task in final['tasks'].items():
        entry = {'state': task['state'], 'blockers': task['blockers'],
                 'model_requested': task.get('model_requested')}
        if pr in adapter.finished:
            entry['result'] = task.get('result')
            if task['state'] == 'COMPLETED' and not dry_run:
                gate = gates.run(task['delegation']['worktree'], task['starting_head'],
                                 task['unit']['files'], commands, gates_config, task['plan_sha256'])
                entry['gates'] = {k: gate[k] for k in ('verdict', 'gates', 'stats')}
                if accept and gate['verdict'] == 'PASS':
                    scheduler.accept(pr, gate['acceptance_evidence'])
                    entry['accepted'] = True
        report[pr] = entry
    return report


def quick(repo, task_id, objective, files, criteria, tests=(), implementer='delegated-agent',
          worktree_root=None, **kwargs):
    """One command for a single-capability ticket: worktree, plan, delegate, gates."""
    require(re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,40}', task_id), 'id must be a short slug')
    workspace = module('workspace')
    root = workspace.root(repo)
    path = Path(worktree_root or root.parent / (root.name + '.worktrees')).resolve() / task_id
    workspace.create(root, 'agentic/' + task_id, str(path))
    plan = {'version': 1, 'story': task_id, 'capabilities': [task_id], 'prs': [{
        'id': task_id, 'reason': objective, 'branch': 'agentic/' + task_id, 'worktree': str(path),
        'implementer': implementer, 'capabilities': [task_id], 'acceptance': list(criteria),
        'tests': list(tests) or ['verification commands from agentic.config.json'],
        'depends_on': [], 'files': list(files), 'contracts': []}]}
    manifest = attempts_file(root).parent / task_id / 'plan.json'
    manifest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest.write_text(json.dumps(plan))
    report = delegate(manifest, root, commands=[shlex.split(t) for t in tests] or None, **kwargs)
    return {'worktree': str(path), 'branch': 'agentic/' + task_id, 'plan': str(manifest),
            'tasks': report}


def succeeded(tasks, dry_run):
    return all(t['state'] == 'COMPLETED' and (dry_run or t.get('gates', {}).get('verdict') == 'PASS')
               for t in tasks.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--repo', default='.')
    common.add_argument('--config', help='default: $AGENTIC_CONFIG or <method>/agentic.config.json')
    flags = argparse.ArgumentParser(add_help=False)
    flags.add_argument('--dry-run', action='store_true', help='route and build argv; spawn nothing')
    flags.add_argument('--accept', action='store_true',
                       help='accept tasks whose gates pass (dependency readiness, not merge)')
    sub.add_parser('inventory', parents=[common])
    sub.add_parser('claude-agents')
    run = sub.add_parser('delegate', parents=[common, flags])
    run.add_argument('manifest')
    run.add_argument('--state')
    fast = sub.add_parser('quick', parents=[common, flags])
    fast.add_argument('--id', required=True)
    fast.add_argument('--objective', required=True)
    fast.add_argument('--file', action='append', required=True)
    fast.add_argument('--ac', action='append', required=True, help='acceptance criterion')
    fast.add_argument('--test', action='append', default=[], help='verification command')
    fast.add_argument('--implementer', default='delegated-agent')
    fast.add_argument('--worktree-root')
    note = sub.add_parser('attempt', parents=[common])
    note.add_argument('--task-id', required=True)
    note.add_argument('--outcome', required=True)
    note.add_argument('--level', required=True)
    note.add_argument('--diagnosis-kind')
    note.add_argument('--diagnosis')
    args = parser.parse_args()
    try:
        if args.action == 'inventory':
            result = build_inventory(load_config(args.config or default_config()))[0]
        elif args.action == 'claude-agents':
            print(json.dumps(claude_agents(), sort_keys=True))
            return 0
        elif args.action == 'attempt':
            entry = {k: v for k, v in {'task_id': args.task_id, 'outcome': args.outcome,
                                       'level': args.level, 'diagnosis_kind': args.diagnosis_kind,
                                       'diagnosis': args.diagnosis}.items() if v}
            result = {'attempts': record_attempt(args.repo, entry)}
        else:
            options = dict(config_path=args.config, accept=args.accept, dry_run=args.dry_run)
            if args.action == 'delegate':
                tasks = delegate(args.manifest, args.repo, state=args.state, **options)
                result = {'tasks': tasks}
            else:
                result = quick(args.repo, args.id, args.objective, args.file, args.ac, args.test,
                               args.implementer, args.worktree_root, **options)
                tasks = result['tasks']
            result['verdict'] = 'PASS' if succeeded(tasks, args.dry_run) else 'BLOCKED'
    except (Blocked, ValueError, OSError, KeyError, TypeError) as error:
        result = {'verdict': 'BLOCKED', 'reason': str(error)}
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result.get('verdict', 'PASS') == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
