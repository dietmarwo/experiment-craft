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
from experiment_craft.storage import Error,Store,read_json,write_json


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
    # The campaign answer and a declared look-ahead: 4 optimization evaluations, then 2
    # fresh replicates at the empirical choice.
    answered={**plan,'proposal_lookahead':1,'answer':{'validation_replicates':2}}
    write_json(base/'answered.json',answered)
    adaptive.initialize(base/'answered.json',base/'answered',a.runner,base/'node')
    with closing(Store(base/'answered')) as store:
        result=adaptive.advance(store)
        assert result['status']=='completed' and result['answer']=='done',result
        state=store.read()
        assert len(state['observations'])==4 and len(state['validation_observations'])==2
        answer=read_json(base/'answered'/'answer.json')
        best=min(state['observations'],key=lambda o:o['values']['score'])
        assert answer['empirical']['observations'][0]['id']==best['id']
        assert answer['validation']['x']==best['x'] and answer['validation']['completed']==2
        assert {o['x']==best['x'] for o in state['validation_observations']}=={True}
        assert len({o['seed'] for o in state['validation_observations']})==2
        assert answer['validation']['standard_error']>=0
        proposals=[j for j in state['jobs'].values() if j['kind']=='proposal']
        assert all(j['request']['q']<=answered['concurrent']+1 for j in proposals)
        before=store.events()
        assert adaptive.advance(store)==result and store.events()==before
    model_answer=None
    if subprocess.run([str(a.python),'-c','import botorch'],capture_output=True).returncode==0:
        # A BoTorch campaign answers with a model recommendation job as well.
        modelled={**plan,'config':{'backend':'botorch','initial_points':3,'num_restarts':2,'raw_samples':32,
                                   'mc_samples':32,'fit_maxiter':20,'acq_maxiter':20},
                  'budget':{**plan['budget'],'wall_seconds':600,'slot_seconds':2000},'proposal_wall_seconds':120}
        write_json(base/'modelled.json',modelled)
        adaptive.initialize(base/'modelled.json',base/'modelled',a.runner,base/'node')
        with closing(Store(base/'modelled')) as store:
            result=adaptive.advance(store)
            assert result['status']=='completed',result
            answer=read_json(base/'modelled'/'answer.json')
            assert answer['model']['kind']=='model' and answer['model']['points'],answer['model']
            model_answer=answer['model']['points'][0]['x']
    # Pruning: the evaluator reports a learning curve; the median rule stops poor trials.
    evaluator=base/'curve_evaluator.py'
    evaluator.write_text("""import json, time
from pathlib import Path
trial = json.loads(Path('trial.json').read_text())
f = sum((v - 0.2) ** 2 for v in trial['x'].values())
with open('progress.jsonl', 'a') as out:
    for step in range(1, 9):
        time.sleep(0.15)
        out.write(json.dumps({'step': step, 'value': f + 1.0 / step}) + '\\n')
        out.flush()
Path('observation.json').write_text(json.dumps({**trial, 'status': 'completed', 'values': {'score': f + 1.0 / 8}}))
""")
    pruning={**plan,'pruning':{'policy':'median','startup_trials':2,'warmup_steps':1,'check_seconds':0.05},
             'evaluator':{**plan['evaluator'],'inputs':[{'file':str(evaluator),'path':'evaluator.py'}]},
             'budget':{**plan['budget'],'evaluations':10,'jobs':40,'slot_seconds':2000}}
    write_json(base/'pruning.json',pruning)
    try:
        adaptive.initialize(base/'pruning.json',base/'pruning',a.runner,base/'node')
    except Error as exc:
        assert exc.code=='unsupported_runtime',exc
        pruned='skipped: runner without command progress'
    else:
        with closing(Store(base/'pruning')) as store:
            result=adaptive.advance(store)
            assert result['status']=='completed',result
            state=store.read()
            runtime=Runtime(a.runner,base/'node',state['runtime'])
            observations=state['observations']
            pruned_obs=[o for o in observations if o['status']=='pruned']
            assert pruned_obs,'the median rule pruned no trial'
            for o in pruned_obs:
                assert 'values' not in o and o['intermediate'] and o['provenance']['pruned_at_step']<8
                job=state['jobs'][o['trial_id']]
                assert runtime.call('jobs','execution',job['job_id'])['state']=='cancelled'
            done=[o for o in observations if o['status']=='completed']
            assert all(len(o['intermediate'])==8 for o in done)
            events=[e['event'] for e in store.events()]
            assert events.count('adaptive_prune')==len(pruned_obs)
            pruned=len(pruned_obs)
    summary={'passed':True,'evaluations':6,'lost_response_reconciled':True,'no_duplicate_continuation':True,
             'paused_backup_restore':True,'unlaunched_intent_retains_uncertainty':True,'backup':saved,
             'answer_with_validation_replicates':True,'model_answer':model_answer if model_answer else 'skipped: no BoTorch',
             'pruned_trials':pruned}
    write_json(base/'summary.json',summary);print(summary)


if __name__=='__main__':main()
