#!/usr/bin/env python3
"""Contracts and conservative arbitration for opt-in independent analyses.

This module validates evidence supplied by the trusted scheduler. It does not
authenticate an orchestrator or judge the truth of an agent's argument.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath

CATEGORIES = ('decisions', 'risks', 'assumptions')
MAX_BUNDLE_BYTES = 60_000


def require(condition, message):
    if not condition:
        raise ValueError('double analysis: ' + message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def settings(config):
    run = config.get('run', {})
    raw = run.get('double_analysis', {})
    require(isinstance(raw, dict) and set(raw) <= {
        'enabled', 'justification', 'arbitration_file'}, 'invalid configuration')
    enabled = raw.get('enabled', False)
    require(type(enabled) is bool, 'enabled must be a boolean')
    if enabled:
        require(nonempty(raw.get('justification')), 'explicit quota justification required')
        require(run.get('subscription_only') is True, 'subscription_only required')
        missions = run.get('missions', {})
        require(isinstance(missions, dict) and missions.get('enabled') is True,
                'missions.enabled required')
    if 'arbitration_file' in raw:
        require(nonempty(raw['arbitration_file']), 'arbitration_file must be a local path')
    return {**raw, 'enabled': enabled}


def indexed(items, label):
    require(isinstance(items, list), label + ' must be a list')
    result = {}
    for item in items:
        require(isinstance(item, dict) and nonempty(item.get('id')), label + ' needs an id')
        require(item['id'] not in result, 'duplicate ' + label + ' id')
        result[item['id']] = item
    return result


def read_source(tree, source):
    require(set(source) == {'id', 'path'}, 'source needs only id and path')
    name = source.get('path')
    require(nonempty(name), 'source path required')
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name and '..' not in path.parts
            and not any(p in ('.git', '.agentic-local') or p.startswith('.env')
                        for p in path.parts), 'source path must be confined and non-secret')
    target = Path(tree).resolve()
    for part in path.parts:
        target /= part
        require(not target.is_symlink(), 'symlink sources refused')
    require(target.is_file() and target.stat().st_size <= MAX_BUNDLE_BYTES,
            'source must be a bounded regular file')
    return {**source, 'content': target.read_text(encoding='utf-8')}


def bundle(unit, tree, evidence):
    contract = unit.get('analysis')
    require(isinstance(contract, dict) and set(contract) == {'rules', 'sources'},
            'prepared rules and sources required')
    rules = indexed(contract['rules'], 'rules')
    sources = indexed(contract['sources'], 'sources')
    require(rules and sources, 'nonempty rules and sources required')
    require(all(set(r) == {'id', 'text'} and nonempty(r.get('text')) for r in rules.values()),
            'each rule needs text')
    result = {**evidence, 'objective': unit['reason'],
              'acceptance': {'AC%d' % (i + 1): text
                             for i, text in enumerate(unit['acceptance'])},
              'rules': list(rules.values()),
              'sources': [read_source(tree, s) for s in sources.values()]}
    require(len(json.dumps(result, ensure_ascii=True).encode()) <= MAX_BUNDLE_BYTES,
            'inline source bundle exceeds 60000 bytes; prepare smaller explicit sources')
    return {**result, 'bundle_sha256': digest(result)}


def references(entry, contract):
    known = {'acceptance': set(contract['acceptance']),
             'rules': {r['id'] for r in contract['rules']},
             'sources': {s['id'] for s in contract['sources']}}
    for key, allowed in known.items():
        values = entry.get(key)
        require(isinstance(values, list) and values and all(nonempty(v) for v in values)
                and len(values) == len(set(values)) and set(values) <= allowed,
                'invalid or missing ' + key + ' references')


def validate_opinion(opinion, contract):
    require(isinstance(opinion, dict) and set(opinion) == {'bundle_sha256', *CATEGORIES},
            'structured opinion required')
    require(opinion['bundle_sha256'] == contract['bundle_sha256'], 'opinion bundle is stale')
    coverage = {'acceptance': set(), 'rules': set()}
    for category in CATEGORIES:
        items = indexed(opinion[category], category)
        require(category != 'decisions' or items, 'at least one sourced decision required')
        for entry in items.values():
            fields = {'id', 'statement', 'rationale', 'acceptance', 'rules', 'sources'}
            if category == 'risks':
                fields |= {'severity', 'status', 'mitigation'}
                require(entry.get('severity') in ('Critical', 'Major', 'Minor', 'Nit')
                        and entry.get('status') in ('open', 'mitigated')
                        and isinstance(entry.get('mitigation'), str), 'invalid risk')
                require(entry['status'] != 'mitigated' or nonempty(entry['mitigation']),
                        'mitigated risk needs a mitigation')
            require(set(entry) == fields and nonempty(entry.get('statement'))
                    and nonempty(entry.get('rationale')), 'opinion entry needs a sourced argument')
            references(entry, contract)
            for key in coverage:
                coverage[key].update(entry[key])
    require(coverage['acceptance'] == set(contract['acceptance'])
            and coverage['rules'] == {r['id'] for r in contract['rules']},
            'opinion must cover every acceptance criterion and business rule')
    return opinion


def observed_opinions(tasks, contract):
    require(len(tasks) == 2, 'two stopped analyses required')
    sessions, cli_sessions, agents, providers, opinions = set(), set(), set(), set(), []
    for task in tasks:
        require(isinstance(task, dict), 'invalid analysis history')
        execution, stop = task.get('model_execution', {}), task.get('stop_evidence', {})
        require(isinstance(execution, dict) and isinstance(stop, dict),
                'runtime execution and stop evidence required')
        session, cli = execution.get('session_id'), execution.get('cli_session_id')
        provider, agent = task.get('analysis_provider'), task.get('agent_id')
        require(task.get('runtime') in ('native', 'process') and task.get('launch_status') == 'OBSERVED'
                and task.get('active') is False and nonempty(agent)
                and task.get('role') == 'explorer' and task.get('phase') == 'PREPARE'
                and task.get('read_only') is True
                and stop.get('agent_id') == agent and stop.get('stopped_confirmed') is True
                and stop.get('identity_verified') is True and task.get('state') == 'COMPLETED',
                'observed launch and confirmed coherent stop required')
        if task['runtime'] == 'process':
            require(type(execution.get('pid')) is int and execution['pid'] > 0,
                    'observed child PID required')
        require(nonempty(session) and session not in sessions and agent not in agents
                and (not cli or cli not in cli_sessions), 'analyses are not independent sessions')
        require(provider in ('codex', 'claude') and provider not in providers,
                'distinct Codex and Claude launches required')
        result = task.get('result')
        require(isinstance(result, dict), 'runtime result required')
        handoff = result.get('handoff')
        require(isinstance(handoff, dict) and handoff.get('status') == 'COMPLETED'
                and not handoff.get('blockers'),
                'two completed handoffs required')
        opinion = validate_opinion(handoff.get('analysis'), contract)
        opinions.append({'provider': provider, 'opinion': opinion,
                         'identity': {'agent_id': agent, 'execution': execution, 'stop': stop}})
        sessions.add(session)
        agents.add(agent)
        providers.add(provider)
        if cli:
            cli_sessions.add(cli)
    return opinions


def compare(opinions):
    agreements, disputes = [], []
    for category in CATEGORIES:
        left, right = [indexed(o['opinion'][category], category) for o in opinions]
        for key in sorted(left.keys() | right.keys()):
            pair = [left.get(key), right.get(key)]
            critical = category == 'risks' and any(
                e and e['severity'] == 'Critical' and e['status'] == 'open' for e in pair)
            item = {'id': category + ':' + key, 'opinions': pair, 'critical': critical}
            (disputes if pair[0] != pair[1] or critical else agreements).append(item)
    return agreements, disputes


def arbitration_for(path, pr):
    if not path or not Path(path).exists():
        return None
    target = Path(path)
    require(not target.is_symlink() and target.is_file() and target.stat().st_size <= 1_000_000,
            'arbitration must be a bounded local regular file')
    document = json.loads(target.read_text())
    require(isinstance(document, dict) and set(document) == {'version', 'units'}
            and document['version'] == 1 and isinstance(document['units'], dict),
            'invalid arbitration document')
    return document['units'].get(pr)


def resolve(summary, contract, arbitration):
    require(isinstance(arbitration, dict) and set(arbitration) == {
        'bundle_sha256', 'opinions_sha256', 'orchestrator_verified', 'verdict', 'resolutions'},
        'explicit arbitration required')
    require(arbitration['bundle_sha256'] == summary['bundle_sha256']
            and arbitration['opinions_sha256'] == summary['opinions_sha256'],
            'arbitration does not match current bundle and opinions')
    require(arbitration['orchestrator_verified'] is True and arbitration['verdict'] == 'PASS',
            'orchestrator-verified arbitration required')
    entries = arbitration['resolutions']
    require(isinstance(entries, list), 'resolutions must be a list')
    resolved = {}
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == {
            'dispute_id', 'decision', 'rationale', 'acceptance', 'rules', 'sources', 'mitigation'},
            'invalid resolution')
        key = entry['dispute_id']
        require(nonempty(key) and key not in resolved and nonempty(entry['decision'])
                and nonempty(entry['rationale']), 'unique argued resolution required')
        references(entry, contract)
        resolved[key] = entry
    require(set(resolved) == {d['id'] for d in summary['disputes']},
            'resolve every dispute exactly once')
    require(all(not d['critical'] or nonempty(resolved[d['id']]['mitigation'])
                for d in summary['disputes']), 'open critical risk needs a sourced mitigation')


def synthesize(tasks, contract, arbitration=None):
    opinions = observed_opinions(tasks, contract)
    agreements, disputes = compare(opinions)
    result = {'verdict': 'BLOCKED' if disputes else 'PASS',
              'bundle_sha256': contract['bundle_sha256'],
              'opinions_sha256': [digest(o) for o in opinions], 'opinions': opinions,
              'agreements': agreements, 'disputes': disputes,
              'contract': {'acceptance': contract['acceptance'], 'rules': contract['rules'],
                           'sources': [{'id': source['id'], 'path': source['path'],
                                        'sha256': hashlib.sha256(
                                            source['content'].encode()).hexdigest()}
                                       for source in contract['sources']]},
              'quota': None, 'quota_verification': 'not_verified'}
    if disputes:
        try:
            resolve(result, contract, arbitration)
            result.update(verdict='PASS', arbitration=arbitration,
                          arbitration_sha256=digest(arbitration))
        except ValueError as error:
            result['reason'] = str(error)
    return result
