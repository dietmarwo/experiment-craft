"""Deterministic bounded expansion; no runtime call or execution in dry-run."""
import copy
from fractions import Fraction
from importlib.resources import files
import itertools
from pathlib import Path
import re
import jsonschema
from .storage import Error, MAX_JSON, canonical, exact, fingerprint, identity, number, read_json, require

NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
KINDS = {'optimization.job/0.1', 'execution.command/0.1'}


def pointer_parts(pointer):
    require(pointer.startswith(('/payload/', '/resources/', '/limits/')),
            'invalid_matrix', 'matrix pointers must address existing payload/resources/limits fields')
    require(not re.search(r'~(?![01])', pointer), 'invalid_matrix', 'invalid JSON pointer escape')
    return [part.replace('~1', '/').replace('~0', '~') for part in pointer[1:].split('/')]


def array_index(part, pointer):
    # Only the canonical decimal form selects an element, so two spellings
    # (/0, /00, /+0) can never address the same value.
    require(part.isascii() and part.isdigit() and str(int(part)) == part,
            'invalid_matrix', f'array index must be a plain decimal number: {pointer}')
    return int(part)


def set_pointer(job, pointer, value):
    parts = pointer_parts(pointer)
    current = job
    try:
        for part in parts[:-1]:
            current = current[array_index(part, pointer)] if isinstance(current, list) else current[part]
        last = array_index(parts[-1], pointer) if isinstance(current, list) else parts[-1]
        require(last in current if isinstance(current, dict) else 0 <= last < len(current),
                'invalid_matrix', f'unknown pointer: {pointer}')
        current[last] = copy.deepcopy(value)
    except (KeyError, IndexError, TypeError) as exc:
        raise Error('invalid_matrix', f'unknown pointer: {pointer}') from exc


def same_value(value):
    """A comparison key under which 5, 5.0 and -0.0/0 coincide but true and 1 do not."""
    if value is None or isinstance(value, (bool, str)):
        return (type(value).__name__, value)
    if isinstance(value, (int, float)):
        return ('number', Fraction(value))
    if isinstance(value, list):
        return ('array', tuple(same_value(v) for v in value))
    return ('object', tuple(sorted((k, same_value(v)) for k, v in value.items())))


def local_file(base, name):
    path = Path(name)
    require(not path.is_absolute() and path.parts and all(p not in ('.', '..') and not p.startswith('.') for p in path.parts),
            'invalid_input', 'input file must be a contained relative path without dot-prefixed segments')
    candidate = base
    for part in path.parts:
        candidate = candidate / part
        require(not candidate.is_symlink(), 'invalid_input', 'source input symlinks are not accepted')
    require(candidate.resolve().is_relative_to(base), 'invalid_input', 'input escapes manifest directory')
    return candidate


def compile_manifest(path):
    path = Path(path).resolve()
    raw = read_json(path)
    schema = read_json(files('experiment_craft').joinpath('schemas/campaign-0.1.schema.json'))
    try:
        jsonschema.Draft202012Validator(schema).validate(raw)
    except jsonschema.ValidationError as exc:
        raise Error('invalid_campaign', exc.message) from exc
    require(all(NAME.fullmatch(step['id']) for step in raw['steps']), 'invalid_campaign', 'step ids must use ASCII letters, digits, underscore or dash')
    templates = {step['id']: step for step in raw['steps']}
    require(len(templates) == len(raw['steps']), 'invalid_campaign', 'duplicate step id')
    expanded, family, sources = [], {}, {}
    for template in raw['steps']:
        name = template['id']
        matrix = template.get('matrix', {})
        pointers = sorted(matrix)
        parts = {pointer: pointer_parts(pointer) for pointer in pointers}
        for a in pointers:
            for b in pointers:
                require(a == b or parts[b][:len(parts[a])] != parts[a], 'invalid_matrix',
                        f'matrix pointers overlap: {a} contains {b}')
        combinations = 1
        for pointer in pointers:
            values = matrix[pointer]
            require(len({same_value(v) for v in values}) == len(values), 'invalid_matrix',
                    'duplicate matrix values (numbers compare by value)')
            combinations *= len(values)
        require(len(expanded) + combinations <= 4096, 'expansion_limit', 'campaign exceeds 4096 expanded jobs')
        family[name] = []
        for values in itertools.product(*(matrix[p] for p in pointers)):
            job = copy.deepcopy(template['job'])
            require('request_key' not in job, 'invalid_campaign', 'campaign assigns request keys')
            require(job.get('schema_version') in KINDS, 'unsupported_job_kind', 'local command/optimization jobs only; fleet is not supported')
            axes = dict(zip(pointers, values))
            for pointer, value in axes.items():
                set_pointer(job, pointer, value)
            kind = job['schema_version']
            allowed = ({'schema_version', 'argv', 'env', 'resources', 'limits', 'replay', 'inputs', 'outputs'}
                       if kind == 'execution.command/0.1' else
                       {'schema_version', 'worker', 'payload_schema', 'payload', 'resources', 'limits', 'inputs', 'artifacts'})
            require(set(job) <= allowed, 'invalid_campaign', 'unknown job fields; use the existing runtime envelope')
            slots = job.get('resources', {}).get('cpu_slots')
            require(type(slots) is int and 1 <= slots <= 1024, 'invalid_campaign', 'cpu_slots must be an integer 1..1024')
            limit = 'wall_seconds' if kind == 'execution.command/0.1' else 'wall_time_seconds'
            wall, grace = job.get('limits', {}).get(limit), job.get('limits', {}).get('grace_seconds')
            require(type(wall) in (int, float) and 0.001 <= wall <= 604800 and
                    type(grace) in (int, float) and 0 <= grace <= 3600,
                    'invalid_campaign', 'every job needs finite wall and grace limits')
            if kind == 'execution.command/0.1':
                require(not template.get('accept'), 'invalid_campaign', 'commands use exit/output success; optimization acceptance rules do not apply')
                require(raw.get('allow_commands', False), 'commands_disabled', 'campaign must opt in with allow_commands=true')
                require(job.get('replay') == 'never', 'invalid_campaign', 'command replay must be never')
                require(isinstance(job.get('argv'), list) and 1 <= len(job['argv']) <= 256
                        and all(isinstance(v, str) and '\x00' not in v for v in job['argv']),
                        'invalid_campaign', 'command argv must be a bounded nonempty string array')
                exe = job['argv'][0]
                if Path(exe).is_absolute():
                    meta = fingerprint(exe, 1024 ** 3)
                    job_exe = {'argv0': exe, 'resolved': str(Path(exe).resolve()), **meta}
                else:
                    require(exe.startswith('./'), 'invalid_campaign', 'command executable must be absolute or a declared ./ input')
                    job_exe = None
            else:
                require(all(type(job['resources'].get(k)) is int and job['resources'][k] >= 1 for k in ['outer_workers', 'inner_threads']),
                        'invalid_campaign', 'optimization jobs need integer thread resources')
                require(job['resources']['outer_workers'] * job['resources']['inner_threads'] <= slots,
                        'invalid_campaign', 'outer_workers * inner_threads exceeds cpu_slots')
                require(isinstance(job.get('payload'), dict) and isinstance(job.get('worker'), str)
                        and isinstance(job.get('payload_schema'), str), 'invalid_campaign', 'missing native worker/payload')
                job_exe = None
            require(isinstance(job.get('inputs', []), list) and len(job.get('inputs', [])) <= (128 if kind == 'execution.command/0.1' else 16),
                    'invalid_input', 'too many inputs')
            total = 0
            for index, item in enumerate(job.setdefault('inputs', [])):
                require(isinstance(item, dict), 'invalid_input', 'input must be an object')
                if 'from' in item:
                    require('file' not in item and 'sha256' not in item and 'bytes' not in item,
                            'invalid_input', 'derived inputs cannot also bind a file/hash/size')
                    ref = item['from']
                    require(isinstance(ref, dict) and set(ref) <= {'step', 'kind', 'output'}
                            and ref.get('kind') in ['native', 'output'] and ref.get('step') in templates,
                            'invalid_input', 'invalid predecessor reference')
                    require(ref['kind'] != 'output' or isinstance(ref.get('output'), str), 'invalid_input', 'output name is required')
                    continue
                require(isinstance(item.get('file'), str), 'invalid_input', 'campaign inputs need a file or predecessor reference')
                source = local_file(path.parent, item['file'])
                meta = fingerprint(source)
                require(item.get('sha256', meta['sha256']) == meta['sha256'] and item.get('bytes', meta['bytes']) == meta['bytes'],
                        'input_changed', f'input digest/size mismatch: {item["file"]}')
                total += meta['bytes']
                require(total <= 256 * 1024 ** 2, 'size_limit', 'combined static inputs exceed 256 MiB')
                sources[meta['sha256']] = {'source': str(source), **meta}
                require(sum(v['bytes'] for v in sources.values()) <= 256 * 1024 ** 2, 'size_limit', 'campaign static snapshots exceed 256 MiB')
                item['file'], item['sha256'] = f'inputs/{index}', meta['sha256']
                if kind == 'execution.command/0.1':
                    item['bytes'] = meta['bytes']
                else:
                    item.pop('bytes', None)
            variant = name + ('-' + identity(axes)[:16] if pointers else '')
            require(variant not in {s['id'] for s in expanded}, 'invalid_campaign', 'expanded step id collision')
            family[name].append(variant)
            expanded.append({'id': variant, 'template': name, 'axes': axes, 'job': job,
                             'needs_templates': template.get('needs', []), 'accept': template.get('accept', {}),
                             'executable': job_exe,
                             'reserved_slot_seconds': number(exact(slots) * (exact(wall) + exact(grace)),
                                                             isinstance(wall, float) or isinstance(grace, float))})
    lookup = {s['id']: s for s in expanded}
    for step in expanded:
        needs = set(step.pop('needs_templates'))
        for item in step['job']['inputs']:
            if 'from' in item:
                ref = item['from']
                require(len(family[ref['step']]) == 1, 'ambiguous_input', 'input producer must have exactly one variant')
                producer = lookup[family[ref['step']][0]]
                require(ref['kind'] != 'output' or producer['job']['schema_version'] == 'execution.command/0.1',
                        'invalid_input', 'binary output binding requires a command producer')
                if ref['kind'] == 'output':
                    # Only a required output is sure to exist once the producer succeeded.
                    require(any(isinstance(o, dict) and o.get('name') == ref['output'] and o.get('required') is True
                                for o in producer['job'].get('outputs', [])),
                            'invalid_input', 'producer does not declare that output as required')
                needs.add(ref['step'])
                ref['step'] = producer['id']
        require(needs <= templates.keys() and step['template'] not in needs, 'invalid_dependency', 'unknown/self dependency')
        step['needs'] = sorted(v for name in needs for v in family[name])
    ordered, waiting = [], set(lookup)
    while waiting:
        ready = sorted(key for key in waiting if all(n not in waiting for n in lookup[key]['needs']))
        require(ready, 'dependency_cycle', 'campaign dependencies contain a cycle')
        for key in ready:
            waiting.remove(key)
            ordered.append(lookup[key])
    budget = raw['budget']
    require(type(budget['max_jobs']) is int, 'invalid_campaign', 'max_jobs must be an integer')
    science = {'schema_version': 'experiment.campaign.plan/0.1', 'name': raw['name'],
               'allow_commands': raw.get('allow_commands', False), 'budget': budget, 'steps': ordered}
    require(len(canonical(science)) <= MAX_JSON, 'size_limit', 'expanded campaign exceeds 4 MiB')
    return {**science, 'plan_id': identity(science), 'sources': sources}


def scientific(plan):
    return {k: v for k, v in plan.items() if k != 'sources'}
