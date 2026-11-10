#!/usr/bin/env python3
"""Persist first-mission choices after subscription checks and isolated smoke tests.

The host asks the questions described in ONBOARDING.md; this noninteractive CLI
never reads answers from a child terminal, installs software or changes accounts.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

METHOD_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('onboarding_run', METHOD_ROOT / 'scripts/agentic-run.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
PROVIDERS = {'codex': 'openai', 'claude': 'anthropic'}
ROLE_PHASES = {'test-author': 'BUILD', 'implementer': 'BUILD', 'reviewer': 'BUILD',
               'lead-tech': 'SHIP', 'explorer': 'PREPARE', 'orchestrator': 'PREPARE'}
MARKER = 'AGENTIC_ONBOARDING_OK'
SMOKE_TIMEOUT = 60
MODEL_FIELDS = ('id', 'harness', 'provider', 'model', 'max_level', 'tiers', 'efforts',
                'cost_rank', 'enabled', 'available', 'modalities')


def require(condition, message):
    if not condition:
        raise ValueError('onboarding: ' + message)


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, 'Git operation failed: ' + args[0])
    return result.stdout.strip()


def project_root(repo):
    return Path(git(repo, 'rev-parse', '--show-toplevel')).resolve()


def safe_path(path):
    require(not any(part.is_symlink() for part in (path, *path.parents)),
            'symlink configuration or parent refused')
    require(not path.exists() or path.is_file(), 'configuration must be a regular file')


def config_path_for(root, config_path):
    configured = config_path or os.environ.get('AGENTIC_CONFIG')
    local = root / '.agentic-local/agentic.config.json'
    if not configured:
        legacy = root / 'agentic.config.json'
        configured = local if local.exists() or not legacy.exists() else legacy
    path = Path(os.path.abspath(root / configured))
    require(path.is_relative_to(root) and '.git' not in path.relative_to(root).parts,
            'configuration must be a private file inside the project')
    require(not any(ord(char) < 32 or ord(char) == 127 for char in str(path)),
            'control characters in configuration path refused')
    safe_path(path)
    return path


def read_config(path):
    safe_path(path)
    if not path.exists():
        return {'version': 1, 'models': []}, None
    original = path.read_bytes()
    try:
        config = RUN.load_config(path)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('onboarding: invalid existing configuration; repair it explicitly') from None
    require(isinstance(config.get('run', {}), dict), 'run must be an object')
    return config, original


def config_digest(config):
    payload = {key: value for key, value in config.items() if key != 'onboarding'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def is_complete(config):
    record = config.get('onboarding', {})
    return (isinstance(record, dict) and record.get('completed') is True
            and record.get('config_sha256') == config_digest(config))


def status(repo, config_path=None):
    """Read local setup state and binary availability, never auth or inference."""
    root = project_root(repo)
    path = config_path_for(root, config_path)
    config, _ = read_config(path)
    return {'verdict': 'PASS', 'config': str(path), 'onboarding_required': not is_complete(config),
            'detected': {name: bool(shutil.which(name)) for name in PROVIDERS},
            'models': [{key: entry[key] for key in MODEL_FIELDS if key in entry}
                       for entry in config['models']],
            'review_cycle': config.get('run', {}).get('review_cycle', {'enabled': False}),
            'runtime_auth': 'not_checked', 'verification': 'recorded_setup_only'}


def check_answers(answers):
    require(isinstance(answers, dict), 'answers must be an object')
    allowed = {'claude', 'reviews', 'models', 'max_attempts', 'max_corrections', 'max_cost_rank'}
    require(not set(answers) - allowed, 'unknown answer fields')
    for key in ('claude', 'reviews'):
        require(type(answers.get(key)) is bool, key + ' requires an explicit yes/no answer')
    for key, minimum in (('max_attempts', 1), ('max_corrections', 0)):
        if key in answers:
            require(type(answers[key]) is int and answers[key] >= minimum,
                    key + ' must be an explicit integer within its limits')


def selected_models(config, answers):
    models = config['models']
    supplied = answers.get('models', [])
    require(isinstance(supplied, list), 'models must be a list of explicit inventory declarations')
    for entry in supplied:
        require(isinstance(entry, dict) and all(isinstance(entry.get(key), str)
                and entry[key].strip() for key in ('id', 'harness', 'model')),
                'model needs explicit id, harness and CLI model')
        require(not entry['model'].startswith('<'), 'fill the actual CLI model identifier')
        matches = [index for index, old in enumerate(models) if old['id'] == entry['id']]
        if matches:
            models[matches[0]] = {**models[matches[0]], **entry}
        else:
            models.append(copy.deepcopy(entry))
    allowed = {'codex', 'claude'} if answers['claude'] else {'codex'}
    active = [entry for entry in models
              if entry.get('enabled', True) and entry.get('available', True)]
    require(active, 'model metadata missing; declare the actual CLI model and capabilities')
    require(all(entry['harness'] in allowed for entry in active),
            'existing enabled provider conflicts with chosen engines; reconcile explicitly')
    require(allowed <= {entry['harness'] for entry in active},
            'model metadata missing for a chosen engine')
    for entry in active:
        name = entry['harness']
        require(entry.get('provider') == PROVIDERS[name], 'declare the model provider explicitly')
        require(RUN.harness_of(config, name) == {'preset': name},
                'custom harness conflicts with subscription-only setup; reconcile explicitly')
        require(shutil.which(name), 'executable missing: ' + name)
    return active


def configure_run(config, answers, active):
    settings = config.setdefault('run', {})
    require(not answers['reviews'] or not RUN.tdd_settings(config)['enabled'],
            'existing enabled TDD conflicts with automatic review in quick; '
            'resolve TDD explicitly or keep the review cycle disabled')
    previous = settings.get('review_cycle', {})
    require(isinstance(previous, dict), 'review_cycle must be an object')
    review = {**previous, 'enabled': answers['reviews']}
    for key, default in (('max_attempts', 7), ('max_corrections', 2)):
        review[key] = answers.get(key, previous.get(key, default))
    rank = max(entry['cost_rank'] for entry in active)
    review['max_cost_rank'] = answers.get('max_cost_rank', previous.get('max_cost_rank', rank))
    review.setdefault('prefer_cross_provider', answers['claude'])
    if review['prefer_cross_provider']:
        review.setdefault('justification', 'Confronter les contributions des deux moteurs choisis')
    RUN.module('scheduler').review_cycle_settings(review)
    if answers['reviews']:
        require(review['max_attempts'] >= 3, 'at least three launches are needed for initial missions')
    settings['review_cycle'] = review
    settings['subscription_only'] = True
    missions = settings.setdefault('missions', {'enabled': True})
    require(isinstance(missions, dict), 'missions must be an object')
    if answers['reviews']:
        missions['enabled'] = True
    analysis = RUN.module('analysis').settings(config)
    require(not analysis['enabled'] or answers['claude'],
            'existing double analysis requires Claude; reconcile explicitly')


def configure_policy(config, answers, active):
    policy = config.get('routing_policy')
    if policy and policy.get('enabled'):
        return
    require(not policy or not policy.get('rules'),
            'existing disabled routing rules need explicit reconciliation')
    by_harness = {name: [entry['id'] for entry in active if entry['harness'] == name]
                  for name in PROVIDERS}
    rules = []
    for role in ROLE_PHASES:
        name = 'claude' if role == 'implementer' and answers['claude'] else 'codex'
        choices = list(by_harness[name])
        if role == 'explorer' and RUN.module('analysis').settings(config)['enabled']:
            choices += by_harness['claude']
        rules.append({'id': 'onboarding-' + role, 'match': {'role': role},
                      'prefer': [{'model': identifier} for identifier in choices],
                      'minimum_level': 'HIGH' if role in ('reviewer', 'lead-tech') else 'LOW',
                      'fallback': 'blocked'})
    config['routing_policy'] = {'version': 1, 'enabled': True, 'rules': rules}


def validated_request(config, inventory, index, role, phase, provider=None):
    task = {'id': 'onboarding-' + role, 'role': role, 'phase': phase,
            'complexity': 'high' if provider or role in ('reviewer', 'lead-tech') else 'medium',
            'session_id': 'setup-review', 'implementer_session_id': 'setup-author'}
    models = RUN.module('models')
    policy = config.get('routing_policy')
    routed = models.route(task, inventory, policy=policy)
    require(routed['verdict'] == 'PASS', role + '/' + phase + ' routing blocked: ' + routed['reason'])
    request = routed['recommendation']
    entry = index[request['model']]
    if provider:
        require(entry['harness'] == provider, 'analysis must use the selected provider')
    elif role in ('lead-tech', 'explorer', 'orchestrator') or (
            role == 'reviewer' and not RUN.review_cycle_settings(config)['enabled']):
        require(entry['harness'] == 'codex', role + ' requires the Codex read-only preset')
    if policy and policy.get('enabled'):
        _, selection = models.policy_context(task, policy['rules'])
        require('effort' not in selection or entry['harness'] == 'codex',
                'Claude preset cannot transmit an explicit effort required by routing')
    return request


def validate_routes(config, active):
    inventory, index = RUN.build_inventory(config)
    require({entry['id'] for entry in active} <= set(index), 'chosen model is unavailable')
    review = RUN.review_cycle_settings(config)
    if review['enabled']:
        inventory['models'] = [entry for entry in inventory['models']
                               if entry['cost_rank'] <= review['max_cost_rank']]
    efforts = {}
    contexts = [(role, phase, None) for role, phase in ROLE_PHASES.items()]
    if RUN.module('analysis').settings(config)['enabled']:
        contexts += [('explorer', 'PREPARE', provider) for provider in PROVIDERS]
    for role, phase, provider in contexts:
        candidates = inventory
        if provider:
            candidates = {**inventory, 'models': [entry for entry in inventory['models']
                                                  if entry['harness'] == provider]}
        request = validated_request(config, candidates, index, role, phase, provider)
        previous = efforts.get(request['model'], 'low')
        efforts[request['model']] = max((previous, request['effort']),
                                         key=RUN.module('models').EFFORTS.get)
    return efforts


def stop_process(process):
    """Stop the CLI's process group, including children, before releasing a probe."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.communicate(timeout=5)


def smoke_process(argv, *, cwd, env, stdin, capture_output, text, timeout):
    require(hasattr(os, 'killpg'), 'smoke process cleanup requires POSIX process groups')
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=text, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        # Also runs on cancellation, KeyboardInterrupt and unexpected exceptions.
        stop_process(process)


def smoke(entry, root, effort, run):
    """One read-only/tool-free access check, with no project sources or raw log retained."""
    harness = {'preset': entry['harness']}
    RUN.check_subscription(harness, root, run or subprocess.run,
                           isolated_claude=entry['harness'] == 'claude')
    with tempfile.TemporaryDirectory(prefix='agentic-onboarding-') as temporary:
        tree = Path(temporary)
        git(tree, 'init', '-q')
        prompt = 'Réponds exactement ' + MARKER + ', sans utiliser aucun outil ni lire de fichier.'
        argv = RUN.build_argv(harness, {
            'prompt': prompt, 'model': entry['model'], 'effort': effort,
            'worktree': str(tree), 'max_turns': 1, 'tools': [], 'read_only': True,
            'review_context': entry['harness'] == 'claude'})
        try:
            result = (run or smoke_process)(
                argv, cwd=tree, env=RUN.child_env(harness), stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=SMOKE_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError('onboarding: ' + entry['harness'] + ' smoke failed ('
                             + type(error).__name__ + ')') from None
        reply = RUN.parse_output(harness, result.stdout)[0]
        structured = RUN.claude_result(harness, result.stdout)
        require(result.returncode == 0 and structured.get('is_error') is not True
                and isinstance(reply, str) and reply.strip() == MARKER,
                entry['harness'] + ' smoke response failed; check access/quota and retry explicitly')


def check_untracked(root, path):
    relative = str(path.relative_to(root))
    require(not git(root, 'ls-files', '--', relative), 'configuration is tracked; choose a private path')


def ensure_ignored(root, path):
    ignored = subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', '--', str(path)],
                             capture_output=True)
    if ignored.returncode == 0:
        return
    require(ignored.returncode == 1, 'cannot check configuration exclusion')
    exclude = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'))
    safe_path(exclude)
    require(exclude.parent.is_dir(), 'Git exclude directory missing')
    relative = path.relative_to(root).as_posix()
    escaped = ''.join('\\' + char if char in '\\*?[]#! ' else char for char in relative)
    with exclude.open('a') as stream:
        stream.write('\n/' + escaped + '\n')
    require(subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', '--', str(path)],
                           capture_output=True).returncode == 0, 'configuration exclusion failed')


def unchanged(path, original):
    safe_path(path)
    require((path.read_bytes() if path.exists() else None) == original,
            'configuration changed concurrently; inspect it before retrying')


def persist(root, path, config, original):
    unchanged(path, original)
    check_untracked(root, path)
    ensure_ignored(root, path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '.',
                                         suffix='.tmp', mode='w', delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        unchanged(path, original)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def configure(repo, answers, config_path=None, reconfigure=False, run=None):
    check_answers(answers)
    root = project_root(repo)
    path = config_path_for(root, config_path)
    config, original = read_config(path)
    require(not is_complete(config) or reconfigure,
            'already configured; use --reconfigure to change the saved choices')
    check_untracked(root, path)
    candidate = copy.deepcopy(config)
    active = selected_models(candidate, answers)
    # Validate declared capacity/effort/rank before deriving any default budget.
    RUN.module('models').legacy_route({'id': 'setup'}, {'models': active})
    configure_run(candidate, answers, active)
    configure_policy(candidate, answers, active)
    efforts = validate_routes(candidate, active)
    for entry in active:
        effort = efforts.get(entry['id']) or min(entry['efforts'], key=RUN.module('models').EFFORTS.get)
        smoke(entry, root, effort, run)
    candidate['onboarding'] = {
        'version': 1, 'completed': True, 'claude': answers['claude'], 'reviews': answers['reviews'],
        'models': [entry['id'] for entry in active], 'verification': 'isolated_smoke_response',
        'capabilities': 'declared', 'config_sha256': config_digest(candidate)}
    persist(root, path, candidate, original)
    return {'verdict': 'PASS', 'config': str(path), 'onboarding_required': False,
            'claude': answers['claude'], 'review_cycle': candidate['run']['review_cycle'],
            'capabilities': 'declared', 'runtime_auth': 'checked_at_setup_only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    for action in ('status', 'configure'):
        command = commands.add_parser(action)
        command.add_argument('--repo', default='.')
        command.add_argument('--config', help='private config; default local or existing project config')
        if action == 'configure':
            command.add_argument('--answers', required=True, help='local JSON with confirmed choices')
            command.add_argument('--reconfigure', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'status':
            result = status(args.repo, args.config)
        else:
            result = configure(args.repo, json.loads(Path(args.answers).read_text()), args.config,
                               args.reconfigure)
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired) as error:
        result = {'verdict': 'BLOCKED', 'reason': str(error)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
