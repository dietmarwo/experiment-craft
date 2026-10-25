"""Pure compiler and transactional campaign-state regressions."""
import copy
from contextlib import closing
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from experiment_craft.manifest import compile_manifest, scientific
from experiment_craft.storage import Error, Store, identity, loads, publish_directory
from experiment_craft.campaign import initialize, request_stop, summary
from experiment_craft.report import diff


def command(argv=None):
    return {'schema_version':'execution.command/0.1','argv':argv or ['/bin/true'],
            'env':{},'resources':{'cpu_slots':1},'limits':{'wall_seconds':3,'grace_seconds':.1},
            'replay':'never','inputs':[],'outputs':[]}


def optimization(payload):
    return {'schema_version':'optimization.job/0.1','worker':'w','payload_schema':'w.solve/1','payload':payload,
            'resources':{'cpu_slots':1,'outer_workers':1,'inner_threads':1},
            'limits':{'wall_time_seconds':5,'grace_seconds':1},'inputs':[]}


def campaign(steps=None):
    return {'schema_version':'experiment.campaign/0.1','name':'unit','allow_commands':True,
            'budget':{'max_jobs':10,'max_wall_seconds':30,'max_reserved_slot_seconds':100},
            'steps':steps or [{'id':'a','job':command()}]}


class Compiler(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.path=self.base/'campaign.json'
    def tearDown(self):self.tmp.cleanup()
    def compile(self,value):
        self.path.write_text(json.dumps(value));return compile_manifest(self.path)
    def rejected(self,value,code):
        with self.assertRaises(Error) as ctx:self.compile(value)
        self.assertEqual(ctx.exception.code,code)
    def test_dry_expansion_is_deterministic_and_does_not_create_state(self):
        value=campaign();value['steps'][0]['matrix']={'/limits/grace_seconds':[.1,.2],'/resources/cpu_slots':[1,2]}
        a=self.compile(value);value['steps'][0]['matrix']=dict(reversed(list(value['steps'][0]['matrix'].items())))
        b=self.compile(value);self.assertEqual(scientific(a),scientific(b));self.assertEqual(len(a['steps']),4)
        self.assertEqual(sorted(p.name for p in self.base.iterdir()),['campaign.json'])
    def test_source_location_is_not_scientific_identity(self):
        value=campaign();(self.base/'data').write_bytes(b'\x00\xff')
        value['steps'][0]['job']['inputs']=[{'path':'data','file':'data'}]
        a=self.compile(value);other=self.base/'moved';other.mkdir();(other/'data').write_bytes(b'\x00\xff');(other/'campaign.json').write_text(json.dumps(value))
        self.assertEqual(scientific(a),scientific(compile_manifest(other/'campaign.json')))
    def test_input_change_changes_identity_and_declared_mismatch_fails(self):
        value=campaign();(self.base/'data').write_text('a');value['steps'][0]['job']['inputs']=[{'path':'x','file':'data'}]
        a=self.compile(value);(self.base/'data').write_text('b');b=self.compile(value);self.assertNotEqual(a['plan_id'],b['plan_id'])
        value['steps'][0]['job']['inputs'][0]['sha256']='0'*64;self.rejected(value,'input_changed')
    def test_dependencies_join_all_matrix_variants(self):
        value=campaign([{'id':'a','job':command(),'matrix':{'/resources/cpu_slots':[1,2]}},{'id':'b','job':command(),'needs':['a']}])
        result=self.compile(value);self.assertEqual(result['steps'][-1]['id'],'b');self.assertEqual(len(result['steps'][-1]['needs']),2)
    def test_dependency_cycle_unknown_and_self_rejected(self):
        self.rejected(campaign([{'id':'a','job':command(),'needs':['b']},{'id':'b','job':command(),'needs':['a']}]),'dependency_cycle')
        self.rejected(campaign([{'id':'a','job':command(),'needs':['missing']}]),'invalid_dependency')
        self.rejected(campaign([{'id':'a','job':command(),'needs':['a']}]),'invalid_dependency')
    def test_duplicate_steps_and_unknown_fields_rejected(self):
        self.rejected(campaign([{'id':'a','job':command()},{'id':'a','job':command()}]),'invalid_campaign')
        value=campaign();value['placement']='auto';self.rejected(value,'invalid_campaign')
    def test_unsupported_job_and_command_optin(self):
        value=campaign();value['steps'][0]['job']['schema_version']='shell/1';self.rejected(value,'unsupported_job_kind')
        value=campaign();value.pop('allow_commands');self.rejected(value,'commands_disabled')
    def test_command_cannot_claim_feasibility_or_optimization_success(self):
        value=campaign();value['steps'][0]['accept']={'require_feasible':True};self.rejected(value,'invalid_campaign')
    def test_fifo_input_is_rejected_without_waiting_for_a_writer(self):
        os.mkfifo(self.base/'fifo');value=campaign();value['steps'][0]['job']['inputs']=[{'path':'x','file':'fifo'}]
        self.rejected(value,'invalid_input')
    def test_generated_keys_cannot_be_overridden(self):
        value=campaign();value['steps'][0]['job']['request_key']='user';self.rejected(value,'invalid_campaign')
    def test_matrix_can_only_change_existing_scientific_fields(self):
        for ptr in ['/argv/0','/request_key','/resources/new','/payload/~2x']:
            value=campaign();value['steps'][0]['matrix']={ptr:[1]};self.rejected(value,'invalid_matrix')
    def test_expansion_is_bounded_before_materializing_product(self):
        value=campaign();value['steps'][0]['matrix']={'/limits/wall_seconds':list(range(1,101)),'/limits/grace_seconds':list(range(100))}
        self.rejected(value,'expansion_limit')
    def test_matrix_duplicate_values_rejected(self):
        value=campaign();value['steps'][0]['matrix']={'/resources/cpu_slots':[1,1]};self.rejected(value,'invalid_matrix')
    def test_matrix_values_equal_as_numbers_are_duplicates(self):
        for values in [[5,5.0],[0,-0.0],[[1,2],[1.0,2]]]:
            value=campaign([{'id':'a','job':optimization({'x':0,'v':[0,0]}),'matrix':{'/payload/x' if not isinstance(values[0],list) else '/payload/v':values}}])
            self.rejected(value,'invalid_matrix')
        value=campaign([{'id':'a','job':optimization({'x':0}),'matrix':{'/payload/x':[1,True]}}])
        self.assertEqual(len(self.compile(value)['steps']),2)
    def test_matrix_pointer_spellings_cannot_alias_one_element(self):
        for pointers in [['/payload/v/0','/payload/v/00'],['/payload/v/+0'],['/payload/v/-0'],['/payload/v/ 0']]:
            value=campaign([{'id':'a','job':optimization({'v':[0,0]}),'matrix':{p:[1,2] for p in pointers}}])
            self.rejected(value,'invalid_matrix')
        value=campaign([{'id':'a','job':optimization({'v':[0,0]}),'matrix':{'/payload/v':[[1,1],[2,2]],'/payload/v/0':[3,4]}}])
        self.rejected(value,'invalid_matrix')
        value=campaign([{'id':'a','job':optimization({'v':[0,0],'vv':0}),'matrix':{'/payload/v/0':[1,2],'/payload/vv':[3,4]}}])
        self.assertEqual(len(self.compile(value)['steps']),4)
    def test_integer_representation_is_strict(self):
        value=campaign();value['budget']['max_jobs']=1.0;self.rejected(value,'invalid_campaign')
        value=campaign();value['steps'][0]['job']['resources']['cpu_slots']=True;self.rejected(value,'invalid_campaign')
    def test_source_path_traversal_symlinks_and_dot_segments_rejected(self):
        (self.base/'data').write_text('x');(self.base/'link').symlink_to(self.base/'data')
        for name in ['../data','/tmp/data','link','.secret']:
            value=campaign();value['steps'][0]['job']['inputs']=[{'path':'x','file':name}];self.rejected(value,'invalid_input')
    def test_strict_json_rejects_duplicate_keys_nan_and_overflow(self):
        for text in ['{"x":1,"x":2}','{"x":NaN}','{"x":1e309}']:
            with self.assertRaises(Error):loads(text)
    def test_derived_input_requires_unambiguous_declared_producer(self):
        prepare=command();prepare['outputs']=[{'name':'data','path':'data','required':True,'max_bytes':100}]
        consume=command();consume['inputs']=[{'path':'data','from':{'step':'a','kind':'output','output':'data'}}]
        value=campaign([{'id':'a','job':prepare},{'id':'b','job':consume}]);result=self.compile(value);self.assertEqual(result['steps'][1]['needs'],['a'])
        value['steps'][0]['matrix']={'/resources/cpu_slots':[1,2]};self.rejected(value,'ambiguous_input')
    def test_binding_requires_a_required_output(self):
        prepare=command();prepare['outputs']=[{'name':'data','path':'data','required':False,'max_bytes':100}]
        consume=command();consume['inputs']=[{'path':'data','from':{'step':'a','kind':'output','output':'data'}}]
        self.rejected(campaign([{'id':'a','job':prepare},{'id':'b','job':consume}]),'invalid_input')
    def test_diff_keeps_absence_distinct_from_null_and_recurses_arrays(self):
        change=diff({'x':None},{})[0];self.assertTrue(change['before_present']);self.assertFalse(change['after_present'])
        self.assertEqual(diff([{'x':1}],[{'x':2}])[0]['pointer'],'/0/x')
    def test_provenance_diff_distinguishes_json_types(self):
        changes=diff({'flag':True,'seed':1,'x':[0]},{'flag':1,'seed':1.0,'x':[False]})
        self.assertEqual([c['pointer'] for c in changes],['/flag','/seed','/x/0'])
    def test_declared_slot_seconds_are_exact_decimals(self):
        value=campaign();value['steps'][0]['job']['limits'].update(wall_seconds=.1,grace_seconds=.2)
        self.assertEqual(self.compile(value)['steps'][0]['reserved_slot_seconds'],.3)
        value['steps'][0]['job']['limits'].update(wall_seconds=5,grace_seconds=1);value['steps'][0]['job']['resources']['cpu_slots']=2
        self.assertEqual(self.compile(value)['steps'][0]['reserved_slot_seconds'],12)
    def test_provenance_diff_is_read_only(self):
        self.assertEqual(diff({'x':1},{'x':2}),[{'pointer':'/x','before':1,'after':2}])


class RuntimeErrors(unittest.TestCase):
    def test_malformed_native_errors_keep_the_error_contract(self):
        from experiment_craft.runtime import Runtime
        for stderr in [b'{"error":"x"}',b'{"error":{"code":5}}',b'{"error":null}',b'[]',b'not json']:
            with self.subTest(stderr=stderr), self.assertRaises(Error) as ctx:Runtime.decode(2,b'',stderr)
            self.assertEqual(ctx.exception.code,'runtime_error')
        with self.assertRaises(Error) as ctx:Runtime.decode(2,b'',b'{"error":{"code":"unknown_job","message":7}}')
        self.assertEqual((ctx.exception.code,str(ctx.exception)),('unknown_job','7'))


class Persistence(unittest.TestCase):
    def test_transaction_commits_decision_and_event_together_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as root, closing(Store(root,create=True)) as store:
            with store.edit({'event':'first'}) as value:value.update(schema_version='experiment.campaign.state/0.1',x=1)
            with self.assertRaises(RuntimeError):
                with store.edit({'event':'bad'}) as value:value['x']=2;raise RuntimeError('interrupt')
            self.assertEqual(store.read()['x'],1);self.assertEqual(len(store.events()),1)
    def test_only_one_advancer_but_stop_can_access_database(self):
        with tempfile.TemporaryDirectory() as root, closing(Store(root,create=True)) as a:
            with a.edit({'event':'init'}) as value:value.update(schema_version='experiment.campaign.state/0.1',steps={},stop_requested=False,stop_reason=None,campaign_id='x',jobs_reserved=0,slot_seconds_reserved=0,deadline_at=1)
            with closing(Store(root)) as b, a.advance_lock():
                with self.assertRaises(Error):
                    with b.advance_lock():pass
                self.assertEqual(request_stop(b)['stop_reason'],'requested')
    def test_a_later_stop_keeps_the_first_reason(self):
        with tempfile.TemporaryDirectory() as root, closing(Store(root,create=True)) as store:
            with store.edit({'event':'init'}) as value:value.update(schema_version='experiment.campaign.state/0.1',steps={'a':{'status':'pending'}},stop_requested=False,stop_reason=None,campaign_id='x',jobs_reserved=0,slot_seconds_reserved=0,deadline_at=1)
            self.assertEqual(request_stop(store,'deadline_exceeded')['stop_reason'],'deadline_exceeded')
            self.assertEqual(request_stop(store)['stop_reason'],'deadline_exceeded')
            self.assertEqual(store.read()['steps']['a']['status'],'stopped')
            self.assertEqual([e['event'] for e in store.events()],['init','stop_requested'])
    def test_directory_publication_never_clobbers_existing_directory(self):
        with tempfile.TemporaryDirectory() as root:
            a,b=Path(root)/'a',Path(root)/'b';a.mkdir();b.mkdir();(b/'keep').write_text('safe')
            with self.assertRaises(FileExistsError):publish_directory(a,b)
            self.assertEqual((b/'keep').read_text(),'safe')


if __name__=='__main__':unittest.main()
