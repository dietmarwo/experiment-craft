#!/usr/bin/env python3
"""Run a pinned CAP command campaign, collect its receipt and report it offline.

This example explicitly initializes its own local foreground test node. The
experiment-craft client itself never administers a node or runs a checker.
"""
import argparse
from contextlib import closing, redirect_stdout
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(PROJECT))
from experiment_craft.artifacts import catalog, collect, input_bytes, native_result, output_bytes
from experiment_craft.campaign import initialize, drive
from experiment_craft.runtime import Runtime
from experiment_craft.storage import Store, canonical, loads
from experiment_craft.verification import report


def capture_snapshot(store,destination):
    """Read-only report test data, deliberately without a campaign database."""
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    state=store.read()
    (destination/'state.json').write_bytes(canonical(state)+b'\n')
    for name,entry in state['steps'].items():
        if entry.get('native'):
            native_result(store,entry,name)
            data=(store.root/entry['native']['path']).read_bytes()
            assert len(data)==entry['native']['bytes'] and hashlib.sha256(data).hexdigest()==entry['native']['sha256']
            target=destination/entry['native']['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    for index,item in enumerate(state['steps']['accept']['submitted_job']['inputs']):
        data,_=input_bytes(store,state,'accept',item['path'])
        target=destination/'requests/accept/inputs'/str(index);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    data,info=output_bytes(store,state,'accept','acceptance')
    target=destination/info['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    manifest={str(path.relative_to(destination)):hashlib.sha256(path.read_bytes()).hexdigest()
              for path in destination.rglob('*') if path.is_file()}
    (destination/'files-sha256.json').write_bytes(canonical(manifest)+b'\n')
    return {'files':len(manifest),'sha256':hashlib.sha256((destination/'files-sha256.json').read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['fcmaes-source','binary','julia','depot','runner','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--problem',choices=['scalar-cuberoot','cahn-hilliard'],default='scalar-cuberoot')
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    source=args.fcmaes_source.resolve()/'tutorials/validated-numerics'
    environment=os.environ.copy()
    environment.update(JULIA_DEPOT_PATH=str(args.depot.resolve()),JULIA_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    manifest=output/'spec/campaign.json'
    generated=subprocess.run([sys.executable,str(source/'make_audit_campaign.py'),'--destination',str(manifest.parent),
        '--julia',str(args.julia.resolve()),'--depot',str(args.depot.resolve()),'--binary',str(args.binary.resolve()),
        '--problem',args.problem],capture_output=True,text=True,env=environment)
    (output/'generator.stdout.log').write_text(generated.stdout);(output/'generator.stderr.log').write_text(generated.stderr)
    if generated.returncode:raise RuntimeError(generated.stderr)
    node,workspace=output/'node',output/'campaign'
    subprocess.run([str(args.runner.resolve()),'--root',str(node),'node','init','--capacity','1','--allow-commands'],check=True,capture_output=True)
    initialize(manifest,workspace,args.runner,node,'foreground')
    with closing(Store(workspace)) as store:
        status=drive(store)
        assert status['status']=='completed' and status['jobs_reserved']==3,status
        before=store.read();events=store.events()
        receipt=collect(store,'accept','acceptance')
        assert receipt['artifact']['availability']=='retained'
        with patch.object(Runtime,'call',side_effect=AssertionError('report contacted the runtime')):
            first=report(store,output/'verification','accept')
            assert report(store,output/'verification','accept')==first
            listing=catalog(store)
        assert first['status']=='reported_accepted',first
        result=loads((output/'verification/verification.json').read_bytes())
        assert result['summary']['total_arms']==result['summary']['reported_accepted_arms']==9
        assert store.read()==before and store.events()==events
        continued=drive(store)
        assert continued['jobs_reserved']==3 and continued['status']=='completed'
        # Independent exact rational validation is example validation, not a
        # feature of the reporting adapter. Load only the explicitly supplied
        # trusted application's standalone checker.
        module_spec=importlib.util.spec_from_file_location('cap_exact_check',source/'exact_check.py')
        checker=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(checker)
        raw,_=input_bytes(store,store.read(),'accept','audit.json')
        audited=loads(raw)
        raw,_=input_bytes(store,store.read(),'accept','candidates.json')
        candidates=loads(raw)
        validation=checker.Report()
        with (output/'exact-check.txt').open('w') as stream,redirect_stdout(stream):
            for row in audited['arms']:
                with tempfile.TemporaryDirectory() as temporary:
                    folder=Path(temporary)/args.problem;folder.mkdir()
                    (folder/'candidate.json').write_text(candidates['arms'][row['id']]['candidate_json'])
                    (folder/'verification.json').write_text(row['verification']['document']['json'])
                    print('ARM '+row['id'])
                    function=checker.scalar if args.problem=='scalar-cuberoot' else checker.cahn_hilliard
                    function(folder.parent,validation)
        assert not validation.failures,validation.failures
        with patch.object(Runtime,'call',side_effect=AssertionError('snapshot contacted runtime')):
            snapshot=capture_snapshot(store,output/'read-only-snapshot')
    jobs=loads(subprocess.check_output([str(args.runner.resolve()),'--root',str(node),'jobs','list']))
    assert len(jobs)==3
    value={'problem':args.problem,'campaign_status':status['status'],'runtime_attempts':3,
        'report_status':first['status'],'reported_accepted_arms':9,'total_arms':9,'exact_rational_checks':9,
        'report_makes_no_runtime_calls':True,'state_and_events_unchanged_by_collection_and_reporting':True,
        'continued_without_duplicates':True,'artifact_catalog':listing,'report':first,'read_only_snapshot':snapshot}
    (output/'summary.json').write_bytes(canonical(value)+b'\n')
    print(canonical(value).decode())


if __name__=='__main__':main()
