#!/usr/bin/env python3
"""A small pipeline check, not a solver benchmark: 17 real mixed native jobs."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))
from experiment_craft.campaign import drive, initialize
from experiment_craft.comparison import declare
from experiment_craft.comparison_report import report as compare
from experiment_craft.manifest import compile_manifest
from experiment_craft.report import report
from experiment_craft.storage import Store, read_json, write_json


def command(argv, inputs=None, outputs=None, wall=10):
    return {'schema_version': 'execution.command/0.1', 'argv': argv, 'env': {},
            'resources': {'cpu_slots': 1}, 'limits': {'wall_seconds': wall, 'grace_seconds': .1},
            'replay': 'never', 'inputs': inputs or [], 'outputs': outputs or []}


def make_source(source):
    source.mkdir()
    mixed = PROJECT / 'examples/campaigns/local-mixed'
    for name in ['prepare.py', 'check.py']:
        shutil.copy2(mixed / name, source / name)
    shutil.copy2(PROJECT / 'examples/smoke/lp-ip/model.json', source / 'model.json')
    steps = [{'id': 'prepare', 'job': command([sys.executable, 'prepare.py'],
        [{'path': 'prepare.py', 'file': 'prepare.py'}, {'path': 'model.json', 'file': 'model.json'}],
        [{'name': 'model', 'path': 'prepared-model.json', 'required': True, 'max_bytes': 10000}])}]
    for name, population in [('bite-default', None), ('bite-larger', 32)]:
        job = read_json(PROJECT / 'examples/smoke/fcmaes/job.json')
        job.pop('request_key')
        job['payload']['optimizer']['parameters']['population'] = population
        steps.append({'id': name, 'job': job, 'matrix': {'/payload/seed': [1, 2, 3]}})
    for presolve in [True, False]:
        for repeat in [1, 2]:
            job = read_json(PROJECT / 'examples/smoke/lp-ip/job.json')
            job.pop('request_key')
            job['payload']['presolve'] = presolve
            job['inputs'] = [{'name': 'model', 'from': {'step': 'prepare', 'kind': 'output', 'output': 'model'}}]
            steps.append({'id': f'lp-{"on" if presolve else "off"}-{repeat}', 'job': job})
    for name, start in [('a', [.1, .2, .3, .4]), ('b', [.4, .3, .2, .1]), ('c', [.7, .1, .1, .1])]:
        job = read_json(PROJECT / 'examples/smoke/sqp/job.json')
        job.pop('request_key')
        job['payload']['starts'] = [start]
        steps.append({'id': 'sqp-' + name, 'job': job})
    check = command([sys.executable, 'check.py'], [{'path': 'check.py', 'file': 'check.py'},
        {'path': 'lp.json', 'from': {'step': 'lp-on-1', 'kind': 'native'}},
        {'path': 'sqp.json', 'from': {'step': 'sqp-a', 'kind': 'native'}}],
        [{'name': 'checks', 'path': 'checks.json', 'required': True, 'max_bytes': 10000}])
    steps += [{'id': 'numerical-check', 'job': check},
              {'id': 'invalid-output', 'job': command(['/bin/true'], outputs=[
                  {'name': 'missing', 'path': 'missing', 'required': True, 'max_bytes': 100}], wall=1)},
              {'id': 'timeout', 'job': command([sys.executable, '-c', 'import time; time.sleep(5)'], wall=.2)}]
    manifest = {'schema_version': 'experiment.campaign/0.1', 'name': 'Scientific comparison pipeline check',
                'allow_commands': True, 'budget': {'max_jobs': 17, 'max_wall_seconds': 120,
                                                  'max_reserved_slot_seconds': 1000}, 'steps': steps}
    write_json(source / 'campaign.json', manifest)
    plan = compile_manifest(source / 'campaign.json')
    metric = {'id': 'objective', 'pointer': '/outcome/objective', 'unit': 'model objective', 'direction': 'minimize'}
    groups = [{
        'id': 'fcmaes-sphere', 'description': 'BiteOpt populations over three common seeds; pipeline validation only',
        'kind': 'optimization', 'arms': [{'id': 'default', 'templates': ['bite-default']},
                                         {'id': 'larger', 'templates': ['bite-larger']}],
        'vary': ['/payload/optimizer'], 'replication': {'kind': 'seed', 'pointer': '/payload/seed'},
        'design': 'paired', 'budget': {'kind': 'fixed_work', 'pointer': '/payload/evaluations_per_retry',
                                      'counter': 'evaluations', 'limit': 100},
        'metrics': [{**metric, 'unit': 'sum of squared coordinates', 'target': .01}]}, {
        'id': 'lp-ip-choice', 'description': 'Known small binary model, presolve on/off; deterministic timing repeats',
        'kind': 'optimization', 'arms': [{'id': 'presolve-on', 'templates': ['lp-on-1', 'lp-on-2']},
                                         {'id': 'presolve-off', 'templates': ['lp-off-1', 'lp-off-2']}],
        'vary': ['/payload/presolve'], 'replication': {'kind': 'deterministic'}, 'design': 'unpaired',
        'budget': {'kind': 'fixed_time', 'seconds': 30},
        'metrics': [metric, {'id': 'bound', 'pointer': '/outcome/details/best_bound', 'unit': 'model objective', 'direction': 'none'},
                    {'id': 'gap', 'pointer': '/outcome/details/gap', 'unit': 'native gap', 'direction': 'minimize'},
                    {'id': 'integrality', 'pointer': '/outcome/details/integrality_violation',
                     'unit': 'native integrality violation', 'direction': 'minimize'}]}, {
        'id': 'sqp-simplex', 'description': 'Three distinct constrained starts; preserve first-order and KKT evidence',
        'kind': 'optimization', 'arms': [{'id': 'active-set', 'templates': ['sqp-a', 'sqp-b', 'sqp-c']}],
        'vary': [], 'replication': {'kind': 'start', 'pointer': '/payload/starts/0'}, 'design': 'unpaired',
        'budget': {'kind': 'fixed_work', 'pointer': '/payload/max_iterations', 'counter': 'iterations', 'limit': 100},
        'metrics': [metric, {'id': 'primal', 'pointer': '/outcome/details/primal_violation',
                             'unit': 'native primal residual', 'direction': 'minimize'},
                    {'id': 'stationarity', 'pointer': '/outcome/details/kkt/stationarity',
                     'unit': 'native stationarity residual', 'direction': 'minimize'}]}]
    for name, wall, description in [
        ('numerical-check', 10, 'Known LP/IP and SQP answers checked by a sealed numerical-check command'),
        ('invalid-output', 1, 'Deliberate missing required output: must stay failed and visible'),
        ('timeout', .2, 'Deliberate native timeout: must stay failed and visible')]:
        groups.append({'id': name, 'description': description, 'kind': 'command',
                       'arms': [{'id': 'check', 'templates': [name]}], 'vary': [],
                       'replication': {'kind': 'deterministic'}, 'design': 'unpaired',
                       'budget': {'kind': 'fixed_time', 'seconds': wall}, 'metrics': []})
    protocol = {'schema_version': 'experiment.comparison/0.1', 'name': 'Small mixed scientific suites',
                'plan_id': plan['plan_id'], 'groups': groups,
                'exclude': [{'template': 'prepare', 'reason': 'Shared input preparation; status and raw native result remain in the campaign report'}]}
    write_json(source / 'comparison.json', protocol)
    return source / 'campaign.json', source / 'comparison.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    node = output / 'node'
    runner = args.bin_dir.resolve() / 'optimization-run'
    def cli(*argv):
        process = subprocess.run([str(runner), '--root', str(node), *map(str, argv)], capture_output=True, text=True, timeout=30)
        if process.returncode:
            raise RuntimeError(process.stderr)
        return json.loads(process.stdout)
    cli('node', 'init', '--capacity', '1', '--allow-commands')
    for name, binary in [('fcmaes', 'fcmaes-job-worker'), ('lp-ip', 'lp-ip-job-worker'), ('sqp', 'sqp-job-worker')]:
        cli('workers', 'add', '--id', name, '--executable', args.bin_dir.resolve() / binary)
    manifest, protocol = make_source(output / 'source')
    initialize(manifest, output / 'campaign', runner, node, 'foreground')
    with closing(Store(output / 'campaign')) as store:
        binding = declare(store, protocol)
        assert cli('jobs', 'list') == []
        outcome = drive(store)
        assert outcome['status'] == 'incomplete' and outcome['steps']['invalid-output'] == 'failed'
        assert outcome['steps']['timeout'] == 'failed'
        assert list(outcome['steps'].values()).count('succeeded') == 15
        basic = report(store, output / 'report')
        scientific = compare(store, output / 'comparison')
        value = read_json(output / 'comparison/comparison.json')
        assert len(value['campaign_report']['steps']) == 17
        assert value['campaign_report']['counts'] == {'failed': 2, 'succeeded': 15}
        assert value['groups'][0]['paired_differences'][0]['summary']['n'] == 3
        for group in value['groups'][:3]:
            for arm in group['arms']:
                assert arm['summary']['complete'] == arm['summary']['planned'], arm
        assert cli('jobs', 'list') and len(cli('jobs', 'list')) == 17
        journals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in node.glob('jobs/*/events.jsonl')}
        before = (store.read(), store.events())
        assert compare(store, output / 'comparison') == scientific
        assert report(store, output / 'report') == basic
        assert (store.read(), store.events()) == before
        assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in journals} == journals
        summary = {'status': 'passed', 'mode': 'real local foreground', 'jobs': 17,
                   'successful': 15, 'deliberate_failures': 2, 'groups': 6,
                   'protocol_id': binding['protocol_id'], 'repeat_did_not_execute': True,
                   'comparison': scientific, 'campaign': outcome}
    write_json(output / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
