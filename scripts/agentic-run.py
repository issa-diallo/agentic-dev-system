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
import math
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
import uuid

METHOD_ROOT = Path(__file__).resolve().parents[1]
BASE_ENV = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TERM', 'TMPDIR', 'USER', 'SHELL')
ENV_PRESET = {'claude': ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL'),
              'codex': ('OPENAI_API_KEY', 'CODEX_HOME')}
DEFAULT_TOOLS = ('Read', 'Edit', 'Write', 'Glob', 'Grep')
SUBSCRIPTION_PRESETS = ('claude', 'codex')
CLAUDE_MANAGED_DIR = Path('/etc/claude-code')
# Refuse ambient billing/routing inputs rather than silently stripping them.
SUBSCRIPTION_ENV_PREFIXES = ('OPENAI_', 'ANTHROPIC_', 'AZURE_OPENAI_', 'CODEX_API_',
                             'CLAUDE_CODE_USE_', 'CLAUDE_CODE_OAUTH_TOKEN')
PROXY_ENV = frozenset(('http_proxy', 'https_proxy', 'all_proxy'))
# Codex settings that move inference to another provider or endpoint.
CODEX_ROUTING_KEYS = ('model_provider', 'model_providers', 'openai_base_url', 'chatgpt_base_url')
QUOTA_MARKERS = re.compile(r'usage limit|out of credits|credit balance is too low|'
                           r'quota (?:exceeded|exhausted)|insufficient_quota', re.I)
# Not exposed by either CLI: reported as such, never claimed.
SUBSCRIPTION_UNVERIFIED = {'quota': 'not_verified', 'overage': 'not_verified'}

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
    if v.get('analysis') or v.get('review_context'):
        return ['claude', '-p', v['prompt'], '--model', v['model'], '--output-format', 'json',
                '--max-turns', str(v['max_turns']), '--permission-mode', 'dontAsk',
                '--safe-mode', '--settings', '{"disableAllHooks":true}',
                '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--disallowedTools', 'mcp__*', '--disable-slash-commands', '--setting-sources', '',
                '--no-session-persistence']
    argv = ['claude', '-p', v['prompt'], '--model', v['model'], '--output-format', 'json',
            '--permission-mode', 'acceptEdits', '--max-turns', str(v['max_turns'])] + v['extra']
    return argv + (['--allowedTools', *v['tools']] if v['tools'] else [])  # variadic: keep last


def codex(v):
    sandbox = 'read-only' if v.get('read_only') else 'workspace-write'
    return (['codex', 'exec', '-m', v['model'], '-s', sandbox, '-C', v['worktree'],
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
        require(entry.get('provider') is None or (isinstance(entry['provider'], str)
                and entry['provider'].strip()), 'provider must be an explicit nonempty name or null')
    subscription_only(config)
    module('analysis').settings(config)
    review_cycle_settings(config)
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
        if (entry.get('enabled', True) is False or entry.get('available', True) is False
                or not which(binary(harness))):
            continue
        keep = {k: entry[k] for k in ('id', 'efforts', 'cost_rank', 'tiers', 'max_level',
                                     'harness', 'provider', 'available', 'enabled', 'modalities') if k in entry}
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


def subscription_only(config):
    enabled = config.get('run', {}).get('subscription_only', False)
    require(type(enabled) is bool, 'run.subscription_only must be a boolean')
    return enabled


def billing_name(name):
    return name.startswith(SUBSCRIPTION_ENV_PREFIXES) or name.lower() in PROXY_ENV


def settings_file(path, parse, required=False):
    try:
        data = parse(Path(path).read_text())
    except FileNotFoundError:
        require(not required and not Path(path).is_symlink(),
                'subscription-only: unreadable settings file: %s' % path)
        return {}
    except (OSError, ValueError):
        raise Blocked('subscription-only: unreadable settings file: %s' % path) from None
    require(isinstance(data, dict), 'subscription-only: invalid settings file: %s' % path)
    return data


def claude_managed_settings(environ):
    r"""Read Linux file policy and every nonhidden JSON fragment before probing.

    Other policy stores need dedicated inspection: macOS uses
    /Library/Application Support/ClaudeCode plus managed preferences; Windows uses
    C:\Program Files\ClaudeCode plus HKLM/HKCU; WSL can inherit Windows policy.
    Those platforms are blocked until their complete policy chain can be checked.
    """
    require(sys.platform == 'linux' and 'microsoft' not in os.uname().release.lower()
            and not any(key in environ for key in ('WSL_DISTRO_NAME', 'WSL_INTEROP')),
            'subscription-only: managed settings inspection requires native Linux')
    directory = CLAUDE_MANAGED_DIR / 'managed-settings.d'
    try:
        fragments = sorted(path for path in directory.iterdir()
                           if not path.name.startswith('.') and path.name.endswith('.json'))
    except FileNotFoundError:
        require(not directory.is_symlink(), 'subscription-only: unreadable managed settings directory')
        fragments = []
    except OSError:
        raise Blocked('subscription-only: unreadable managed settings directory') from None
    return [settings_file(CLAUDE_MANAGED_DIR / 'managed-settings.json', json.loads)] + [
        settings_file(path, json.loads, required=True) for path in fragments]


def routing_overrides(preset, worktree, environ):
    """Names (never values) of local settings that reroute the CLI away from the subscription."""
    home = Path(environ.get('HOME') or Path.home())
    found = []
    if preset == 'codex':
        try:
            import tomllib
        except ImportError:
            raise Blocked('subscription-only: Python 3.11+ required to read Codex settings')
        for path in (Path('/etc/codex/config.toml'),
                     Path(environ.get('CODEX_HOME') or home / '.codex') / 'config.toml',
                     Path(worktree) / '.codex' / 'config.toml'):
            config = settings_file(path, tomllib.loads)
            profiles = config.get('profiles')
            tables = [config] + [p for p in (profiles.values() if isinstance(profiles, dict) else ())
                                 if isinstance(p, dict)]
            found += [key for table in tables for key in CODEX_ROUTING_KEYS
                      if key in table and not (key == 'model_provider' and table[key] == 'openai')]
        return found
    settings_sources = claude_managed_settings(environ) + [
        settings_file(path, json.loads) for path in (
            home / '.claude' / 'settings.json', Path(worktree) / '.claude' / 'settings.json',
            Path(worktree) / '.claude' / 'settings.local.json')]
    for settings in settings_sources:
        env = settings.get('env', {})
        require(isinstance(env, dict), 'subscription-only: invalid settings env object')
        found += [key for key in ('apiKeyHelper', 'policyHelper', 'forceLoginGatewayUrl')
                  if key in settings]
        found += [name for name in env if billing_name(name)]
    return found


def probe_subscription(preset, worktree, env, run=subprocess.run):
    """Ask the CLI how it is logged in. No inference; identity fields are not kept."""
    argv = [preset, 'auth', 'status', '--json'] if preset == 'claude' else [preset, 'login', 'status']
    try:
        done = run(argv, cwd=worktree, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                   text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Blocked('subscription-only: %s login check failed (%s)' % (preset, type(error).__name__))
    if preset == 'codex':
        require(done.returncode == 0 and 'Logged in using ChatGPT' in done.stdout + done.stderr,
                'subscription-only: codex is not logged in with ChatGPT (run `codex login`)')
        return {'auth': 'chatgpt', 'plan': None}
    try:
        status = json.loads(done.stdout)
    except ValueError:
        status = None
    require(done.returncode == 0 and isinstance(status, dict) and status.get('loggedIn') is True
            and status.get('authMethod') == 'claude.ai' and status.get('apiProvider') == 'firstParty',
            'subscription-only: claude is not logged in with a Claude subscription '
            '(run `claude auth login`)')
    plan = status.get('subscriptionType')
    return {'auth': 'claude.ai', 'plan': plan if isinstance(plan, str) else None}


def check_claude_isolation(environ):
    """Safe mode preserves managed policy: refuse it, never attempt to override it.

    Only personal plans are accepted later, so a new organization policy cannot be
    fetched after this check. An old remote cache must not apply at startup either.
    """
    home = Path(environ.get('HOME') or Path.home())
    sources = claude_managed_settings(environ)
    sources.append(settings_file(home / '.claude' / 'remote-settings.json', json.loads))
    require(not any(sources),
            'isolated Claude: nonempty managed or remote settings are not supported')


def check_subscription(harness, worktree, run=subprocess.run, isolated_claude=False):
    """Allow an unmodified codex/claude preset only when logged in with a subscription.

    Proven before launch: no API key, endpoint or proxy in the environment or in the
    CLI settings, and the CLI's own login method. Remaining quota and paid overage or
    credits are not exposed by the CLIs: they are reported not_verified. Disable paid
    overage in the account. The executable is the one found on PATH (origin not verified).
    """
    preset = harness.get('preset')
    require(preset in SUBSCRIPTION_PRESETS and harness == {'preset': preset},
            'subscription-only: harness must be an unmodified codex or claude preset')
    require(not any(billing_name(name) for name in os.environ),
            'subscription-only: billing or endpoint environment inputs are forbidden')
    if isolated_claude:
        check_claude_isolation(os.environ)
    found = routing_overrides(preset, worktree, os.environ)
    require(not found, 'subscription-only: routing settings forbidden: ' + ', '.join(sorted(set(found))))
    require(shutil.which(preset), 'subscription-only: executable not found: ' + preset)
    subscription = probe_subscription(preset, worktree, child_env(harness), run)
    if isolated_claude:
        require(subscription['plan'] in ('pro', 'max', 'ultra'),
                'isolated Claude: verified personal subscription (pro/max/ultra) required; '
                'organization or unknown plans may load uninspected remote settings')
    return {**subscription, **SUBSCRIPTION_UNVERIFIED}


def quota_exhausted(job):
    """A subscription run that failed on its usage limit; the scheduler never retries it.

    Only the CLI's own error channel is read (stderr, or Claude's JSON error result), never
    the agent transcript, so a task about rate limiting is not misreported as quota.
    """
    if job.get('subscription') is None or job['process'].returncode is None:
        return False
    stderr = job['dir'] / 'stderr.log'
    text = (stderr.read_bytes()[-20_000:].decode('utf-8', 'replace')
            if job['process'].returncode != 0 and stderr.exists() else '')
    if job['harness'].get('preset') == 'claude':
        try:
            data = json.loads((job['dir'] / 'stdout.log').read_text())
        except (OSError, ValueError):
            data = None
        if (isinstance(data, dict) and data.get('is_error') is True
                and isinstance(data.get('result'), str)):
            text += '\n' + data['result']
    return bool(QUOTA_MARKERS.search(text))


def tool_rules(config, commands):
    run = config.get('run', {})
    return list(run.get('allowed_tools', DEFAULT_TOOLS)) + [
        'Bash(%s)' % shlex.join(command) for command in commands]


def claude_result(harness, text):
    """Return only a structured result emitted by the Claude CLI, never handoff claims."""
    if harness.get('preset') != 'claude' or 'argv' in harness:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    if isinstance(data, list):
        data = next((i for i in reversed(data) if isinstance(i, dict) and i.get('type') == 'result'), {})
    return data if isinstance(data, dict) else {}


def parse_output(harness, text):
    """Return (reply_text, usage, cost, models). Only Claude's JSON carries metrics."""
    data = claude_result(harness, text)
    models = data.get('modelUsage')
    return (data.get('result') if isinstance(data.get('result'), str) else text,
            data.get('usage'), data.get('total_cost_usd'),
            sorted(models) if isinstance(models, dict) else None)


def numeric_metric(value):
    """CLI metrics are observations, not arbitrary transcript-bearing JSON."""
    number = type(value) is int or (type(value) is float and math.isfinite(value))
    return value if number and value >= 0 else None


def mission_metadata(task):
    """Project decision/execution metadata without prompts, handoffs or diagnoses."""
    routing, result = task.get('model_routing') or {}, task.get('result') or {}
    policy, selection = routing.get('policy') or {}, routing.get('review_selection') or {}
    raw_usage = result.get('usage')
    counters = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
                'cache_read_input_tokens')
    usage = {key: numeric_metric(raw_usage[key]) for key in counters if key in raw_usage
             and numeric_metric(raw_usage[key]) is not None} if isinstance(raw_usage, dict) else {}
    return {'role': task.get('role'), 'phase': task.get('phase'),
            'routing_decision': {
                'level': routing.get('level'), 'reason': routing.get('reason'),
                'source': policy.get('source', 'legacy' if routing else None),
                'matched_rule': policy.get('matched_rule'),
                'preference_index': policy.get('preference_index'),
                'fallback_used': policy.get('fallback_used'),
                'review_selection': {key: selection.get(key) for key in
                                     ('reason', 'alternative_available', 'provider_provenance')}
                                    if selection else None,
                'provenance': 'model router recommendation' if routing else None},
            'attempts_used': task.get('attempts_used'),
            'duration_seconds': numeric_metric(result.get('duration_seconds')),
            'usage': usage or None, 'cost_usd': numeric_metric(result.get('cost_usd'))}


class ProcessAdapter:
    """Scheduler adapter: launch() spawns, wait() joins. dry_run spawns no agent (subscription_only
    still runs the login check, which makes no inference)."""

    def __init__(self, config, index, run_dir, commands=(), dry_run=False, popen=subprocess.Popen,
                 run_probe=subprocess.run):
        self.config, self.index, self.run_dir = config, index, Path(run_dir)
        self.commands, self.dry_run, self.popen = commands, dry_run, popen
        self.run_probe = run_probe
        self.jobs, self.finished = {}, []
        self.brief = module('brief')

    def launch(self, task):
        pr = task['unit']['id']
        request = task.get('model_requested')
        require(request and request['model'] in self.index, 'routed model not in inventory')
        entry = self.index[request['model']]
        harness, run = entry['harness_config'], self.config.get('run', {})
        read_only = task.get('role') in self.brief.READ_ONLY_ROLES
        analyzing = bool(task['delegation'].get('analysis') and task.get('phase') == 'PREPARE'
                         and task.get('role') == 'explorer')
        reviewing = bool(task['delegation'].get('review_context'))
        if reviewing:
            require(subscription_only(self.config) and review_cycle_settings(self.config)['enabled'],
                    'review cycle requires enabled subscription-only configuration')
        if read_only:
            require(harness == {'preset': 'codex'} or (
                (reviewing or (analyzing and task.get('analysis_provider') == 'claude'))
                and harness == {'preset': 'claude'}),
                    'read-only missions require the unmodified codex preset')
        if analyzing:
            require(subscription_only(self.config), 'double analysis requires subscription-only')
            require(harness == {'preset': task['analysis_provider']},
                    'analysis requires the matching unmodified provider preset')
        active_policy = bool(self.config.get('routing_policy', {}).get('enabled'))
        preset = harness.get('preset') if 'argv' not in harness else None
        tokens = ' '.join(harness.get('argv', []))
        model_sent = preset in PRESETS or '{model}' in tokens
        effort_sent = preset == 'codex' or '{effort}' in tokens
        require(not task.get('model_effort_required') or effort_sent,
                'configured harness cannot transmit required effort')
        if active_policy:
            require(model_sent, 'configured harness cannot transmit selected model')
            require(not harness.get('extra_args'),
                    'active routing policy refuses preset argument overrides')
        subscription = (check_subscription(harness, task['delegation']['worktree'], self.run_probe,
                                           isolated_claude=preset == 'claude' and (analyzing or reviewing))
                        if subscription_only(self.config) else None)
        launch_id = uuid.uuid4().hex
        directory = self.run_dir / pr / (time.strftime('%Y%m%dT%H%M%S') + '-' + launch_id)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        commands = self.commands(task) if callable(self.commands) else list(self.commands)
        prompt = self.brief.render(task['delegation'], commands, task.get('skill_instructions'))
        (directory / 'brief.md').write_text(prompt)
        argv = build_argv(harness, {
            'prompt': prompt, 'model': entry['model'], 'effort': request['effort'],
            'worktree': task['delegation']['worktree'], 'max_turns': run.get('max_turns', 40),
            'tools': tool_rules(self.config, commands), 'read_only': read_only, 'analysis': analyzing,
            'review_context': reviewing})
        job = {'pr': pr, 'dir': directory, 'harness': harness, 'entry': entry, 'request': request,
               'argv': [a if a != prompt else '<brief.md>' for a in argv],
               'timeout': run.get('timeout_seconds', 1800), 'started': time.time(),
               'subscription': subscription,
               'transmission_supported': {'model': model_sent, 'effort': effort_sent},
               'model_execution': {
                   'selected': dict(request),
                   'requested': {'model': entry['model'], 'effort': request['effort']},
                   'observed': {'model': None, 'effort': None},
                   'applied': {'model': False, 'effort': False},
                   'transmitted': {'model': False, 'effort': False},
                   'harness': entry['harness'], 'provider': entry.get('provider'),
                   'pid': None, 'session_id': None, 'cli_session_id': None,
                   'provenance': {'selected': 'model router recommendation',
                                  'requested': 'configured argv; transmission is not execution proof',
                                  'provider': 'model configuration' if entry.get('provider') else None,
                                  'identity': None, 'model': None, 'effort': None}}}
        if self.dry_run:
            job['agent_id'] = 'dry-run:' + pr
            self.jobs[pr] = job
            return {'agent_id': job['agent_id'], 'runtime': 'simulated', 'launch_observed': True,
                    'identity_verified': True, 'model_execution': job['model_execution']}
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
        job['model_execution'].update(pid=process.pid, session_id='process:' + launch_id)
        job['model_execution']['provenance']['identity'] = (
            'runner launch UUID correlated with spawned child PID; not a CLI session')
        # The child is held at the handshake, so no model arguments have been consumed yet.
        receipt = json.loads(json.dumps(job['model_execution']))
        receipt['transmitted'] = {'model': False, 'effort': False}
        self.jobs[pr] = job
        return {'agent_id': job['agent_id'], 'runtime': 'process', 'launch_observed': True,
                'identity_verified': True, 'model_observed': None, 'model_execution': receipt}

    def release(self):
        """Let every receipted agent start. dispatch() calls wait() only after all receipts."""
        for job in self.jobs.values():
            if not job.get('released') and 'process' in job:
                job['released'] = True
                try:
                    job['process'].stdin.write(b'go\n')
                    job['process'].stdin.close()
                    job['model_execution']['transmitted'] = dict(job['transmission_supported'])
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
                    'result': {'dry_run': True, 'model': job['request'], 'argv': job['argv'],
                               'subscription': job['subscription']},
                    'model_execution': job['model_execution']}
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
        execution = job['model_execution']
        metadata = claude_result(job['harness'], raw.decode('utf-8', 'replace'))
        session = metadata.get('session_id')
        if isinstance(session, str) and session.strip():
            execution['cli_session_id'] = session
            execution['provenance']['cli_session_id'] = 'CLI stdout Claude result.session_id'
        execution['observed']['model'] = (
            reported[0] if reported and len(reported) == 1 and reported[0].strip() else None)
        execution['applied']['model'] = (execution['observed']['model'] is not None
                                        and execution['observed']['model'] == job['entry']['model'])
        if reported:
            execution['provenance']['model'] = 'CLI stdout Claude modelUsage; aliases not resolved'
        handoff = self.brief.parse_handoff(reply)
        blockers = []
        if timed_out:
            blockers.append('timeout after %ss' % job['timeout'])
        elif quota_exhausted(job):
            blockers.append('subscription-only: quota exhausted; no automatic retry')
        elif process.returncode != 0:
            blockers.append('exit code %s' % process.returncode)
        if handoff and handoff['status'] == 'BLOCKED':
            blockers += handoff['blockers'] or ['agent reported BLOCKED']
        result = {'exit_code': process.returncode, 'handoff': handoff, 'usage': usage,
                  'cost_usd': cost, 'models_reported': reported, 'model_requested': job['request'],
                  'log': str(job['dir']), 'duration_seconds': round(time.time() - job['started'], 1),
                  'subscription': job['subscription'], 'model_execution': execution}
        with open(self.run_dir / 'runs.jsonl', 'a') as stream:
            stream.write(json.dumps({'pr': job['pr'], 'harness': job['entry']['harness'],
                                     'model': job['entry']['id'], 'blocked': bool(blockers),
                                     'model_execution': execution,
                                     **mission_metadata({**task, 'result': result})})
                         + '\n')
        return {**base, 'outcome': 'BLOCKED' if blockers else 'COMPLETED', 'blockers': blockers,
                'result': result, 'model_execution': execution}


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


def review_cycle_settings(config):
    return module('scheduler').review_cycle_settings(config.get('run', {}).get('review_cycle'))


def missions_enabled(config):
    raw = config.get('run', {}).get('missions', {})
    require(isinstance(raw, dict) and set(raw) <= {'enabled'},
            'run.missions must contain only enabled')
    enabled = raw.get('enabled', False)
    require(type(enabled) is bool, 'run.missions.enabled must be a boolean')
    return enabled


def mission_pipeline(scheduler, adapter, commands_for, settings, accept, dry_run):
    """Use the existing task/ownership lifecycle, retaining every stopped mission."""
    gates = module('gates')
    if not dry_run and scheduler.double_analysis['enabled']:
        for pr in scheduler.pending_analyses():
            scheduler.resolve_analysis(pr)
    while True:
        final = scheduler.dispatch(adapter)
        advanced = False
        for pr, task in final['tasks'].items():
            if dry_run or task['state'] != 'COMPLETED' or not task.get('mission_roles'):
                continue
            if task.get('mission_complete'):
                if accept and not task.get('accepted'):
                    scheduler.accept(pr, task['mission_gate']['acceptance_evidence'])
                    advanced = True
                continue
            if task['phase'] == 'PREPARE' and task.get('analysis_required'):
                gate = {'verdict': 'PASS', 'snapshot': task['result_snapshot'],
                        'plan_sha256': task['plan_sha256'], 'base': task['starting_head']}
            elif task['role'] == 'reviewer':
                gate = task['verify_evidence']
            else:
                options = {**settings, 'baseline_only': task['role'] == 'test-author'}
                gate = gates.run(task['delegation']['worktree'], task.get('scope_base', task['starting_head']),
                                 task['unit']['files'], commands_for(task), options, task['plan_sha256'])
            checked = scheduler.finish_mission(pr, gate)
            if checked['state'] == 'PLANNED':
                advanced = True
            elif checked.get('mission_complete') and accept:
                scheduler.accept(pr, checked['mission_gate']['acceptance_evidence'])
                advanced = True  # Dependants may now be ready.
        if not advanced:
            break
    final = scheduler.resume()
    report = {}
    for pr, task in final['tasks'].items():
        entry = {k: task.get(k) for k in ('state', 'blockers', 'model_requested',
                                         'model_execution', 'result')}
        entry.update(mission_metadata(task))
        if task.get('analysis_summary'):
            entry['analysis'] = task['analysis_summary']
            if task.get('analysis_stale'):
                entry['analysis'] = {**entry['analysis'], 'verdict': 'BLOCKED', 'stale': True,
                                     'historical_verdict': task['analysis_summary']['verdict'],
                                     'reason': task['analysis_stale']}
        if task.get('review_identity'):
            entry['review_identity'] = task['review_identity']
        entry['missions'] = [{**mission_metadata(h['task']), 'agent_id': h['task']['agent_id'],
                              'gate': h['gate']['verdict'],
                              'model_execution': h['task'].get('model_execution')}
                             for h in task.get('mission_history', [])]
        if task.get('mission_complete') and task['state'] == 'COMPLETED':
            entry.update(gates=task['mission_gate'], next='SHIP', accepted=task.get('accepted', False))
        elif dry_run:
            entry['dry_run'] = True
        report[pr] = entry
    return report


def delegate(manifest, repo, config_path=None, state=None, accept=False, dry_run=False,
             commands=None, which=shutil.which, popen=subprocess.Popen, gates_extra=None,
             missions=None):
    config = load_config(config_path or default_config())
    inventory, index = build_inventory(config, which)
    require(index, 'no available model: check config models, "enabled" flags and installed harnesses')
    repo = module('workspace').root(repo)
    gates_config = {**config.get('gates', {}), **(gates_extra or {})}
    configured = commands or gates_config.get('commands', 'auto')
    mission_mode = missions_enabled(config) if missions is None else missions
    analysis = module('analysis').settings(config)
    review_cycle = review_cycle_settings(config)
    require(not review_cycle['enabled'] or (mission_mode and subscription_only(config)),
            'review cycle requires missions and subscription-only')
    require(not analysis['enabled'] or mission_mode,
            'double analysis requires the mission pipeline; explicit TDD is not supported')
    detect = module('detect')

    def commands_for(task):
        if task['delegation'].get('analysis'):
            return []
        if configured != 'auto':
            return configured
        found = detect.detect(task['delegation']['worktree'], task['unit']['files'])
        return [c['argv'] for c in found['commands']]

    run_dir = attempts_file(repo).parent
    if dry_run and not state:
        state = str(Path(tempfile.mkdtemp(prefix='agentic-dry-')) / 'state.json')
    scheduler = module('scheduler').Scheduler(
        manifest, repo, state, skill_roots=[str(METHOD_ROOT / 'skills')], models=inventory,
        attempts=load_attempts(repo), routing_policy=config.get('routing_policy'),
        missions=mission_mode, review_cycle=review_cycle,
        double_analysis=analysis,
        analysis_models={provider: [identifier for identifier, entry in index.items()
                                   if entry['harness_config'] == {'preset': provider}]
                         for provider in ('codex', 'claude')},
        execution_context={'config': config, 'commands': configured} if mission_mode else None)
    adapter = ProcessAdapter(config, index, run_dir, commands_for, dry_run, popen)
    try:
        if mission_mode:
            return mission_pipeline(scheduler, adapter, commands_for, gates_config, accept, dry_run)
        final = scheduler.dispatch(adapter)
    finally:
        adapter.close()
    gates, report = module('gates'), {}
    for pr, task in final['tasks'].items():
        entry = {'state': task['state'], 'blockers': task['blockers'],
                 'model_requested': task.get('model_requested'),
                 'model_execution': task.get('model_execution'), **mission_metadata(task)}
        if pr in adapter.finished:
            entry['result'] = task.get('result')
            if task['state'] == 'COMPLETED' and not dry_run:
                gate = gates.run(task['delegation']['worktree'], task['starting_head'],
                                 task['unit']['files'], commands_for(task), gates_config, task['plan_sha256'])
                entry['gates'] = {k: gate[k] for k in ('verdict', 'gates', 'stats')}
                if accept and gate['verdict'] == 'PASS':
                    scheduler.accept(pr, gate['acceptance_evidence'])
                    entry['accepted'] = True
        report[pr] = entry
    return report


def _plan(root, plan_id, branch, path, objective, files, criteria, tests, implementer, routing=None):
    plan = {'version': 1, 'story': plan_id, 'capabilities': [plan_id], 'prs': [{
        'id': plan_id, 'reason': objective, 'branch': branch, 'worktree': str(path),
        'implementer': implementer, 'capabilities': [plan_id], 'acceptance': list(criteria),
        'tests': list(tests) or ['verification commands from agentic.config.json'],
        'depends_on': [], 'files': list(files), 'contracts': []}]}
    if routing:
        plan['prs'][0]['routing'] = routing
    manifest = attempts_file(root).parent / plan_id / 'plan.json'
    manifest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest.write_text(json.dumps(plan))
    return manifest


LEVEL_ROUTING = {'LOW': {'type': 'mechanical', 'complexity': 'simple', 'risk': 'low'}, 'MEDIUM': {},
                 'HIGH': {'complexity': 'high'}, 'EXTRA_HIGH': {'risk': 'critical'}}
RISKY = re.compile(r'auth|login|password|mot de passe|token|secret|credential|migration|schema|\.sql\b|'
                   r'paiement|payment|permission|tenant', re.I)


def tdd_settings(config):
    """run.tdd: false | true | {enabled, red_level, green_level, review_before_green}."""
    raw = config.get('run', {}).get('tdd', False)
    raw = {'enabled': raw} if isinstance(raw, bool) else dict(raw)
    settings = {'enabled': True, 'red_level': 'MEDIUM', 'green_level': 'LOW',
                'review_before_green': 'auto', **raw}
    require(settings['red_level'] in LEVEL_ROUTING and settings['green_level'] in LEVEL_ROUTING,
            'tdd levels must be LOW, MEDIUM, HIGH or EXTRA_HIGH')
    require(settings['review_before_green'] in (True, False, 'auto'),
            'review_before_green must be true, false or "auto"')
    return settings


def needs_review(settings, review, objective, files, rules):
    """Review of the red tests before green: explicit flag, else config, else risk heuristic."""
    if review is not None:
        return review
    if settings['review_before_green'] == 'auto':
        return bool(RISKY.search(' '.join([objective, *files, *rules])))
    return settings['review_before_green']


def quick(repo, task_id, objective, files, criteria, tests=(), implementer='delegated-agent',
          worktree_root=None, rules=(), tdd=None, review=None, green_only=False, **kwargs):
    """One command for a single-capability ticket: worktree, plan, delegate, gates.

    TDD (config run.tdd): phase red writes only the tests of the business rules, on its own
    model level, and must fail; the orchestrator commits them; phase green implements with the
    test files out of scope, so any edit to them is a scope FAIL. When the red tests need a
    review (risky ticket or --review-red) the run stops after the commit; --green-only resumes.
    """
    require(re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,40}', task_id), 'id must be a short slug')
    workspace = module('workspace')
    root = workspace.root(repo)
    config = load_config(kwargs.get('config_path') or default_config())
    settings = tdd_settings(config)
    if tdd is None:
        tdd = settings['enabled'] and bool(config.get('run', {}).get('tdd'))
    verify = [shlex.split(t) for t in tests] or None
    path = Path(worktree_root or root.parent / (root.name + '.worktrees')).resolve() / task_id
    gates_module = module('gates')
    test_files = [f for f in files if gates_module.TEST_PATH.search(f)]
    source_files = [f for f in files if f not in test_files]
    if tdd:
        kwargs = {**kwargs, 'missions': False}  # Explicit TDD keeps its existing two-phase contract.
        require(rules or green_only, 'TDD needs the ticket business rules (--rule "RM1: ..."); --no-tdd '
                'only for docs, config, covered refactor or spike')
        require(test_files, 'TDD needs test files in scope (paths such as tests/test_x.py)')
        require(source_files, 'TDD needs source files to implement after the tests')
        ids = [re.match(r'\s*([A-Za-z][\w-]*)', r).group(1) for r in rules if re.match(r'\s*[A-Za-z][\w-]*', r)]
        require(len(ids) == len(rules), 'each rule starts with its identifier, e.g. "RM1: ..."')
    require(not green_only or tdd, '--green-only needs TDD')
    if not green_only:
        workspace.create(root, 'agentic/' + task_id, str(path))
    if not tdd:
        manifest = _plan(root, task_id, 'agentic/' + task_id, path, objective, files, criteria, tests,
                         implementer)
        report = delegate(manifest, root, commands=verify, **kwargs)
        return {'worktree': str(path), 'branch': 'agentic/' + task_id, 'plan': str(manifest),
                'tasks': report}
    result = {'worktree': str(path), 'branch': 'agentic/' + task_id}
    if green_only:
        require(path.is_dir(), 'no worktree to resume: run the red phase first')
        require('Tests (rouge)' in workspace.git(path, 'log', '-1', '--format=%s'),
                'the last commit is not the red tests commit')
    else:
        red_id = task_id + '-red'
        red_manifest = _plan(
            root, red_id, 'agentic/' + task_id, path,
            'Écris UNIQUEMENT les tests unitaires des règles métier de : ' + objective + '. Aucun code de '
            'production. Chaque test nomme sa règle (RM1…) dans son nom ou un commentaire. Les tests '
            'doivent échouer maintenant, sur une assertion.',
            test_files, ['Règle ' + r for r in rules], tests, implementer,
            LEVEL_ROUTING[settings['red_level']])
        red = delegate(red_manifest, root, commands=verify,
                       gates_extra={'expect_red': True, 'rule_ids': ids}, **{**kwargs, 'accept': True})
        result.update(plan=str(red_manifest), phase='red', tasks=red)
        if kwargs.get('dry_run') or not succeeded(red, False):
            return result
        workspace.git(path, 'add', '--', *test_files)
        workspace.git(path, 'commit', '-q', '-m', '✅ Tests (rouge) : ' + task_id)
        if needs_review(settings, review, objective, source_files + test_files, rules):
            return {**result, 'phase': 'awaiting-review', 'awaiting_review': True,
                    'next': 'review the red tests (%s), then rerun the same command with --green-only'
                            % ', '.join(test_files)}
        result['red'] = red
    green_manifest = _plan(
        root, task_id, 'agentic/' + task_id, path,
        objective + ' Les tests existent déjà et sont verrouillés (ne les modifie pas) : '
        + ', '.join(test_files) + '. Fais-les passer.',
        source_files, list(criteria) + ['Les tests des règles métier passent sans être modifiés'], tests,
        implementer, LEVEL_ROUTING[settings['green_level']])
    green = delegate(green_manifest, root, commands=verify,
                     gates_extra={'require_tests': False}, **kwargs)
    return {**result, 'phase': 'green', 'plan': str(green_manifest), 'tasks': green}


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
    flags.add_argument('--dry-run', action='store_true', help='route and build argv; spawn no agent')
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
    fast.add_argument('--rule', action='append', default=[], help='business rule "RM1: ..." (TDD)')
    fast.add_argument('--no-tdd', action='store_true', help='docs, config, covered refactor, spike')
    fast.add_argument('--review-red', action='store_true', default=None,
                      help='stop after the red tests commit for review (auto on risky tickets)')
    fast.add_argument('--no-review-red', dest='review_red', action='store_false')
    fast.add_argument('--green-only', action='store_true', help='resume after the red tests review')
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
                               args.implementer, args.worktree_root, rules=args.rule,
                               tdd=False if args.no_tdd else None, review=args.review_red,
                               green_only=args.green_only, **options)
                tasks = result['tasks']
            result['verdict'] = ('AWAITING_REVIEW' if result.get('awaiting_review') else
                                 'PASS' if succeeded(tasks, args.dry_run) else 'BLOCKED')
    except (Blocked, ValueError, OSError, KeyError, TypeError) as error:
        result = {'verdict': 'BLOCKED', 'reason': str(error)}
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result.get('verdict', 'PASS') in ('PASS', 'AWAITING_REVIEW') else 1


if __name__ == '__main__':
    raise SystemExit(main())
