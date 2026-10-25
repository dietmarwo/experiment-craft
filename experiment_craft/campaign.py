"""Sequential DAG decisions and at-most-once client dispatch intent."""
import copy
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import time
from .manifest import compile_manifest, scientific
from .runtime import Runtime, TERMINAL
from .storage import Error, MAX_FILE, Store, canonical, exact, fingerprint, identity, loads, number, require, snapshot, write_json, atomic, publish_directory, regular_bytes, read_json

ACTIVE = {'dispatching', 'active', 'unknown'}
CLOCK_SECONDS = 10
DONE = {'succeeded', 'failed', 'cancelled', 'blocked', 'budget_exhausted', 'stopped'}
# Errors before dispatch that reject the job for good: native rejections of
# the job itself, and retained inputs, executables or results that no longer
# match the plan. Any other error leaves the step pending, because nothing was
# submitted and the cause may pass.
REJECTED = {'invalid_job', 'invalid_command_spec', 'file_transfer_failed', 'unsupported_job_kind',
            'unsupported_profile', 'size_limit', 'output_unavailable', 'executable_changed',
            'input_changed', 'result_changed', 'invalid_json'}


def rejects_job(exc):
    # The runner reports a worker validator that ran out of time as
    # invalid_job; a slow machine is not a property of the job.
    if exc.code == 'invalid_job' and 'took longer than' in str(exc):
        return False
    return exc.code in REJECTED


def over_budget(state, cost):
    # Decimal arithmetic: three steps of 0.1 fit a budget of 0.3.
    budget = state['plan']['budget']
    return (state['jobs_reserved'] >= budget['max_jobs'] or
            exact(state['slot_seconds_reserved']) + exact(cost) > exact(budget['max_reserved_slot_seconds']))


def reserve(state, cost):
    state['slot_seconds_reserved'] = number(exact(state['slot_seconds_reserved']) + exact(cost))


def event(kind, **fields):
    return {'event': kind, 'at': time.time(), **fields}


def initialize(manifest, workspace, runner, root, mode='systemd'):
    plan = compile_manifest(manifest)
    runtime = Runtime(runner, root)
    binding = runtime.binding(plan, mode)
    workspace = Path(workspace).absolute()
    if workspace.exists():
        store = Store(workspace)
        try:
            state = store.read()
            require(state['plan'] == scientific(plan) and state['runtime'] == binding,
                    'campaign_conflict', 'workspace binds a different campaign/runtime; continue the saved campaign or choose a new workspace')
            return summary(state)
        finally:
            store.close()
    workspace.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.campaign-', dir=workspace.parent))
    try:
        for sha, source in plan['sources'].items():
            snapshot(source['source'], temp / 'files' / sha, {k: source[k] for k in ['bytes', 'sha256']})
        # A workspace is one run of the plan. Its random instance keeps the
        # request keys of two workspaces apart, so neither adopts, counts or
        # cancels the other's native jobs.
        instance = secrets.token_hex(16)
        bound_id = identity({'plan_id': plan['plan_id'], 'runtime': binding, 'instance': instance})
        state = {'schema_version': 'experiment.campaign.state/0.1', 'campaign_id': bound_id,
                 'instance': instance,
                 'plan': scientific(plan), 'runtime': binding,
                 'stop_requested': False, 'stop_reason': None,
                 'jobs_reserved': 0, 'slot_seconds_reserved': 0, 'steps': {}}
        for step in plan['steps']:
            key = 'ec:' + bound_id + ':' + step['id']
            state['steps'][step['id']] = {'status': 'pending', 'request_key': key,
                'job_id': hashlib.sha256(key.encode()).hexdigest()[:32], 'issued': False}
        validate_static(runtime, plan, state, temp)
        # The campaign's wall-clock budget starts once initialization is done;
        # validating thousands of steps must not use it up.
        now = time.time()
        state.update(created_at=now, deadline_at=now + plan['budget']['max_wall_seconds'], last_clock=now)
        store = Store(temp, create=True)
        with store.edit(event('initialized', campaign_id=bound_id)) as target:
            target.update(state)
        store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        store.close()
        write_json(temp / 'plan.json', scientific(plan))
        # Publish a complete initial state, never replace another campaign.
        publish_directory(temp, workspace)
        fd = os.open(workspace.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return summary(state)
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def validate_static(runtime, plan, state, temp):
    """Validate, through the runtime, every step whose inputs are all static.

    A malformed envelope or payload then fails initialization instead of
    surfacing after earlier steps have run. Steps that read another step's
    result are validated when they become ready.
    """
    scratch = temp / 'validation'
    for step in plan['steps']:
        job = copy.deepcopy(step['job'])
        if any('from' in item for item in job['inputs']):
            continue
        job['request_key'] = state['steps'][step['id']]['request_key']
        directory = scratch / step['id']
        for index, item in enumerate(job['inputs']):
            dest = directory / 'inputs' / str(index)
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(temp / 'files' / item['sha256'], dest)
            except OSError:
                shutil.copyfile(temp / 'files' / item['sha256'], dest)
        write_json(directory / 'request.json', job)
        try:
            result = runtime.call('validate', '--spec', directory / 'request.json')
        except Error as exc:
            raise Error(exc.code, f"step {step['id']}: {exc}") from None
        require(result.get('valid') is True, 'runtime_protocol', f"runner did not validate step {step['id']}")
    if scratch.exists():
        shutil.rmtree(scratch)


def summary(state):
    statuses = {key: value['status'] for key, value in state['steps'].items()}
    if any(s in ACTIVE for s in statuses.values()):
        status = 'unknown' if 'unknown' in statuses.values() else ('stopping' if state['stop_requested'] else 'running')
    elif any(s == 'pending' for s in statuses.values()):
        status = 'stopping' if state['stop_requested'] else 'ready'
    elif all(s == 'succeeded' for s in statuses.values()):
        status = 'completed'
    else:
        status = 'stopped' if state['stop_requested'] else 'incomplete'
    return {'schema_version': 'experiment.campaign.status/0.1', 'campaign_id': state['campaign_id'],
            'status': status, 'steps': statuses, 'jobs_reserved': state['jobs_reserved'],
            'declared_slot_seconds_reserved': state['slot_seconds_reserved'],
            'stop_reason': state['stop_reason'], 'deadline_at': state['deadline_at']}


def runtime_for(state):
    binding = state['runtime']
    return Runtime(binding['runner'], binding['root'], binding)


def checked_native(runtime, job):
    record = runtime.call('jobs', 'execution', job['id'])
    require(record.get('schema_version') == 'execution.record/0.1' and record.get('attempt_id') == job['id']
            and record.get('state') == job['state'], 'runtime_protocol', 'execution record does not match terminal job')
    ref = record['native_result']
    require(ref['file'] in ['run.json', 'command-result.json'], 'runtime_protocol', 'unexpected native attachment name')
    path = Path(job['directory']) / ref['file']
    require(not path.is_symlink(), 'runtime_protocol', 'native attachment is a symlink')
    data = regular_bytes(path, MAX_FILE)
    require(len(data) <= MAX_FILE and len(data) == ref['bytes'] and hashlib.sha256(data).hexdigest() == ref['sha256'],
            'result_changed', 'native attachment size/digest mismatch')
    native = loads(data)
    require(native.get('schema_version') == ref['schema_version'], 'runtime_protocol', 'native schema mismatch')
    return record, native, data


def accepted(step, job, record, native):
    if job['state'] != 'completed':
        return False
    kind = step['job']['schema_version']
    if kind == 'execution.command/0.1':
        return (record['kind'] == 'command' and native.get('schema_version') == 'execution.command.result/0.1'
                and native.get('state') == 'completed' and native.get('process', {}).get('code') == 0
                and native.get('process', {}).get('signal') is None and not native.get('output_errors'))
    if (record['kind'] != 'optimization' or native.get('schema_version') != 'optimization.result/0.2'
            or native.get('status') != 'completed' or native.get('runner', {}).get('accounting_complete') is not True
            or not native.get('results') or native.get('completed_tasks') != native.get('requested_tasks')
            or native['completed_tasks'] != len(native['results'])):
        return False
    policy = step.get('accept', {})
    return all((not policy.get('require_feasible') or row['outcome'].get('feasible') is True)
               and (not policy.get('claims') or row['outcome'].get('claim') in policy['claims'])
               for row in native['results'])


def observe(store, runtime, step):
    saved = store.read()['steps'][step['id']]
    try:
        job = runtime.get(saved['job_id'])
        require(saved.get('expected_resolved') is not None, 'execution_unverifiable',
                'saved dispatch lacks validated resolution; retain uncertainty rather than adopting a result')
        provenance = read_json(Path(job['directory']) / 'provenance.json')
        if saved.get('expected_resolved') is not None:
            require(canonical(read_json(Path(job['directory']) / 'resolved.json')) == canonical(saved['expected_resolved']),
                    'execution_mismatch', 'native resolved request differs from validated campaign intent')
        if saved.get('expected_identity') is not None:
            require(provenance.get('identity') == saved['expected_identity'],
                    'execution_mismatch', 'native execution identity differs from validated intent')
        if saved.get('expected_worker_digest') is not None:
            require(provenance.get('worker_digest') == saved['expected_worker_digest'],
                    'execution_mismatch', 'native worker digest differs from campaign binding')
        if job['state'] not in TERMINAL:
            uncertain = saved.get('error') and job['state'] in ['submitted', 'starting']
            status = 'unknown' if job.get('observed_state') or uncertain else 'active'
            previous = saved.get('observation') or {}
            if (saved['status'] == status and previous.get('state') == job['state']
                    and previous.get('observed_state') == job.get('observed_state')):
                return  # Polling an unchanged job writes no decision.
            with store.edit(event('observed', step=step['id'], job_state=job['state'])) as state:
                state['steps'][step['id']].update(status=status, observation=job)
            return
        record, native, data = checked_native(runtime, job)
        if saved.get('execution_identity'):
            require(saved['execution_identity'] == record.get('identity'), 'result_changed', 'execution identity changed')
        path = store.root / 'results' / step['id'] / 'native.json'
        atomic(path, data)
        write_json(path.with_name('execution.json'), record)
        passed = accepted(step, job, record, native)
        # Cancelled work (a stop, the deadline, an interrupt) is not a scientific failure.
        status = 'succeeded' if passed else ('cancelled' if job['state'] == 'cancelled' else 'failed')
        with store.edit(event('collected', step=step['id'], accepted=passed)) as state:
            state['steps'][step['id']].update(status=status, observation=job,
                execution_identity=record.get('identity'), native={'path': str(path.relative_to(store.root)),
                'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}, error=None)
    except (Error, OSError, KeyError, TypeError) as exc:
        with store.edit(event('observation_failed', step=step['id'])) as state:
            status = 'failed' if getattr(exc, 'code', '') == 'execution_mismatch' else 'unknown'
            state['steps'][step['id']].update(status=status, error={'code': getattr(exc, 'code', 'result_unavailable'), 'message': str(exc)})


def cached_native(store, entry):
    ref = entry['native']
    # Check and parse the same bytes; a second read could see another file.
    data = regular_bytes(store.root / ref['path'])
    require(len(data) == ref['bytes'] and hashlib.sha256(data).hexdigest() == ref['sha256'],
            'result_changed', 'cached native result changed')
    return loads(data)


def materialize(store, runtime, step):
    state = store.read()
    job = copy.deepcopy(step['job'])
    job['request_key'] = state['steps'][step['id']]['request_key']
    directory = store.root / 'requests' / step['id']
    directory.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for index, item in enumerate(job['inputs']):
        dest = directory / 'inputs' / str(index)
        if 'from' in item:
            ref = item.pop('from')
            producer = state['steps'][ref['step']]
            native = cached_native(store, producer)
            if ref['kind'] == 'native':
                meta = {k: producer['native'][k] for k in ['bytes', 'sha256']}
                source = store.root / producer['native']['path']
                snapshot(source, dest, meta)
            else:
                meta = (native.get('outputs') or {}).get(ref['output'])
                require(isinstance(meta, dict), 'output_unavailable',
                        f"step {ref['step']} has no sealed output {ref['output']!r}")
                expected = {k: meta[k] for k in ['bytes', 'sha256']}
                if dest.exists():
                    require(fingerprint(dest) == expected, 'input_changed', 'prior collected input differs')
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    # '--' keeps an output name such as -x or --help a positional value.
                    runtime.call('jobs', 'collect', '--destination', dest, '--', producer['job_id'], ref['output'])
                meta = expected
                require(fingerprint(dest) == meta, 'input_changed', 'collected input mismatch')
            item['sha256'] = meta['sha256']
            if job['schema_version'] == 'execution.command/0.1':
                item['bytes'] = meta['bytes']
            item['file'] = f'inputs/{index}'
        else:
            source = store.root / 'files' / item['sha256']
            meta = fingerprint(source)
            require(meta['sha256'] == item['sha256'], 'input_changed', 'retained source changed')
            snapshot(source, dest, meta)
        total_bytes += meta['bytes']
        require(total_bytes <= 256 * 1024 ** 2, 'size_limit', 'combined resolved inputs exceed 256 MiB')
    if step.get('executable'):
        ex = step['executable']
        require(str(Path(ex['argv0']).resolve()) == ex['resolved'] and
                fingerprint(ex['argv0'], 1024 ** 3) == {k: ex[k] for k in ['bytes', 'sha256']},
                'executable_changed', 'command interpreter/executable changed')
    path = directory / 'request.json'
    write_json(path, job)
    validation = runtime.call('validate', '--spec', path)
    require(validation.get('valid') is True, 'runtime_protocol', 'runner did not validate the request')
    return path, job, validation


def request_stop(store, reason='requested'):
    current = store.read()
    if not current['stop_requested'] or any(e['status'] == 'pending' for e in current['steps'].values()):
        record = event('stop_requested', reason=reason)
        with store.edit(record) as state:
            if state['stop_requested']:
                # The first reason stands; a later stop does not relabel a deadline.
                record.update(event='stop_repeated', reason=state['stop_reason'])
            else:
                state['stop_requested'], state['stop_reason'] = True, reason
            for entry in state['steps'].values():
                if entry['status'] == 'pending':
                    entry['status'] = 'stopped'
    runtime = None
    for name, entry in store.read()['steps'].items():
        # A cancellation the runtime accepted is not sent again; one that
        # found no job yet (a stop racing the launch) is.
        if entry['status'] in ACTIVE and not entry.get('cancel_requested'):
            try:
                runtime = runtime or runtime_for(store.read())
                runtime.cancel(entry['job_id'])
                with store.edit(event('cancel_requested', step=name)) as state:
                    state['steps'][name]['cancel_requested'] = True
            except Error as exc:
                with store.edit(event('cancel_pending', step=name)) as state:
                    state['steps'][name]['cancel_error'] = {'code': exc.code, 'message': str(exc)}
    return summary(store.read())


def check_deadline(store):
    now = max(time.time(), store.read()['last_clock'])
    # The persisted clock keeps the deadline monotonic across restarts; a
    # ten-second resolution avoids rewriting the state every second.
    if now - store.read()['last_clock'] >= CLOCK_SECONDS:
        with store.edit(event('clock')) as state:
            state['last_clock'] = now
    if now >= store.read()['deadline_at'] and not store.read()['stop_requested']:
        request_stop(store, 'deadline_exceeded')


def dispatch(store, runtime, step):
    path, job, validation = materialize(store, runtime, step)
    cost = step['reserved_slot_seconds']
    record = event('dispatch_intent', step=step['id'])
    with store.edit(record) as state:
        # This transaction serializes the launch decision with stop and budgets.
        # The event names the decision actually taken.
        if state['stop_requested'] or time.time() >= state['deadline_at']:
            record['event'] = 'dispatch_refused'
            return
        if over_budget(state, cost):
            record['event'] = 'budget_exhausted'
            state['steps'][step['id']]['status'] = 'budget_exhausted'
            return
        state['jobs_reserved'] += 1
        reserve(state, cost)
        state['steps'][step['id']].update(status='dispatching', issued=True, submitted_job=job, error=None,
            expected_resolved=validation['resolved'], expected_identity=validation.get('identity'),
            expected_worker_digest=runtime.expected['workers'].get(job.get('worker'), {}).get('digest'))
    try:
        if runtime.expected['mode'] == 'systemd':
            runtime.call('submit', '--spec', path)
        else:
            with path.with_name('runner.stdout').open('wb') as out, path.with_name('runner.stderr').open('wb') as err:
                process = runtime.foreground(path, out, err)
                stopping_since = None
                while process.poll() is None:
                    check_deadline(store)
                    if store.read()['stop_requested']:
                        # Stop may have raced preparation before the job existed.
                        request_stop(store, store.read()['stop_reason'])
                        stopping_since = stopping_since or time.monotonic()
                        if time.monotonic() - stopping_since >= 5:
                            raise Error('cancellation_unconfirmed', 'runtime cancellation is unconfirmed; retain and observe the same job')
                    time.sleep(0.1)
                out.flush()
                err.flush()
            with path.with_name('runner.stdout').open('rb') as stdout, path.with_name('runner.stderr').open('rb') as stderr:
                runtime.decode(process.returncode, stdout.read(4*1024*1024+1), stderr.read(4*1024*1024+1))
    except Error as exc:
        with store.edit(event('dispatch_error', step=step['id'], code=exc.code)) as state:
            entry = state['steps'][step['id']]
            entry['error'] = {'code': exc.code, 'message': str(exc)}
            if exc.code == 'runtime_not_started':
                entry.update(status='pending', issued=False)
                state['jobs_reserved'] -= 1
                reserve(state, -cost)
            elif exc.code == 'request_key_conflict':
                entry['status'] = 'failed'
            else:
                entry['status'] = 'unknown'
        if exc.code == 'request_key_conflict':
            return
        if exc.code == 'runtime_not_started':
            raise
    if store.read()['stop_requested']:
        # A stop committed while the launch was in flight found no job to
        # cancel; the job may exist now, also when advancing with --once.
        request_stop(store)
    observe(store, runtime, step)


def collect_now(store):
    """Observe issued work once; refused while another client advances."""
    with store.advance_lock():
        return collect(store)


def collect(store):
    state = store.read()
    runtime = runtime_for(state)
    for step in state['plan']['steps']:
        if store.read()['steps'][step['id']]['status'] in ACTIVE:
            observe(store, runtime, step)
    return summary(store.read())


def drive(store, once=False, poll_seconds=0.2):
    with store.advance_lock():
        if all(e['status'] in DONE for e in store.read()['steps'].values()):
            return summary(store.read())
        runtime = runtime_for(store.read())
        while True:
            if all(e['status'] in DONE for e in store.read()['steps'].values()):
                return summary(store.read())
            check_deadline(store)
            collect(store)
            state = store.read()
            for step in state['plan']['steps']:
                if state['steps'][step['id']]['status'] != 'pending':
                    continue
                if state['stop_requested']:
                    status = 'stopped'
                elif any(state['steps'][need]['status'] in DONE - {'succeeded'} for need in step['needs']):
                    status = 'blocked'
                else:
                    continue
                with store.edit(event(status, step=step['id'])) as current:
                    current['steps'][step['id']]['status'] = status
                state['steps'][step['id']]['status'] = status
            state = store.read()
            active = [e for e in state['steps'].values() if e['status'] in ACTIVE]
            if active:
                if state['stop_requested']:
                    request_stop(store, state['stop_reason'])
                    return summary(store.read())
                if once or any(e['status'] == 'unknown' for e in active):
                    return summary(store.read())
                time.sleep(poll_seconds)
                continue
            candidate = next((s for s in state['plan']['steps'] if state['steps'][s['id']]['status'] == 'pending'
                              and all(state['steps'][n]['status'] == 'succeeded' for n in s['needs'])), None)
            if candidate is None:
                return summary(state)
            if over_budget(state, candidate['reserved_slot_seconds']):
                with store.edit(event('budget_exhausted', step=candidate['id'])) as current:
                    current['steps'][candidate['id']]['status'] = 'budget_exhausted'
                if once:
                    return summary(store.read())
                continue
            runtime.verify(state['plan'])
            try:
                dispatch(store, runtime, candidate)
            except Error as exc:
                if exc.code == 'runtime_not_started':
                    raise
                if not rejects_job(exc):
                    # Nothing was submitted, and the cause (a timeout, an
                    # unavailable runtime, a changed file) may pass: keep the
                    # step pending, record why, and stop advancing.
                    with store.edit(event('step_deferred', step=candidate['id'], code=exc.code)) as current:
                        current['steps'][candidate['id']]['error'] = {'code': exc.code, 'message': str(exc)}
                    raise
                with store.edit(event('step_rejected', step=candidate['id'], code=exc.code)) as current:
                    current['steps'][candidate['id']].update(status='failed', error={'code': exc.code, 'message': str(exc)})
            if once:
                return summary(store.read())
