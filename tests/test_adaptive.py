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


if __name__ == '__main__':
    unittest.main()
