"""Required real-runner campaign tests; missing binaries fail, never skip."""
import copy
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from experiment_craft.campaign import initialize, drive, collect, request_stop, summary
from experiment_craft.manifest import compile_manifest
from experiment_craft.report import report
from experiment_craft.runtime import Runtime
from experiment_craft.storage import Error, Store, read_json
from test_campaign import command, campaign
BINS=Path(os.environ['EXPERIMENT_CRAFT_TEST_BIN_DIR']).resolve()
RUN=BINS/'optimization-run'


class Campaigns(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.node=self.base/'node';self.workspace=self.base/'campaign';self.manifest=self.base/'campaign.json'
        self.runtime('node','init','--capacity','1','--allow-commands')
    def tearDown(self):
        try:
            for row in self.runtime('jobs','list'):
                if row.get('state') not in ['completed','cancelled','failed','timed_out','interrupted']:
                    self.runtime('jobs','cancel',row['id'],'--now')
        except Exception:pass
        self.tmp.cleanup()
    def runtime(self,*argv):
        p=subprocess.run([str(RUN),'--root',str(self.node),*map(str,argv)],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)
    def init(self,value):
        self.manifest.write_text(json.dumps(value));return initialize(self.manifest,self.workspace,RUN,self.node,'foreground')
    def cli(self,*argv):
        return subprocess.run([sys.executable,'-m','experiment_craft',*map(str,argv)],cwd=PROJECT,capture_output=True,text=True,timeout=30)
    def wait(self,condition,timeout=10):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            result=condition()
            if result:return result
            time.sleep(.03)
        self.fail('condition timed out')
    def marker(self,path,delay=0):
        return command([sys.executable,'-c',f"from pathlib import Path; import time; time.sleep({delay}); p=Path({str(path)!r}); p.write_text(p.read_text()+'x' if p.exists() else 'x')"])
    def execute(self,once=False):
        with closing(Store(self.workspace)) as store:return drive(store,once=once)
    def test_real_command_sweep_stable_keys_and_no_repeat(self):
        marker=self.base/'marker';value=campaign([{'id':'sweep','job':self.marker(marker),'matrix':{'/limits/grace_seconds':[.1,.2]}}])
        self.init(value);self.assertEqual(self.execute()['status'],'completed');self.assertEqual(marker.read_text(),'xx')
        self.assertEqual(self.execute()['status'],'completed');self.assertEqual(marker.read_text(),'xx')
        self.assertEqual(len(self.runtime('jobs','list')),2)
    def test_two_workspaces_of_one_manifest_never_share_native_jobs(self):
        marker=self.base/'marker';self.manifest.write_text(json.dumps(campaign([{'id':'a','job':self.marker(marker)}])))
        first=initialize(self.manifest,self.base/'w1',RUN,self.node,'foreground')
        second=initialize(self.manifest,self.base/'w2',RUN,self.node,'foreground')
        self.assertNotEqual(first['campaign_id'],second['campaign_id'])
        with closing(Store(self.base/'w1')) as one, closing(Store(self.base/'w2')) as two:
            self.assertNotEqual(one.read()['steps']['a']['request_key'],two.read()['steps']['a']['request_key'])
            self.assertEqual(drive(one)['status'],'completed');self.assertEqual(drive(two)['status'],'completed')
        # Each workspace is its own run: neither adopted the other's job.
        self.assertEqual(marker.read_text(),'xx');self.assertEqual(len(self.runtime('jobs','list')),2)
    def test_snapshot_continue_after_original_inputs_removed(self):
        source=self.base/'input';source.write_bytes(b'\x00\xffhello')
        job=command([sys.executable,'-c',"from pathlib import Path; Path('out').write_bytes(Path('in').read_bytes())"])
        job['inputs']=[{'path':'in','file':'input'}];job['outputs']=[{'name':'out','path':'out','required':True,'max_bytes':100}]
        self.init(campaign([{'id':'copy','job':job}]));source.unlink();self.manifest.unlink()
        self.assertEqual(self.execute()['status'],'completed')
        with closing(Store(self.workspace)) as store:self.assertEqual(store.read()['steps']['copy']['status'],'succeeded')
    def test_failed_prerequisite_blocks_transitive_dependents(self):
        self.init(campaign([{'id':'a','job':command(['/bin/false'])},{'id':'b','job':command(),'needs':['a']},{'id':'c','job':command(),'needs':['b']}]))
        result=self.execute();self.assertEqual(result['steps'],{'a':'failed','b':'blocked','c':'blocked'});self.assertEqual(result['jobs_reserved'],1)
    def test_job_and_declared_slot_budgets_do_not_launch_excess(self):
        for budget in [{'max_jobs':0},{'max_reserved_slot_seconds':0}]:
            with self.subTest(budget=budget):
                self.workspace=self.base/('w-'+next(iter(budget)));value=campaign();value['budget'].update(budget);self.init(value)
                result=self.execute();self.assertEqual(result['steps']['a'],'budget_exhausted');self.assertEqual(result['jobs_reserved'],0)
        self.assertEqual(self.runtime('jobs','list'),[])
    def test_issued_intent_without_observed_job_never_relaunches(self):
        marker=self.base/'never';self.init(campaign([{'id':'a','job':self.marker(marker)}]))
        with closing(Store(self.workspace)) as store:
            with store.edit({'event':'injected_crash_before_rpc'}) as state:
                state['steps']['a'].update(status='dispatching',issued=True);state['jobs_reserved']=1;state['slot_seconds_reserved']=3.1
        self.assertEqual(self.execute()['status'],'unknown');self.assertEqual(self.execute()['status'],'unknown')
        self.assertFalse(marker.exists());self.assertEqual(self.runtime('jobs','list'),[])
    def test_spawn_failure_is_definitely_unsent_and_can_continue(self):
        self.init(campaign())
        with closing(Store(self.workspace)) as store, patch.object(Runtime,'foreground',side_effect=Error('runtime_not_started','injected spawn failure')):
            with self.assertRaises(Error):drive(store)
            state=store.read();self.assertEqual(state['steps']['a']['status'],'pending');self.assertEqual(state['jobs_reserved'],0)
        self.assertEqual(self.execute()['status'],'completed')
    def test_killed_campaign_continues_the_same_real_execution(self):
        marker=self.base/'once';self.init(campaign([{'id':'a','job':self.marker(marker,1.5)}]))
        out=(self.base/'client.out').open('w');err=(self.base/'client.err').open('w')
        process=subprocess.Popen([sys.executable,'-m','experiment_craft','continue','--workspace',str(self.workspace)],cwd=PROJECT,stdout=out,stderr=err)
        try:
            self.wait(lambda:any(j.get('state')=='running' for j in self.runtime('jobs','list')))
            os.kill(process.pid,signal.SIGKILL);process.wait(timeout=5)
            with closing(Store(self.workspace)) as store:
                saved=store.read()['steps']['a']['job_id'];result=drive(store)
            self.assertEqual(result['status'],'completed');self.assertEqual(marker.read_text(),'x')
            self.assertEqual([j['id'] for j in self.runtime('jobs','list')],[saved])
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=5)
            out.close();err.close()
    def test_concurrent_stop_reaches_runtime_and_prevents_dependents(self):
        marker=self.base/'never';self.init(campaign([{'id':'a','job':self.marker(marker,10)},{'id':'b','job':command(),'needs':['a']}]))
        out=(self.base/'client.out').open('w');err=(self.base/'client.err').open('w')
        process=subprocess.Popen([sys.executable,'-m','experiment_craft','continue','--workspace',str(self.workspace)],cwd=PROJECT,stdout=out,stderr=err)
        try:
            self.wait(lambda:any(j.get('state')=='running' for j in self.runtime('jobs','list')))
            p=self.cli('stop','--workspace',self.workspace);self.assertEqual(p.returncode,0,p.stderr)
            process.wait(timeout=10)
            with closing(Store(self.workspace)) as store:result=summary(store.read())
            self.assertEqual(result['steps']['b'],'stopped');self.assertFalse(marker.exists());self.assertEqual(len(self.runtime('jobs','list')),1)
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=5)
            out.close();err.close()
    def test_deadline_includes_queued_waiting(self):
        blocker=self.base/'blocker.json';job=command([sys.executable,'-c','import time; time.sleep(2)']);job['request_key']='blocker';blocker.write_text(json.dumps(job))
        with (self.base/'blocker.out').open('w') as out:
            process=subprocess.Popen([str(RUN),'--root',str(self.node),'run','--spec',str(blocker)],stdout=out,stderr=out)
            try:
                self.wait(lambda:any(j.get('state')=='running' for j in self.runtime('jobs','list')))
                marker=self.base/'not-started';value=campaign([{'id':'a','job':self.marker(marker)}]);value['budget']['max_wall_seconds']=.4
                self.init(value);result=self.execute();self.assertEqual(result['stop_reason'],'deadline_exceeded');self.assertFalse(marker.exists())
            finally:process.wait(timeout=10)
    def test_binary_output_binding_native_binding_and_offline_report(self):
        producer=command([sys.executable,'-c',"from pathlib import Path; Path('data').write_bytes(b'\\x00\\xff')"])
        producer['outputs']=[{'name':'data','path':'data','required':True,'max_bytes':100}]
        consumer=command([sys.executable,'-c',"from pathlib import Path; assert Path('input').read_bytes()==b'\\x00\\xff'"])
        consumer['inputs']=[{'path':'input','from':{'step':'prepare','kind':'output','output':'data'}}]
        checker=command([sys.executable,'-c',"import json; assert json.load(open('native'))['state']=='completed'"])
        checker['inputs']=[{'path':'native','from':{'step':'consume','kind':'native'}}]
        self.init(campaign([{'id':'prepare','job':producer},{'id':'consume','job':consumer},{'id':'check','job':checker}]))
        self.assertEqual(self.execute()['status'],'completed')
        with closing(Store(self.workspace)) as store, patch.object(Runtime,'call',side_effect=AssertionError('report called runtime')):
            a=report(store,self.base/'report');b=report(store,self.base/'report');self.assertEqual(a,b)
            state=store.read();ref=state['steps']['consume']['native'];(self.workspace/ref['path']).write_bytes(b'bad')
            with self.assertRaises(Error):report(store,self.base/'bad-report')
    def test_changed_manifest_cannot_rebind_workspace(self):
        self.init(campaign());value=campaign();value['steps'][0]['job']['limits']['wall_seconds']=4;self.manifest.write_text(json.dumps(value))
        with self.assertRaises(Error) as ctx:initialize(self.manifest,self.workspace,RUN,self.node,'foreground')
        self.assertEqual(ctx.exception.code,'campaign_conflict')
    def test_systemd_client_delegates_with_simulated_manager(self):
        value=campaign();self.manifest.write_text(json.dumps(value));log=self.base/'units.jsonl'
        env={'PATH':str(PROJECT/'tests/fixtures')+os.pathsep+os.environ['PATH'],'REMOTE_MANAGER_LOG':str(log)}
        with patch.dict(os.environ,env):
            initialize(self.manifest,self.workspace,RUN,self.node,'systemd')
            self.assertIn(self.execute(once=True)['status'],['running','completed'])
            self.assertEqual(self.execute()['status'],'completed')
            self.assertEqual(self.execute()['status'],'completed')
        self.assertEqual(len(log.read_text().splitlines()),1)
    def test_uncertain_systemd_launch_is_not_repeated(self):
        self.manifest.write_text(json.dumps(campaign()));log=self.base/'units.jsonl'
        env={'PATH':str(PROJECT/'tests/fixtures')+os.pathsep+os.environ['PATH'],'REMOTE_MANAGER_LOG':str(log),'REMOTE_FAIL_START':'1'}
        with patch.dict(os.environ,env):
            initialize(self.manifest,self.workspace,RUN,self.node,'systemd')
            self.assertEqual(self.execute()['status'],'unknown')
            self.assertEqual(self.execute()['status'],'unknown')
        self.assertEqual(len(self.runtime('jobs','list')),1);self.assertFalse(log.exists())
    def test_stop_racing_before_actual_cli_start_is_retried(self):
        marker=self.base/'never';self.init(campaign([{'id':'a','job':self.marker(marker,5)}]))
        original=Runtime.foreground
        def racing(runtime,*args):
            with closing(Store(self.workspace)) as other:request_stop(other)
            return original(runtime,*args)
        with patch.object(Runtime,'foreground',racing):result=self.execute()
        self.assertTrue(result['stop_reason']);self.assertFalse(marker.exists())
    def test_empty_mcp_refusal_environment_is_respected(self):
        self.manifest.write_text(json.dumps(campaign()))
        with patch.dict(os.environ,{'OPTIMIZATION_RUN_REFUSE_COMMANDS':''}):
            with self.assertRaises(Error) as ctx:initialize(self.manifest,self.workspace,RUN,self.node,'foreground')
        self.assertEqual(ctx.exception.code,'commands_disabled');self.assertFalse(self.workspace.exists())
    def test_completed_campaign_can_continue_offline_without_deadline_rewrite(self):
        self.init(campaign());result=self.execute()
        with closing(Store(self.workspace)) as store:
            with store.edit({'event':'clock_test'}) as state:state['deadline_at']=0
            with patch.object(Runtime,'__init__',side_effect=AssertionError('completed campaign contacted runtime')):
                again=drive(store)
            self.assertEqual(again['status'],'completed');self.assertIsNone(again['stop_reason'])
    def test_foreground_literal_dollar_root_and_systemd_refusal(self):
        self.node=self.base/'node $ literal';self.runtime('node','init','--capacity','1','--allow-commands')
        self.manifest.write_text(json.dumps(campaign()))
        with self.assertRaises(Error) as ctx:initialize(self.manifest,self.workspace,RUN,self.node,'systemd')
        self.assertEqual(ctx.exception.code,'invalid_runtime_root')
        self.init(campaign());self.assertEqual(self.execute()['status'],'completed')
    def test_conflicting_native_key_is_rejected_without_adopting_its_result(self):
        self.init(campaign())
        with closing(Store(self.workspace)) as store:key=store.read()['steps']['a']['request_key']
        foreign=command(['/bin/echo','foreign']);foreign['request_key']=key
        path=self.base/'foreign.json';path.write_text(json.dumps(foreign));self.runtime('run','--spec',path)
        result=self.execute();self.assertEqual(result['steps']['a'],'failed')
        with closing(Store(self.workspace)) as store:
            entry=store.read()['steps']['a'];self.assertEqual(entry['error']['code'],'request_key_conflict');self.assertNotIn('native',entry)
        self.assertEqual(len(self.runtime('jobs','list')),1)
    def test_lost_reply_cannot_adopt_a_foreign_resolved_request(self):
        from experiment_craft.campaign import materialize,runtime_for
        self.init(campaign())
        with closing(Store(self.workspace)) as store:
            step=store.read()['plan']['steps'][0];path,job,validation=materialize(store,runtime_for(store.read()),step)
            with store.edit({'event':'injected_lost_reply'}) as state:
                state['steps']['a'].update(status='dispatching',issued=True,submitted_job=job,
                    expected_resolved=validation['resolved'],expected_identity=validation['identity'])
            foreign=command(['/bin/echo','foreign']);foreign['request_key']=job['request_key']
            path=self.base/'foreign.json';path.write_text(json.dumps(foreign));self.runtime('run','--spec',path)
            result=drive(store);self.assertEqual(result['steps']['a'],'failed')
            self.assertEqual(store.read()['steps']['a']['error']['code'],'execution_mismatch')
            self.assertNotIn('native',store.read()['steps']['a'])
    def test_observation_refuses_a_replaced_node_identity(self):
        from experiment_craft.campaign import runtime_for
        self.init(campaign())
        with closing(Store(self.workspace)) as store:runtime=runtime_for(store.read())
        node=read_json(self.node/'node.json');node['node_id']='0'*64;(self.node/'node.json').write_text(json.dumps(node))
        with self.assertRaises(Error) as ctx:runtime.get('0'*32)
        self.assertEqual(ctx.exception.code,'node_identity_mismatch')
    def test_missing_validation_evidence_does_not_adopt_an_existing_job(self):
        self.init(campaign())
        with closing(Store(self.workspace)) as store:
            key=store.read()['steps']['a']['request_key']
            with store.edit({'event':'incomplete_intent'}) as state:state['steps']['a'].update(status='dispatching',issued=True)
            job=command();job['request_key']=key;path=self.base/'existing.json';path.write_text(json.dumps(job));self.runtime('run','--spec',path)
            self.assertEqual(drive(store)['status'],'unknown');self.assertNotIn('native',store.read()['steps']['a'])
    def test_failed_cli_run_has_nonzero_status(self):
        self.init(campaign([{'id':'a','job':command(['/bin/false'])}]))
        p=self.cli('continue','--workspace',self.workspace);self.assertEqual(p.returncode,1,p.stderr)
        self.assertEqual(json.loads(p.stdout)['steps']['a'],'failed')
    def test_all_three_real_workers_preserve_native_claims(self):
        steps=[]
        for worker in ['fcmaes','lp-ip','sqp']:
            binary=BINS/{'fcmaes':'fcmaes-job-worker','lp-ip':'lp-ip-job-worker','sqp':'sqp-job-worker'}[worker]
            self.assertTrue(binary.is_file(),str(binary));self.runtime('workers','add','--id',worker,'--executable',binary)
            source=PROJECT/'examples/smoke'/worker;job=read_json(source/'job.json');job.pop('request_key')
            if worker=='lp-ip':
                (self.base/'model.json').write_bytes((source/'model.json').read_bytes())
            steps.append({'id':worker,'job':job,'accept':{'require_feasible':True,'claims':[{'fcmaes':'best_found','lp-ip':'numerical_optimum','sqp':'first_order'}[worker]]}})
        value=campaign(steps);value['budget'].update(max_reserved_slot_seconds=1000,max_wall_seconds=120)
        self.init(value);self.assertEqual(self.execute()['status'],'completed')
        with closing(Store(self.workspace)) as store:
            result=report(store,self.base/'report');data=read_json(self.base/'report/report.json');self.assertEqual(result['counts'],{'succeeded':3})
            import jsonschema
            for name,value in [('campaign-plan-0.1',store.read()['plan']),('campaign-status-0.1',summary(store.read())),('campaign-report-0.1',data)]:
                schema=read_json(PROJECT/'experiment_craft/schemas'/(name+'.schema.json'))
                jsonschema.Draft202012Validator(schema).validate(value)

            for step in data['steps']:
                self.assertTrue(step['native']['runner']['accounting_complete']);self.assertEqual(step['native']['schema_version'],'optimization.result/0.2')


if __name__=='__main__':unittest.main(verbosity=2)
