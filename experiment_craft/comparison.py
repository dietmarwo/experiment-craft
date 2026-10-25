"""Predeclared comparison designs over an existing immutable campaign plan.

This module has no runtime dependency: declaring a design cannot launch a job.
Supported adapters deliberately cover one native task per campaign step.
"""
import copy
from importlib.resources import files
import re
import time

import jsonschema

from .manifest import same_value
from .storage import Error, canonical, identity, loads, read_json, require

SCHEMA = 'experiment.comparison/0.1'
BINDING = 'experiment.comparison.binding/0.1'
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
# A design may vary solver choices, never a problem, tolerance or input model.
# New profiles need an explicit reviewed adapter instead of guessed semantics.
ADAPTERS = {
    'fcmaes.retry/1': {
        'sample': '/payload/seed', 'replication': 'seed',
        'vary': {'/payload/optimizer'},
        'work': {'/payload/evaluations_per_retry': 'evaluations'},
    },
    'lp-ip.solve/1': {
        'sample': '/payload/starts/0', 'replication': 'start',
        'vary': {'/payload/presolve'},
        'work': {'/payload/node_limit': 'nodes', '/payload/iteration_limit': 'simplex_iterations'},
    },
    'sqp.solve/1': {
        'sample': '/payload/starts/0', 'replication': 'start',
        'vary': {'/payload/backend'},
        'work': {'/payload/max_iterations': 'iterations'},
    },
}


def parts(pointer):
    require(isinstance(pointer, str) and pointer.startswith('/') and
            not re.search(r'~(?![01])', pointer), 'invalid_protocol', 'invalid JSON pointer')
    return [p.replace('~1', '/').replace('~0', '~') for p in pointer[1:].split('/')]


def at(value, pointer):
    """Return presence separately from null; list indices must be canonical."""
    try:
        for part in parts(pointer):
            if isinstance(value, list):
                require(part.isascii() and part.isdigit() and str(int(part)) == part,
                        'invalid_protocol', 'array indices must be canonical decimal numbers')
                value = value[int(part)]
            elif isinstance(value, dict):
                value = value[part]
            else:
                return False, None
        return True, value
    except (KeyError, IndexError):
        return False, None


def mask(value, pointer):
    path = parts(pointer)
    current = value
    for part in path[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    current[int(path[-1]) if isinstance(current, list) else path[-1]] = {'comparison_parameter': pointer}


def validate_protocol(value):
    schema = read_json(files('experiment_craft').joinpath('schemas/comparison-0.1.schema.json'))
    try:
        jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        raise Error('invalid_protocol', exc.message) from exc
    return value


def closure(plan):
    """Content identity of dependency plans, including preparation code and inputs."""
    result = {}
    for step in plan['steps']:
        job = copy.deepcopy(step['job'])
        for item in job.get('inputs', []):
            if 'from' in item:
                item['from']['step'] = result[item['from']['step']]
        result[step['id']] = identity({'job': job, 'executable': step['executable'],
                                      'needs': [result[n] for n in step['needs']]})
    return result


def resolve(protocol, state):
    """Validate coverage and compatibility and resolve every declared observation."""
    validate_protocol(protocol)
    plan = state['plan']
    require(protocol['plan_id'] == plan['plan_id'], 'protocol_plan_mismatch',
            'comparison protocol names another scientific plan')
    by_template = {}
    for step in plan['steps']:
        by_template.setdefault(step['template'], []).append(step)
    covered, group_ids, groups = set(), set(), []
    dependencies = closure(plan)
    for group in protocol['groups']:
        gid = group['id']
        require(NAME.fullmatch(gid) and gid not in group_ids, 'invalid_protocol', 'duplicate or invalid group ID')
        group_ids.add(gid)
        metrics = group['metrics']
        require(len({m['id'] for m in metrics}) == len(metrics) and
                all(NAME.fullmatch(m['id']) for m in metrics), 'invalid_protocol', 'duplicate or invalid metric ID')
        for metric in metrics:
            require(metric['pointer'].startswith('/outcome/'), 'invalid_protocol', 'metrics address native task outcomes')
            parts(metric['pointer'])
        varied = group['vary']
        require(len(set(varied)) == len(varied), 'invalid_protocol', 'duplicate varied pointer')
        replication, budget = group['replication'], group['budget']
        require(group['design'] != 'paired' or replication['kind'] != 'deterministic',
                'invalid_protocol', 'deterministic timing repeats are not independent paired discoveries')
        require(group['design'] != 'paired' or len(group['arms']) >= 2, 'invalid_protocol', 'pairing needs two arms')
        require(('pointer' in replication) == (replication['kind'] != 'deterministic'),
                'invalid_protocol', 'only seed/start replication has a pointer')
        fingerprints, arm_ids, arms = set(), set(), []
        for arm in group['arms']:
            aid = arm['id']
            require(NAME.fullmatch(aid) and aid not in arm_ids, 'invalid_protocol', 'duplicate or invalid arm ID')
            arm_ids.add(aid)
            samples, settings, units = set(), set(), []
            for template in arm['templates']:
                require(template in by_template and template not in covered, 'invalid_protocol',
                        f'template missing or selected twice: {template}')
                covered.add(template)
                for step in by_template[template]:
                    job = step['job']
                    command = job['schema_version'] == 'execution.command/0.1'
                    require(group['kind'] == ('command' if command else 'optimization'),
                            'incompatible_comparison', 'command and optimization observations cannot be pooled')
                    if command:
                        require(not metrics and not varied and replication['kind'] == 'deterministic' and
                                budget['kind'] == 'fixed_time', 'unsupported_comparison',
                                'commands report exit/output checks and timing; no optimizer metrics or inferred seeds')
                        adapter = None
                    else:
                        profile = job['payload_schema']
                        require(profile in ADAPTERS, 'unsupported_comparison', f'no comparison adapter for {profile}')
                        adapter = ADAPTERS[profile]
                        require(set(varied) <= adapter['vary'], 'unsupported_comparison',
                                'vary only the adapter\'s solver choices, not problems, tolerances or inputs')
                        if profile == 'fcmaes.retry/1':
                            require(job['payload'].get('retries') == 1 and
                                    (budget['kind'] != 'fixed_work' or job['payload'].get('evaluation_limit_mode') == 'hard'),
                                    'unsupported_comparison', 'fcmaes comparisons require one retry; fixed work requires a hard evaluation limit')
                        else:
                            require(isinstance(job['payload'].get('starts'), list) and
                                    len(job['payload']['starts']) == 1, 'unsupported_comparison',
                                    'comparison steps must contain exactly one native start/task')
                    normalized = copy.deepcopy(job)
                    # Source paths are not scientific input identity. Digests and
                    # the preparation closure remain; no derived input is guessed.
                    for item in normalized.get('inputs', []):
                        item.pop('file', None)
                        if 'from' in item:
                            item['from']['step'] = dependencies[item['from']['step']]
                    sample = None
                    if replication['kind'] != 'deterministic':
                        pointer = replication['pointer']
                        require(adapter and pointer == adapter['sample'] and
                                replication['kind'] == adapter['replication'], 'unsupported_comparison',
                                'replication pointer/kind does not match the native profile')
                        present, sample = at(job, pointer)
                        require(present, 'invalid_protocol', 'replication pointer is absent')
                        if replication['kind'] == 'seed':
                            require(type(sample) is int and sample >= 0, 'invalid_protocol', 'a seed must be a nonnegative integer')
                        token = same_value(sample)
                        require(token not in samples, 'invalid_protocol', f'duplicate sample in arm {aid}')
                        samples.add(token)
                        mask(normalized, pointer)
                    chosen = {}
                    for pointer in varied:
                        present, setting = at(job, pointer)
                        require(present, 'invalid_protocol', f'varied pointer is absent: {pointer}')
                        chosen[pointer] = setting
                        mask(normalized, pointer)
                    settings.add(canonical(chosen))
                    require(len(settings) == 1, 'invalid_protocol', 'an arm must have one fixed configuration')
                    if budget['kind'] == 'fixed_work':
                        require(adapter and adapter['work'].get(budget['pointer']) == budget['counter'],
                                'unsupported_comparison', 'work pointer/counter does not match the native profile')
                        present, limit = at(job, budget['pointer'])
                        require(present and type(limit) is int and limit == budget['limit'],
                                'invalid_protocol', 'work limits must match the predeclared cap')
                    else:
                        key = 'wall_seconds' if command else 'wall_time_seconds'
                        require(job['limits'][key] == budget['seconds'], 'invalid_protocol',
                                'wall limits must match the predeclared time cap')
                    fingerprint = identity({'job': normalized, 'executable': step['executable'], 'accept': step['accept']})
                    fingerprints.add(fingerprint)
                    units.append({'step': step['id'], 'sample': sample, 'configuration': chosen})
            arms.append({'id': aid, 'units': units})
        require(len(fingerprints) == 1, 'incompatible_comparison',
                f'group {gid} contains different profiles, models, inputs, tolerances, resources or undeclared choices')
        if group['design'] == 'paired':
            schedules = [{same_value(u['sample']) for u in arm['units']} for arm in arms]
            require(all(schedule == schedules[0] for schedule in schedules), 'invalid_protocol',
                    'paired arms need the same predeclared seed/start schedule')
        groups.append({'id': gid, 'compatibility_id': next(iter(fingerprints)), 'arms': arms})
    excluded = []
    for item in protocol['exclude']:
        template = item['template']
        require(template in by_template and template not in covered, 'invalid_protocol', 'duplicate or unknown exclusion')
        covered.add(template)
        excluded.extend({'step': s['id'], 'reason': item['reason']} for s in by_template[template])
    require(covered == by_template.keys(), 'invalid_protocol',
            'every template must be compared or explicitly excluded with a reason')
    return {'groups': groups, 'excluded': excluded}


def bound_protocol(store):
    row = store.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comparison_protocol'").fetchone()
    require(row is not None, 'comparison_not_declared', 'declare-comparison before the first dispatch')
    row = store.db.execute('SELECT value FROM comparison_protocol WHERE id=1').fetchone()
    require(row is not None, 'comparison_not_declared', 'comparison protocol is missing')
    value = loads(row[0])
    require(isinstance(value, dict), 'comparison_changed', 'comparison binding is not an object')
    payload = {k: v for k, v in value.items() if k != 'binding_id'}
    require(value.get('schema_version') == BINDING and value.get('binding_id') == identity(payload) and
            value.get('protocol_id') == identity(value.get('protocol')), 'comparison_changed', 'comparison binding changed')
    return value


def declare(store, path):
    protocol = validate_protocol(read_json(path))
    with store.advance_lock():
        exists = store.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comparison_protocol'").fetchone()
        if exists:
            saved = bound_protocol(store)
            require(canonical(saved['protocol']) == canonical(protocol), 'comparison_conflict',
                    'this campaign already has a different immutable comparison protocol')
            state = store.read()
            require(saved['campaign_id'] == state['campaign_id'] and saved['plan_id'] == state['plan']['plan_id'],
                    'comparison_changed', 'comparison belongs to another campaign')
            return saved
        with store.edit({'event': 'comparison_declared', 'at': time.time(), 'protocol_id': identity(protocol)}) as state:
            require(state['jobs_reserved'] == 0 and not state['stop_reason'] and
                    all(s['status'] == 'pending' and not s['issued'] for s in state['steps'].values()),
                    'comparison_too_late', 'declare a comparison before any dispatch or completed/failed step')
            design = resolve(protocol, state)
            value = {'schema_version': BINDING, 'campaign_id': state['campaign_id'],
                     'plan_id': state['plan']['plan_id'], 'protocol_id': identity(protocol),
                     'protocol': protocol, 'resolved': design}
            value['binding_id'] = identity(value)
            store.db.execute('CREATE TABLE comparison_protocol (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
            store.db.execute('INSERT INTO comparison_protocol VALUES (1,?)', (canonical(value).decode(),))
        return value
