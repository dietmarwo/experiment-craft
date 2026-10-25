"""Comparison designs, missing-data arithmetic and immutable declarations."""
import copy
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import jsonschema

from experiment_craft.comparison import at, bound_protocol, declare, resolve
from experiment_craft.comparison_report import build, report, stats
from experiment_craft.manifest import compile_manifest, scientific
from experiment_craft.storage import Error, Store, canonical, identity, read_json, write_json
from test_campaign import campaign

PROJECT = Path(__file__).resolve().parents[1]


def fcmaes(seed=1, population=None):
    job = read_json(PROJECT / 'examples/smoke/fcmaes/job.json')
    job.pop('request_key')
    job['payload']['seed'] = seed
    job['payload']['optimizer']['parameters']['population'] = population
    return job


def protocol(plan):
    return {'schema_version': 'experiment.comparison/0.1', 'name': 'Seeded population comparison',
            'plan_id': plan['plan_id'], 'groups': [{
                'id': 'sphere', 'description': 'Same sphere, hard work cap, declared seeds', 'kind': 'optimization',
                'arms': [{'id': 'default', 'templates': ['a']}, {'id': 'larger', 'templates': ['b']}],
                'vary': ['/payload/optimizer'], 'replication': {'kind': 'seed', 'pointer': '/payload/seed'},
                'design': 'paired', 'budget': {'kind': 'fixed_work', 'pointer': '/payload/evaluations_per_retry',
                                               'counter': 'evaluations', 'limit': 100},
                'metrics': [{'id': 'objective', 'pointer': '/outcome/objective', 'unit': 'sphere',
                             'direction': 'minimize', 'target': .1}]}], 'exclude': []}


def state_for(plan):
    return {'schema_version': 'experiment.campaign.state/0.1', 'campaign_id': 'a' * 64,
            'plan': scientific(plan), 'runtime': {}, 'stop_requested': False, 'stop_reason': None,
            'jobs_reserved': 0, 'slot_seconds_reserved': 0, 'deadline_at': 2000000000,
            'steps': {s['id']: {'status': 'pending', 'issued': False, 'job_id': identity(s['id'])[:32]}
                      for s in plan['steps']}}


def native(value=.1, feasible=True, complete=True):
    return {'schema_version': 'optimization.result/0.2', 'worker': 'fcmaes', 'payload_schema': 'fcmaes.retry/1',
            'status': 'completed' if complete else 'timed_out', 'requested_tasks': 1,
            'completed_tasks': 1 if complete else 0, 'elapsed_seconds': .01,
            'runner': {'accounting_complete': complete}, 'work': {'evaluations': 100} if complete else None,
            'known_work_lower_bound': {'evaluations': 12 if not complete else 100},
            'results': [{'task_id': 0, 'outcome': {'termination': 'evaluation_limit' if complete else 'cancelled',
                        'claim': 'best_found', 'feasible': feasible, 'objective': value,
                        'evidence': {'level': 'rechecked', 'checks': ['objective', 'bounds']}}}]}


class Comparisons(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.manifest = self.base / 'campaign.json'
        self.raw = campaign([{'id': 'a', 'job': fcmaes(), 'matrix': {'/payload/seed': [1, 2, 3]}},
                             {'id': 'b', 'job': fcmaes(population=32), 'matrix': {'/payload/seed': [1, 2, 3]}}])
        self.plan = self.compile()
        self.state = state_for(self.plan)
        self.spec = protocol(self.plan)

    def tearDown(self):
        self.tmp.cleanup()

    def compile(self):
        write_json(self.manifest, self.raw)
        return compile_manifest(self.manifest)

    def rejected(self, code, spec=None, state=None):
        with self.assertRaises(Error) as caught:
            resolve(spec or self.spec, state or self.state)
        self.assertEqual(caught.exception.code, code)

    def store(self):
        root = self.base / 'workspace'
        root.mkdir()
        store = Store(root, create=True)
        self.addCleanup(store.close)
        with store.edit({'event': 'test_fixture'}) as state:
            state.update(self.state)
        return store

    def declare(self, store):
        path = self.base / 'protocol.json'
        write_json(path, self.spec)
        return declare(store, path)

    def attach(self, store, step, value, status='succeeded'):
        data = canonical(value)
        path = 'results/' + step + '/native.json'
        target = store.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        job = next(s['job'] for s in self.plan['steps'] if s['id'] == step)
        with store.edit({'event': 'test_observation'}) as state:
            state['steps'][step].update(status=status, issued=True, submitted_job=copy.deepcopy(job),
                observation={'state': value['status']},
                native={'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def test_unpaired_start_designs_need_the_same_starts_in_every_arm(self):
        sqp = read_json(PROJECT / 'examples/smoke/sqp/job.json')
        sqp.pop('request_key')
        other = copy.deepcopy(sqp)
        other['payload']['backend'] = 'interior_point'
        starts = [[[0.1, 0.2, 0.3, 0.4]], [[0.25, 0.25, 0.25, 0.25]]]
        self.raw = campaign([{'id': 'a', 'job': sqp, 'matrix': {'/payload/starts': starts}},
                             {'id': 'b', 'job': other, 'matrix': {'/payload/starts': [starts[0], [[0.9, 0.0, 0.1, 0.0]]]}}])
        self.raw['budget']['max_reserved_slot_seconds'] = 1000
        plan = self.compile()
        spec = protocol(plan)
        spec['groups'][0].update(vary=['/payload/backend'], design='unpaired',
                                 replication={'kind': 'start', 'pointer': '/payload/starts/0'},
                                 budget={'kind': 'fixed_work', 'pointer': '/payload/max_iterations',
                                         'counter': 'iterations', 'limit': 100})
        self.rejected('incompatible_comparison', spec, state_for(plan))
        self.raw['steps'][1]['matrix'] = {'/payload/starts': starts}
        plan = self.compile()
        spec['plan_id'] = plan['plan_id']
        self.assertEqual(len(resolve(spec, state_for(plan))['groups'][0]['arms'][1]['units']), 2)

    def test_design_resolves_the_planned_pairs_without_native_calls(self):
        value = resolve(self.spec, self.state)
        self.assertEqual(len(value['groups']), 1)
        arms = value['groups'][0]['arms']
        self.assertEqual([len(a['units']) for a in arms], [3, 3])
        self.assertEqual({u['sample'] for u in arms[0]['units']}, {1, 2, 3})

    def test_profiles_models_tolerances_and_resource_definitions_cannot_be_pooled(self):
        for pointer, value in [('/payload/problem/config/dimension', 3), ('/resources/cpu_slots', 2),
                               ('/payload/evaluations_per_retry', 101), ('/accept/require_feasible', True)]:
            state = copy.deepcopy(self.state)
            for step in state['plan']['steps']:
                if step['template'] == 'b':
                    current = step if pointer.startswith('/accept/') else step['job']
                    path = pointer.strip('/').split('/')
                    for part in path[:-1]:
                        current = current.setdefault(part, {})
                    current[path[-1]] = value
            self.rejected('invalid_protocol' if 'evaluations_per_retry' in pointer else 'incompatible_comparison', state=state)

    def test_problem_and_tolerance_fields_are_not_allowed_configuration_axes(self):
        for pointer in ['/payload', '/payload/problem', '/resources/cpu_slots', '/payload/seed']:
            spec = copy.deepcopy(self.spec)
            spec['groups'][0]['vary'] = [pointer]
            self.rejected('unsupported_comparison', spec)

    def test_paired_schedules_require_unique_identical_samples(self):
        state = copy.deepcopy(self.state)
        state['plan']['steps'] = [s for s in state['plan']['steps'] if not (s['template'] == 'b' and s['job']['payload']['seed'] == 3)]
        self.rejected('invalid_protocol', state=state)
        state = copy.deepcopy(self.state)
        variants = [s for s in state['plan']['steps'] if s['template'] == 'b']
        variants[1]['job']['payload']['seed'] = variants[0]['job']['payload']['seed']
        self.rejected('invalid_protocol', state=state)

    def test_unpaired_design_does_not_fabricate_pairing(self):
        self.spec['groups'][0]['design'] = 'unpaired'
        store = self.store()
        self.declare(store)
        self.assertEqual(build(store)['groups'][0]['paired_differences'], [])

    def test_start_samples_compare_by_numeric_value_without_inventing_independence(self):
        group = self.spec['groups'][0]
        group.update(vary=['/payload/backend'], replication={'kind': 'start', 'pointer': '/payload/starts/0'},
                     budget={'kind': 'fixed_work', 'pointer': '/payload/max_iterations', 'counter': 'iterations', 'limit': 100})
        for step in self.state['plan']['steps']:
            job = step['job']
            seed = job['payload']['seed']
            job['payload_schema'] = 'sqp.solve/1'
            job['payload'] = {'starts': [[seed if step['template'] == 'a' else float(seed), 0]],
                              'backend': 'active_set', 'max_iterations': 100}
        self.assertEqual(len(resolve(self.spec, self.state)['groups']), 1)
        variants = [s for s in self.state['plan']['steps'] if s['template'] == 'a']
        variants[1]['job']['payload']['starts'] = [[float(variants[0]['job']['payload']['starts'][0][0]), 0.0]]
        self.rejected('invalid_protocol')

    def test_every_template_is_included_or_explicitly_excluded(self):
        spec = copy.deepcopy(self.spec)
        spec['groups'][0]['arms'].pop()
        spec['groups'][0]['design'] = 'unpaired'
        self.rejected('invalid_protocol', spec)
        spec['exclude'] = [{'template': 'b', 'reason': 'Separate confirmation sample'}]
        self.assertEqual(len(resolve(spec, self.state)['excluded']), 3)
        spec['exclude'].append(spec['exclude'][0])
        self.rejected('invalid_protocol', spec)

    def test_an_arm_has_one_fixed_solver_configuration(self):
        state = copy.deepcopy(self.state)
        state['plan']['steps'][0]['job']['payload']['optimizer']['parameters']['population'] = 99
        self.rejected('invalid_protocol', state=state)

    def test_unknown_profiles_and_multitask_jobs_need_an_adapter(self):
        for key, value in [('payload_schema', 'fcmaes.mode/1'), ('retries', 2)]:
            state = copy.deepcopy(self.state)
            for step in state['plan']['steps']:
                (step['job'] if key == 'payload_schema' else step['job']['payload'])[key] = value
            self.rejected('unsupported_comparison', state=state)

    def test_soft_work_limits_cannot_claim_a_fixed_work_comparison(self):
        for step in self.state['plan']['steps']:
            step['job']['payload']['evaluation_limit_mode'] = 'soft'
        self.rejected('unsupported_comparison')
        self.spec['groups'][0]['budget'] = {'kind': 'fixed_time', 'seconds': 30}
        self.assertEqual(len(resolve(self.spec, self.state)['groups']), 1)

    def test_time_caps_cannot_mix_and_match(self):
        self.spec['groups'][0]['budget'] = {'kind': 'fixed_time', 'seconds': 2}
        self.rejected('invalid_protocol')

    def test_deterministic_repeats_have_no_paired_quality_inference(self):
        self.spec['groups'][0]['replication'] = {'kind': 'deterministic'}
        self.rejected('invalid_protocol')
        self.spec['groups'][0]['design'] = 'unpaired'
        for step in self.state['plan']['steps']:
            step['job']['payload']['seed'] = 1
        self.assertEqual(len(resolve(self.spec, self.state)['groups']), 1)

    def test_wrong_plan_unknown_fields_and_invalid_metric_targets_fail_early(self):
        spec = copy.deepcopy(self.spec)
        spec['plan_id'] = '0' * 64
        self.rejected('protocol_plan_mismatch', spec)
        spec = copy.deepcopy(self.spec)
        spec['ranking'] = 'best'
        self.rejected('invalid_protocol', spec)
        spec = copy.deepcopy(self.spec)
        spec['groups'][0]['metrics'][0]['direction'] = 'none'
        self.rejected('invalid_protocol', spec)

    def test_declaration_is_atomic_immutable_and_idempotent(self):
        store = self.store()
        first = self.declare(store)
        events = store.events()
        self.assertEqual(self.declare(store), first)
        self.assertEqual(store.events(), events)
        self.spec['name'] += ' edited'
        with self.assertRaises(Error) as caught:
            self.declare(store)
        self.assertEqual(caught.exception.code, 'comparison_conflict')
        self.assertEqual(bound_protocol(store), first)

    def test_failed_declaration_commits_neither_table_nor_event(self):
        store = self.store()
        before = store.events()
        self.spec['plan_id'] = '0' * 64
        with self.assertRaises(Error):
            self.declare(store)
        self.assertEqual(store.events(), before)
        self.assertIsNone(store.db.execute("SELECT name FROM sqlite_master WHERE name='comparison_protocol'").fetchone())

    def test_declaration_after_a_dispatch_or_terminal_step_is_refused(self):
        for mode in ['issued', 'failed', 'stopped']:
            with self.subTest(mode=mode):
                if (self.base / 'workspace').exists():
                    self.base = self.base / mode
                    self.base.mkdir()
                store = self.store()
                with store.edit({'event': 'test_late'}) as state:
                    entry = next(iter(state['steps'].values()))
                    entry.update(issued=mode == 'issued', status='failed' if mode == 'failed' else 'pending')
                    state['stop_reason'] = 'requested' if mode == 'stopped' else None
                with self.assertRaises(Error) as caught:
                    self.declare(store)
                self.assertEqual(caught.exception.code, 'comparison_too_late')

    def test_declaration_respects_the_campaign_advancement_lock(self):
        store = self.store()
        with store.advance_lock(), self.assertRaises(Error) as caught:
            self.declare(store)
        self.assertEqual(caught.exception.code, 'campaign_busy')

    def test_foreign_or_changed_bindings_are_not_accepted(self):
        store = self.store()
        value = self.declare(store)
        value['protocol']['name'] = 'changed'
        store.db.execute('UPDATE comparison_protocol SET value=?', (canonical(value).decode(),))
        with self.assertRaises(Error) as caught:
            build(store)
        self.assertEqual(caught.exception.code, 'comparison_changed')

    def test_all_failures_partial_unknown_and_infeasible_runs_remain_in_the_denominator(self):
        store = self.store()
        self.declare(store)
        steps = self.plan['steps']
        self.attach(store, steps[0]['id'], native(.05))
        self.attach(store, steps[1]['id'], native(.2, complete=False), 'failed')
        self.attach(store, steps[2]['id'], native(-100, feasible=False))
        with store.edit({'event': 'test_unknown'}) as state:
            state['steps'][steps[3]['id']]['status'] = 'unknown'
            state['steps'][steps[4]['id']]['status'] = 'blocked'
            state['steps'][steps[5]['id']]['status'] = 'budget_exhausted'
        value = build(store)
        arms = value['groups'][0]['arms']
        summaries = [a['summary'] for a in arms]
        self.assertEqual(sum(s['planned'] for s in summaries), 6)
        self.assertEqual(sum(s['metrics']['objective']['complete_feasible']['n'] for s in summaries), 1)
        self.assertEqual(sum(s['metrics']['objective']['available_feasible']['n'] for s in summaries), 2)
        self.assertEqual(sum(s['metrics']['objective']['target']['unresolved'] for s in summaries), 5)
        self.assertEqual(sum(value['campaign_report']['counts'].values()), 6)
        self.assertEqual(sum(s['work']['evaluations']['unknown_runs'] for s in summaries), 4)
        self.assertEqual(sum(s['known_work_lower_bound']['evaluations']['known_total'] for s in summaries), 212)

    def test_missing_null_and_boolean_metrics_are_not_zero_or_measurements(self):
        store = self.store()
        self.declare(store)
        for step, value in zip(self.plan['steps'][:3], [None, True, 'missing']):
            result = native(value)
            if value == 'missing':
                result['results'][0]['outcome'].pop('objective')
            self.attach(store, step['id'], result)
        rows = build(store)['groups'][0]['arms'][0]
        self.assertEqual(rows['summary']['metrics']['objective']['complete_feasible']['n'], 0)
        self.assertEqual({o['metrics']['objective']['excluded_reason'] for o in rows['observations']}, {'missing', 'not_numeric'})
        self.assertEqual(at({'x': [None]}, '/x/0'), (True, None))
        self.assertEqual(at({'x': []}, '/x/0'), (False, None))
        with self.assertRaises(Error):
            at({'x': [1]}, '/x/00')

    def test_a_rewritten_and_rehashed_binding_is_refused(self):
        store = self.store()
        sealed = self.declare(store)
        self.assertEqual(store.read()['comparison_binding_id'], sealed['binding_id'])
        for step in self.plan['steps']:
            self.attach(store, step['id'], native(.5))
        self.assertEqual(build(store)['groups'][0]['arms'][0]['summary']['metrics']['objective']['target']['attained'], 0)
        forged = copy.deepcopy(sealed)
        forged['protocol']['groups'][0]['metrics'][0]['target'] = 1.0
        forged['protocol_id'] = identity(forged['protocol'])
        forged.pop('binding_id')
        forged['binding_id'] = identity(forged)
        store.db.execute('UPDATE comparison_protocol SET value=? WHERE id=1', (canonical(forged).decode(),))
        for action in [lambda: build(store), lambda: self.declare(store)]:
            with self.assertRaises(Error) as caught:
                action()
            self.assertIn(caught.exception.code, ['comparison_changed', 'comparison_conflict'])

    def test_a_metric_name_that_meets_a_native_array_is_missing(self):
        self.spec['groups'][0]['metrics'][0]['pointer'] = '/outcome/x/norm'
        store = self.store()
        self.declare(store)
        result = native()
        result['results'][0]['outcome']['x'] = [0.1, 0.2]
        self.attach(store, self.plan['steps'][0]['id'], result)
        observation = build(store)['groups'][0]['arms'][0]['observations'][0]
        self.assertEqual(observation['metrics']['objective']['excluded_reason'], 'missing')
        self.assertEqual(at({'x': [1]}, '/x/norm', strict=False), (False, None))

    def test_work_cap_overruns_and_missing_accounting_do_not_enter_complete_results(self):
        store = self.store()
        self.declare(store)
        result = native(.02)
        result['work']['evaluations'] = 101
        self.attach(store, self.plan['steps'][0]['id'], result)
        obs = build(store)['groups'][0]['arms'][0]['observations'][0]
        self.assertFalse(obs['complete'])
        self.assertTrue(obs['metrics']['objective']['available_feasible'])
        self.assertEqual(obs['budget_observation'], 'work_limit_exceeded')

    def test_actual_staged_input_bytes_are_checked_beyond_preparation_code_identity(self):
        store = self.store()
        self.declare(store)
        with store.edit({'event': 'test_staging'}) as state:
            for index, step in enumerate(self.plan['steps']):
                state['steps'][step['id']]['submitted_job'] = {'inputs': [{'name': 'model', 'sha256': str(index) * 64}]}
        with self.assertRaises(Error) as caught:
            build(store)
        self.assertEqual(caught.exception.code, 'incompatible_comparison')

    def test_paired_differences_only_use_two_complete_feasible_observations(self):
        store = self.store()
        self.declare(store)
        for step in self.plan['steps']:
            value = .1 if step['template'] == 'a' else .3
            self.attach(store, step['id'], native(value))
        value = build(store)
        pair = value['groups'][0]['paired_differences'][0]
        self.assertEqual(pair['summary'], {'n': 3, 'minimum': -.2, 'maximum': -.2, 'mean': -.2, 'median': -.2})
        self.assertEqual(pair['excluded'], 0)
        for group in value['groups']:
            for arm in group['arms']:
                values = [o['metrics']['objective']['value'] for o in arm['observations']]
                self.assertEqual(arm['summary']['metrics']['objective']['complete_feasible'], stats(values))

    def test_statistics_retain_missing_values_and_avoid_cancellation_error(self):
        self.assertEqual(stats([])['mean'], None)
        self.assertEqual(stats([.1, .2, .3])['mean'], .2)
        self.assertEqual(stats([-1e308, .3, 1e308])['mean'], .1)
        self.assertEqual(stats([2, 8])['median'], 5)

    def test_reporting_is_offline_repeatable_and_tampering_creates_no_report(self):
        store = self.store()
        self.declare(store)
        self.attach(store, self.plan['steps'][0]['id'], native())
        before = (store.events(), store.read())
        result = report(store, self.base / 'report')
        first_bytes = {p.name: p.read_bytes() for p in (self.base / 'report').iterdir()}
        self.assertEqual(report(store, self.base / 'report'), result)
        self.assertEqual({p.name: p.read_bytes() for p in (self.base / 'report').iterdir()}, first_bytes)
        self.assertEqual((store.events(), store.read()), before)
        ref = store.read()['steps'][self.plan['steps'][0]['id']]['native']
        (store.root / ref['path']).write_text('changed')
        with self.assertRaises(Error):
            report(store, self.base / 'bad-report')
        self.assertFalse((self.base / 'bad-report').exists())

    def test_all_shipped_schemas_and_actual_new_outputs_validate(self):
        store = self.store()
        binding = self.declare(store)
        result = build(store)
        for name in ['comparison', 'comparison-binding', 'comparison-report']:
            schema = read_json(files('experiment_craft').joinpath('schemas/' + name + '-0.1.schema.json'))
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.Draft202012Validator(schema).validate({'comparison': self.spec, 'comparison-binding': binding,
                                                            'comparison-report': result}[name])

    def test_missing_protocol_uses_the_cli_json_error_contract(self):
        store = self.store()
        process = subprocess.run([sys.executable, '-m', 'experiment_craft', 'compare', '--workspace', str(store.root),
                                  '--destination', str(self.base / 'no-report')], cwd=PROJECT, capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stderr)['error']['code'], 'comparison_not_declared')
        self.assertFalse((self.base / 'no-report').exists())


if __name__ == '__main__':
    unittest.main()
