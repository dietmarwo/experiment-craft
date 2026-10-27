"""Offline artifact/verification reports; fixtures are recorded observations, not proof runs."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jsonschema

from experiment_craft.artifacts import catalog, output_bytes
from experiment_craft.comparison_report import publish
from experiment_craft.storage import Error, atomic, canonical, identity
from experiment_craft.verification import build, report
from verification_fixture import encode, inputs, sha


class MemoryStore:
    def __init__(self, root, rejected=False, code=None):
        self.root = root
        raw, receipt = inputs(rejected)
        entry = {'job_id': 'a' * 32, 'status': 'failed' if rejected else 'succeeded', 'issued': True,
                 'execution_identity': 'b' * 64, 'observation': {'state': 'failed' if rejected else 'completed'}}
        command_inputs = []
        for index, (path, data) in enumerate(raw.items()):
            target = root / 'requests/accept/inputs' / str(index)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            command_inputs.append({'path': path, 'file': f'inputs/{index}', 'bytes': len(data), 'sha256': sha(data)})
        entry['submitted_job'] = {'schema_version':'execution.command/0.1', 'inputs': copy.deepcopy(command_inputs)}
        entry['expected_resolved'] = copy.deepcopy(entry['submitted_job'])
        data = encode(receipt)
        self.output_path = root / 'results/accept/outputs/acceptance'
        self.output_path.parent.mkdir(parents=True)
        self.output_path.write_bytes(data)
        native = {'schema_version': 'execution.command.result/0.1', 'state': entry['observation']['state'],
                  'process': {'code': (3 if rejected else 0) if code is None else code, 'signal': None},
                  'outputs': {'acceptance': {'bytes': len(data), 'sha256': sha(data), 'path': '.command-outputs/acceptance'}},
                  'output_errors': [], 'collection_attempted': True}
        path = root / 'results/accept/native.json'
        path.write_bytes(encode(native))
        entry['native'] = {'path':'results/accept/native.json', 'bytes':path.stat().st_size, 'sha256':sha(path.read_bytes())}
        plan = {'plan_id': 'c' * 64, 'name': 'report fixture', 'steps': [{'id': 'accept', 'job': {
            'schema_version': 'execution.command/0.1', 'inputs': command_inputs,
            'outputs': [{'name':'acceptance','path':'out/acceptance.json','required':True,'max_bytes':1048576}]}}]}
        self.state = {'campaign_id': 'd' * 64, 'plan': plan, 'steps': {'accept':entry},
            'runtime': {'root': str(root.parent / 'node')}, 'jobs_reserved': 1, 'slot_seconds_reserved': 4,
            'deadline_at': 1e20, 'stop_requested':False, 'stop_reason':None}

    def read(self):
        return copy.deepcopy(self.state)

    def replace_input(self, name, data):
        entry = self.state['steps']['accept']
        for index, item in enumerate(entry['submitted_job']['inputs']):
            if item['path'] == name:
                (self.root / 'requests/accept/inputs' / str(index)).write_bytes(data)
                item.update(bytes=len(data), sha256=sha(data))
                entry['expected_resolved']['inputs'][index].update(bytes=len(data), sha256=sha(data))
                self.state['plan']['steps'][0]['job']['inputs'][index].update(bytes=len(data),sha256=sha(data))
                return
        raise AssertionError(name)

    def replace_receipt(self, value):
        data=encode(value);self.output_path.write_bytes(data)
        entry=self.state['steps']['accept'];path=self.root/entry['native']['path'];native=json.loads(path.read_bytes())
        native['outputs']['acceptance'].update(bytes=len(data),sha256=sha(data))
        data=encode(native);path.write_bytes(data);entry['native'].update(bytes=len(data),sha256=sha(data))


class Verification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.store = MemoryStore(self.base / 'workspace')

    def fails(self, function, code):
        with self.assertRaises(Error) as caught:
            function()
        self.assertEqual(caught.exception.code, code, str(caught.exception))

    def test_accepted_report_preserves_native_and_reported_scope(self):
        with patch('experiment_craft.runtime.Runtime.call', side_effect=AssertionError('offline report called runtime')):
            value = build(self.store, 'accept')
        self.assertEqual(value['status'], 'reported_accepted')
        self.assertTrue(value['execution_consistent'])
        self.assertEqual(value['summary']['reported_accepted_arms'], 6)
        self.assertEqual(len(value['arms']), 6)
        self.assertIn('does not run a checker', value['interpretation'][0])

    def test_rejected_receipt_stays_a_failed_native_command_and_keeps_all_arms(self):
        store = MemoryStore(self.base / 'rejected', rejected=True)
        value = build(store, 'accept')
        self.assertEqual(value['status'], 'reported_rejected')
        self.assertEqual(value['source']['artifact']['native_state'], 'failed')
        self.assertEqual(value['summary'], {'total_arms':6,'reported_accepted_arms':5,'right_censored_arms':1,'audit_complete':True})
        self.assertTrue(value['arms'][0]['observation']['right_censored'])

    def test_failed_execution_does_not_confirm_an_accepted_receipt(self):
        entry = self.store.state['steps']['accept']
        native = json.loads((self.store.root / entry['native']['path']).read_bytes())
        native.update(state='failed', process={'code':7,'signal':None})
        entry['status']='failed';entry['observation']['state']='failed'
        data=encode(native);(self.store.root/entry['native']['path']).write_bytes(data)
        entry['native'].update(bytes=len(data),sha256=sha(data))
        value=build(self.store,'accept')
        self.assertEqual(value['status'],'unconfirmed');self.assertFalse(value['execution_consistent'])
        self.assertEqual(value['reported_outcome'],'accepted')

    def test_uncertain_step_or_missing_execution_identity_does_not_confirm_a_receipt(self):
        self.store.state['steps']['accept']['status']='unknown'
        self.assertEqual(build(self.store,'accept')['status'],'unconfirmed')
        self.store.state['steps']['accept']['status']='succeeded'
        self.store.state['steps']['accept'].pop('execution_identity')
        self.assertEqual(build(self.store,'accept')['status'],'unconfirmed')

    def test_pending_and_missing_outputs_are_unknown_not_zero_successes(self):
        entry=self.store.state['steps']['accept'];entry.pop('native');entry['status']='pending';entry.pop('observation')
        value=build(self.store,'accept')
        self.assertEqual(value['status'],'unavailable');self.assertIsNone(value['summary']);self.assertEqual(value['arms'],[])

    def test_sealed_but_uncollected_output_requires_explicit_collection(self):
        self.store.output_path.unlink()
        self.fails(lambda:build(self.store,'accept'),'artifact_not_collected')
        self.assertEqual(catalog(self.store)['artifacts'][0]['availability'],'sealed')

    def test_catalog_and_output_reads_are_offline_and_detect_corruption(self):
        with patch('experiment_craft.runtime.Runtime.call',side_effect=AssertionError('offline catalog called runtime')):
            first=catalog(self.store);data,info=output_bytes(self.store,self.store.read(),'accept','acceptance')
        self.assertEqual(info['availability'],'retained')
        self.assertEqual(sha(data),info['sha256'])
        self.store.output_path.write_bytes(data+b' ')
        self.fails(lambda:catalog(self.store),'artifact_changed')

    def test_cached_symlink_is_refused(self):
        data=self.store.output_path.read_bytes();self.store.output_path.unlink()
        target=self.base/'external';target.write_bytes(data);self.store.output_path.symlink_to(target)
        self.fails(lambda:build(self.store,'accept'),'artifact_changed')

    def test_changed_input_or_native_manifest_is_refused(self):
        path=self.store.root/'requests/accept/inputs/0';path.write_bytes(path.read_bytes()+b' ')
        self.fails(lambda:build(self.store,'accept'),'input_changed')
        entry=self.store.state['steps']['accept'];path=self.store.root/entry['native']['path'];path.write_bytes(path.read_bytes()+b' ')
        self.fails(lambda:build(self.store,'accept'),'result_changed')

    def test_rehashed_foreign_input_is_not_the_receipt_subject(self):
        self.store.replace_input('problem.json',b'{}\n')
        self.fails(lambda:build(self.store,'accept'),'verification_mismatch')

    def test_changed_checker_source_is_refused(self):
        self.store.replace_input('app/audit.py',b'another checker\n')
        self.fails(lambda:build(self.store,'accept'),'verification_mismatch')

    def test_changed_admitted_metadata_is_refused(self):
        self.store.state['steps']['accept']['expected_resolved']['inputs'][0]['sha256']='0'*64
        self.fails(lambda:build(self.store,'accept'),'artifact_changed')

    def test_unsupported_adapter_and_unknown_steps_fail_with_stable_codes(self):
        self.fails(lambda:build(self.store,'accept',adapter='unknown/1'),'unsupported_verification')
        self.fails(lambda:catalog(self.store,'../accept'),'unknown_step')
        self.fails(lambda:build(self.store,'accept','missing'),'unknown_artifact')

    def test_atomic_publication_idempotence_and_existing_report_preserved_on_bad_source(self):
        destination=self.base/'report'
        before=report(self.store,destination,'accept')
        self.assertEqual(report(self.store,destination,'accept'),before)
        data=(destination/'verification.json').read_bytes()
        self.store.output_path.write_bytes(b'bad')
        self.fails(lambda:report(self.store,destination,'accept'),'artifact_changed')
        self.assertEqual((destination/'verification.json').read_bytes(),data)

    def test_destination_does_not_replace_authoritative_or_foreign_files(self):
        self.fails(lambda:report(self.store,self.store.root/'report','accept'),'invalid_destination')
        # A directory holding only a file name that both report kinds use is not
        # an earlier report of either kind; its file is not replaced.
        for name, publisher in (('verification-only-csv', lambda path: report(self.store, path, 'accept')),
                                ('comparison-only-csv', lambda path: publish(path, {'comparison.json': b'{}'}))):
            path = self.base / name
            path.mkdir()
            (path / 'observations.csv').write_text('kept\n')
            self.fails(lambda: publisher(path), 'invalid_destination')
            self.assertEqual((path / 'observations.csv').read_text(), 'kept\n')
        other=self.base/'foreign';other.mkdir();(other/'keep').write_text('keep')
        self.fails(lambda:report(self.store,other,'accept'),'invalid_destination')
        self.assertEqual((other/'keep').read_text(),'keep')

    def test_new_output_formats_validate(self):
        schemas=Path(__file__).resolve().parents[1]/'experiment_craft/schemas'
        jsonschema.validate(catalog(self.store),json.loads((schemas/'artifacts-0.1.schema.json').read_bytes()))
        jsonschema.validate(build(self.store,'accept'),json.loads((schemas/'verification-report-0.1.schema.json').read_bytes()))

    def test_catalog_pages_are_bounded_and_have_stable_offsets(self):
        value=catalog(self.store,after=0,limit=1)
        self.assertEqual(value['total_outputs'],1);self.assertIsNone(value['next_offset'])
        self.assertEqual(catalog(self.store,after=1,limit=1)['artifacts'],[])
        for after,limit in [(-1,1),(0,0),(0,1001),(True,1)]:
            with self.subTest(after=after,limit=limit):self.fails(lambda:catalog(self.store,after=after,limit=limit),'invalid_command')

    def test_rehashed_receipt_still_has_to_match_arm_order_counts_and_costs(self):
        original=json.loads(self.store.output_path.read_bytes())
        for mutation in [lambda x:x.update(accepted_arms=5),
                         lambda x:x['observations'].reverse(),
                         lambda x:x['observations'][0].update(observed_seconds=0),
                         lambda x:x['observations'][0].update(right_censored=True),
                         lambda x:x['observations'][0].update(reason='inconclusive/rejected')]:
            value=copy.deepcopy(original);mutation(value);self.store.replace_receipt(value)
            with self.subTest(mutation=mutation):self.fails(lambda:build(self.store,'accept'),'verification_mismatch')

    def test_missing_admitted_input_uses_a_stable_error(self):
        (self.store.root/'requests/accept/inputs/0').unlink()
        self.fails(lambda:build(self.store,'accept'),'input_changed')

    def test_admitted_input_cannot_be_rebound_away_from_the_scientific_plan(self):
        entry=self.store.state['steps']['accept']
        for key in ('submitted_job','expected_resolved'):entry[key]['inputs'][0]['sha256']='0'*64
        self.fails(lambda:build(self.store,'accept'),'artifact_changed')

    def test_displayed_stage_budget_cannot_be_changed_or_exceeded(self):
        entry=self.store.state['steps']['accept']
        item=next(x for x in entry['submitted_job']['inputs'] if x['path']=='audit.json')
        original=json.loads((self.store.root/'requests/accept'/item['file']).read_bytes())
        receipt=json.loads(self.store.output_path.read_bytes())
        for field,value,message in [('wall_limit_seconds',60,'differs from the audit protocol'),
                                     ('wall_seconds',121,'exceeds its budget')]:
            checked=copy.deepcopy(original);checked['arms'][0]['verification'][field]=value
            data=encode(checked);self.store.replace_input('audit.json',data)
            result=copy.deepcopy(receipt);result['audit_sha256']=sha(data)
            if field=='wall_seconds':result['observations'][0]['observed_seconds']=1+.5+value+.25
            self.store.replace_receipt(result)
            with self.subTest(field=field),self.assertRaises(Error) as caught:build(self.store,'accept')
            self.assertEqual(caught.exception.code,'verification_mismatch');self.assertIn(message,str(caught.exception))


if __name__=='__main__':unittest.main()
