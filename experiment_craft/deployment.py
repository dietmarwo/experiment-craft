"""Offline inventory and literal native CLI plans; never probe or administer."""
from importlib.resources import files
from pathlib import Path
import re
import shutil
import tempfile

import jsonschema

from .storage import Error, identity, publish_directory, read_json, require, write_json

NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
SSH_HOST = re.compile(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z')
SSH_USER = re.compile(r'[A-Za-z_][A-Za-z0-9_-]{0,63}\Z')
SAFE_PATH = re.compile(r'/[A-Za-z0-9_./-]+\Z')


def absolute(value, safe=False):
    require(isinstance(value, str) and value.startswith('/') and len(value) > 1 and '\x00' not in value and
            '\n' not in value and '\r' not in value and all(p not in ['', '.', '..'] for p in value.split('/')[1:]),
            'invalid_deployment', 'deployment paths must be explicit absolute paths without traversal')
    require(not safe or SAFE_PATH.fullmatch(value), 'invalid_deployment', 'SSH helper/known-hosts paths require safe ASCII')


def load(path):
    try:
        value = read_json(path)
        schema = read_json(files('experiment_craft').joinpath('schemas/deployment-0.1.schema.json'))
        jsonschema.Draft202012Validator(schema).validate(value)
    except (OSError, Error, jsonschema.ValidationError) as exc:
        raise Error('invalid_deployment', str(exc)) from exc
    control = value['coordinator']
    absolute(control['runner']); absolute(control['root'])
    ids, endpoints, local_roots = set(), set(), set()
    for node in value['nodes']:
        require(NAME.fullmatch(node['id']) and node['id'] not in ids, 'invalid_deployment', 'duplicate or invalid node ID')
        ids.add(node['id'])
        require(type(node['declared']['cpu_slots']) is int, 'invalid_deployment', 'declared capacity must be an integer')
        root = node['root']
        absolute(root)
        if node['transport'] == 'local':
            require(node['role'] == 'test' and root not in local_roots,
                    'invalid_deployment', 'local nodes are distinct test roots, not desktop workers')
            local_roots.add(root)
            if node['mode'] == 'systemd':
                require('$' not in root and '$' not in control['runner'], 'invalid_deployment', 'systemd paths cannot contain $')
        else:
            require(node['role'] == 'worker' and SSH_HOST.fullmatch(node['host']) and SSH_USER.fullmatch(node['user']),
                    'invalid_deployment', 'invalid explicit SSH host/user')
            require(type(node['port']) is int and type(node['timeout_seconds']) is int,
                    'invalid_deployment', 'SSH port/timeout must be integers')
            absolute(node['helper'], safe=True); absolute(node['known_hosts'], safe=True)
            if node.get('identity_file') is not None:
                absolute(node['identity_file'])
            require('$' not in root, 'invalid_deployment', 'remote systemd root cannot contain $')
            endpoint = (node['host'].lower(), node['user'], node['port'], root)
            require(endpoint not in endpoints, 'invalid_deployment', 'duplicate SSH endpoint/root')
            endpoints.add(endpoint)
        worker_ids = set()
        for worker in node['workers']:
            require(NAME.fullmatch(worker['id']) and worker['id'] not in worker_ids,
                    'invalid_deployment', 'duplicate or invalid worker registration ID')
            absolute(worker['executable'])
            worker_ids.add(worker['id'])
    default = next((n for n in value['nodes'] if n['id'] == value['default_node']), None)
    require(default is not None and default['enabled'] and default['transport'] == 'local',
            'invalid_deployment', 'the default must be an enabled local test node')
    return value


def select(path, node_id=None, mode=None):
    value = load(path)
    node = next((n for n in value['nodes'] if n['id'] == (node_id or value['default_node'])), None)
    require(node is not None, 'unknown_node', 'node is not in the deployment inventory')
    require(node['enabled'], 'node_disabled', 'the planned node is disabled')
    require(node['transport'] == 'local', 'unsupported_placement',
            'campaigns currently target local nodes; export the plan for explicit native fleet registration')
    return Path(value['coordinator']['runner']), Path(node['root']), mode or node['mode'], node['allow_commands']


def plan(value):
    coordinator = value['coordinator']
    runner = coordinator['runner']
    nodes = []
    for node in value['nodes']:
        executable = runner if node['transport'] == 'local' else node['helper']
        admin = [executable, '--root', node['root']]
        setup = [admin + ['node', 'init', '--capacity', str(node['declared']['cpu_slots'])] +
                 (['--allow-commands'] if node['allow_commands'] else [])]
        setup += [admin + ['workers', 'add', '--id', w['id'], '--executable', w['executable']] for w in node['workers']]
        registration = None
        probe = None
        if node['transport'] == 'ssh':
            registration = [runner, '--root', coordinator['root'], 'fleet', 'nodes', 'add', node['id'],
                            '--host', node['host'], '--user', node['user'], '--port', str(node['port']),
                            '--remote-root', node['root'], '--helper', node['helper'],
                            '--known-hosts', node['known_hosts'], '--timeout-seconds', str(node['timeout_seconds'])]
            if node.get('identity_file'):
                registration += ['--identity-file', node['identity_file']]
            probe = [runner, '--root', coordinator['root'], 'fleet', 'nodes', 'probe', node['id']]
        nodes.append({'id': node['id'], 'transport': node['transport'], 'role': node['role'], 'enabled': node['enabled'],
                      'declared': node['declared'], 'setup_on_node': setup,
                      'register_on_coordinator': registration, 'probe_on_coordinator': probe})
    return {'schema_version': 'experiment.deployment.plan/0.1', 'deployment_id': identity(value),
            'default_node': value['default_node'], 'placement': 'explicit', 'validation': 'offline_structure_only',
            'runtime_contacted': False, 'commands_executed': False, 'nodes': nodes,
            'blocked_checks': ['real SSH node identity and user manager/linger', 'logout/reboot and containment',
                               'automatic allocation and durable backend group budgets']}


def export(path, destination):
    value = load(path)
    result = plan(value)
    destination = Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink(), 'destination_exists', 'deployment export needs a new directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.deployment-', dir=destination.parent))
    try:
        write_json(temp / 'deployment.json', value)
        write_json(temp / 'plan.json', result)
        (temp / 'README.md').write_text('''# Deployment preparation

This is an offline plan. No node was contacted, configured or commissioned.
The default is one local test node. Worker entries are explicit future endpoints;
disabled entries are templates, not activation instructions. Commands in plan.json
are literal argument arrays: setup_on_node runs on that node, while registration
and probing run on the coordinator through optimization-jobs. This export does
not execute them, enable automatic placement, copy SSH keys, accept host keys,
or prove resource enforcement. Read the operations/deployment guides and complete
the January commissioning gates before activating real workers.
''')
        publish_directory(temp, destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {'destination': str(destination), 'deployment_id': result['deployment_id'],
            'nodes': len(result['nodes']), 'runtime_contacted': False, 'commands_executed': False}
