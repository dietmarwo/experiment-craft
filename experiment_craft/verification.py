"""Offline views of application-reported verification; never run a checker or submit work."""
import csv
import hashlib
from importlib.resources import files
import io
from pathlib import Path

import jsonschema

from .artifacts import input_bytes, native_result, output_bytes, output_info, step_state
from .campaign import summary
from .comparison_report import cell, publish
from .storage import Error, MAX_FILE, MAX_JSON, canonical, identity, loads, read_json, require

INPUTS = {'problem': 'problem.json', 'study': 'study.json', 'candidates': 'candidates.json',
          'evaluations': 'evaluations.jsonl', 'search_protocol': 'protocol.json'}
# The arguments that fcmaes-rust's make_audit_campaign.py gives `audit.py run` and `accept`.
COMMON = ['--problem', 'problem.json', '--study', 'study.json', '--candidates', 'candidates.json',
          '--evaluations', 'evaluations.jsonl', '--search-protocol', 'protocol.json',
          '--project', 'project', '--protocol', 'audit-protocol.json']
CHECKER = ('app/audit.py', 'app/schemas/cap-audit-0.1.schema.json', 'app/schemas/cap-artifacts-0.1.schema.json',
           'app/schemas/cap-search-0.1.schema.json')
SEARCHED = {'study.json': 'out/study.json', 'candidates.json': 'out/candidates.json',
            'evaluations.jsonl': 'out/evaluations.jsonl'}


def validate(value, definition):
    document = read_json(files('experiment_craft').joinpath('schemas/verification-cap-0.1.schema.json'))
    try:
        jsonschema.Draft202012Validator({'$ref': '#/$defs/' + definition, **document}).validate(value)
    except jsonschema.ValidationError as exc:
        raise Error('invalid_verification', exc.message) from exc


def provenance(state, step_id, output):
    """The receipt must come from the application's `accept` over the outputs of
    its own `audit.py run` step, which audited the outputs of one search step.

    Without this, any command that exits 0 and writes a matching receipt over
    literal inputs would be reported as accepted. The plan, not a runtime call,
    shows which commands ran.
    """
    jobs = {step['id']: step['job'] for step in state['plan']['steps']}

    def inputs(job):
        return {item['path']: item for item in job.get('inputs', [])}

    def source(item):
        return item['from'] if 'from' in item else {'bytes': item.get('bytes'), 'sha256': item.get('sha256')}

    def produced(item, paths):
        reference = (item or {}).get('from')
        require(isinstance(reference, dict) and reference.get('kind') == 'output' and reference.get('step') in jobs,
                'unsupported_verification', 'an audit or search input is not the output of a campaign step')
        outputs = {value['name']: value['path'] for value in jobs[reference['step']].get('outputs', [])}
        require(outputs.get(reference['output']) == paths, 'unsupported_verification',
                'an audit or search input is not the expected output of its step')
        return reference['step']

    accept = jobs[step_id]
    declared = {item['name']: item['path'] for item in accept.get('outputs', [])}
    require(accept.get('argv', [])[1:] == ['app/audit.py', 'accept', *COMMON, '--audit', 'audit.json',
                                           '--events', 'events.jsonl', '--output', declared.get(output)],
            'unsupported_verification', "the receipt is not written by the application's accept command")
    accepted = inputs(accept)
    require(all(path in accepted for path in (*CHECKER, 'problem.json', 'protocol.json', 'audit-protocol.json')),
            'unsupported_verification', 'the acceptance step lacks an application input')
    auditor = {produced(accepted.get('audit.json'), 'out/audit.json'),
               produced(accepted.get('events.jsonl'), 'out/events.jsonl')}
    require(len(auditor) == 1, 'unsupported_verification', 'the audit and its ledger come from different steps')
    collector = jobs[auditor.pop()]
    argv = collector.get('argv', [])
    require(argv[1:3 + len(COMMON)] == ['app/audit.py', 'run', *COMMON] and len(argv) == len(COMMON) + 7
            and argv[-4] == '--julia' and argv[-2:] == ['--output', 'out'],
            'unsupported_verification', "the audit is not written by the application's run command")
    collected = inputs(collector)
    shared = (*CHECKER, 'problem.json', 'protocol.json', 'audit-protocol.json', *SEARCHED)
    require(all(path in collected and source(collected[path]) == source(accepted[path]) for path in shared),
            'unsupported_verification', 'the audit and the acceptance read different inputs')
    searcher = {produced(accepted.get(path), output_path) for path, output_path in SEARCHED.items()}
    require(len(searcher) == 1, 'unsupported_verification', 'the search outputs come from different steps')
    search = jobs[searcher.pop()]
    flags = search.get('argv', [])[1:]
    flags = dict(zip(flags[::2], flags[1::2])) if len(flags) % 2 == 0 else {}
    searched = inputs(search)
    require(all(flags.get(flag) == value for flag, value in (('--problem', 'problem.json'), ('--protocol', 'protocol.json'),
                                                             ('--output', 'out')))
            and all(path in searched and source(searched[path]) == source(accepted[path])
                    for path in ('problem.json', 'protocol.json')),
            'unsupported_verification', 'the search did not use the audited problem and protocol')


def embedded(value, expected_kind, problem_sha, candidate_sha):
    require(isinstance(value, dict) and set(value) == {'sha256', 'json'} and isinstance(value['json'], str),
            'invalid_verification', 'missing stage document')
    data = value['json'].encode('utf-8')
    require(len(data) <= 256 * 1024 and hashlib.sha256(data).hexdigest() == value['sha256'],
            'verification_mismatch', 'stage document digest mismatch')
    document = loads(data)
    require(isinstance(document, dict) and document.get('schema_version') == expected_kind
            and document.get('problem_sha256') == problem_sha and document.get('candidate_sha256') == candidate_sha,
            'verification_mismatch', 'stage document subject mismatch')
    return document


def cap_audit(store, state, step_id, receipt, native):
    """Validate the fields displayed by this adapter against the admitted inputs.

    This is not CAPReference or audit.py accept. The admitted acceptance command
    remains the authority for its verdict, and its original artifacts are retained.
    """
    validate(receipt, 'receipt')
    raw, metadata = {}, {}
    for role, path in {**INPUTS, 'audit': 'audit.json', 'events': 'events.jsonl',
                       'audit_protocol': 'audit-protocol.json'}.items():
        raw[role], metadata[role] = input_bytes(store, state, step_id, path)
    require(receipt['inputs'] == {key: metadata[key]['sha256'] for key in INPUTS}
            and receipt['audit_sha256'] == metadata['audit']['sha256']
            and receipt['protocol_sha256'] == metadata['audit_protocol']['sha256'],
            'verification_mismatch', 'receipt differs from the acceptance command inputs')
    problem, study, bundle, protocol, audit = (loads(raw[key]) for key in ('problem', 'study', 'candidates', 'search_protocol', 'audit'))
    audit_protocol = loads(raw['audit_protocol'])
    validate(problem, 'problem')
    require(isinstance(study, dict) and study.get('schema_version') == 'cap.search.study/0.1'
            and study.get('outcome') == 'completed' and study.get('certification_performed') is False
            and study.get('problem_sha256') == metadata['problem']['sha256']
            and study.get('problem_id') == problem['id']
            and study.get('protocol_sha256') == metadata['search_protocol']['sha256']
            and canonical(study.get('protocol')) == canonical(protocol)
            and study.get('evaluation_log_sha256') == metadata['evaluations']['sha256'],
            'verification_mismatch', 'search study differs from the admitted problem/protocol/ledger')
    require(isinstance(audit, dict) and audit.get('schema_version') == 'cap.audit/0.1'
            and audit.get('inputs') == receipt['inputs'] and audit.get('complete') is receipt['complete']
            and audit.get('protocol_sha256') == receipt['protocol_sha256']
            and canonical(audit.get('protocol')) == canonical(audit_protocol)
            and audit.get('events_sha256') == metadata['events']['sha256']
            and audit_protocol.get('schema_version') == 'cap.audit.protocol/0.1'
            and audit_protocol.get('scope') == 'final-candidates-only'
            and audit_protocol.get('acceptance') == 'all-arms-verified-and-replayed',
            'verification_mismatch', 'audit differs from the acceptance input chain')
    implementation = audit.get('implementation')
    require(isinstance(implementation, dict) and set(implementation) == {
        'audit.py', 'schemas/cap-audit-0.1.schema.json', 'schemas/cap-artifacts-0.1.schema.json',
        'schemas/cap-search-0.1.schema.json'}, 'invalid_verification', 'unsupported audit implementation identity')
    for name, digest in implementation.items():
        _, meta = input_bytes(store, state, step_id, 'app/' + name, MAX_JSON)
        require(meta['sha256'] == digest, 'verification_mismatch', 'admitted checker source differs from the audit')
    require(isinstance(bundle, dict) and bundle.get('schema_version') == 'cap.search.candidates/0.1'
            and isinstance(bundle.get('arms'), dict), 'invalid_verification', 'missing candidate bundle')
    require(isinstance(protocol, dict) and protocol.get('schema_version') == 'cap.search.protocol/0.1'
            and isinstance(protocol.get('arms'), list), 'invalid_verification', 'missing search arms')
    declared = protocol['arms']
    require(6 <= len(declared) <= 16, 'invalid_verification', 'expected 6..16 declared arms')
    for arm in declared:
        validate(arm, 'declared_arm')
    ids = [arm['id'] for arm in declared]
    require(len(ids) == len(set(ids)) and set(bundle['arms']) == set(ids)
            and [arm.get('id') for arm in study.get('arms', [])] == ids
            and [arm.get('id') for arm in audit.get('arms', [])] == ids
            and [arm['arm'] for arm in receipt['observations']] == ids,
            'verification_mismatch', 'missing, foreign, duplicated or reordered verification arm')
    require(type(study.get('startup_wall_seconds')) in (int, float) and study['startup_wall_seconds'] >= 0,
            'invalid_verification', 'missing search startup cost')
    rows = []
    for declared_arm, search, checked, observation in zip(declared, study['arms'], audit['arms'], receipt['observations']):
        validate(search, 'search_arm')
        require(all(search[key] == declared_arm[key] for key in ('id', 'method', 'seed')),
                'verification_mismatch', 'search arm configuration changed')
        item = bundle['arms'][search['id']]
        require(isinstance(item, dict) and isinstance(item.get('candidate_json'), str),
                'invalid_verification', 'missing candidate bytes')
        candidate = item['candidate_json'].encode('utf-8')
        digest = hashlib.sha256(candidate).hexdigest()
        require(len(candidate) <= MAX_JSON and digest == item.get('candidate_sha256') == search['candidate_sha256']
                == checked.get('candidate_sha256'), 'verification_mismatch', 'candidate identity changed')
        candidate_value = loads(candidate)
        require(candidate_value.get('schema_version') == 'cap.candidate/0.1'
                and candidate_value.get('problem_sha256') == metadata['problem']['sha256']
                and candidate_value.get('problem_id') == problem['id'],
                'verification_mismatch', 'candidate belongs to another problem')
        stages = {}
        documents = {}
        for name in ('verification', 'replay'):
            stage = checked.get(name)
            validate(stage, 'stage')
            require(stage['wall_limit_seconds'] == audit_protocol.get(name + '_wall_seconds'),
                    'verification_mismatch', 'displayed stage budget differs from the audit protocol')
            outcome, document_sha = None, None
            if stage['status'] == 'completed':
                kind = 'cap.verification/0.1' if name == 'verification' else 'cap.replay/0.1'
                document = embedded(stage['document'], kind, metadata['problem']['sha256'], digest)
                require(document.get('problem_id') == problem['id'] and stage['wall_seconds'] <= stage['wall_limit_seconds'],
                        'verification_mismatch', 'reported completed stage has the wrong subject or exceeds its budget')
                allowed = ('verified', 'inconclusive') if name == 'verification' else ('verified', 'rejected')
                require(document.get('outcome') in allowed, 'invalid_verification', 'unknown reported verdict')
                outcome, document_sha = document['outcome'], stage['document']['sha256']
                documents[name] = document
            else:
                require(stage['document'] is None, 'invalid_verification', 'failed stage carries a trusted document')
            stages[name] = {'status': stage['status'], 'outcome': outcome, 'document_sha256': document_sha,
                            'wall_seconds': stage['wall_seconds'], 'wall_limit_seconds': stage['wall_limit_seconds']}
        if 'replay' in documents:
            require('verification' in documents and documents['replay'].get('certificate_sha256') == stages['verification']['document_sha256'],
                    'verification_mismatch', 'replay is not bound to this certificate')
        event = all(stages[name]['status'] == 'completed' and stages[name]['outcome'] == 'verified'
                    for name in ('verification', 'replay'))
        seconds = study['startup_wall_seconds'] + search['warm_wall_seconds'] + sum(stages[name]['wall_seconds'] for name in ('verification', 'replay'))
        reason = 'accepted' if event else '/'.join(stages[name]['outcome'] or stages[name]['status'] for name in ('verification', 'replay'))
        require(observation['event'] is event and observation['right_censored'] is not event
                and observation['observed_seconds'] == seconds and observation['reason'] == reason,
                'verification_mismatch', 'reported observation contradicts the stages/costs')
        rows.append({'arm': search['id'], 'method': search['method'], 'seed': search['seed'],
                     'candidate_sha256': digest, 'estimated_score': search['best']['score'],
                     **stages, 'observation': observation})
    count = sum(row['observation']['event'] for row in rows)
    require(receipt['total_arms'] == len(ids) and receipt['accepted_arms'] == count
            and receipt['outcome'] == ('accepted' if receipt['complete'] and count == len(ids) else 'rejected'),
            'verification_mismatch', 'receipt totals/outcome contradict its observations')
    process = native.get('process') or {}
    expected_state, expected_code = ('completed', 0) if receipt['outcome'] == 'accepted' else ('failed', 3)
    entry = state['steps'][step_id]
    expected_status = 'succeeded' if receipt['outcome'] == 'accepted' else 'failed'
    consistent = (native['state'] == expected_state and process.get('code') == expected_code
                  and process.get('signal') is None and not native.get('output_errors')
                  and entry['status'] == expected_status and isinstance(entry.get('execution_identity'), str))
    return {'status': ('reported_' + receipt['outcome']) if consistent else 'unconfirmed',
            'reported_outcome': receipt['outcome'], 'execution_consistent': consistent,
            'subject': problem, 'summary': {'total_arms': len(ids), 'reported_accepted_arms': count,
                                          'right_censored_arms': len(ids) - count, 'audit_complete': receipt['complete']},
            'arms': rows, 'input_hashes': {key: item['sha256'] for key, item in metadata.items()},
            'checker_inputs': implementation}


def build(store, step_id, output='acceptance', adapter='cap.audit/0.1'):
    require(adapter == 'cap.audit/0.1', 'unsupported_verification', 'supported adapter: cap.audit/0.1')
    state = store.read()
    _, entry = step_state(store, state, step_id)
    info = output_info(store, state, step_id, output)
    provenance(state, step_id, output)
    native = native_result(store, entry, step_id)
    value = {'schema_version': 'experiment.verification.report/0.1', 'adapter': adapter,
             'campaign': summary(state), 'plan_id': state['plan']['plan_id'],
             'source': {'step': step_id, 'job_id': entry['job_id'], 'step_status': entry['status'],
                        'execution_identity': entry.get('execution_identity'), 'artifact': info,
                        'native_process': native.get('process') if native else None},
             'status': 'unavailable', 'reported_outcome': None, 'execution_consistent': None,
             'subject': None, 'summary': None, 'arms': [], 'input_hashes': {}, 'checker_inputs': {},
             'interpretation': [
                 'Application-reported verification and replay, bound to admitted inputs and a sealed native output. This report does not run a checker or prove a theorem.',
                 'Final-candidate observations only. Censoring can be informative; no survival estimate, successful-only median, ranking or optimizer advantage is inferred.',
                 'Native command state and reported scientific verdict remain separate. Unconfirmed or unavailable evidence is not accepted.']}
    if info['availability'] not in ('pending', 'unavailable'):
        data, _ = output_bytes(store, state, step_id, output, MAX_JSON)
        try:
            value.update(cap_audit(store, state, step_id, loads(data), native))
        except Error:
            raise
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
            raise Error('invalid_verification', f'malformed CAP audit evidence: {exc}') from exc
    return value


def render(value):
    """The same checked bytes for CLI publication and explicit dashboard downloads."""
    text = ['# Recorded certificate audit', '', 'Status: `' + value['status'] + '`.', '',
            'Native campaign status: `' + value['campaign']['status'] + '`.', '',
            'Native acceptance-step state: `' + str(value['source']['artifact']['native_state']) + '`.', '',
            '| Arm | Method | Seed | Verification | Replay | Reported certificate | Accounted seconds |',
            '| --- | --- | ---: | --- | --- | --- | ---: |']
    stream = io.StringIO()
    writer = csv.DictWriter(stream, lineterminator='\n', fieldnames=['arm', 'method', 'seed', 'candidate_sha256',
        'verification_status', 'verification_outcome', 'replay_status', 'replay_outcome', 'event', 'right_censored', 'observed_seconds', 'reason'])
    writer.writeheader()
    for row in value['arms']:
        observation = row['observation']
        stages = [row[name]['outcome'] or row[name]['status'] for name in ('verification', 'replay')]
        text.append('| ' + ' | '.join(cell(item) for item in [row['arm'], row['method'], row['seed'], *stages,
            'yes' if observation['event'] else 'no', observation['observed_seconds']]) + ' |')
        writer.writerow({key: row[key] for key in ('arm', 'method', 'seed', 'candidate_sha256')} | {
            'verification_status': row['verification']['status'], 'verification_outcome': row['verification']['outcome'],
            'replay_status': row['replay']['status'], 'replay_outcome': row['replay']['outcome'],
            **{key: observation[key] for key in ('event', 'right_censored', 'observed_seconds', 'reason')}})
    if value['summary'] is None:
        text += ['', 'No retained acceptance observation is available; arm counts and costs are unknown.']
    text += ['', *value['interpretation'], '']
    document = read_json(files('experiment_craft').joinpath('schemas/verification-report-0.1.schema.json'))
    try:
        jsonschema.Draft202012Validator(document).validate(value)
    except jsonschema.ValidationError as exc:
        raise Error('invalid_verification', exc.message) from exc
    return {'verification.json': canonical(value) + b'\n', 'verification.md': '\n'.join(text).encode(),
            'observations.csv': stream.getvalue().encode()}


def report(store, destination, step_id, output='acceptance', adapter='cap.audit/0.1'):
    value = build(store, step_id, output, adapter)
    destination = Path(destination).absolute()
    for authority in (store.root, Path(store.read()['runtime']['root']).resolve()):
        require(not destination.resolve().is_relative_to(authority) and not authority.is_relative_to(destination.resolve()),
                'invalid_destination', 'keep verification reports outside campaign and native node roots')
    publish(destination, render(value),
            report_files=('verification.json', 'verification.md', 'observations.csv'))
    return {'verification': str(destination / 'verification.json'), 'sha256': identity(value), 'status': value['status']}
