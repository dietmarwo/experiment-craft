"""Local UI over existing campaign operations; history is observation, never authority."""
from contextlib import closing
import copy
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import math
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import stat
import sys
import threading
import time
from urllib.parse import urlsplit

from .campaign import ACTIVE, DONE, collect_now, drive, request_stop, summary
from .deployment import load as load_deployment
from .operations import pause, unpause
from .runtime import Runtime
from .storage import Error, Store, canonical, identity, loads, require

VERSION = 'experiment.dashboard/0.1'
STATES = ('pending', 'dispatching', 'active', 'unknown', 'succeeded', 'failed',
          'cancelled', 'blocked', 'budget_exhausted', 'stopped')
ACTIONS = ('continue', 'pause', 'unpause', 'stop', 'collect')
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}
HISTORY_APPLICATION_ID = 0x45434448


def failure(exc):
    return {'code': getattr(exc, 'code', 'dashboard_error'), 'message': str(exc)}


def read_campaign(path):
    """One consistent SQLite snapshot; no runtime call and no decision write."""
    with closing(Store(path)) as store:
        store.db.execute('BEGIN')
        try:
            state = store.read()
            maintenance = store.maintenance()
            recent = store.db.execute('SELECT seq,value FROM events ORDER BY seq DESC LIMIT 30').fetchall()
        finally:
            store.db.execute('ROLLBACK')
    steps = []
    counts = dict.fromkeys(STATES, 0)
    unresolved_slots = 0
    for step in state['plan']['steps']:
        saved = state['steps'][step['id']]
        require(saved['status'] in counts, 'unsupported_state', 'unrecognized step status')
        counts[saved['status']] += 1
        if saved['status'] in ACTIVE:
            unresolved_slots += step['job']['resources']['cpu_slots']
        steps.append({'id': step['id'], 'status': saved['status'], 'job_id': saved['job_id'],
                      'issued': saved['issued'], 'cpu_slots': step['job']['resources']['cpu_slots'],
                      'error': saved.get('error')})
    return {'id': state['campaign_id'], 'name': state['plan']['name'], 'workspace': str(path),
            'node_id': state['runtime']['node_id'], 'node_root': state['runtime']['root'],
            'mode': state['runtime']['mode'], 'created_at': state['created_at'],
            'summary': summary(state), 'maintenance': maintenance, 'steps': steps, 'counts': counts,
            'unresolved_declared_slots': unresolved_slots,
            'events': [{'seq': seq, **loads(value)} for seq, value in reversed(recent)],
            'read_error': None}


class History:
    """Bounded, disposable observation cache separate from campaign/native databases."""
    def __init__(self, root, limit):
        self.root, self.limit = root, limit
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ('dashboard.lock', 'history.sqlite3'):
            path = root/name
            require(not path.is_symlink() and (not path.exists() or stat.S_ISREG(path.stat().st_mode)),
                    'invalid_history', 'history files must be regular files, not symlinks')
        self.lock = (root / 'dashboard.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock.close()
            raise Error('dashboard_busy', 'another dashboard uses this history directory') from exc
        self.path = root / 'history.sqlite3'
        try:
            with closing(self.connect()) as db, db:
                version = db.execute('PRAGMA user_version').fetchone()[0]
                require(version in (0, 1), 'unsupported_history', 'unsupported dashboard history version')
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                application = db.execute('PRAGMA application_id').fetchone()[0]
                require((not tables and version == 0 and application == 0) or
                        (version == 1 and application == HISTORY_APPLICATION_ID),
                        'invalid_history', 'database is not a dashboard history cache')
                db.execute('CREATE TABLE IF NOT EXISTS samples (seq INTEGER PRIMARY KEY, scope TEXT NOT NULL, value TEXT NOT NULL)')
                db.execute('CREATE INDEX IF NOT EXISTS by_scope ON samples(scope,seq)')
                db.execute('PRAGMA user_version=1')
                db.execute(f'PRAGMA application_id={HISTORY_APPLICATION_ID}')
        except BaseException:
            self.close()
            raise
        self.previous = {}

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def append(self, scope, point):
        old = self.previous.get(scope)
        counts = {k: v for k, v in point.items() if k not in ('at', 'segment')}
        if old and old[0] == counts and 0 <= point['at'] - old[1] < 30:
            return
        with closing(self.connect()) as db, db:
            db.execute('INSERT INTO samples(scope,value) VALUES (?,?)', (scope, canonical(point).decode()))
            db.execute('DELETE FROM samples WHERE scope=? AND seq NOT IN '
                       '(SELECT seq FROM samples WHERE scope=? ORDER BY seq DESC LIMIT ?)',
                       (scope, scope, self.limit))
        self.previous[scope] = (counts, point['at'])

    def read(self, scope):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT value FROM samples WHERE scope=? ORDER BY seq DESC LIMIT ?',
                              (scope, self.limit)).fetchall()
        return [loads(row[0]) for row in reversed(rows)]

    def retain(self, scopes):
        # Only current node/campaign-set scopes are retained. Changing the set
        # starts a separate series, never a misleading continuation of totals.
        with closing(self.connect()) as db, db:
            marks = ','.join('?' for _ in scopes)
            db.execute(f'DELETE FROM samples WHERE scope NOT IN ({marks})', scopes)

    def close(self):
        self.lock.close()


class Dashboard:
    def __init__(self, workspaces, directory, deployment=None, sample_seconds=2, history_limit=2000):
        require(1 <= len(workspaces) <= 32, 'invalid_command', 'attach 1..32 initialized campaign workspaces')
        require(math.isfinite(sample_seconds) and .25 <= sample_seconds <= 60,
                'invalid_command', 'sample-seconds must be 0.25..60')
        require(type(history_limit) is int and 10 <= history_limit <= 10000,
                'invalid_command', 'history-limit must be 10..10000 points per node scope')
        paths = [Path(p).resolve() for p in workspaces]
        require(len(set(paths)) == len(paths), 'duplicate_campaign', 'duplicate workspace')
        initial = [read_campaign(path) for path in paths]
        ids = [c['id'] for c in initial]
        require(len(set(ids)) == len(ids), 'duplicate_campaign', 'do not attach two copies of one campaign')
        self.paths = dict(zip(ids, paths))
        self.bindings = {c['id']: (c['node_id'], c['node_root']) for c in initial}
        self.inventory = load_deployment(deployment) if deployment else None
        directory = Path(directory).resolve()
        # A UI cache must not become a campaign backup input or native artifact.
        for path in paths + [Path(c['node_root']).resolve() for c in initial]:
            require(not directory.is_relative_to(path) and not path.is_relative_to(directory),
                    'invalid_command', 'dashboard history must be separate from campaign and node trees')
        self.history = History(directory, history_limit)
        self.sample_seconds, self.history_limit = sample_seconds, history_limit
        self.segment = secrets.token_hex(16)
        self.token = secrets.token_urlsafe(32)
        self.stopping = threading.Event()
        self.mutex, self.sampling = threading.RLock(), threading.Lock()
        self.threads, self.operations = {}, {}
        self.workers = set()
        self.snapshot = {'schema_version': VERSION, 'sampled_at': time.time(), 'campaigns': initial, 'nodes': [],
                         'sample_seconds': sample_seconds, 'history_limit': history_limit, 'monitor_error': None}
        self.monitor = None
        try:
            self.sample()
            self.history.retain([n['scope'] for n in self.snapshot['nodes']])
        except BaseException:
            self.history.close()
            raise

    def nodes(self, campaigns):
        nodes = {}
        for campaign in campaigns:
            key = identity({'node_id': campaign['node_id'], 'root': campaign['node_root']})
            node = nodes.setdefault(key, {'id': key, 'name': 'Local ' + campaign['node_id'][:8],
                'native_node_id': campaign['node_id'], 'root': campaign['node_root'], 'transport': 'local',
                'enabled': True, 'declared_cpu_slots': None, 'availability': 'saved_state', 'campaign_ids': [],
                'counts': dict.fromkeys(STATES, 0), 'unresolved_declared_slots': 0})
            node['campaign_ids'].append(campaign['id'])
            if campaign['read_error']:
                node['availability'] = 'read_unavailable'
            for status, count in campaign['counts'].items():
                node['counts'][status] += count
            node['unresolved_declared_slots'] += campaign['unresolved_declared_slots']
        if self.inventory:
            for entry in self.inventory['nodes']:
                matching = [n for n in nodes.values() if entry['transport'] == 'local' and
                            Path(n['root']).resolve() == Path(entry['root']).resolve()]
                if not matching:
                    key = identity({'inventory': self.inventory, 'node': entry['id']})
                    matching = [{'id': key, 'native_node_id': None, 'root': entry['root'],
                        'transport': entry['transport'], 'availability': 'not_observed', 'campaign_ids': [],
                        'counts': dict.fromkeys(STATES, 0), 'unresolved_declared_slots': 0}]
                    nodes[key] = matching[0]
                for node in matching:
                    node.update(name=entry['id'], enabled=entry['enabled'],
                                declared_cpu_slots=entry['declared']['cpu_slots'])
                    if not entry['enabled']:
                        node['availability'] = 'disabled'
                    elif entry['transport'] == 'ssh':
                        node['availability'] = 'remote_unsupported'
        for node in nodes.values():
            node['campaign_ids'].sort()
            node['scope'] = identity({'node': node['id'], 'campaigns': node['campaign_ids']})
            if any(c['read_error'] and c['id'] in node['campaign_ids'] for c in campaigns):
                node['availability'] = 'read_unavailable'
                node['counts'] = None
                node['unresolved_declared_slots'] = None
        return list(nodes.values())

    def sample(self):
        with self.sampling:
            with self.mutex:
                previous = {c['id']: copy.deepcopy(c) for c in self.snapshot['campaigns']}
            campaigns = []
            for campaign_id, path in self.paths.items():
                try:
                    value = read_campaign(path)
                    require(value['id'] == campaign_id and
                            (value['node_id'], value['node_root']) == self.bindings[campaign_id],
                            'campaign_changed', 'attached workspace identity/binding changed; restart after inspection')
                except (Error, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    value = previous[campaign_id]
                    value['read_error'] = failure(exc)
                campaigns.append(value)
            nodes, now = self.nodes(campaigns), time.time()
            with self.mutex:
                if now < self.snapshot['sampled_at']:
                    self.segment = secrets.token_hex(16)  # never connect a backwards clock jump
            for node in nodes:
                if node['campaign_ids']:
                    self.history.append(node['scope'], {'at': now, 'segment': self.segment,
                        'counts': node['counts'], 'unresolved_declared_slots': node['unresolved_declared_slots']})
            with self.mutex:
                self.snapshot.update(sampled_at=now, campaigns=campaigns, nodes=nodes, monitor_error=None)

    def start(self):
        def poll():
            while not self.stopping.wait(self.sample_seconds):
                try:
                    self.sample()
                except Exception as exc:
                    with self.mutex:
                        self.snapshot['monitor_error'] = failure(exc)
        self.monitor = threading.Thread(target=poll, name='dashboard-observer', daemon=True)
        self.monitor.start()

    def view(self):
        with self.mutex:
            value = copy.deepcopy(self.snapshot)
            for campaign in value['campaigns']:
                campaign['operations'] = [copy.deepcopy(op) for (cid, _), op in self.operations.items()
                                          if cid == campaign['id']]
            return value

    def history_view(self, node_id):
        with self.mutex:
            node = next((n for n in self.snapshot['nodes'] if n['id'] == node_id), None)
            require(node is not None, 'unknown_node', 'node is not attached to this dashboard')
            scope, campaign_ids = node['scope'], node['campaign_ids']
        return {'schema_version': 'experiment.dashboard.history/0.1', 'node_id': node_id,
                'scope': scope, 'campaign_ids': campaign_ids, 'limit': self.history_limit,
                'points': self.history.read(scope)}

    def action(self, campaign_id, action):
        require(action in ACTIONS, 'invalid_action', 'unknown dashboard action')
        require(campaign_id in self.paths, 'unknown_campaign', 'campaign is not attached')
        # Control has a separate lane: pause and stop remain usable during a foreground run.
        lane = 'control' if action in ('pause', 'stop') else 'advance'
        key = (campaign_id, lane)
        with self.mutex:
            require(not self.stopping.is_set(), 'dashboard_stopping', 'dashboard is stopping')
            require(not self.operations.get(key, {}).get('running'), 'operation_busy', 'operation already in progress')
            op = {'id': secrets.token_hex(16), 'action': action, 'running': True,
                  'started_at': time.time(), 'finished_at': None, 'error': None}
            thread = threading.Thread(target=self.execute, args=(campaign_id, key, op), daemon=False)
            previous = self.operations.get(key), self.threads.get(key)
            self.operations[key], self.threads[key] = op, thread
            self.workers.add(thread)
            try:
                thread.start()
            except RuntimeError as exc:
                # A lane whose thread never started must not stay "running".
                self.workers.discard(thread)
                for table, old in ((self.operations, previous[0]), (self.threads, previous[1])):
                    if old is None:
                        table.pop(key, None)
                    else:
                        table[key] = old
                raise Error('dashboard_busy', f'cannot start the operation: {exc}') from None
            return copy.deepcopy(op)

    def execute(self, campaign_id, key, op):
        try:
            # Check identity again immediately before using the pre-attached path.
            current = read_campaign(self.paths[campaign_id])
            require(current['id'] == campaign_id and
                    (current['node_id'], current['node_root']) == self.bindings[campaign_id],
                    'campaign_changed', 'workspace identity/binding changed')
            with closing(Store(self.paths[campaign_id])) as store:
                action = op['action']
                if action == 'continue':
                    advanced = False
                    while not self.stopping.is_set():
                        try:
                            value = drive(store, once=True)
                        except Error as exc:
                            # A pause that arrives during advancement ends it
                            # normally. Continuing an already paused campaign
                            # is still refused with its error.
                            if exc.code == 'dispatch_paused' and advanced:
                                break
                            raise
                        advanced = True
                        self.sample()
                        if value['status'] in ('completed', 'incomplete', 'stopped', 'stopping', 'unknown'):
                            break
                        if self.stopping.wait(.2):
                            break
                elif action == 'pause':
                    pause(store, 'dashboard operator')
                elif action == 'unpause':
                    unpause(store)  # verifies saved identities/handles, does not dispatch
                elif action == 'stop':
                    request_stop(store)
                else:
                    collect_now(store)
        except Exception as exc:
            with self.mutex:
                op['error'] = failure(exc)
        finally:
            with self.mutex:
                op.update(running=False, finished_at=time.time())
            try:
                self.sample()
            except Exception as exc:
                with self.mutex:
                    self.snapshot['monitor_error'] = failure(exc)
            finally:
                with self.mutex:
                    self.workers.discard(threading.current_thread())

    def close(self):
        with self.mutex:
            self.stopping.set()
            workers = list(self.workers)
        if self.monitor:
            self.monitor.join()
        # Native supervision is unchanged. Graceful exit waits for an in-flight
        # call, stops between steps and neither cancels nor replays native work.
        for thread in workers:
            thread.join()
        errors = []
        try:
            # Close every UI reader/writer before checkpointing and truncating
            # WAL. A busy external reader retains it and is reported below.
            for campaign_id, path in self.paths.items():
                try:
                    with closing(Store(path)) as store:
                        state = store.read()
                        require(state['campaign_id'] == campaign_id and
                                (state['runtime']['node_id'], state['runtime']['root']) == self.bindings[campaign_id],
                                'campaign_changed', 'workspace binding changed before dashboard shutdown')
                        checkpoint = store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                        require(checkpoint[0] == 0, 'checkpoint_busy',
                                'another SQLite client retained WAL pages; keep the complete workspace')
                except (Error, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    errors.append({'campaign_id': campaign_id, **failure(exc)})
        finally:
            self.history.close()
        return errors


class Server(ThreadingHTTPServer):
    daemon_threads = False

    def __init__(self, dashboard, port=8765):
        require(type(port) is int and 0 <= port <= 65535, 'invalid_command', 'port must be 0..65535')
        self.dashboard = dashboard
        self.active, self.active_lock = set(), threading.Lock()
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(5)
        with self.active_lock:
            self.active.add(sock)
        return sock, address

    def shutdown_request(self, request):
        with self.active_lock:
            self.active.discard(request)
        super().shutdown_request(request)

    def handle_error(self, request, client_address):
        # A client that disconnects, or is dropped at shutdown, needs no traceback.
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            super().handle_error(request, client_address)

    def drop_requests(self):
        """End open connections, so that a slow client cannot hold up shutdown."""
        with self.active_lock:
            sockets = list(self.active)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class Handler(BaseHTTPRequestHandler):
    server_version = 'experiment-craft'

    def log_message(self, *args):
        pass  # no URLs, authorization tokens or campaign data in access logs

    def reply(self, code, body, content_type='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else canonical(body)
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def handle_api(self, post=False):
        try:
            origin = self.server.origin
            require(self.headers.get_all('Host') == [urlsplit(origin).netloc],
                    'forbidden', 'use the printed 127.0.0.1 URL')
            require(not urlsplit(self.path).query, 'invalid_command', 'query parameters are not supported')
            path = urlsplit(self.path).path
            if not post and path in ASSETS:
                name, mime = ASSETS[path]
                return self.reply(200, files('experiment_craft').joinpath('web', name).read_bytes(), mime)
            token = self.headers.get('Authorization', '')
            require(secrets.compare_digest(token, 'Bearer ' + self.server.dashboard.token),
                    'unauthorized', 'open the URL printed by the dashboard command')
            if post:
                require(self.headers.get_all('Origin') == [origin], 'forbidden', 'same-origin control required')
                require(self.headers.get_all('Content-Type') == ['application/json'],
                        'invalid_command', 'send application/json')
                lengths = self.headers.get_all('Content-Length') or []
                require(len(lengths) == 1 and lengths[0].isdigit() and int(lengths[0]) <= 1024 and
                        not self.headers.get('Transfer-Encoding'), 'size_limit', 'control body must be at most 1024 bytes')
                require(loads(self.rfile.read(int(lengths[0]))) == {}, 'invalid_command', 'control body must be {}')
                parts = path.split('/')
                require(len(parts) == 5 and parts[1:3] == ['api', 'campaigns'], 'not_found', 'unknown endpoint')
                return self.reply(202, self.server.dashboard.action(parts[3], parts[4]))
            if path == '/api/snapshot':
                return self.reply(200, self.server.dashboard.view())
            if path.startswith('/api/history/') and len(path.split('/')) == 4:
                return self.reply(200, self.server.dashboard.history_view(path.split('/')[-1]))
            raise Error('not_found', 'unknown endpoint')
        except (Error, OSError, ValueError, TypeError, sqlite3.Error) as exc:
            code = getattr(exc, 'code', 'dashboard_error')
            status = {'unauthorized': 401, 'forbidden': 403, 'not_found': 404,
                      'unknown_node': 404, 'unknown_campaign': 404, 'operation_busy': 409}.get(code, 400)
            self.reply(status, {'error': failure(exc)})

    def do_GET(self):
        try:
            self.handle_api()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def do_POST(self):
        try:
            self.handle_api(post=True)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass


def interrupt(signum, frame):
    raise KeyboardInterrupt  # SIGTERM shuts down like Ctrl-C


def serve(workspaces, directory, deployment=None, port=8765, sample_seconds=2, history_limit=2000):
    dashboard = Dashboard(workspaces, directory, deployment, sample_seconds, history_limit)
    # A terminal's Ctrl-C reaches the whole foreground process group. Runner
    # calls get their own session, so it stops the dashboard between steps
    # instead of cancelling the job in flight; Stop remains the way to cancel.
    isolated, Runtime.isolate = Runtime.isolate, True
    main = threading.current_thread() is threading.main_thread()
    previous = signal.signal(signal.SIGTERM, interrupt) if main else None
    try:
        with Server(dashboard, port) as server:
            dashboard.start()
            print(canonical({'status': 'dashboard_listening', 'url': server.origin + '/#token=' + dashboard.token,
                             'workspaces': len(workspaces), 'history_directory': str(dashboard.history.root)}).decode(), flush=True)
            try:
                server.serve_forever(poll_interval=.2)
            except KeyboardInterrupt:
                pass
            finally:
                # Advancement stops between steps from here on, new actions are
                # refused, and open connections cannot hold the process.
                dashboard.stopping.set()
                server.drop_requests()
    finally:
        errors = dashboard.close()
        Runtime.isolate = isolated
        if main:
            signal.signal(signal.SIGTERM, previous)
    return {'status': 'dashboard_stopped', 'checkpoint_errors': errors}
