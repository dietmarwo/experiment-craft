"""History scope, snapshot consistency and the local HTTP control boundary."""
from contextlib import closing
import http.client
import json
import sqlite3
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import jsonschema

from experiment_craft.dashboard import Dashboard, History, Server, read_campaign
from experiment_craft.manifest import compile_manifest
from experiment_craft.storage import Error, Store, canonical, write_json
from test_campaign import campaign
from test_comparison import state_for


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.workspace = self.base / 'campaign'
        self.workspace.mkdir()
        source = self.base / 'source.json'
        write_json(source, campaign())
        state = state_for(compile_manifest(source))
        state.update(created_at=time.time(), runtime={'node_id': 'node-1', 'root': str(self.base/'node'), 'mode': 'foreground'})
        with closing(Store(self.workspace, create=True)) as store:
            with store.edit({'event': 'initialized', 'at': time.time()}) as value:
                value.update(state)
        self.dashboard = Dashboard([self.workspace], self.base / 'ui', sample_seconds=.25, history_limit=10)
        self.server = Server(self.dashboard, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.dashboard.close()
        self.tmp.cleanup()

    def request(self, path='/api/snapshot', method='GET', headers=None, body=None):
        headers = headers if headers is not None else {'Authorization': 'Bearer ' + self.dashboard.token}
        with closing(http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)) as client:
            client.request(method, path, body, headers)
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def error(self, code, fn):
        with self.assertRaises(Error) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def verification_fixture(self, rejected=False, code=None, missing=False):
        """Recorded observations in a local DB, never a scientific verification run."""
        import shutil
        from test_verification import MemoryStore
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.dashboard.close()
        shutil.rmtree(self.workspace)
        memory = MemoryStore(self.workspace, rejected, code)
        if missing:
            memory.native('accept', lambda native: native.update(outputs={}))
            memory.output_path.unlink()
        state = memory.read()
        state.update(schema_version='experiment.campaign.state/0.1', created_at=time.time())
        state['runtime'].update(node_id='node-1', mode='foreground')
        for step in state['plan']['steps']:
            step['job']['resources'] = {'cpu_slots': 1}
        with closing(Store(self.workspace, create=True)) as store:
            with store.edit({'event': 'recorded_test_fixture'}) as saved:
                saved.update(state)
        self.dashboard = Dashboard([self.workspace], self.base/'ui', sample_seconds=.25)
        self.server = Server(self.dashboard, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        return memory

    def test_artifact_and_verification_http_reads_are_offline_and_match_cli_bytes(self):
        from experiment_craft.verification import report
        self.verification_fixture()
        cid = 'd'*64
        with closing(Store(self.workspace)) as store:
            before, events = store.read(), store.events()
            report(store, self.base/'expected', 'accept')
        with patch('experiment_craft.runtime.Runtime.call', side_effect=AssertionError('offline HTTP called runtime')):
            status, _, data = self.request(f'/api/campaigns/{cid}/artifacts/0')
            self.assertEqual(status, 200); self.assertEqual(json.loads(data)['total_outputs'], 6)
            self.assertEqual(json.loads(self.request(f'/api/campaigns/{cid}/artifacts/100')[2])['artifacts'], [])
            for extension, name in [('json','verification.json'), ('md','verification.md'), ('csv','observations.csv')]:
                status, headers, data = self.request(f'/api/campaigns/{cid}/verification/accept/acceptance/{extension}')
                self.assertEqual(status, 200); self.assertEqual(data, (self.base/'expected'/name).read_bytes())
                self.assertIn(name, headers['Content-Disposition'])
            status, headers, data = self.request(f'/api/campaigns/{cid}/artifact/accept/acceptance')
            self.assertEqual(status, 200); self.assertEqual(data, (self.workspace/'results/accept/outputs/acceptance').read_bytes())
            self.assertEqual(headers['Content-Type'], 'application/octet-stream')
        with closing(Store(self.workspace)) as store:
            self.assertEqual((store.read(), store.events()), (before, events))

    def test_recorded_http_verdicts_keep_rejection_uncertainty_and_missing_receipts(self):
        for options, expected in [({},'reported_accepted'), ({'rejected':True},'reported_rejected'),
                                  ({'code':7},'unconfirmed'), ({'missing':True},'unavailable')]:
            with self.subTest(expected=expected):
                self.verification_fixture(**options)
                with patch('experiment_craft.runtime.Runtime.call', side_effect=AssertionError('checker ran')):
                    status, _, data = self.request(f'/api/campaigns/{"d"*64}/verification/accept/acceptance/json')
                self.assertEqual(status, 200); self.assertEqual(json.loads(data)['status'], expected)

    def test_result_routes_refuse_unattached_paths_unsupported_shapes_and_bad_targets(self):
        cid = self.dashboard.view()['campaigns'][0]['id']
        for path, expected in [(f'/api/campaigns/{cid}/artifacts/-1','invalid_command'),
                               ('/api/campaigns/unknown/artifacts/0','unknown_campaign'),
                               (f'/api/campaigns/{cid}/verification/a/answer/json','unknown_artifact'),
                               (f'/api/campaigns/{cid}/verification/a/answer/html','invalid_command')]:
            self.assertEqual(json.loads(self.request(path)[2])['error']['code'], expected)
        headers = {'Authorization':'Bearer '+self.dashboard.token,'Origin':self.server.origin,'Content-Type':'application/json'}
        for body in ['{}', 'null', '[]', '{"step":"a","output":"../secret"}', '{"step":"a","output":"answer","workspace":"/tmp"}']:
            self.assertEqual(self.request(f'/api/campaigns/{cid}/collect-artifact', 'POST', headers, body)[0], 400)
        self.assertEqual(self.dashboard.view()['campaigns'][0]['operations'], [])

    def test_download_checks_cache_again_and_does_not_serve_changed_or_symlink_bytes(self):
        self.verification_fixture()
        path = self.workspace/'results/accept/outputs/acceptance'
        for corrupt in ('bytes', 'symlink'):
            if corrupt == 'bytes':
                path.write_text('tampered')
            else:
                path.unlink(); path.symlink_to(self.base/'secret'); (self.base/'secret').write_text('private')
            with patch('experiment_craft.runtime.Runtime.call', side_effect=AssertionError('cache was repaired')):
                for route in ('artifact/accept/acceptance', 'verification/accept/acceptance/json'):
                    status, _, data = self.request(f'/api/campaigns/{"d"*64}/{route}')
                    self.assertEqual((status, json.loads(data)['error']['code']), (400, 'artifact_changed'))
                    self.assertNotIn(b'private', data)

    def test_result_read_refuses_a_replaced_campaign_binding(self):
        cid = self.dashboard.view()['campaigns'][0]['id']
        with closing(Store(self.workspace)) as store:
            with store.edit({'event':'test_replaced'}) as state: state['runtime']['node_id']='replaced'
        self.assertEqual(json.loads(self.request(f'/api/campaigns/{cid}/artifacts/0')[2])['error']['code'], 'campaign_changed')

    def test_a_slow_client_cannot_hold_up_shutdown(self):
        import socket
        sock = socket.create_connection(('127.0.0.1', self.server.server_port))
        stop = threading.Event()
        def trickle():
            sock.sendall(b'G')
            deadline = time.monotonic() + 8  # bounded, so an unfixed server fails instead of hanging
            while not stop.wait(1) and time.monotonic() < deadline:
                try:
                    sock.sendall(b'E')
                except OSError:
                    return
            sock.close()
        sender = threading.Thread(target=trickle, daemon=True)
        sender.start()
        time.sleep(.5)
        started = time.monotonic()
        self.server.shutdown()
        self.server.drop_requests()
        self.server.server_close()
        self.assertLess(time.monotonic() - started, 3)
        stop.set()
        sock.close()

    def test_a_thread_that_cannot_start_leaves_the_lane_free(self):
        cid = self.dashboard.view()['campaigns'][0]['id']
        with patch('threading.Thread.start', side_effect=RuntimeError("can't start new thread")):
            self.error('dashboard_busy', lambda: self.dashboard.action(cid, 'stop'))
        self.assertEqual(self.dashboard.view()['campaigns'][0]['operations'], [])
        self.assertEqual(self.dashboard.workers, set())

    def test_continuing_an_already_paused_campaign_is_still_refused(self):
        cid = self.dashboard.view()['campaigns'][0]['id']
        self.dashboard.action(cid, 'pause')
        self.dashboard.threads[(cid, 'control')].join(10)
        self.dashboard.action(cid, 'continue')
        self.dashboard.threads[(cid, 'advance')].join(10)
        errors = {o['action']: o['error'] for o in self.dashboard.view()['campaigns'][0]['operations']}
        self.assertIsNone(errors['pause'])
        self.assertEqual(errors['continue']['code'], 'dispatch_paused')

    def test_a_pause_before_the_first_dispatch_ends_continue_without_an_error(self):
        from experiment_craft import dashboard as module
        from experiment_craft.operations import pause
        real = module.drive
        def paused_first(store, **kwargs):
            pause(store, 'operator')  # Pause pressed right after Start
            return real(store, **kwargs)
        cid = self.dashboard.view()['campaigns'][0]['id']
        with patch.object(module, 'drive', paused_first):
            self.dashboard.action(cid, 'continue')
            self.dashboard.threads[(cid, 'advance')].join(10)
        [op] = self.dashboard.view()['campaigns'][0]['operations']
        self.assertEqual((op['action'], op['error']), ('continue', None))

    def test_malformed_authorization_and_length_headers_keep_their_codes(self):
        status, _, body = self.request(headers={'Authorization': 'Bearer \xe9'})
        self.assertEqual((status, json.loads(body)['error']['code']), (401, 'unauthorized'))
        cid = self.dashboard.view()['campaigns'][0]['id']
        status, _, body = self.request(f'/api/campaigns/{cid}/pause', 'POST', {
            'Authorization': 'Bearer ' + self.dashboard.token, 'Origin': self.server.origin,
            'Content-Type': 'application/json', 'Content-Length': '\xb2'})
        self.assertEqual((status, json.loads(body)['error']['code']), (400, 'size_limit'))

    def test_a_stopping_dashboard_answers_503(self):
        cid = self.dashboard.view()['campaigns'][0]['id']
        self.dashboard.stopping.set()
        status, _, body = self.request(f'/api/campaigns/{cid}/pause', 'POST', {
            'Authorization': 'Bearer ' + self.dashboard.token, 'Origin': self.server.origin,
            'Content-Type': 'application/json', 'Content-Length': '2'}, b'{}')
        self.assertEqual((status, json.loads(body)['error']['code']), (503, 'dashboard_stopping'))

    def test_history_stays_apart_from_inventory_roots(self):
        from test_operations import PROJECT as root
        from experiment_craft.storage import read_json
        inventory = read_json(root / 'examples/deployment/local.json')
        inventory['coordinator']['root'] = str(self.base / 'coordinator')
        write_json(self.base / 'deployment.json', inventory)
        self.error('invalid_command', lambda: Dashboard([self.workspace], self.base / 'coordinator' / 'ui',
                                                        self.base / 'deployment.json'))

    def test_an_unusable_port_fails_before_history_is_written(self):
        import socket
        from experiment_craft.dashboard import serve
        with socket.socket() as taken:
            taken.bind(('127.0.0.1', 0))
            taken.listen()
            port = taken.getsockname()[1]
            self.error('port_unavailable', lambda: serve([self.workspace], self.base / 'other-ui', port=port))
        self.assertFalse((self.base / 'other-ui').exists())

    def test_checkpoint_errors_give_the_dashboard_command_a_failing_status(self):
        import io
        from contextlib import redirect_stdout
        from experiment_craft import cli
        stopped = {'status': 'dashboard_stopped',
                   'checkpoint_errors': [{'campaign_id': 'c', 'code': 'checkpoint_busy', 'message': 'reader'}]}
        with patch('experiment_craft.dashboard.serve', return_value=stopped), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['dashboard', '--workspace', str(self.workspace),
                                       '--state-dir', str(self.base / 'ui')]), 1)
        self.assertEqual(json.loads(out.getvalue()), stopped)

    def test_the_example_refuses_an_existing_output_with_a_json_error(self):
        import subprocess
        import sys
        from test_operations import PROJECT as root
        run = subprocess.run([sys.executable, str(root / 'examples/dashboard/prepare.py'), '--bin-dir', str(self.base / 'bin'),
                              '--output', str(self.workspace)], capture_output=True, text=True, timeout=60)
        self.assertEqual((run.returncode, json.loads(run.stderr)['error']['code']), (2, 'output_exists'))

    def test_snapshot_and_assets_do_not_call_runtime_or_change_decisions(self):
        with closing(Store(self.workspace)) as store:
            before = store.events()
        with patch('experiment_craft.runtime.Runtime.call', side_effect=AssertionError('runtime contacted')):
            self.dashboard.sample()
            code, headers, data = self.request()
            self.assertEqual(code, 200)
            value = json.loads(data)
            self.assertEqual(value['campaigns'][0]['counts']['pending'], 1)
            self.assertEqual(value['nodes'][0]['availability'], 'saved_state')
            for asset in ['/', '/app.js', '/evidence.js', '/style.css']:
                status, headers, data = self.request(asset, headers={})
                self.assertEqual(status, 200)
                self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertNotIn(self.dashboard.token.encode(), data)
        with closing(Store(self.workspace)) as store:
            self.assertEqual(before, store.events())

    def test_published_snapshot_and_history_schemas_validate(self):
        schema_root = Path(__file__).resolve().parents[1]/'experiment_craft/schemas'
        values = {'dashboard': self.dashboard.view(), 'dashboard-history':
                  self.dashboard.history_view(self.dashboard.view()['nodes'][0]['id'])}
        for name, value in values.items():
            schema = json.loads((schema_root/(name+('-0.2' if name == 'dashboard' else '-0.1')+'.schema.json')).read_text())
            jsonschema.Draft202012Validator.check_schema(schema)
            jsonschema.Draft202012Validator(schema).validate(value)

    def test_api_requires_token_and_control_requires_same_origin(self):
        self.assertEqual(self.request(headers={})[0], 401)
        self.assertEqual(self.request(headers={'Authorization': 'Bearer wrong'})[0], 401)
        path = '/api/campaigns/' + 'a'*64 + '/pause'
        headers = {'Authorization': 'Bearer ' + self.dashboard.token, 'Content-Type': 'application/json'}
        self.assertEqual(self.request(path, 'POST', headers, '{}')[0], 403)
        headers['Origin'] = 'https://evil.example'
        self.assertEqual(self.request(path, 'POST', headers, '{}')[0], 403)
        headers['Origin'] = self.server.origin
        self.assertEqual(self.request(path, 'POST', headers, '{}')[0], 202)
        for thread in list(self.dashboard.threads.values()):
            thread.join(5)
        with closing(Store(self.workspace)) as store:
            self.assertTrue(store.maintenance()['paused'])

    def test_http_refuses_rebinding_paths_host_confusion_and_large_bodies(self):
        headers = {'Authorization': 'Bearer ' + self.dashboard.token, 'Content-Type': 'application/json', 'Origin': self.server.origin}
        path = '/api/campaigns/' + 'a'*64 + '/stop'
        self.assertEqual(self.request(path, 'POST', headers, '{"workspace":"/tmp/other"}')[0], 400)
        self.assertEqual(self.request(path, 'POST', headers, ' '*1025)[0], 400)
        self.assertEqual(self.request('/api/snapshot?token=bad', headers=headers)[0], 400)
        self.assertEqual(self.request(headers={**headers, 'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/../../etc/passwd', headers=headers)[0], 404)
        self.assertEqual(self.request('/api/campaigns/unknown/pause', 'POST', headers, '{}')[0], 404)
        self.assertEqual(self.request(path.replace('stop','launch-shell'), 'POST', headers, '{}')[0], 400)
        with closing(Store(self.workspace)) as store:
            self.assertFalse(store.read()['stop_requested'])

    def test_history_is_persistent_scoped_bounded_and_distinct_from_utilization(self):
        node = self.dashboard.view()['nodes'][0]
        history = self.dashboard.history
        for i in range(20):
            history.append(node['scope'], {'at': 100+i, 'segment': 'test', 'counts': {'pending': i}, 'unresolved_declared_slots': 2})
        value = self.dashboard.history_view(node['id'])
        self.assertEqual(len(value['points']), 10)
        self.assertEqual(value['points'][0]['at'], 110)
        self.assertNotIn('cpu_utilization', canonical(value).decode())
        with closing(history.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM samples').fetchone()[0], 10)
        # A second history reader instance would conflict; on restart the same bytes survive.
        self.error('dashboard_busy', lambda: History(self.base/'ui', 10))
        history.close()
        self.dashboard.history = History(self.base/'ui', 10)
        self.assertEqual(self.dashboard.history_view(node['id']), value)
        self.dashboard.history.retain(['different-scope'])
        self.assertEqual(self.dashboard.history_view(node['id'])['points'], [])

    def test_unchanged_samples_are_coalesced_but_restart_starts_a_new_segment(self):
        node = self.dashboard.view()['nodes'][0]
        self.dashboard.sample()
        self.assertEqual(len(self.dashboard.history_view(node['id'])['points']), 1)
        self.dashboard.history.close()
        self.dashboard.history = History(self.base/'ui', 10)
        self.dashboard.segment = 'next-session'
        self.dashboard.sample()
        points = self.dashboard.history_view(node['id'])['points']
        self.assertEqual(len(points), 2)
        self.assertNotEqual(points[0]['segment'], points[1]['segment'])

    def test_unavailable_workspace_becomes_gap_not_zero_or_rebind(self):
        path = self.workspace/'campaign.sqlite3'
        path.rename(self.workspace/'saved.sqlite3')
        self.dashboard.sample()
        value = self.dashboard.view()
        self.assertEqual(value['campaigns'][0]['read_error']['code'], 'unknown_campaign')
        self.assertIsNone(value['nodes'][0]['counts'])
        self.assertIsNone(self.dashboard.history_view(value['nodes'][0]['id'])['points'][-1]['counts'])
        (self.workspace/'saved.sqlite3').rename(path)
        with closing(Store(self.workspace)) as store:
            with store.edit({'event': 'tampered'}) as state:
                state['runtime']['node_id'] = 'other-node'
        self.dashboard.sample()
        value = self.dashboard.view()
        self.assertEqual(value['campaigns'][0]['read_error']['code'], 'campaign_changed')
        op = self.dashboard.action('a'*64, 'pause')
        self.dashboard.threads[('a'*64, 'control')].join(5)
        self.assertEqual(self.dashboard.view()['campaigns'][0]['operations'][0]['error']['code'], 'campaign_changed')
        self.assertTrue(op['running'])

    def test_duplicate_copies_and_nested_history_refused(self):
        self.error('duplicate_campaign', lambda: Dashboard([self.workspace, self.workspace], self.base/'else'))
        self.error('invalid_command', lambda: Dashboard([self.workspace], self.workspace/'ui'))
        self.error('invalid_command', lambda: Dashboard([self.workspace], self.base/'node'/'ui'))
        self.error('invalid_command', lambda: Dashboard([self.workspace], self.base/'else', sample_seconds=float('nan')))

    def test_history_refuses_symlinks_and_an_unrelated_database(self):
        root = self.base/'other-ui';root.mkdir()
        path = root/'history.sqlite3'
        path.symlink_to(self.workspace/'campaign.sqlite3')
        self.error('invalid_history', lambda: History(root, 10))
        path.unlink()
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE important (value TEXT)')
            db.execute("INSERT INTO important VALUES ('keep')")
        self.error('invalid_history', lambda: History(root, 10))
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT value FROM important').fetchone()[0], 'keep')
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [('important',)])

    def test_inventory_never_fabricates_remote_observations(self):
        project = Path(__file__).resolve().parents[1]
        inventory = project/'examples/deployment/home-lab.json'
        with closing(Dashboard([self.workspace], self.base/'other-ui', deployment=inventory)) as dashboard:
            nodes = dashboard.view()['nodes']
            remote = [n for n in nodes if n['transport'] == 'ssh']
            self.assertEqual(len(remote), 6)
            self.assertTrue(all(not n['enabled'] and n['native_node_id'] is None and not n['campaign_ids'] for n in remote))
            self.assertTrue(all(dashboard.history_view(n['id'])['points'] == [] for n in remote))

    def test_disabled_inventory_does_not_mask_missing_campaign_state(self):
        project = Path(__file__).resolve().parents[1]
        inventory = json.loads((project/'examples/deployment/local.json').read_text())
        node = dict(inventory['nodes'][0], id='disabled-test', root=str(self.base/'node'), enabled=False)
        inventory['nodes'].append(node)
        path=self.base/'inventory.json';write_json(path,inventory)
        with closing(Dashboard([self.workspace],self.base/'other-ui',deployment=path)) as dashboard:
            (self.workspace/'campaign.sqlite3').rename(self.workspace/'saved.sqlite3')
            dashboard.sample()
            attached=next(n for n in dashboard.view()['nodes'] if n['campaign_ids'])
            self.assertFalse(attached['enabled'])
            self.assertIsNone(attached['counts'])
            self.assertIsNone(dashboard.history_view(attached['id'])['points'][-1]['counts'])

    def test_error_while_sampling_is_exposed_and_observer_recovers(self):
        with patch.object(self.dashboard, 'sample', side_effect=OSError('disk test')):
            self.dashboard.start()
            end = time.monotonic()+3
            while not self.dashboard.view()['monitor_error'] and time.monotonic()<end:
                time.sleep(.01)
            self.assertEqual(self.dashboard.view()['monitor_error']['message'], 'disk test')
        end = time.monotonic()+3
        while self.dashboard.view()['monitor_error'] and time.monotonic()<end:
            time.sleep(.01)
        self.assertIsNone(self.dashboard.view()['monitor_error'])

    def test_shutdown_waits_for_every_worker_and_refuses_new_actions(self):
        entered = [threading.Event(), threading.Event()]
        release = [threading.Event(), threading.Event()]
        order = iter(range(2))
        def slow_final_sample():
            i = next(order)
            entered[i].set()
            release[i].wait(5)
        with patch.object(self.dashboard, 'sample', side_effect=slow_final_sample):
            self.dashboard.action('a'*64, 'pause');self.assertTrue(entered[0].wait(3))
            self.dashboard.action('a'*64, 'pause');self.assertTrue(entered[1].wait(3))
            closer = threading.Thread(target=self.dashboard.close)
            closer.start()
            self.assertTrue(self.dashboard.stopping.wait(3))
            self.error('dashboard_stopping', lambda: self.dashboard.action('a'*64, 'pause'))
            release[1].set()
            time.sleep(.05)
            self.assertTrue(closer.is_alive(), 'the earlier operation must also finish')
            release[0].set();closer.join(5)
            self.assertFalse(closer.is_alive())
            self.assertEqual(self.dashboard.workers, set())


if __name__ == '__main__':
    unittest.main()


class PageMarkup(unittest.TestCase):
    def test_page_markup_parses_and_the_stop_dialog_can_confirm(self):
        from html.parser import HTMLParser
        import re
        text = (Path(__file__).resolve().parents[1] / 'experiment_craft/web/index.html').read_text()
        self.assertIsNone(re.search(r'</[A-Za-z]+\s[^>]*>', text), 'an end tag carries attributes')

        class Buttons(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack, self.dialog_buttons = [], []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'button' and any(t == 'dialog' for t, _ in self.stack):
                    self.dialog_buttons.append(attrs.get('value'))
                if tag not in ('meta', 'link', 'br', 'img', 'input'):
                    self.stack.append((tag, attrs))
            def handle_endtag(self, tag):
                self.assertion = self.stack and self.stack[-1][0] == tag
                if not self.assertion:
                    raise AssertionError(f'unbalanced </{tag}>')
                self.stack.pop()

        parser = Buttons()
        parser.feed(text)
        self.assertEqual(parser.stack, [])
        self.assertEqual(sorted(parser.dialog_buttons), ['cancel', 'stop'])
