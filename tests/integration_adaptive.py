"""Real runtime acceptance: concurrency, lost launch answer, no duplicate continuation, backup.

Usage: python tests/integration_adaptive.py --runner ABS --python ABS --bo-root ABS --output NEW
Missing binaries fail; this test never substitutes a simulated execution backend.
"""
import argparse
from contextlib import closing
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiment_craft import adaptive
from experiment_craft.operations import backup,pause,restore,unpause
from experiment_craft.runtime import Runtime
from experiment_craft.storage import Error,Store,write_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--runner',type=Path,required=True);p.add_argument('--python',type=Path,required=True)
    p.add_argument('--bo-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    base=a.output.resolve();base.mkdir(parents=True,exist_ok=False)
    subprocess.run([str(a.runner),'--root',str(base/'node'),'node','init','--capacity','4','--allow-commands'],check=True)
    plan={'schema_version':'experiment.adaptive/0.1','problem':{'schema_version':'bo.problem/0.1',
        'parameters':[{'name':'x','type':'continuous','lower':-2.,'upper':2.}],
        'objectives':[{'name':'score','direction':'minimize'}]},'config':{'backend':'random'},'seed':7,
        'concurrent':2,'python':str(a.python),'proposal_slots':1,'proposal_wall_seconds':30,
        'evaluator':{'kind':'command','argv':[str(a.python),'evaluator.py'],'slots':1,'wall_seconds':10,
                    'inputs':[{'file':str(a.bo_root/'examples/noisy_evaluator.py'),'path':'evaluator.py'}]},
        'budget':{'evaluations':6,'jobs':20,'wall_seconds':180,'slot_seconds':500}}
    write_json(base/'manifest.json',plan)
    adaptive.initialize(base/'manifest.json',base/'campaign',a.runner,base/'node')
    with closing(Store(base/'campaign')) as store:
        # Lose the response after the real runtime process was started.
        original=Runtime.foreground;lost=[False];launched=[]
        def lost_ack(self,*args):
            proc=original(self,*args);launched.append(proc)
            if not lost[0]:
                lost[0]=True
                raise Error('runtime_timeout','injected lost response after process creation')
            return proc
        Runtime.foreground=lost_ack
        try:
            try:adaptive.advance(store)
            except Error as exc:assert exc.code=='submission_unknown',exc
            else:raise AssertionError('lost response was not exercised')
        finally:Runtime.foreground=original
        issued=store.read()['jobs_reserved']
        time.sleep(.1)
        result=adaptive.advance(store)
        assert result['status']=='completed',result
        for proc in launched:proc.wait(timeout=10)
        state=store.read()
        assert len(state['observations'])==6
        assert len({x['id'] for x in state['observations']})==6
        assert state['jobs_reserved']>=issued
        before=store.events()
        assert adaptive.advance(store)==result
        assert store.events()==before
        pause(store,'backup test')
        saved=backup(store,base/'backup.zip')
    restore(base/'backup.zip',base/'restored')
    with closing(Store(base/'restored')) as store:
        assert store.maintenance()['paused']
        unpause(store)
        restored=adaptive.advance(store)
        assert restored['status']=='completed'
        assert len(store.read()['observations'])==6
    # Intent persisted but no process launch: absence is not permission to resubmit.
    adaptive.initialize(base/'manifest.json',base/'uncertain',a.runner,base/'node')
    with closing(Store(base/'uncertain')) as store:
        runtime=Runtime(a.runner,base/'node',store.read()['runtime'])
        request={'schema_version':'bo.request/0.1','problem':plan['problem'],'config':plan['config'],
                 'seed':7,'q':1,'observations':[],'pending':[]}
        adaptive._intend(store,runtime,'proposal-unlaunched','proposal',None,request)
        value=adaptive.advance(store)
        assert value['status']=='unknown'
        assert store.read()['jobs_reserved']==1
        assert adaptive.advance(store)['jobs_reserved']==1
    summary={'passed':True,'evaluations':6,'lost_response_reconciled':True,'no_duplicate_continuation':True,
             'paused_backup_restore':True,'unlaunched_intent_retains_uncertainty':True,'backup':saved}
    write_json(base/'summary.json',summary);print(summary)


if __name__=='__main__':main()
