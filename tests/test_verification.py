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
from verification_fixture import AUDITED, SEARCHED, STATIC, argv, encode, inputs, outputs, sha


class MemoryStore:
    """A campaign state in the application's plan shape: a search, its audit and
    the acceptance of that audit, with recorded documents in place of runs."""

    def __init__(self, root, rejected=False, code=None):
        self.root = root
        raw, receipt = inputs(rejected)
        searched = [{'path': path, 'from': {'step': 'search', 'kind': 'output', 'output': name}}
                    for path, name in SEARCHED.items()]
        audited = [{'path': path, 'from': {'step': 'audit', 'kind': 'output', 'output': name}}
                   for path, name in AUDITED.items()]

        def literal(paths):
            return [{'path': path, 'bytes': len(raw[path]), 'sha256': sha(raw[path])} for path in paths]

        produced = {'search': {name: raw[path] for path, name in SEARCHED.items()},
                    'audit': {name: raw[path] for path, name in AUDITED.items()},
                    'accept': {'acceptance': encode(receipt)}}
        planned = {'search': literal(('problem.json', 'protocol.json')), 'audit': literal(STATIC) + searched,
                   'accept': literal(STATIC) + searched + audited}
        self.state = {'campaign_id': 'd' * 64, 'plan': {'plan_id': 'c' * 64, 'name': 'report fixture', 'steps': []},
            'steps': {}, 'runtime': {'root': str(root.parent / 'node')}, 'jobs_reserved': 3, 'slot_seconds_reserved': 12,
            'deadline_at': 1e20, 'stop_requested': False, 'stop_reason': None}
        for index, step in enumerate(('search', 'audit', 'accept')):
            self.state['plan']['steps'].append({'id': step, 'job': {'schema_version': 'execution.command/0.1',
                'argv': argv(step, '/usr/bin/python3'), 'inputs': planned[step], 'outputs': outputs(step)}})
            failed = step == 'accept' and rejected
            entry = {'job_id': str(index) * 32, 'status': 'failed' if failed else 'succeeded', 'issued': True,
                     'execution_identity': str(index) * 64, 'observation': {'state': 'failed' if failed else 'completed'}}
            admitted = []
            for position, item in enumerate(planned[step]):
                reference = item.get('from')
                data = produced[reference['step']][reference['output']] if reference else raw[item['path']]
                target = root / 'requests' / step / 'inputs' / str(position)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                admitted.append({'path': item['path'], 'file': f'inputs/{position}', 'bytes': len(data), 'sha256': sha(data)})
            entry['submitted_job'] = {'schema_version': 'execution.command/0.1', 'inputs': admitted}
            entry['expected_resolved'] = copy.deepcopy(entry['submitted_job'])
            process = 0 if step != 'accept' else (3 if rejected else 0) if code is None else code
            native = {'schema_version': 'execution.command.result/0.1', 'state': entry['observation']['state'],
                      'process': {'code': process, 'signal': None}, 'output_errors': [], 'collection_attempted': True,
                      'outputs': {name: {'bytes': len(data), 'sha256': sha(data), 'path': '.command-outputs/' + name}
                                  for name, data in produced[step].items()}}
            path = root / 'results' / step / 'native.json'
            path.parent.mkdir(parents=True)
            path.write_bytes(encode(native))
            entry['native'] = {'path': f'results/{step}/native.json', 'bytes': path.stat().st_size,
                               'sha256': sha(path.read_bytes())}
            self.state['steps'][step] = entry
        self.output_path = root / 'results/accept/outputs/acceptance'
        self.output_path.parent.mkdir(parents=True)
        self.output_path.write_bytes(produced['accept']['acceptance'])

    def read(self):
        return copy.deepcopy(self.state)

    def job(self, step):
        return next(item['job'] for item in self.state['plan']['steps'] if item['id'] == step)

    def native(self, step, change):
        """Rewrite a step's native result, keeping its recorded digest current."""
        entry = self.state['steps'][step]
        path = self.root / entry['native']['path']
        native = json.loads(path.read_bytes())
        change(native)
        data = encode(native)
        path.write_bytes(data)
        entry['native'].update(bytes=len(data), sha256=sha(data))

    def replace_output(self, step, name, data):
        self.native(step, lambda native: native['outputs'][name].update(bytes=len(data), sha256=sha(data)))
        cached = self.root / 'results' / step / 'outputs' / name
        if cached.exists():
            cached.write_bytes(data)

    def replace_input(self, name, data):
        """Give every step that reads `name` the new bytes, as a plan built
        with them would: literal inputs everywhere, or the producer's output."""
        planned = next(item for item in self.job('accept')['inputs'] if item['path'] == name)
        if 'from' in planned:
            self.replace_output(planned['from']['step'], planned['from']['output'], data)
        for step in self.state['plan']['steps']:
            for index, item in enumerate(step['job']['inputs']):
                if item['path'] != name:
                    continue
                if 'from' not in item:
                    item.update(bytes=len(data), sha256=sha(data))
                entry = self.state['steps'][step['id']]
                (self.root / 'requests' / step['id'] / 'inputs' / str(index)).write_bytes(data)
                for key in ('submitted_job', 'expected_resolved'):
                    entry[key]['inputs'][index].update(bytes=len(data), sha256=sha(data))

    def replace_receipt(self, value):
        self.replace_output('accept', 'acceptance', encode(value))


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
        self.assertEqual(catalog(self.store,'accept')['artifacts'][0]['availability'],'sealed')

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
        self.assertEqual(value['total_outputs'],6);self.assertEqual(value['next_offset'],1)
        last=catalog(self.store,after=5,limit=1)
        self.assertEqual([row['output'] for row in last['artifacts']],['acceptance']);self.assertIsNone(last['next_offset'])
        self.assertEqual(catalog(self.store,after=6,limit=1)['artifacts'],[])
        self.assertEqual(catalog(self.store,'accept')['total_outputs'],1)
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

    def test_native_result_without_the_receipt_is_unavailable(self):
        self.store.native('accept',lambda native:(native['outputs'].clear(),native['output_errors'].append(
            {'name':'acceptance','code':'missing_output','message':'required output is missing'})))
        self.store.output_path.unlink()
        value=build(self.store,'accept')
        self.assertEqual(value['status'],'unavailable');self.assertIsNone(value['summary'])
        self.assertIsNone(value['execution_consistent']);self.assertEqual(value['source']['artifact']['availability'],'unavailable')

    def test_receipt_must_come_from_the_applications_acceptance_command(self):
        # A step that exits 0 and writes a matching receipt is not the
        # application's acceptance unless it runs audit.py accept itself.
        job=self.store.job('accept')
        for argv in (['/bin/sh','-c','cp receipt.json out/acceptance.json'],
                     [*job['argv'][:2],'run',*job['argv'][3:]],
                     [*job['argv'][:-1],'out/other.json']):
            with self.subTest(argv=argv),patch.dict(job,argv=argv):
                self.fails(lambda:build(self.store,'accept'),'unsupported_verification')

    def test_audit_must_be_the_output_of_the_applications_audit_step(self):
        # Literal audit documents could have been written by hand.
        job=self.store.job('accept');entry=self.store.state['steps']['accept']
        index=next(i for i,item in enumerate(job['inputs']) if item['path']=='audit.json')
        admitted=entry['submitted_job']['inputs'][index]
        with patch.dict(job['inputs'][index],{'bytes':admitted['bytes'],'sha256':admitted['sha256']}):
            job['inputs'][index].pop('from')
            self.fails(lambda:build(self.store,'accept'),'unsupported_verification')
        audit=self.store.job('audit')
        for argv in (['/bin/sh','-c','true'],[*audit['argv'][:2],'accept',*audit['argv'][3:]]):
            with self.subTest(argv=argv),patch.dict(audit,argv=argv):
                self.fails(lambda:build(self.store,'accept'),'unsupported_verification')

    def test_acceptance_without_a_search_output_is_unsupported(self):
        # The audit step still reads all three; only the acceptance lacks one.
        for path in ('study.json','candidates.json','evaluations.jsonl'):
            job=self.store.job('accept');kept=list(job['inputs'])
            job['inputs']=[item for item in kept if item['path']!=path]
            try:
                with self.subTest(path=path):self.fails(lambda:build(self.store,'accept'),'unsupported_verification')
            finally:job['inputs']=kept

    def test_audit_acceptance_and_search_must_read_the_same_inputs(self):
        for step,path in (('audit','app/audit.py'),('audit','audit-protocol.json'),('search','problem.json')):
            job=self.store.job(step);item=next(x for x in job['inputs'] if x['path']==path)
            with self.subTest(step=step,path=path),patch.dict(item,sha256='0'*64):
                self.fails(lambda:build(self.store,'accept'),'unsupported_verification')
        search=self.store.job('search')
        changed=[*search['argv']];changed[changed.index('--problem')+1]='other.json'
        with patch.dict(search,argv=changed):
            self.fails(lambda:build(self.store,'accept'),'unsupported_verification')

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
