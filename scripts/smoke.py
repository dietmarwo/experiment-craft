#!/usr/bin/env python3
"""Keep evidence from three small real jobs; use the existing runner as-is."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import jsonschema

PROJECT = Path(__file__).resolve().parents[1]
CALL_TIMEOUT = 90


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir', type=Path, required=True)
    parser.add_argument('--schemas', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='must not already exist')
    args = parser.parse_args()
    bins, schemas, output = args.bin_dir.resolve(), args.schemas.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        return smoke(bins, schemas, output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, jsonschema.ValidationError) as error:
        message = getattr(error, 'message', None) or str(error)
        write(output / 'summary.json', {'status': 'failed', 'error': f'{type(error).__name__}: {message}',
                                        'recorded_at': datetime.now(timezone.utc).isoformat()})
        print(f'smoke: {type(error).__name__}: {message}', file=sys.stderr)
        return 1


def smoke(bins, schemas, output):
    for binary in ['optimization-run', 'fcmaes-job-worker', 'lp-ip-job-worker', 'sqp-job-worker']:
        check((bins / binary).is_file(), f'Missing required binary: {bins / binary}')
    root = output / 'node'
    commands = []

    def call(label, *argv, error=None):
        # Always pass --root: without it the runner falls back to environment variables and the cwd.
        command = [str(bins / 'optimization-run'), '--json', '--root', str(root), *map(str, argv)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=CALL_TIMEOUT)
        except subprocess.TimeoutExpired as expired:
            raise ValueError(f'{label}: no answer within {CALL_TIMEOUT} s') from expired
        commands.append({'label': label, 'argv': result.args, 'exit_code': result.returncode})
        (output / f'{label}.stdout').write_text(result.stdout)
        (output / f'{label}.stderr').write_text(result.stderr)
        write(output / 'commands.json', commands)
        if error is not None:
            # Runner errors exit 2 with one JSON object on stderr; classify by code, not message.
            check(result.returncode == 2, f'{label}: expected error {error}, got exit {result.returncode}')
            lines = result.stderr.strip().splitlines()
            check(bool(lines), f'{label}: no error object on stderr')
            value = json.loads(lines[-1])
            check(value['error']['code'] == error, f'{label}: expected {error}, got {value}')
        else:
            check(result.returncode == 0, f'{label}: exit {result.returncode}: {result.stderr}')
            value = json.loads(result.stdout)
        write(output / f'{label}.json', value)
        return value

    job_schema = json.loads((schemas / 'optimization.job-0.1.schema.json').read_text())
    result_schema = json.loads((schemas / 'optimization.result-0.2.schema.json').read_text())
    call('init', 'node', 'init', '--capacity', '1')
    call('doctor', 'node', 'doctor')
    summaries = []
    for worker in ['fcmaes', 'lp-ip', 'sqp']:
        call(worker + '-register', 'workers', 'add', '--id', worker,
             '--executable', bins / f'{worker}-job-worker')
        description = call(worker + '-describe', 'problems', 'describe', worker)
        check(description['protocol'] == 'optimization.worker/0.2', 'Unexpected worker protocol')
        fixture = output / worker
        shutil.copytree(PROJECT / 'examples/smoke' / worker, fixture)
        path = fixture / 'job.json'
        spec = json.loads(path.read_text())
        jsonschema.Draft202012Validator(job_schema).validate(spec)
        jsonschema.Draft202012Validator(description['payload_schemas'][spec['payload_schema']]).validate(spec['payload'])
        for item in spec['inputs']:
            check(sha(fixture / item['file']) == item['sha256'], 'Fixture input digest mismatch')
        check(call(worker + '-validate', 'validate', '--spec', path)['valid'], 'Validation failed')
        job = call(worker + '-run', 'run', '--spec', path)
        check(job['state'] == 'completed', f'{worker}: {job}')
        directory = Path(job['directory'])
        manifest = call(worker + '-result', 'result', directory)
        jsonschema.Draft202012Validator(result_schema).validate(manifest)
        check(manifest['status'] == 'completed' and manifest['completed_tasks'] == 1, 'Incomplete smoke job')
        check(len(manifest['results']) == 1, 'Unexpected task count')
        record = manifest['results'][0]
        outcome = record['outcome']
        check(outcome['feasible'] is True and outcome['evidence']['level'] == 'rechecked', 'Missing rechecked feasibility')
        x, objective = outcome['x'], outcome['objective']
        check(math.isfinite(objective) and all(map(math.isfinite, x)), 'Non-finite result')
        if worker == 'fcmaes':
            check(outcome['claim'] == 'best_found', 'An optimizer best point is not an optimality proof')
            check(record['work']['evaluations'] == 100, 'Evaluation accounting differs')
            check(all(-5 <= v <= 5 for v in x), 'Bounds violated')
            check(math.isclose(objective, sum(v*v for v in x), rel_tol=1e-10, abs_tol=1e-12), 'Sphere objective differs')
        elif worker == 'lp-ip':
            check(outcome['claim'] == 'numerical_optimum', 'Unexpected LP/IP claim')
            check(math.isclose(objective, 7, abs_tol=1e-8), 'Wrong LP/IP objective')
            check(all(math.isclose(a, b, abs_tol=1e-8) for a, b in zip(x, [1, 0])) and len(x) == 2, 'Wrong LP/IP solution')
            check(math.isclose(outcome['details']['best_bound'], 7, abs_tol=1e-8), 'Wrong numerical bound')
        else:
            check(outcome['claim'] == 'first_order', 'Unexpected SQP claim')
            check(math.isclose(objective, .25, abs_tol=1e-6), 'Wrong simplex objective')
            check(len(x) == 4 and all(math.isclose(v, .25, abs_tol=1e-6) for v in x), 'Wrong simplex point')
            check(outcome['details']['kkt']['stationarity'] <= 1e-6, 'Stationarity tolerance violated')
        journal_digest = sha(directory / 'results.jsonl')
        repeated = call(worker + '-repeat', 'run', '--spec', path)
        check(repeated['id'] == job['id'] and repeated['state'] == 'completed', 'Request did not reuse its handle')
        check(sha(directory / 'results.jsonl') == journal_digest, 'Repeated request changed the journal')
        changed = copy.deepcopy(spec)
        changed['limits']['wall_time_seconds'] += 1
        conflict = fixture / 'conflict.json'
        write(conflict, changed)
        call(worker + '-conflict', 'run', '--spec', conflict, error='request_key_conflict')
        summaries.append({'worker': worker, 'job_id': job['id'], 'state': job['state'],
                          'objective': objective, 'claim': outcome['claim'], 'evidence': outcome['evidence'],
                          'binary_sha256': sha(bins / f'{worker}-job-worker'),
                          'journal_sha256': journal_digest, 'idempotency': 'passed', 'conflict': 'passed'})
    # Existing checked file staging: validation must reject changed bytes under an old hash.
    model = output / 'lp-ip/model.json'
    original = model.read_bytes()
    try:
        model.write_bytes(original + b' ')
        call('lp-ip-input-corruption', 'validate', '--spec', output / 'lp-ip/job.json', error='invalid_job')
    finally:
        model.write_bytes(original)
    report = {'status': 'passed', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'mode': 'foreground_local', 'node_capacity': 1, 'jobs': summaries,
              'input_checksum_rejection': 'passed',
              'runner_sha256': sha(bins / 'optimization-run')}
    write(output / 'summary.json', report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
