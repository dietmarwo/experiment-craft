#!/usr/bin/env python3
"""Private local P7 rehearsal; no real fleet, service or power-loss acceptance."""
import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from experiment_craft.campaign import drive, initialize
from experiment_craft.comparison import declare
from experiment_craft.comparison_report import report as compare
from experiment_craft.deployment import export, load, plan, select
from experiment_craft.operations import backup, pause, restore, unpause
from experiment_craft.runtime import TERMINAL
from experiment_craft.storage import Store, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    bins = args.bin_dir.resolve()
    node = output / 'node'
    config = read_json(PROJECT / 'examples/deployment/home-lab.json')
    config['coordinator'].update(runner=str(bins / 'optimization-run'), root=str(output / 'coordinator'))
    config['nodes'][0].update(root=str(node), allow_commands=True,
        workers=[{'id': name, 'executable': str(bins / binary)} for name, binary in
                 [('fcmaes', 'fcmaes-job-worker'), ('lp-ip', 'lp-ip-job-worker'), ('sqp', 'sqp-job-worker')]])
    path = output / 'deployment.json'
    write_json(path, config)
    exported = export(path, output / 'deployment-plan')
    assert not node.exists() and exported['nodes'] == 7 and not exported['runtime_contacted']
    setup = plan(load(path))['nodes'][0]['setup_on_node']
    calls = []
    def call(argv):
        result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, timeout=30)
        calls.append({'argv': list(map(str, argv)), 'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError(result.stderr)
        return json.loads(result.stdout)
    for argv in setup:
        call(argv)  # Explicit administration of this newly created private test node.
    runner, root, mode, commands = select(path)
    def native(*argv):
        return call([runner, '--root', root, *argv])
    spec = importlib.util.spec_from_file_location('scientific_example', PROJECT / 'examples/campaigns/scientific/run.py')
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    manifest, protocol = example.make_source(output / 'source')
    initialize(manifest, output / 'campaign', runner, root, mode, commands)
    with closing(Store(output / 'campaign')) as store:
        declaration = declare(store, protocol)
        outcome = drive(store)
        assert outcome['status'] == 'incomplete'
        assert list(outcome['steps'].values()).count('succeeded') == 15
        assert list(outcome['steps'].values()).count('failed') == 2
        before = compare(store, output / 'before-report')
        pause(store, 'P7 private rehearsal')
        saved = backup(store, output / 'campaign-backup.zip')
        original_ids = {key: value['job_id'] for key, value in store.read()['steps'].items()}
    jobs = native('jobs', 'list')
    assert len(jobs) == 17 and all(job['state'] in TERMINAL for job in jobs)
    journals = {str(p.relative_to(node)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in node.glob('jobs/*/events.jsonl')}
    # This script is the sole client of its fresh node, and all jobs are terminal.
    # Runtime backup/restore is an explicit operator file-copy rehearsal, not a
    # second runtime snapshot API or a claim about concurrent/live services.
    runtime_copy = output / 'runtime-quiescent-copy'
    shutil.copytree(node, runtime_copy, symlinks=True)
    node.rename(output / 'runtime-retired-original')
    shutil.copytree(runtime_copy, node, symlinks=True)
    native('jobs', 'reconcile')
    restored = restore(output / 'campaign-backup.zip', output / 'restored-campaign')
    assert restored['dispatch_paused'] and not restored['runtime_contacted']
    with closing(Store(output / 'restored-campaign')) as store:
        assert store.maintenance()['paused']
        assert {key: value['job_id'] for key, value in store.read()['steps'].items()} == original_ids
        paused_report = compare(store, output / 'paused-report')
        assert paused_report['sha256'] == before['sha256']
        unpause(store)  # Native identity, resolutions, terminal records and bytes are checked.
        assert drive(store) == outcome
        after = compare(store, output / 'after-report')
        assert after['sha256'] == before['sha256']
    assert len(native('jobs', 'list')) == 17
    assert {str(p.relative_to(node)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in node.glob('jobs/*/events.jsonl')} == journals
    for name in ['comparison.json', 'comparison.md', 'observations.csv']:
        assert (output / 'before-report' / name).read_bytes() == (output / 'after-report' / name).read_bytes()
    result = {'status': 'passed', 'mode': 'real local foreground; private quiescent runtime copy',
              'configured_nodes': 7, 'tested_nodes': 1, 'remote_nodes_enabled': 0,
              'real_jobs': 17, 'succeeded': 15, 'deliberate_failures': 2, 'new_jobs_after_restore': 0,
              'same_native_handles': True, 'native_journals_unchanged': True, 'comparison_bytes_unchanged': True,
              'protocol_id': declaration['protocol_id'], 'backup': saved, 'campaign': outcome,
              'blocked': ['real independent SSH hosts', 'systemd/logout/reboot', 'cgroup enforcement',
                          'automatic placement', 'live/concurrent native-root backup', 'power-loss recovery']}
    write_json(output / 'calls.json', calls)
    write_json(output / 'summary.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
