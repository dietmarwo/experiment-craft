#!/usr/bin/env python3
"""Seven real jobs: prepare, seeded sweep, LP/IP, SQP, and numerical checks."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(PROJECT))
from experiment_craft.campaign import initialize, drive
from experiment_craft.manifest import compile_manifest
from experiment_craft.report import report
from experiment_craft.storage import Store, read_json, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    source=output/'source';source.mkdir();node=output/'node';runner=args.bin_dir.resolve()/'optimization-run'
    def cli(*argv):
        p=subprocess.run([str(runner),'--root',str(node),*map(str,argv)],capture_output=True,text=True,timeout=30)
        if p.returncode:raise RuntimeError(p.stderr)
        return json.loads(p.stdout)
    cli('node','init','--capacity','1','--allow-commands')
    for worker,binary in [('fcmaes','fcmaes-job-worker'),('lp-ip','lp-ip-job-worker'),('sqp','sqp-job-worker')]:
        cli('workers','add','--id',worker,'--executable',args.bin_dir.resolve()/binary)
    for name in ['prepare.py','check.py']:shutil.copy2(Path(__file__).parent/name,source/name)
    shutil.copy2(PROJECT/'examples/smoke/lp-ip/model.json',source/'model.json')
    def command(script,inputs,outputs):
        return {'schema_version':'execution.command/0.1','argv':[sys.executable,script],'env':{},
                'resources':{'cpu_slots':1},'limits':{'wall_seconds':10,'grace_seconds':1},
                'replay':'never','inputs':inputs,'outputs':outputs}
    prepare=command('prepare.py',[{'path':'prepare.py','file':'prepare.py'},{'path':'model.json','file':'model.json'}],
                    [{'name':'model','path':'prepared-model.json','required':True,'max_bytes':10000}])
    steps=[{'id':'prepare','job':prepare}]
    for worker in ['fcmaes','lp-ip','sqp']:
        job=read_json(PROJECT/'examples/smoke'/worker/'job.json');job.pop('request_key')
        if worker=='lp-ip':job['inputs']=[{'name':'model','from':{'step':'prepare','kind':'output','output':'model'}}]
        step={'id':worker,'needs':['prepare'],'job':job,'accept':{'require_feasible':True,
            'claims':[{'fcmaes':'best_found','lp-ip':'numerical_optimum','sqp':'first_order'}[worker]]}}
        if worker=='fcmaes':step['matrix']={'/payload/seed':[1,2,3]}
        steps.append(step)
    checker=command('check.py',[{'path':'check.py','file':'check.py'},
                   {'path':'lp.json','from':{'step':'lp-ip','kind':'native'}},
                   {'path':'sqp.json','from':{'step':'sqp','kind':'native'}}],
                   [{'name':'checks','path':'checks.json','required':True,'max_bytes':10000}])
    steps.append({'id':'check','needs':['fcmaes','lp-ip','sqp'],'job':checker})
    manifest={'schema_version':'experiment.campaign/0.1','name':'Prepare sweep and check','allow_commands':True,
              'budget':{'max_jobs':7,'max_wall_seconds':120,'max_reserved_slot_seconds':200},'steps':steps}
    path=source/'campaign.json';write_json(path,manifest)
    a,b=compile_manifest(path),compile_manifest(path);assert a['plan_id']==b['plan_id']
    initialize(path,output/'campaign',runner,node,'foreground')
    with closing(Store(output/'campaign')) as store:
        outcome=drive(store);assert outcome['status']=='completed',outcome
        first=report(store,output/'report');jobs=cli('jobs','list');assert len(jobs)==7
        journal_sizes={p:p.stat().st_size for p in node.glob('jobs/*/events.jsonl')}
        assert drive(store)==outcome
        assert report(store,output/'report')==first
        assert {p:p.stat().st_size for p in journal_sizes}==journal_sizes
        summary={'status':'passed','mode':'real local foreground','jobs':7,'repeat_did_not_execute':True,
                 'report':first,'campaign':outcome}
    write_json(output/'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
