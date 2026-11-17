"""Adaptive BO decisions over the existing admitted runtime; one authoritative ledger.

The numerical dependency is optional. No evaluator or Torch work runs in this client.
"""
import copy
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import time

from .campaign import checked_native
from .runtime import Runtime, TERMINAL
from .storage import (Error, Store, canonical, fingerprint, identity, read_json, require,
                      snapshot, write_json, publish_directory)


ACTIVE_JOB = ('intent', 'running', 'unknown')


def bo_craft_specs():
    """BO-craft's contracts; the optional dependency of adaptive campaigns."""
    try:
        from bo_craft import specs
    except ImportError as exc:
        raise Error('missing_dependency', 'adaptive campaigns need BO-craft (docs/adaptive-bo.md)') from exc
    return specs


def validate_manifest(value):
    import jsonschema
    schema = read_json(Path(__file__).parent / 'schemas/adaptive-0.1.schema.json')
    try:
        jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        raise Error('invalid_manifest', exc.message) from exc
    specs = bo_craft_specs()
    try:
        # BO-craft's own request schema checks the problem and the configuration.
        specs.validate_request({'schema_version': 'bo.request/0.1', 'problem': value['problem'],
                                'config': value['config'], 'seed': 0, 'q': 1})
    except specs.Error as exc:
        raise Error(exc.code, str(exc)) from exc
    require(value['concurrent'] <= 32, 'invalid_manifest', 'concurrency cap 32')
    replicates = validation_count(value)
    require(replicates < value['budget']['evaluations'], 'invalid_manifest',
            'validation replicates must leave evaluations for the optimization')
    require(not replicates or len(value['problem']['objectives']) == 1, 'invalid_manifest',
            'validation replicates need one objective')
    require(not wants_model(value) or not any(p.get('active_if') for p in value['problem']['parameters']),
            'invalid_manifest', 'model recommendations need an unconditional space')
    require(not value.get('pruning') or (len(value['problem']['objectives']) == 1
                                         and not value['problem'].get('constraints')),
            'invalid_manifest', 'pruning compares one unconstrained objective')
    require(value['config'].get('threads', 1) <= value['proposal_slots'],
            'invalid_manifest', 'proposal threads exceed admitted slots')
    if value['evaluator']['kind'] == 'native':
        # Rejected here, before any job, rather than at the first dispatch.
        problem = value['problem']
        require(value['evaluator']['job'].get('payload_schema') == 'fcmaes.evaluate/1',
                'unsupported_profile', 'native bridge requires fcmaes.evaluate/1')
        require(len(problem['objectives']) == 1 and not problem.get('constraints'),
                'unsupported_profile', 'native scalar bridge requires one unconstrained metric')
        require(value['config'].get('noise') != 'known', 'unsupported_profile',
                'native evaluations carry no observation variances; use inferred or deterministic noise')
        require(not value.get('pruning'), 'unsupported_profile',
                'pruning needs progress files: use a command evaluator')
        require(value['evaluator'].get('seeded', True) or (
                    value['config'].get('replication', 'none') == 'none' and not replicates),
                'unsupported_profile', 'replicates of an unseeded native evaluation would repeat it')
    return value


def wants_model(plan):
    """Whether the campaign answer includes a model recommendation (a BoTorch job)."""
    return plan.get('answer', {}).get('model', plan['config']['backend'] == 'botorch')


def validation_count(plan):
    return plan.get('answer', {}).get('validation_replicates', 0)


def optimization_budget(plan):
    return plan['budget']['evaluations'] - validation_count(plan)


def optimization_trials(state):
    return {k: t for k, t in state['trials'].items() if t.get('kind', 'optimization') == 'optimization'}


def check_candidates(request, proposal, config):
    """A proposal's (candidate, replicate_of) pairs.

    Only a declared replicate of a completed observation, with replication
    enabled, may repeat an observed point; nothing may repeat a pending one.
    """
    from bo_craft.specs import validate_point
    candidates = proposal['candidates']
    sources = proposal.get('replicate_of') or [None] * len(candidates)
    require(len(sources) == len(candidates), 'invalid_proposal', 'replicate list cardinality')
    completed = {o['id']: o for o in request.get('observations', []) if o['status'] == 'completed'}
    observed = {canonical(o['x']) for o in request.get('observations', [])}
    occupied = {canonical(o['x']) for o in request.get('pending', [])}
    for x, source in zip(candidates, sources):
        validate_point(request['problem'], x)
        key = canonical(x)
        if source is None:
            require(key not in observed, 'duplicate_candidate', 'proposal duplicate')
        else:
            require(config.get('replication', 'none') != 'none' and source in completed
                    and canonical(completed[source]['x']) == key,
                    'invalid_proposal', 'undeclared or mismatched replicate')
        require(key not in occupied, 'duplicate_candidate', 'proposal duplicate')
        occupied.add(key)
    return list(zip(candidates, sources))


PROGRESS_FILE = 'progress.jsonl'


def read_curve(runtime, job_id):
    """A running or finished evaluation's learning curve: {step: value}.

    The evaluator appends `{"step": N, "value": V}` lines to progress.jsonl;
    lines of another shape are ignored, and a later line for a step wins.
    The runner pages complete lines; the file itself is bounded by its
    declared size.
    """
    import math
    curve = {}
    offset = 0
    while True:
        value = runtime.call('jobs', 'progress', job_id, '--offset', str(offset), '--limit', '10000')
        for line in value.get('lines', []):
            step, number = line.get('step'), line.get('value')
            if (type(step) is int and step >= 0 and isinstance(number, (int, float))
                    and not isinstance(number, bool) and math.isfinite(number)):
                curve[step] = float(number)
        following = value.get('next_offset', offset)
        if not value.get('lines') or type(following) is not int or following <= offset:
            return curve
        offset = following


def check_progress_support(runtime, directory):
    """Pruning needs a runner whose command jobs accept a progress file."""
    spec = {'schema_version': 'execution.command/0.1', 'request_key': 'progress-probe', 'argv': ['/bin/true'],
            'env': {}, 'resources': {'cpu_slots': 1}, 'limits': {'wall_seconds': 1, 'grace_seconds': 0},
            'replay': 'never', 'inputs': [], 'outputs': [],
            'progress': {'path': PROGRESS_FILE, 'max_bytes': 64}}
    path = Path(directory) / 'progress-probe.json'
    write_json(path, spec)
    try:
        runtime.call('validate', '--spec', path)
    except Error as exc:
        # Only a refused spec means an older runner; disabled commands and
        # other node errors keep their own code.
        if exc.code != 'invalid_command_spec':
            raise
        raise Error('unsupported_runtime', 'pruning needs a runner with command progress files '
                    '(optimization-jobs after 0.4.1): ' + str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)


def _prune(store, runtime, clock):
    """Cancel running evaluations whose curve the median rule prunes; record first, then cancel."""
    from bo_craft.pruning import median_decision
    state = store.read()
    plan = state['plan']
    spec = plan.get('pruning')
    now = time.monotonic()
    if not spec or state['stop_requested'] or now - clock.get('last', 0.0) < spec.get('check_seconds', 1.0):
        return
    clock['last'] = now
    completed = [{int(k): v for k, v in t['curve'].items()} for t in state['trials'].values()
                 if t['state'] == 'completed' and t.get('curve')]
    direction = plan['problem']['objectives'][0]['direction']
    for name, job in state['jobs'].items():
        trial = state['trials'].get(job.get('payload')) if job['kind'] == 'evaluation' else None
        if trial is None or trial.get('kind') == 'validation' or job['state'] != 'running':
            continue
        if job.get('prune_requested'):
            if not job.get('cancel_requested'):
                _cancel_pruned(store, runtime, name, job)
            continue
        try:
            curve = read_curve(runtime, job['job_id'])
        except Error as exc:
            if exc.code in ('unknown_job',):
                continue
            raise
        if not curve:
            continue
        decision = median_decision(completed, curve, direction=direction,
                                   startup_trials=spec.get('startup_trials', 5),
                                   warmup_steps=spec.get('warmup_steps', 1))
        if decision['should_prune']:
            with store.edit({'event': 'adaptive_prune', 'job': name, 'step': decision['step']}) as target:
                target['jobs'][name]['prune_requested'] = {'step': decision['step'], 'median': decision['median']}
            _cancel_pruned(store, runtime, name, job)


def _cancel_pruned(store, runtime, name, job):
    try:
        runtime.cancel(job['job_id'])
    except Error as exc:
        if exc.code not in ('already_terminal', 'unknown_job'):
            raise
        if exc.code == 'unknown_job':
            return
    with store.edit({'event': 'adaptive_prune_cancel_requested', 'job': name}) as target:
        target['jobs'][name]['cancel_requested'] = True


def validation_summary(answer, trials, observations, metric):
    """Fresh replicates at the answer's point: mean and standard error of the metric."""
    import math
    values = [o['values'][metric] for o in observations if o['status'] == 'completed']
    n = len(values)
    mean = sum(values) / n if n else None
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else None
    return {'x': answer['validation_x'], 'source': answer['validation_source'], 'metric': metric,
            'trial_ids': sorted(trials), 'completed': n, 'not_completed': len(trials) - n,
            'values': values, 'mean': mean, 'standard_deviation': sd,
            'standard_error': sd / math.sqrt(n) if sd is not None else None,
            'evidence': 'fresh independent evaluations at the recommended point'}


def initialize(manifest, workspace, runner, root, mode='foreground'):
    plan = validate_manifest(read_json(manifest))
    plan['plan_id'] = identity(plan)
    require(mode in ('foreground', 'systemd'), 'invalid_manifest', 'local execution mode required')
    workspace = Path(workspace).absolute()
    runtime = Runtime(runner, root)
    dummy = {'steps': [{'job': {'schema_version': 'execution.command/0.1',
                              'resources': {'cpu_slots': plan['proposal_slots']}}}]}
    if plan['evaluator']['kind'] == 'native':
        dummy['steps'].append({'job': plan['evaluator']['job']})
    binding = runtime.binding(dummy, mode)
    if plan.get('pruning'):
        workspace_parent = Path(workspace).absolute().parent
        workspace_parent.mkdir(parents=True, exist_ok=True)
        check_progress_support(runtime, workspace_parent)
    import importlib.metadata
    package_root = Path(bo_craft_specs().__file__).parent
    package_files={str(p.resolve()):fingerprint(p) for p in sorted(package_root.rglob('*'))
                   if p.is_file() and p.suffix in ('.py','.json')}
    versions={}
    for package in ['bo-craft','torch','botorch','gpytorch','optuna']:
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    executables = {str(Path(plan['python']).absolute()): fingerprint(plan['python'], 1024**3)}
    if plan['evaluator']['kind'] == 'command':
        path = plan['evaluator']['argv'][0]
        executables[str(Path(path).absolute())] = fingerprint(path, 1024**3)
    if workspace.exists():
        store = Store(workspace)
        try:
            state = store.read()
            require(state['plan'] == plan and state['runtime'] == binding and state['executables'] == executables and state['package_files']==package_files and state['versions']==versions,
                    'campaign_conflict', 'continue the existing binding or use a new workspace')
            return status(state)
        finally:
            store.close()
    workspace.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.adaptive-', dir=workspace.parent))
    try:
        files = []
        for item in plan['evaluator'].get('inputs', []):
            source = Path(item['file'])
            if not source.is_absolute():
                source = Path(manifest).resolve().parent / source
            meta = fingerprint(source)
            snapshot(source, temp / 'files' / meta['sha256'], meta)
            files.append({**item, **meta})
        now = time.time()
        state = {'schema_version': 'experiment.adaptive.state/0.1', 'campaign_id': secrets.token_hex(32),
                 'plan': plan, 'runtime': binding, 'executables': executables, 'package_files':package_files,'versions':versions,'files': files,
                 'stop_requested': False, 'stop_reason': None, 'created_at': now, 'last_clock': now,
                 'deadline_at': now + plan['budget']['wall_seconds'], 'jobs_reserved': 0,
                 'slot_seconds_reserved': 0, 'trials': {}, 'jobs': {}, 'observations': [], 'proposal_seq': 0}
        store = Store(temp, create=True)
        with store.edit({'event': 'adaptive_initialized'}) as target:
            target.update(state)
        store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        store.close()
        write_json(temp / 'plan.json', plan)
        publish_directory(temp, workspace)
        return status(state)
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def status(state):
    require(state['schema_version'] == 'experiment.adaptive.state/0.1', 'unsupported_state', 'adaptive state required')
    active = [j for j in state['jobs'].values() if j['state'] in ACTIVE_JOB]
    unknown = any(j['state'] == 'unknown' for j in active)
    answer = state.get('answer')
    done = (len(optimization_trials(state)) >= optimization_budget(state['plan']) and not active
            and answer is not None and answer['state'] == 'done')
    return {'schema_version': 'experiment.adaptive.status/0.1', 'campaign_id': state['campaign_id'],
            'status': 'unknown' if unknown else ('stopping' if state['stop_requested'] and active else (
                'stopped' if state['stop_requested'] else ('completed' if done else 'running'))),
            'accepted_trials': len(state['trials']), 'observations': len(state['observations']),
            'pending': len(active), 'jobs_reserved': state['jobs_reserved'],
            'declared_slot_seconds_reserved': state['slot_seconds_reserved'],
            'stop_reason': state['stop_reason'], 'deadline_at': state['deadline_at'],
            'answer': answer['state'] if answer else None}


def audit(store):
    state=store.read()
    plan=read_json(store.root/'plan.json')
    require(plan==state['plan'] and plan['plan_id']==identity({k:v for k,v in plan.items() if k!='plan_id'}),
            'backup_integrity','adaptive plan identity changed')
    for item in state['files']:
        path=store.root/'files'/item['sha256']
        require(not path.is_symlink() and fingerprint(path)=={k:item[k] for k in ['bytes','sha256']},
                'input_changed','adaptive retained input changed')
    for name,entry in state['jobs'].items():
        require(entry['spec']==f'requests/{name}/job.json','backup_integrity','unexpected job spec path')
        for output,meta in entry.get('output_meta',{}).items():
            path=store.root/'results'/name/(output+'.json')
            require(not path.is_symlink() and fingerprint(path)=={k:meta[k] for k in ['bytes','sha256']},
                    'result_changed','adaptive retained output changed')
    require(store.db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'backup_integrity','SQLite integrity')
    return state


def reconcile_unpause(store,before):
    state=audit(store)
    runtime=Runtime(state['runtime']['runner'],state['runtime']['root'],state['runtime'])
    runtime.assert_node()
    for entry in state['jobs'].values():
        job=runtime.get(entry['job_id'])
        require(read_json(Path(job['directory'])/'resolved.json')==entry['resolved'],
                'recovery_unverified','adaptive native request differs')
        if entry.get('ingested'):
            record,_,_=checked_native(runtime,job)
            require(record==entry['native_record'],'recovery_unverified','adaptive terminal evidence differs')
    with store.edit({'event':'adaptive_unpaused'}):
        value=store.maintenance()
        require(value['generation']==before['generation'],'maintenance_changed','pause changed during reconciliation')
        value.update(paused=False,generation=value['generation']+1,reason=None)
        store.set_maintenance(value)
    return value


def stop(store, reason='user_stop'):
    """Record the stop once and ask the runtime to cancel each active job once.

    A cancel that finds no native job is retried by a later call, since a lost
    launch answer can still produce the job; nothing else is repeated.
    """
    state = store.read()
    if not state['stop_requested']:
        with store.edit({'event': 'adaptive_stop', 'reason': reason}) as target:
            target['stop_requested'] = True
            target['stop_reason'] = target['stop_reason'] or reason
        state = store.read()
    runtime = Runtime(state['runtime']['runner'], state['runtime']['root'], state['runtime'])
    cancelled = []
    for key, job in state['jobs'].items():
        if job['state'] in ACTIVE_JOB and not job.get('cancel_requested'):
            try:
                runtime.cancel(job['job_id'])
            except Error as exc:
                if exc.code == 'unknown_job':
                    continue
                if exc.code != 'already_terminal':
                    raise
            cancelled.append(key)
    if cancelled:
        with store.edit({'event': 'adaptive_cancel_requested', 'jobs': cancelled}) as target:
            for key in cancelled:
                target['jobs'][key]['cancel_requested'] = True
    return status(store.read())


def _command(argv, inputs, output, slots, wall):
    return {'schema_version': 'execution.command/0.1', 'argv': argv,
            'env': {'OMP_NUM_THREADS': str(slots), 'MKL_NUM_THREADS': str(slots),
                    'OPENBLAS_NUM_THREADS': str(slots)}, 'resources': {'cpu_slots': slots},
            'limits': {'wall_seconds': wall, 'grace_seconds': 1}, 'replay': 'never', 'inputs': inputs,
            'outputs': [{'name': output, 'path': output + '.json', 'required': True, 'max_bytes': 4*1024**2}]}


def _input(path, local, relative):
    return {'path': path, 'file': relative, **fingerprint(local)}


def _intend(store, runtime, name, kind, payload, request):
    state = store.read()
    path = store.root / 'requests' / name
    path.mkdir(parents=True, exist_ok=True)
    write_json(path / 'input.json', request)
    plan = state['plan']
    remaining = max(0.001, state['deadline_at']-time.time())
    if kind == 'proposal':
        job = _command([plan['python'], '-m', 'bo_craft.cli', 'propose', 'input.json', '--output', 'proposal.json'],
                       [_input('input.json', path/'input.json', 'input.json')], 'proposal',
                       plan['proposal_slots'], min(remaining, plan['proposal_wall_seconds']))
    elif kind == 'recommendation':
        job = _command([plan['python'], '-m', 'bo_craft.cli', 'recommend', 'input.json', '--kind', 'model',
                        '--output', 'recommendation.json'],
                       [_input('input.json', path/'input.json', 'input.json')], 'recommendation',
                       plan['proposal_slots'], min(remaining, plan['proposal_wall_seconds']))
    elif plan['evaluator']['kind'] == 'command':
        ev = plan['evaluator']
        inputs = [_input('trial.json', path/'input.json', 'input.json')]
        for i, item in enumerate(state['files']):
            source = store.root / 'files' / item['sha256']
            require(fingerprint(source) == {k: item[k] for k in ['bytes','sha256']}, 'input_changed', 'evaluator source changed')
            local = path / f'source-{i}'
            if not local.exists():
                shutil.copyfile(source, local)
            inputs.append(_input(item['path'], local, local.name))
        job = _command(ev['argv'], inputs, 'observation', ev['slots'], min(remaining, ev['wall_seconds']))
        if plan.get('pruning'):
            job['progress'] = {'path': PROGRESS_FILE,
                               'max_bytes': plan['pruning'].get('progress_max_bytes', 65536)}
    else:
        job = copy.deepcopy(plan['evaluator']['job'])
        require(job['payload_schema'] == 'fcmaes.evaluate/1', 'unsupported_profile', 'native bridge requires fcmaes.evaluate/1')
        require(len(plan['problem']['objectives']) == 1 and not plan['problem'].get('constraints'),
                'unsupported_profile', 'native scalar bridge requires one unconstrained metric')
        job['payload']['points'] = [[request['x'][p['name']] for p in plan['problem']['parameters']]]
        if plan['evaluator'].get('seeded',True):
            job['payload']['run_seed'] = request['seed']
        else:
            job['payload'].pop('run_seed',None)
        job['limits']['wall_time_seconds'] = min(remaining, job['limits']['wall_time_seconds'])
    key = 'bo:' + state['campaign_id'] + ':' + name
    job['request_key'] = key
    write_json(path/'job.json', job)
    validation = runtime.call('validate', '--spec', path/'job.json')
    require(validation.get('valid') is True, 'invalid_job', 'runtime refused adaptive request')
    job_id = hashlib.sha256(key.encode()).hexdigest()[:32]
    try:
        runtime.get(job_id)
    except Error as exc:
        require(exc.code == 'unknown_job', exc.code, str(exc))
    else:
        raise Error('recovery_diverged', 'another workspace copy already issued this decision')
    cost = job['resources']['cpu_slots'] * (job['limits'].get('wall_seconds',job['limits'].get('wall_time_seconds'))+job['limits']['grace_seconds'])
    with store.edit({'event': 'adaptive_dispatch_intent', 'job': name}) as target:
        store.require_dispatch()
        require(not target['stop_requested'] and time.time() < target['deadline_at'], 'stopped', 'dispatch stopped')
        require(target['jobs_reserved'] < plan['budget']['jobs'] and
                target['slot_seconds_reserved']+cost <= plan['budget']['slot_seconds'],
                'budget_exhausted', 'declared adaptive work budget exhausted')
        target['jobs_reserved'] += 1
        target['slot_seconds_reserved'] += cost
        target['jobs'][name] = {'state': 'intent', 'job_id': job_id, 'kind': kind,
                                'payload': payload, 'request': request, 'resolved': validation['resolved'],
                                'spec': str((path/'job.json').relative_to(store.root))}
    return name


def _launch(store, runtime, name, live):
    entry = store.read()['jobs'][name]
    try:
        if store.read()['runtime']['mode'] == 'systemd':
            runtime.call('submit', '--spec', store.root/entry['spec'])
        else:
            base = (store.root/entry['spec']).parent
            with (base/'runner.stdout').open('wb') as out, (base/'runner.stderr').open('wb') as err:
                live[name] = runtime.foreground(store.root/entry['spec'], out, err)
    except (Error, KeyboardInterrupt) as exc:
        with store.edit({'event': 'adaptive_launch_unknown', 'job': name}) as state:
            state['jobs'][name]['state'] = 'unknown'
        raise Error('submission_unknown', 'observe the existing native handle; do not resubmit') from exc


def _collect(store, runtime, name, job):
    from bo_craft.specs import digest, schema_check, validate_request
    entry = store.read()['jobs'][name]
    resolved = read_json(Path(job['directory'])/'resolved.json')
    require(resolved == entry['resolved'], 'request_key_conflict', 'native resolved request differs from intent')
    record, native, _ = checked_native(runtime, job)
    observation = None
    proposal = None
    recommendation = None
    if job['state'] == 'completed' and record['kind'] == 'command' and not native.get('output_errors'):
        output = entry['kind'] if entry['kind'] in ('proposal', 'recommendation') else 'observation'
        destination = store.root/'results'/name/(output+'.json')
        destination.parent.mkdir(parents=True, exist_ok=True)
        meta = native.get('outputs', {}).get(output)
        require(meta is not None, 'output_unavailable', 'required adaptive output missing')
        if not destination.exists():
            runtime.call('jobs', 'collect', '--destination', destination, '--', entry['job_id'], output)
        require(fingerprint(destination) == {k: meta[k] for k in ['bytes', 'sha256']}, 'result_changed', 'adaptive output digest mismatch')
        value = read_json(destination)
        if entry['kind'] == 'proposal':
            schema_check(value, 'proposal')
            require(value['request_sha256'] == digest(entry['request']) and
                    value['problem_sha256'] == digest(entry['request']['problem']), 'result_changed', 'proposal identity mismatch')
            require(len(value['candidates']) == entry['request']['q'], 'invalid_proposal', 'candidate count')
            proposal = check_candidates(entry['request'], value, entry['request']['config'])
        elif entry['kind'] == 'recommendation':
            require(value.get('schema_version') == 'bo.recommendation/0.1' and value.get('kind') == 'model'
                    and value.get('points'), 'invalid_recommendation', 'model recommendation expected')
            recommendation = value
        else:
            observation = value
    elif entry['kind'] != 'proposal' and job['state'] == 'completed' and record['kind'] == 'optimization':
        rows = native.get('results', [])
        require(len(rows) == 1, 'runtime_protocol', 'one-point native evaluation required')
        outcome = rows[0]['outcome']
        if outcome.get('objective') is not None:
            metric = store.read()['plan']['problem']['objectives'][0]['name']
            observation = {**entry['request'], 'status': 'completed', 'values': {metric: outcome['objective']},
                           'provenance': {'native_outcome': outcome}}
    curve = None
    plan = store.read()['plan']
    if entry['kind'] == 'evaluation' and plan.get('pruning') and record['kind'] == 'command':
        curve = read_curve(runtime, entry['job_id'])
    if entry['kind'] not in ('proposal', 'recommendation'):
        pruned = entry.get('prune_requested') and job['state'] == 'cancelled'
        if pruned:
            observation = {**entry['request'], 'status': 'pruned',
                           'provenance': {'pruned_at_step': entry['prune_requested']['step'],
                                          'median_at_step': entry['prune_requested']['median']}}
        observation = observation or {**entry['request'], 'status': 'cancelled' if job['state'] in ('cancelled','timed_out') else 'failed'}
        if curve and observation['status'] in ('completed', 'pruned'):
            observation['intermediate'] = {str(k): v for k, v in sorted(curve.items())}
        for key in ['id', 'trial_id', 'x', 'seed']:
            require(observation.get(key) == entry['request'][key], 'result_changed', 'observation trial identity mismatch')
        check = {'schema_version': 'bo.request/0.1', 'problem': store.read()['plan']['problem'],
                 'config': store.read()['plan']['config'], 'seed': 0, 'q': 1, 'observations': [observation]}
        validate_request(check)
    with store.edit({'event': 'adaptive_ingested', 'job': name}) as state:
        require(not state['jobs'][name].get('ingested'), 'duplicate_ingestion', 'already ingested')
        state['jobs'][name].update(state=job['state'], ingested=True, native_record=record, output_meta=native.get('outputs', {}))
        if observation:
            trial = state['trials'][entry['payload']]
            if curve and observation['status'] == 'completed':
                trial['curve'] = {str(k): v for k, v in sorted(curve.items())}
            if trial.get('kind') == 'validation':
                state.setdefault('validation_observations', []).append(observation)
            else:
                state['observations'].append(observation)
            trial['state'] = observation['status']
        if proposal and not state['stop_requested']:
            for x, source in proposal:
                trial_id = f'trial-{len(state["trials"]):06d}'
                state['trials'][trial_id] = {'x': x, 'state': 'accepted', 'seed': int(identity(
                    {'seed': state['plan']['seed'], 'trial': trial_id})[:15], 16), 'proposal': name}
                if source is not None:
                    state['trials'][trial_id]['replicate_of'] = source
        if entry['kind'] == 'recommendation':
            answer = state['answer']
            answer['model'] = recommendation or {'error': f'recommendation job {job["state"]}'}
            answer['state'] = 'validation' if validation_count(state['plan']) else 'done'
        if entry['kind'] == 'proposal' and proposal is None:
            state['stop_requested'] = True
            state['stop_reason'] = state['stop_reason'] or 'proposal_failed'


def check_environment(state):
    """The bound runner node, package versions, executables and BO-craft files."""
    import importlib.metadata
    for package, version in state['versions'].items():
        try:
            installed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        require(installed == version, 'environment_changed', f'adaptive package {package} changed')
    for path, meta in {**state['executables'], **state['package_files']}.items():
        require(fingerprint(path, 1024**3) == meta, 'executable_changed', 'adaptive executable changed')


def _answer(store, runtime, live):
    """The campaign's answer: empirical choice, model choice (a job), fresh validation replicates."""
    from bo_craft import recommend
    from bo_craft.specs import Error as SpecError
    state = store.read()
    plan = state['plan']
    request = {'schema_version': 'bo.request/0.1', 'problem': plan['problem'], 'config': plan['config'],
               'seed': plan['seed'], 'q': 1, 'observations': state['observations']}
    answer = state.get('answer')
    if answer is None:
        try:
            empirical = recommend(request, kind='empirical')
        except SpecError as exc:
            empirical = {'error': exc.code, 'message': str(exc)}
        with store.edit({'event': 'adaptive_answer_started'}) as target:
            target['answer'] = {'state': 'model' if wants_model(plan) else (
                                    'validation' if validation_count(plan) else 'done'),
                                'empirical': empirical, 'model': None, 'validation': None}
    elif answer['state'] == 'model':
        if 'recommendation' not in state['jobs']:
            check_environment(state)
            _intend(store, runtime, 'recommendation', 'recommendation', None, request)
            _launch(store, runtime, 'recommendation', live)
    elif answer['state'] == 'validation':
        chosen = [k for k, t in state['trials'].items() if t.get('kind') == 'validation']
        if not chosen:
            # The empirical choice by default: BO-craft's gate G1 found the model's
            # choice not reliably better (docs/evidence/plan-2026-11-17 there).
            model, empirical = answer.get('model') or {}, answer['empirical']
            prefer_model = plan.get('answer', {}).get('validate', 'empirical') == 'model'
            if prefer_model and model.get('points'):
                x, source = model['points'][0]['x'], 'model'
            elif empirical.get('observations'):
                x, source = empirical['observations'][0]['x'], 'empirical'
            elif model.get('points'):
                x, source = model['points'][0]['x'], 'model'
            else:
                with store.edit({'event': 'adaptive_answer_unvalidated'}) as target:
                    target['answer'].update(state='done', validation={'error': 'no recommended point'})
                return
            with store.edit({'event': 'adaptive_validation_accepted'}) as target:
                target['answer'].update(validation_x=x, validation_source=source)
                for _ in range(validation_count(plan)):
                    trial_id = f'trial-{len(target["trials"]):06d}'
                    target['trials'][trial_id] = {'x': x, 'state': 'accepted', 'kind': 'validation', 'seed': int(
                        identity({'seed': plan['seed'], 'trial': trial_id})[:15], 16), 'proposal': None}
        elif all(state['trials'][k]['state'] not in ('accepted', 'pending') for k in chosen):
            metric = plan['problem']['objectives'][0]['name']
            summary = validation_summary(answer, chosen, state.get('validation_observations', []), metric)
            with store.edit({'event': 'adaptive_validated'}) as target:
                target['answer'].update(state='done', validation=summary)
    state = store.read()
    if state['answer']['state'] == 'done' and not (store.root / 'answer.json').exists():
        write_json(store.root / 'answer.json', {'schema_version': 'experiment.adaptive.answer/0.1',
                                                'campaign_id': state['campaign_id'], **state['answer']})


def advance(store, once=False, poll_seconds=0.05):
    try:
        return _advance(store,once,poll_seconds)
    except Error as exc:
        if exc.code in ('budget_exhausted','stopped'):
            return stop(store,'budget_exhausted' if exc.code=='budget_exhausted' else 'deadline_exceeded')
        raise


def _advance(store, once=False, poll_seconds=0.05):
    with store.advance_lock():
        live = {}
        prune_clock = {}
        # Hashing the bound files on every poll would cost far more than the
        # poll itself; they are checked once here and before each dispatch.
        check_environment(store.read())
        while True:
            state = store.read()
            runtime = Runtime(state['runtime']['runner'], state['runtime']['root'], state['runtime'])
            runtime.assert_node()
            now=max(time.time(),state['last_clock'])
            if now-state['last_clock']>=10:
                with store.edit({'event':'adaptive_clock'}) as target:
                    target['last_clock']=now
            if now >= state['deadline_at'] and not state['stop_requested']:
                stop(store, 'deadline_exceeded')
            for name, entry in state['jobs'].items():
                if entry['state'] not in ACTIVE_JOB:
                    continue
                try:
                    job = runtime.get(entry['job_id'])
                except Error as exc:
                    if exc.code != 'unknown_job':
                        raise
                    if name not in live:
                        with store.edit({'event': 'adaptive_unknown', 'job': name}) as target:
                            target['jobs'][name]['state'] = 'unknown'
                    continue
                if job['state'] in TERMINAL:
                    _collect(store,runtime,name,job)
                elif entry['state'] != 'running':
                    with store.edit({'event':'adaptive_running','job':name}) as target:
                        target['jobs'][name]['state']='running'
            for name, process in list(live.items()):
                if process.poll() is not None:
                    process.wait()
                    del live[name]
            _prune(store, runtime, prune_clock)
            state=store.read()
            if state['stop_requested']:
                stop(store,state['stop_reason'])
                if not live or once:
                    return status(store.read())
            elif not store.maintenance()['paused'] and not any(j['state']=='unknown' for j in state['jobs'].values()):
                active_evals=sum(j['kind']=='evaluation' and j['state'] in ('intent','running') for j in state['jobs'].values())
                for trial_id, trial in state['trials'].items():
                    if trial['state']!='accepted' or active_evals>=state['plan']['concurrent']:
                        continue
                    request={'id':trial_id,'trial_id':trial_id,'x':trial['x'],'seed':trial['seed']}
                    check_environment(state)
                    name=_intend(store,runtime,trial_id,'evaluation',trial_id,request)
                    with store.edit({'event':'adaptive_trial_dispatch','trial':trial_id}) as target:
                        target['trials'][trial_id]['state']='pending'
                    _launch(store,runtime,name,live)
                    active_evals+=1
                state=store.read()
                plan=state['plan']
                trials=optimization_trials(state)
                accepted=sum(t['state']=='accepted' for t in trials.values())
                pending_proposal=any(j['kind']=='proposal' and j['state'] in ('intent','running','unknown') for j in state['jobs'].values())
                remaining=optimization_budget(plan)-len(trials)
                lookahead=plan.get('proposal_lookahead')
                # Without a declared look-ahead, the original rule: a full batch whenever none waits.
                q=min(remaining,plan['concurrent']) if lookahead is None else min(remaining,plan['concurrent']-active_evals+lookahead)
                if remaining<=0 and not any(j['state'] in ACTIVE_JOB for j in state['jobs'].values()):
                    _answer(store,runtime,live)
                elif not accepted and not pending_proposal and q>0:
                    from bo_craft.specs import validate_request
                    request={'schema_version':'bo.request/0.1','problem':state['plan']['problem'],
                        'config':state['plan']['config'],'seed':state['plan']['seed']+state['proposal_seq'],
                        'q':q, 'observations':state['observations'],
                        'pending':[{'id':k,'x':t['x']} for k,t in state['trials'].items() if t['state']=='pending']}
                    validate_request(request)
                    check_environment(state)
                    name=f'proposal-{state["proposal_seq"]:06d}'
                    _intend(store,runtime,name,'proposal',None,request)
                    with store.edit({'event':'adaptive_proposal_number'}) as target:
                        target['proposal_seq']+=1
                    _launch(store,runtime,name,live)
            value=status(store.read())
            if once or value['status'] in ('completed','stopped','unknown'):
                return value
            time.sleep(poll_seconds)
