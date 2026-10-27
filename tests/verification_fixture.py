"""Recorded scalar documents plus synthetic reporting metadata, not a new proof run."""
import copy
import hashlib
import json
from pathlib import Path
import sys

from test_campaign import command

FIXTURE = Path(__file__).parent / 'fixtures/verification'


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs(rejected=False):
    problem = (FIXTURE / 'problem.json').read_bytes()
    candidate = (FIXTURE / 'candidate.json').read_bytes()
    protocol = {'schema_version': 'cap.search.protocol/0.1', 'evaluation_budget': 9, 'arms': [
        {'id': method, 'method': method, 'seed': 0} for method in ('reference', 'grid', 'local', 'random', 'cmaes', 'biteopt')]}
    policy = {'schema_version': 'cap.audit.protocol/0.1', 'scope': 'final-candidates-only',
              'acceptance': 'all-arms-verified-and-replayed', 'verification_wall_seconds': 120, 'replay_wall_seconds': 120}
    raw = {'problem.json': problem, 'protocol.json': encode(protocol), 'audit-protocol.json': encode(policy),
           'evaluations.jsonl': b'fixture search ledger\n', 'events.jsonl': b'fixture audit ledger\n'}
    implementation = {}
    for name in ('audit.py', 'schemas/cap-audit-0.1.schema.json', 'schemas/cap-artifacts-0.1.schema.json', 'schemas/cap-search-0.1.schema.json'):
        data = ('fixture checker input: ' + name + '\n').encode()
        raw['app/' + name] = data
        implementation[name] = sha(data)
    study = {'schema_version': 'cap.search.study/0.1', 'outcome': 'completed', 'certification_performed': False,
        'problem_id': 'scalar-cuberoot', 'problem_sha256': sha(problem), 'protocol': protocol,
        'protocol_sha256': sha(raw['protocol.json']), 'evaluation_log_sha256': sha(raw['evaluations.jsonl']),
        'startup_wall_seconds': 1.0, 'arms': []}
    bundle = {'schema_version': 'cap.search.candidates/0.1', 'arms': {}}
    audited, observations = [], []
    for index, arm in enumerate(protocol['arms']):
        study['arms'].append({**arm, 'candidate_sha256': sha(candidate), 'warm_wall_seconds': .5,
            'best': {'evaluations': 1 if arm['method'] == 'reference' else 9, 'parameters': [1.0], 'score': -.99}})
        bundle['arms'][arm['id']] = {'candidate_sha256': sha(candidate), 'candidate_json': candidate.decode()}
        verification = json.loads((FIXTURE / 'verification.json').read_bytes())
        verification['elapsed_seconds'] = .101 + index / 1000
        replay = json.loads((FIXTURE / 'replay.json').read_bytes())
        replay['elapsed_seconds'] = .201 + index / 1000
        replay['recomputed']['elapsed_seconds'] = .301 + index / 1000
        if rejected and index == 0:
            verification['outcome'] = 'inconclusive'
            replay['outcome'] = 'rejected'
        vdata = encode(verification)
        replay['certificate_sha256'] = sha(vdata)
        stages = {}
        for stage, data in [('verification', vdata), ('replay', encode(replay))]:
            stages[stage] = {'status': 'completed', 'wall_seconds': .25, 'wall_limit_seconds': 120,
                'pid': 100 + 2 * index + (stage == 'replay'), 'returncode': 3 if rejected and index == 0 and stage == 'replay' else 0,
                'document': {'sha256': sha(data), 'json': data.decode()}, 'error': None, 'stdout': '', 'stderr': ''}
        audited.append({'id': arm['id'], 'candidate_sha256': sha(candidate), **stages})
        hit = not (rejected and index == 0)
        observations.append({'arm': arm['id'], 'event': hit, 'right_censored': not hit, 'observed_seconds': 2.0,
                             'reason': 'accepted' if hit else 'inconclusive/rejected'})
    raw['study.json'], raw['candidates.json'] = encode(study), encode(bundle)
    hashes = {name: sha(raw[path]) for name, path in {'problem':'problem.json', 'study':'study.json',
        'candidates':'candidates.json', 'evaluations':'evaluations.jsonl', 'search_protocol':'protocol.json'}.items()}
    audit = {'schema_version': 'cap.audit/0.1', 'inputs': hashes, 'protocol': policy,
        'protocol_sha256': sha(raw['audit-protocol.json']), 'implementation': implementation, 'complete': True,
        'total_wall_seconds': 4.0, 'events_sha256': sha(raw['events.jsonl']), 'arms': audited}
    raw['audit.json'] = encode(audit)
    receipt = {'schema_version': 'cap.audit.acceptance/0.1', 'inputs': hashes,
        'audit_sha256': sha(raw['audit.json']), 'protocol_sha256': sha(raw['audit-protocol.json']),
        'outcome': 'rejected' if rejected else 'accepted', 'complete': True,
        'accepted_arms': 5 if rejected else 6, 'total_arms': 6, 'observations': observations}
    return raw, receipt


def job(base, rejected=False, code=None):
    """A real command that copies a fixture receipt, without running its checker inputs."""
    raw, receipt = inputs(rejected)
    raw['receipt-source.json'] = encode(receipt)
    specification = command([sys.executable, '-c',
        "from pathlib import Path; import sys; Path('out').mkdir(exist_ok=True); "
        "Path('out/acceptance.json').write_bytes(Path('receipt-source.json').read_bytes()); "
        f"sys.exit({3 if rejected else 0 if code is None else code})"])
    if code is not None:
        specification['argv'][-1] = specification['argv'][-1].rsplit('sys.exit(', 1)[0] + f'sys.exit({code})'
    specification['inputs'] = []
    for index, (path, data) in enumerate(raw.items()):
        source = Path(base) / ('input-' + str(index))
        source.write_bytes(data)
        specification['inputs'].append({'path': path, 'file': source.name})
    specification['outputs'] = [{'name': 'acceptance', 'path': 'out/acceptance.json', 'max_bytes': 1048576, 'required': True}]
    return specification
