"""Adaptive BO campaigns: manifest checks, stop and the optional dependency.

These need BO-craft's contracts (CI installs the revision in
docs/adaptive-bo.md); the runner-backed acceptance is in
tests/integration_adaptive.py.
"""
from contextlib import closing, redirect_stderr
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from experiment_craft import adaptive, cli
from experiment_craft.storage import Error, Store, write_json

MANIFEST = {
    'schema_version': 'experiment.adaptive/0.1',
    'problem': {'schema_version': 'bo.problem/0.1',
                'parameters': [{'name': 'x', 'type': 'continuous', 'lower': -2.0, 'upper': 2.0}],
                'objectives': [{'name': 'score', 'direction': 'minimize'}]},
    'config': {'backend': 'random'}, 'seed': 7, 'concurrent': 2, 'python': sys.executable,
    'proposal_slots': 1, 'proposal_wall_seconds': 30,
    'evaluator': {'kind': 'command', 'argv': [sys.executable, 'evaluator.py'], 'slots': 1, 'wall_seconds': 10},
    'budget': {'evaluations': 6, 'jobs': 20, 'wall_seconds': 180, 'slot_seconds': 500}}

NATIVE = {'kind': 'native', 'job': {'payload_schema': 'fcmaes.evaluate/1'}}


class FakeRuntime:
    """Records cancellations; `missing` jobs answer unknown_job."""
    calls = []
    missing = set()

    def __init__(self, *args):
        pass

    def cancel(self, job_id):
        FakeRuntime.calls.append(job_id)
        if job_id in FakeRuntime.missing:
            raise Error('unknown_job', 'no such job')


class Adaptive(unittest.TestCase):
    def test_native_bridge_combinations_are_rejected_before_any_job(self):
        self.assertEqual(adaptive.validate_manifest(copy.deepcopy(MANIFEST))['seed'], 7)
        known = copy.deepcopy(MANIFEST)
        known['evaluator'] = NATIVE
        known['config']['noise'] = 'known'
        two = copy.deepcopy(MANIFEST)
        two['evaluator'] = NATIVE
        two['problem']['objectives'].append({'name': 'other', 'direction': 'maximize'})
        retry = copy.deepcopy(MANIFEST)
        retry['evaluator'] = {'kind': 'native', 'job': {'payload_schema': 'fcmaes.retry/1'}}
        for manifest in (known, two, retry):
            with self.assertRaises(Error) as caught:
                adaptive.validate_manifest(manifest)
            self.assertEqual(caught.exception.code, 'unsupported_profile')

    def test_bo_craft_contract_errors_keep_their_code(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest['problem']['parameters'].append(dict(manifest['problem']['parameters'][0]))
        with self.assertRaises(Error) as caught:
            adaptive.validate_manifest(manifest)
        self.assertEqual(caught.exception.code, 'invalid_spec')

    def test_a_missing_bo_craft_is_a_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            write_json(path, MANIFEST)
            stderr = io.StringIO()
            with patch.dict(sys.modules, {'bo_craft': None}), redirect_stderr(stderr):
                code = cli.main(['adaptive-init', str(path), '--workspace', str(Path(tmp) / 'campaign'),
                                 '--runner', '/missing/optimization-run', '--node-root', str(Path(tmp) / 'node')])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(stderr.getvalue())['error']['code'], 'missing_dependency')

    def test_stop_is_recorded_once_and_cancels_each_job_once(self):
        jobs = {'running': {'state': 'running', 'job_id': 'a'}, 'lost': {'state': 'unknown', 'job_id': 'b'},
                'done': {'state': 'completed', 'job_id': 'c'}}
        with tempfile.TemporaryDirectory() as tmp, closing(Store(tmp, create=True)) as store:
            with store.edit({'event': 'adaptive_initialized'}) as state:
                state.update({'schema_version': 'experiment.adaptive.state/0.1', 'campaign_id': 'c' * 64,
                              'plan': {'budget': {'evaluations': 6}}, 'runtime': {'runner': 'r', 'root': 'n'},
                              'stop_requested': False, 'stop_reason': None, 'deadline_at': 0,
                              'jobs_reserved': 3, 'slot_seconds_reserved': 0, 'trials': {}, 'jobs': jobs,
                              'observations': []})
            FakeRuntime.calls, FakeRuntime.missing = [], {'b'}
            with patch.object(adaptive, 'Runtime', FakeRuntime):
                for _ in range(3):
                    value = adaptive.stop(store)
            events = [e['event'] for e in store.events()]
            self.assertEqual(events.count('adaptive_stop'), 1)
            self.assertEqual(events.count('adaptive_cancel_requested'), 1)
            # The running job is cancelled once; the one without a native job
            # is asked again, as a lost launch answer can still produce it.
            self.assertEqual(sorted(FakeRuntime.calls), ['a', 'b', 'b', 'b'])
            self.assertEqual(value['status'], 'unknown')
            self.assertEqual(store.read()['stop_reason'], 'user_stop')

    def test_configuration_is_checked_by_bo_craft(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest['config']['unknown_setting'] = 1
        with self.assertRaises(Error) as caught:
            adaptive.validate_manifest(manifest)
        self.assertEqual(caught.exception.code, 'invalid_spec')
        manifest['config'] = {'backend': 'botorch', 'replication': 'incumbent', 'acq_maxiter': 20}
        self.assertTrue(adaptive.validate_manifest(manifest))

    def test_answer_settings_are_checked(self):
        for answer, change in [({'validation_replicates': 6}, None), ({'validation_replicates': 2}, 'two'),
                               ({'model': True}, 'conditional')]:
            manifest = copy.deepcopy(MANIFEST)
            manifest['answer'] = answer
            if change == 'two':
                manifest['problem']['objectives'].append({'name': 'other', 'direction': 'maximize'})
            if change == 'conditional':
                manifest['problem']['parameters'] = [
                    {'name': 'kind', 'type': 'categorical', 'choices': ['a', 'b']},
                    {'name': 'x', 'type': 'continuous', 'lower': 0, 'upper': 1, 'active_if': {'kind': ['a']}}]
            with self.assertRaises(Error) as caught:
                adaptive.validate_manifest(manifest)
            self.assertEqual(caught.exception.code, 'invalid_manifest')
        unseeded = copy.deepcopy(MANIFEST)
        unseeded['evaluator'] = {**NATIVE, 'seeded': False}
        unseeded['answer'] = {'validation_replicates': 2}
        with self.assertRaises(Error) as caught:
            adaptive.validate_manifest(unseeded)
        self.assertEqual(caught.exception.code, 'unsupported_profile')

    def test_only_declared_replicates_may_repeat_a_point(self):
        problem = MANIFEST['problem']
        request = {'problem': problem, 'observations': [
            {'id': 'a', 'trial_id': 'a', 'x': {'x': 0.5}, 'status': 'completed', 'values': {'score': 1.0}},
            {'id': 'f', 'trial_id': 'f', 'x': {'x': 0.7}, 'status': 'failed'}],
            'pending': [{'id': 'p', 'x': {'x': -1.0}}]}
        on = {'backend': 'botorch', 'replication': 'incumbent'}
        pairs = adaptive.check_candidates(request, {'candidates': [{'x': 0.5}, {'x': 0.1}],
                                                    'replicate_of': ['a', None]}, on)
        self.assertEqual(pairs, [({'x': 0.5}, 'a'), ({'x': 0.1}, None)])
        refused = [({'candidates': [{'x': 0.5}]}, on, 'duplicate_candidate'),
                   ({'candidates': [{'x': 0.5}], 'replicate_of': ['a']}, {'backend': 'botorch'}, 'invalid_proposal'),
                   ({'candidates': [{'x': 0.7}], 'replicate_of': ['f']}, on, 'invalid_proposal'),
                   ({'candidates': [{'x': -1.0}]}, on, 'duplicate_candidate')]
        for proposal, config, code in refused:
            with self.assertRaises(Error) as caught:
                adaptive.check_candidates(request, proposal, config)
            self.assertEqual(caught.exception.code, code)

    def test_validation_summary_and_completion_wait_for_the_answer(self):
        answer = {'validation_x': {'x': 0.2}, 'validation_source': 'model'}
        rows = [{'status': 'completed', 'values': {'score': v}} for v in (1.0, 3.0)] + [{'status': 'failed'}]
        summary = adaptive.validation_summary(answer, ['t1', 't2', 't3'], rows, 'score')
        self.assertEqual((summary['mean'], summary['completed'], summary['not_completed']), (2.0, 2, 1))
        self.assertAlmostEqual(summary['standard_error'], 1.0)
        state = {'schema_version': 'experiment.adaptive.state/0.1', 'campaign_id': 'c' * 64,
                 'plan': {'budget': {'evaluations': 2}}, 'stop_requested': False, 'stop_reason': None,
                 'jobs_reserved': 2, 'slot_seconds_reserved': 0, 'deadline_at': 0, 'observations': [],
                 'jobs': {}, 'trials': {'a': {'state': 'completed'}, 'b': {'state': 'completed'}}}
        self.assertEqual(adaptive.status(state)['status'], 'running')
        state['answer'] = {'state': 'done'}
        self.assertEqual(adaptive.status(state)['status'], 'completed')


class ProgressRuntime:
    """Serves progress pages from `curves` and records cancellations."""

    def __init__(self, curves, page=2, terminal=()):
        self.curves, self.page, self.terminal = curves, page, set(terminal)
        self.cancelled, self.calls = [], []

    def call(self, *args):
        self.calls.append(args)
        assert args[:2] == ('jobs', 'progress')
        job_id, offset, limit = args[2], int(args[4]), int(args[6])
        lines = self.curves[job_id]
        page = lines[offset:offset + min(limit, self.page)]
        following = offset + len(page)
        return {'lines': page, 'next_offset': following if following < len(lines) else None}

    def cancel(self, job_id):
        self.cancelled.append(job_id)
        if job_id in self.terminal:
            raise Error('already_terminal', 'finished first')


def points(*values):
    return [{'step': k + 1, 'value': v} for k, v in enumerate(values)]


def pruning_state(store, pruning, running):
    """Two completed trials with curves and the given running evaluations."""
    trials = {'t0': {'state': 'completed', 'curve': {'1': 1.0, '2': 0.5}},
              't1': {'state': 'completed', 'curve': {'1': 2.0, '2': 1.0}}}
    jobs = {}
    for trial_id in running:
        trials[trial_id] = {'state': 'pending'}
        jobs[trial_id] = {'kind': 'evaluation', 'payload': trial_id, 'state': 'running', 'job_id': 'job-' + trial_id}
    with store.edit({'event': 'adaptive_initialized'}) as state:
        state.update({'plan': {'problem': MANIFEST['problem'], 'pruning': pruning}, 'stop_requested': False,
                      'trials': trials, 'jobs': jobs, 'observations': []})


class Pruning(unittest.TestCase):
    PRUNING = {'policy': 'median', 'startup_trials': 2, 'warmup_steps': 1, 'check_seconds': 0.01}

    def test_pruning_needs_one_unconstrained_objective_and_a_command_evaluator(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest['pruning'] = dict(self.PRUNING)
        self.assertEqual(adaptive.validate_manifest(copy.deepcopy(manifest))['pruning']['policy'], 'median')
        two = copy.deepcopy(manifest)
        two['problem']['objectives'].append({'name': 'other', 'direction': 'maximize'})
        constrained = copy.deepcopy(manifest)
        constrained['problem']['constraints'] = [{'name': 'c', 'type': 'outcome', 'upper': 0.0}]
        native = copy.deepcopy(manifest)
        native['evaluator'] = NATIVE
        other_policy = copy.deepcopy(manifest)
        other_policy['pruning']['policy'] = 'hyperband'
        fast = copy.deepcopy(manifest)
        fast['pruning']['check_seconds'] = 0.0
        for case, codes in [(two, {'invalid_manifest'}), (constrained, {'invalid_manifest', 'invalid_spec'}),
                            (native, {'unsupported_profile'}), (other_policy, {'invalid_manifest'}),
                            (fast, {'invalid_manifest'})]:
            with self.assertRaises(Error) as caught:
                adaptive.validate_manifest(case)
            self.assertIn(caught.exception.code, codes)

    def test_curves_are_paged_and_malformed_lines_ignored(self):
        lines = [{'step': 1, 'value': 3.0}, {'step': 2, 'value': 2.5}, {'step': 'x', 'value': 1.0},
                 {'step': 3, 'value': True}, {'step': -1, 'value': 1.0}, {'other': 1},
                 {'step': 2, 'value': 2.0}, {'step': 4, 'value': 1}]
        runtime = ProgressRuntime({'j': lines}, page=3)
        self.assertEqual(adaptive.read_curve(runtime, 'j'), {1: 3.0, 2: 2.0, 4: 1.0})
        self.assertEqual([c[4] for c in runtime.calls], ['0', '3', '6'])
        self.assertEqual(adaptive.read_curve(ProgressRuntime({'j': []}), 'j'), {})

    def test_an_older_runner_is_refused_before_any_job(self):
        class Node:
            def __init__(self, code):
                self.code = code

            def call(self, *args):
                raise Error(self.code, 'refused')
        with tempfile.TemporaryDirectory() as tmp:
            # 0.4.1 refuses the unknown `progress` field; disabled commands keep their code.
            for code, expected in [('invalid_command_spec', 'unsupported_runtime'),
                                   ('commands_disabled', 'commands_disabled')]:
                with self.assertRaises(Error) as caught:
                    adaptive.check_progress_support(Node(code), tmp)
                self.assertEqual(caught.exception.code, expected)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_the_median_rule_records_then_cancels_once(self):
        curves = {'job-bad': points(3.0, 2.5), 'job-good': points(0.9, 0.4), 'job-early': []}
        with tempfile.TemporaryDirectory() as tmp, closing(Store(tmp, create=True)) as store:
            pruning_state(store, self.PRUNING, ['bad', 'good', 'early'])
            runtime = ProgressRuntime(curves)
            clock = {}
            adaptive._prune(store, runtime, clock)
            self.assertEqual(runtime.cancelled, ['job-bad'])
            jobs = store.read()['jobs']
            self.assertEqual(jobs['bad']['prune_requested'], {'step': 2, 'median': 0.75})
            self.assertTrue(jobs['bad']['cancel_requested'])
            self.assertNotIn('prune_requested', jobs['good'])
            # Rate limited, then idempotent: a pruned job is not cancelled again.
            calls = len(runtime.calls)
            adaptive._prune(store, runtime, clock)
            self.assertEqual(len(runtime.calls), calls)
            clock['last'] = 0.0
            adaptive._prune(store, runtime, clock)
            self.assertEqual(runtime.cancelled, ['job-bad'])
            events = [e['event'] for e in store.events()]
            self.assertEqual((events.count('adaptive_prune'), events.count('adaptive_prune_cancel_requested')), (1, 1))

    def test_no_pruning_before_the_startup_trials_or_after_a_stop(self):
        curves = {'job-bad': points(9.0, 9.0)}
        for startup, stop in [(3, False), (2, True)]:
            with tempfile.TemporaryDirectory() as tmp, closing(Store(tmp, create=True)) as store:
                pruning_state(store, {**self.PRUNING, 'startup_trials': startup}, ['bad'])
                if stop:
                    with store.edit({'event': 'adaptive_stop'}) as state:
                        state['stop_requested'] = True
                runtime = ProgressRuntime(curves)
                adaptive._prune(store, runtime, {})
                self.assertEqual(runtime.cancelled, [])
                self.assertNotIn('prune_requested', store.read()['jobs']['bad'])

    def test_a_recorded_prune_is_cancelled_after_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp, closing(Store(tmp, create=True)) as store:
            pruning_state(store, self.PRUNING, ['bad', 'done'])
            with store.edit({'event': 'adaptive_prune', 'job': 'bad'}) as state:
                state['jobs']['bad']['prune_requested'] = {'step': 2, 'median': 0.75}
                state['jobs']['done']['prune_requested'] = {'step': 2, 'median': 0.75}
            runtime = ProgressRuntime({}, terminal={'job-done'})
            adaptive._prune(store, runtime, {})
            self.assertEqual(sorted(runtime.cancelled), ['job-bad', 'job-done'])
            self.assertEqual(runtime.calls, [])
            jobs = store.read()['jobs']
            self.assertTrue(jobs['bad']['cancel_requested'] and jobs['done']['cancel_requested'])

    def test_a_cancelled_pruned_job_becomes_a_pruned_observation_with_its_curve(self):
        request = {'id': 'bad', 'trial_id': 'bad', 'x': {'x': 0.5}, 'seed': 3}
        with tempfile.TemporaryDirectory() as tmp, closing(Store(tmp, create=True)) as store:
            pruning_state(store, self.PRUNING, ['bad', 'late'])
            directory = Path(tmp) / 'native'
            directory.mkdir(exist_ok=True)
            write_json(directory / 'resolved.json', {'r': 1})
            with store.edit({'event': 'adaptive_prune', 'job': 'bad'}) as state:
                state['plan']['config'] = {'backend': 'botorch', 'pruned': 'last'}
                for name in ('bad', 'late'):
                    state['jobs'][name].update(request={**request, 'id': name, 'trial_id': name},
                                               resolved={'r': 1})
                    state['jobs'][name]['prune_requested'] = {'step': 2, 'median': 0.75}
            runtime = ProgressRuntime({'job-bad': points(3.0, 2.5), 'job-late': points(3.0, 2.5, 0.1)})
            native = ({'kind': 'command'}, {'outputs': {}}, None)
            with patch.object(adaptive, 'checked_native', return_value=native):
                adaptive._collect(store, runtime, 'bad', {'state': 'cancelled', 'directory': str(directory)})
                # The cancel came too late: the job finished, so it is no pruned trial.
                adaptive._collect(store, runtime, 'late', {'state': 'failed', 'directory': str(directory)})
            state = store.read()
            pruned, late = state['observations']
            self.assertEqual(pruned['status'], 'pruned')
            self.assertEqual(pruned['intermediate'], {'1': 3.0, '2': 2.5})
            self.assertEqual(pruned['provenance'], {'pruned_at_step': 2, 'median_at_step': 0.75})
            self.assertNotIn('values', pruned)
            self.assertEqual((late['status'], 'intermediate' in late), ('failed', False))
            self.assertEqual(state['trials']['bad']['state'], 'pruned')
            self.assertNotIn('curve', state['trials']['bad'])


if __name__ == '__main__':
    unittest.main()
