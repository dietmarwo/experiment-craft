#!/usr/bin/env python3
"""Prepare (do not start) a real single-node campaign for the dashboard."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from experiment_craft.campaign import initialize
from experiment_craft.dashboard import serve
from experiment_craft.storage import read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    output, binaries = args.output.resolve(), args.bin_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    node, runner = output/'node', binaries/'optimization-run'
    def native(*argv):
        result = subprocess.run([str(runner), '--root', str(node), *map(str, argv)],
                                capture_output=True, text=True, timeout=30, check=True)
        return json.loads(result.stdout)
    native('node', 'init', '--capacity', '1', '--allow-commands')
    for worker in ('fcmaes', 'lp-ip', 'sqp'):
        native('workers', 'add', '--id', worker, '--executable', binaries/(worker+'-job-worker'))
    shutil.copy2(PROJECT/'examples/smoke/lp-ip/model.json', source/'model.json')
    steps = []
    # Real trusted delay commands make pause/stop and the time axis easy to try.
    # They are explicitly displayed steps, not synthetic solver progress.
    for index in range(4):
        wait_id = f'checkpoint-{index+1}'
        steps.append({'id': wait_id, 'needs': [steps[-1]['id']] if steps else [], 'job': {
            'schema_version': 'execution.command/0.1', 'argv': [sys.executable, '-c', 'import time; time.sleep(2)'],
            'env': {}, 'resources': {'cpu_slots': 1}, 'limits': {'wall_seconds': 10, 'grace_seconds': 1},
            'replay': 'never', 'inputs': [], 'outputs': []}})
        job = read_json(PROJECT/'examples/smoke/fcmaes/job.json')
        job.pop('request_key'); job['payload']['seed'] = index+1
        steps.append({'id': f'sphere-seed-{index+1}', 'needs': [wait_id], 'job': job,
                      'accept': {'require_feasible': True, 'claims': ['best_found']}})
    for worker, claim in [('lp-ip', 'numerical_optimum'), ('sqp', 'first_order')]:
        job = read_json(PROJECT/'examples/smoke'/worker/'job.json'); job.pop('request_key')
        steps.append({'id': worker, 'needs': [steps[-1]['id']], 'job': job,
                      'accept': {'require_feasible': True, 'claims': [claim]}})
    manifest = {'schema_version': 'experiment.campaign/0.1', 'name': 'Local solver tour', 'allow_commands': True,
                'budget': {'max_jobs': 10, 'max_wall_seconds': 3600, 'max_reserved_slot_seconds': 300}, 'steps': steps}
    write_json(source/'campaign.json', manifest)
    initialize(source/'campaign.json', output/'campaign', runner, node, 'foreground')
    inventory = read_json(PROJECT/'examples/deployment/home-lab.json')
    inventory['coordinator'].update(runner=str(runner), root=str(output/'fleet'))
    local = next(n for n in inventory['nodes'] if n['transport']=='local')
    local['root'] = str(node)
    local['workers'] = [{'id': w, 'executable': str(binaries/(w+'-job-worker'))} for w in ('fcmaes','lp-ip','sqp')]
    write_json(output/'deployment.json', inventory)
    argv = [sys.executable, '-m', 'experiment_craft', 'dashboard', '--workspace', str(output/'campaign'),
            '--state-dir', str(output/'dashboard'), '--deployment', str(output/'deployment.json'), '--port', str(args.port)]
    print(json.dumps({'initialized': True, 'jobs_submitted': len(native('jobs', 'list')), 'dashboard_argv': argv}), flush=True)
    if args.serve:
        print(json.dumps(serve([output/'campaign'], output/'dashboard', output/'deployment.json', args.port,
                               sample_seconds=.5)), flush=True)


if __name__ == '__main__':
    main()
