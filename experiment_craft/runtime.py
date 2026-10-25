"""Thin local CLI/JSON client. The Rust runner supervises all workloads."""
import os
from pathlib import Path
import subprocess
import tempfile
from .storage import Error, MAX_JSON, fingerprint, loads, require

TERMINAL = {'completed', 'failed', 'cancelled', 'timed_out', 'interrupted'}


class Runtime:
    def __init__(self, runner, root, expected=None):
        self.runner = Path(runner).absolute()
        self.root = Path(root).resolve()
        require(self.root.is_dir(), 'node_unavailable', 'initialize the runtime node before creating a campaign')
        self.expected = expected

    def argv(self, *args):
        return [str(self.runner), '--json', '--root', str(self.root), *map(str, args)]

    @staticmethod
    def decode(code, stdout, stderr):
        require(len(stdout) <= MAX_JSON and len(stderr) <= MAX_JSON, 'runtime_protocol', 'CLI response exceeds 4 MiB')
        if code:
            try:
                error = loads(stderr)['error']
            except (Error, KeyError, TypeError):
                raise Error('runtime_error', f'CLI exited {code}: {stderr[:4096]!r}') from None
            raise Error(error.get('code', 'runtime_error'), error.get('message', 'runtime error'))
        return loads(stdout)

    def assert_node(self):
        if self.expected is not None:
            node = self.call('node', 'identity')
            require(node.get('node_id') == self.expected['node_id'] and node.get('root') == str(self.root),
                    'node_identity_mismatch', 'persistent node identity differs from the campaign binding')

    def call(self, *args):
        if args[:2] != ('node', 'identity'):
            try:
                self.assert_node()
            except Error as exc:
                if args and args[0] == 'submit':
                    raise Error('runtime_not_started', 'pre-launch identity check failed: ' + str(exc)) from exc
                raise
        # Disk files avoid inherited PIPE readers after a killed client.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                result = subprocess.run(self.argv(*args), stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err, timeout=60)
            except subprocess.TimeoutExpired as exc:
                raise Error('runtime_timeout', 'CLI acknowledgement timed out; observe the same handle') from exc
            except OSError as exc:
                raise Error('runtime_not_started' if args and args[0] == 'submit' else 'runtime_unavailable', str(exc)) from exc
            out.seek(0)
            err.seek(0)
            return self.decode(result.returncode, out.read(MAX_JSON + 1), err.read(MAX_JSON + 1))

    def binding(self, plan, mode):
        node = self.call('node', 'identity')
        require(node.get('schema_version') == 'execution.node.identity/0.1' and
                node.get('root') == str(self.root) and isinstance(node.get('node_id'), str),
                'runtime_protocol', 'persistent node identity is required')
        caps = self.call('node', 'capabilities')
        require(caps.get('schema_version') == 'execution.capabilities/0.3', 'unsupported_runtime', 'capabilities 0.3 required')
        if any(s['job']['schema_version'] == 'execution.command/0.1' for s in plan['steps']):
            require(caps.get('command_jobs') is True and 'OPTIMIZATION_RUN_REFUSE_COMMANDS' not in os.environ,
                    'commands_disabled', 'command jobs are disabled for this node/caller')
        doctor = self.call('node', 'doctor')
        if mode == 'systemd':
            # The runner hands systemd-run its resolved path, so check that one too.
            require('$' not in str(self.root) and '$' not in str(self.runner) and '$' not in str(self.runner.resolve()),
                    'invalid_runtime_root',
                    'systemd expands dollars in launcher arguments; choose a root/helper path without $')
            require(doctor.get('systemd_user_manager') is True, 'backend_unavailable',
                    'systemd user manager unavailable; foreground is an explicit local test mode')
        registry = self.call('workers', 'list')
        workers = {}
        for step in plan['steps']:
            job = step['job']
            require(job['resources']['cpu_slots'] <= doctor.get('capacity', 0), 'capacity_exceeded', 'step exceeds node capacity')
            if job['schema_version'] != 'optimization.job/0.1':
                continue
            name = job['worker']
            require(name in registry, 'unknown_worker', f'worker is not registered: {name}')
            item = registry[name]
            require(job['payload_schema'] in item['description']['profiles'], 'unsupported_profile', job['payload_schema'])
            require(fingerprint(item['executable'], 1024 ** 3)['sha256'] == item['digest'],
                    'worker_changed', 'registered worker bytes changed')
            workers[name] = {'digest': item['digest'], 'executable': item['executable'],
                             'build': item['description'].get('build')}
        return {'runner': str(self.runner), 'runner_file': fingerprint(self.runner, 1024 ** 3),
                'root': str(self.root), 'node_id': node['node_id'], 'mode': mode, 'workers': workers}

    def verify(self, plan):
        actual = self.binding(plan, self.expected['mode'])
        require(actual == self.expected, 'runtime_changed', 'runtime/node/worker binding changed; accepted jobs are not resubmitted')

    def get(self, job_id):
        value = self.call('jobs', 'get', job_id)
        expected = self.root / 'jobs' / job_id
        require(value.get('id') == job_id and Path(value.get('directory', '')).resolve() == expected,
                'runtime_protocol', 'unexpected local job handle/directory')
        return value

    def cancel(self, job_id):
        try:
            return self.call('jobs', 'cancel', job_id, '--now')
        except Error as exc:
            if exc.code == 'already_terminal':
                return None
            raise

    def foreground(self, spec, stdout, stderr):
        # No detached process group, worker launcher or termination policy here.
        # Signals and process supervision remain the runner's responsibility.
        try:
            self.assert_node()
        except Error as exc:
            raise Error('runtime_not_started', 'pre-launch identity check failed: ' + str(exc)) from exc
        try:
            return subprocess.Popen(self.argv('run', '--spec', spec), stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, close_fds=True)
        except OSError as exc:
            raise Error('runtime_not_started', str(exc)) from exc
