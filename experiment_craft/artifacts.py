"""Named command artifacts. Transfer remains owned by optimization-jobs."""
import hashlib
from pathlib import Path
import re
import tempfile

from .campaign import DONE, cached_native, checked_native, runtime_for, verified_job
from .runtime import TERMINAL
from .storage import (Error, MAX_FILE, fingerprint, publish_directory, regular_bytes, require)

STEP = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,127}\Z')
OUTPUT = re.compile(r'[A-Za-z0-9_-]{1,100}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')


def contained(store, *parts):
    """Known relative cache paths only, refusing symlinks at every component."""
    path = store.root
    for part in parts:
        require(isinstance(part, str) and part not in ('', '.', '..') and '/' not in part,
                'artifact_changed', 'invalid retained artifact path')
        path = path / part
        require(not path.is_symlink(), 'artifact_changed', 'retained artifact path is a symlink')
    return path


def step_state(store, state, name):
    require(isinstance(name, str) and STEP.fullmatch(name), 'unknown_step', 'use an expanded campaign step ID')
    step = next((item for item in state['plan']['steps'] if item['id'] == name), None)
    require(step is not None, 'unknown_step', f'unknown campaign step: {name}')
    require(step['job']['schema_version'] == 'execution.command/0.1', 'unsupported_artifact',
            'named output collection supports command steps')
    return step, state['steps'][name]


def native_result(store, entry, name):
    if not entry.get('native'):
        return None
    require(entry['native']['path'] == f'results/{name}/native.json', 'artifact_changed', 'native cache path changed')
    contained(store, 'results', name, 'native.json')
    value = cached_native(store, entry)
    require(value.get('schema_version') == 'execution.command.result/0.1'
            and value.get('state') in TERMINAL
            and value['state'] == entry.get('observation', {}).get('state'),
            'artifact_changed', 'cached command result does not match the terminal observation')
    return value


def output_info(store, state, step_id, name):
    step, entry = step_state(store, state, step_id)
    require(isinstance(name, str) and OUTPUT.fullmatch(name), 'unknown_artifact', 'invalid output name')
    declared = next((item for item in step['job'].get('outputs', []) if item['name'] == name), None)
    require(declared is not None, 'unknown_artifact', f'step {step_id} does not declare output {name}')
    native = native_result(store, entry, step_id)
    meta = (native or {}).get('outputs', {}).get(name)
    info = {'step': step_id, 'job_id': entry['job_id'], 'step_status': entry['status'],
            'native_state': native.get('state') if native else None, 'output': name,
            'required': declared['required'], 'max_bytes': declared['max_bytes'],
            'bytes': None, 'sha256': None, 'path': None,
            'availability': 'unavailable' if native or entry['status'] in DONE else 'pending'}
    if meta is None:
        return info
    require(isinstance(meta, dict) and type(meta.get('bytes')) is int
            and 0 <= meta['bytes'] <= min(MAX_FILE, declared['max_bytes'])
            and isinstance(meta.get('sha256'), str) and SHA.fullmatch(meta['sha256']),
            'artifact_changed', 'invalid native output metadata')
    info.update(bytes=meta['bytes'], sha256=meta['sha256'], availability='sealed')
    path = contained(store, 'results', step_id, 'outputs', name)
    if path.exists():
        require(fingerprint(path) == {key: meta[key] for key in ('bytes', 'sha256')},
                'artifact_changed', 'retained output differs from its native digest')
        info.update(availability='retained', path=str(path.relative_to(store.root)))
    return info


def catalog(store, step_id=None, after=0, limit=1000):
    """Offline: list declarations, sealed metadata and checked retained copies."""
    state = store.read()
    require(type(after) is int and after >= 0 and type(limit) is int and 1 <= limit <= 1000,
            'invalid_command', 'artifact pages require after>=0 and limit 1..1000')
    steps = state['plan']['steps']
    if step_id is not None:
        step_state(store, state, step_id)
        steps = [item for item in steps if item['id'] == step_id]
    references = [(step['id'], output['name']) for step in steps
                  if step['job']['schema_version'] == 'execution.command/0.1'
                  for output in step['job'].get('outputs', [])]
    rows = [output_info(store, state, step, name) for step, name in references[after:after + limit]]
    return {'schema_version': 'experiment.artifacts/0.1', 'campaign_id': state['campaign_id'],
            'plan_id': state['plan']['plan_id'], 'artifacts': rows, 'total_outputs': len(references),
            'offset': after, 'next_offset': after + len(rows) if after + len(rows) < len(references) else None}


def collect(store, step_id, name):
    """Collect one existing sealed output; never observe, dispatch, retry or repair a job."""
    with store.advance_lock():
        state = store.read()
        info = output_info(store, state, step_id, name)
        require(info['availability'] not in ('pending', 'unavailable'), 'output_unavailable',
                'no collected native output; observe the existing attempt with collect first')
        contacted = info['availability'] != 'retained'
        if contacted:
            step, entry = step_state(store, state, step_id)
            binding = state['runtime']
            require(fingerprint(binding['runner'], 1024 ** 3) == binding['runner_file'],
                    'runtime_changed', 'bound runner executable changed')
            runtime = runtime_for(state)
            job = verified_job(runtime, entry)
            require(job['state'] in TERMINAL, 'artifact_changed', 'retained terminal job is no longer terminal')
            record, _, data = checked_native(runtime, job)
            require(record.get('identity') == entry.get('execution_identity') and
                    len(data) == entry['native']['bytes'] and hashlib.sha256(data).hexdigest() == entry['native']['sha256'],
                    'artifact_changed', 'native result changed since campaign observation')
            path = contained(store, 'results', step_id, 'outputs', name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.collect-', dir=path.parent) as directory:
                source = Path(directory) / 'data'
                runtime.call('jobs', 'collect', '--destination', source, '--', entry['job_id'], name)
                require(fingerprint(source) == {key: info[key] for key in ('bytes', 'sha256')},
                        'artifact_changed', 'runtime collected different output bytes')
                # renameat2 with NOREPLACE also applies to regular files.
                publish_directory(source, path)
            info = output_info(store, state, step_id, name)
        return {'schema_version': 'experiment.artifact.collection/0.1', 'campaign_id': state['campaign_id'],
                'plan_id': state['plan']['plan_id'], 'runtime_contacted': contacted, 'artifact': info}


def output_bytes(store, state, step_id, name, limit=MAX_FILE):
    info = output_info(store, state, step_id, name)
    require(info['availability'] == 'retained', 'artifact_not_collected',
            f'collect-artifact --step {step_id} --output {name} before offline reporting')
    data = regular_bytes(store.root / info['path'], limit)
    require(len(data) == info['bytes'] and hashlib.sha256(data).hexdigest() == info['sha256'],
            'artifact_changed', 'retained output changed while reading')
    return data, info


def input_bytes(store, state, step_id, staged_path, limit=MAX_FILE):
    """Read an admitted input snapshot, anchored to the saved runtime resolution."""
    step, entry = step_state(store, state, step_id)
    require(entry.get('issued') and isinstance(entry.get('submitted_job'), dict)
            and isinstance(entry.get('expected_resolved'), dict), 'verification_unavailable',
            'step has no admitted input identity')
    source = entry['submitted_job'].get('inputs', [])
    matches = [(index, item) for index, item in enumerate(source) if item.get('path') == staged_path]
    require(len(matches) == 1, 'unsupported_verification', f'expected one admitted input at {staged_path}')
    index, item = matches[0]
    original = [value for value in step['job'].get('inputs', []) if value.get('path') == staged_path]
    require(len(original) == 1, 'artifact_changed', 'admitted input is absent from the scientific plan')
    original = original[0]
    if 'from' in original:
        reference = original['from']
        producer = state['steps'][reference['step']]
        if reference['kind'] == 'native':
            expected_source = producer.get('native') or {}
        else:
            result = native_result(store, producer, reference['step'])
            expected_source = (result or {}).get('outputs', {}).get(reference['output'], {})
    else:
        expected_source = original
    require(all(item.get(key) == expected_source.get(key) for key in ('bytes', 'sha256')),
            'artifact_changed', 'admitted input differs from its planned source')
    expected = [value for value in entry['expected_resolved'].get('inputs', []) if value.get('path') == staged_path]
    require(len(expected) == 1 and all(item.get(key) == expected[0].get(key) for key in ('bytes', 'sha256'))
            and item.get('file') == f'inputs/{index}', 'artifact_changed', 'admitted input identity changed')
    require(type(item.get('bytes')) is int and 0 <= item['bytes'] <= MAX_FILE
            and isinstance(item.get('sha256'), str) and SHA.fullmatch(item['sha256']),
            'artifact_changed', 'invalid admitted input metadata')
    path = contained(store, 'requests', step_id, 'inputs', str(index))
    try:
        data = regular_bytes(path, limit)
    except OSError as exc:
        raise Error('input_changed', f'admitted input is unavailable: {staged_path}') from exc
    require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'],
            'input_changed', f'admitted input changed: {staged_path}')
    return data, {key: item[key] for key in ('bytes', 'sha256')}


def audit_cache(store, state):
    """Backup/restore validates every retained named output against the native manifest."""
    for step in state['plan']['steps']:
        directory = contained(store, 'results', step['id'], 'outputs')
        if not directory.exists():
            continue
        require(directory.is_dir(), 'artifact_changed', 'output cache is not a directory')
        for path in directory.iterdir():
            info = output_info(store, state, step['id'], path.name)
            require(info['availability'] == 'retained', 'artifact_changed', 'unbound cached output')
