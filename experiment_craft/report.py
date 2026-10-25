"""Reports inspect retained evidence and never contact the runtime."""
import csv
import io
from .campaign import cached_native, summary
from .storage import atomic, canonical, identity, write_json


def snapshot(store, state=None):
    """A consistent state snapshot and its checked native bytes, with no writes."""
    state = store.read() if state is None else state
    rows = []
    for step in state['plan']['steps']:
        entry = state['steps'][step['id']]
        row = {'step': step['id'], 'template': step['template'], 'axes': step['axes'],
               'status': entry['status'], 'job_id': entry['job_id'],
               'job_state': entry.get('observation', {}).get('state'),
               'kind': 'command' if step['job']['schema_version'] == 'execution.command/0.1' else 'optimization',
               'worker': step['job'].get('worker'), 'payload_schema': step['job'].get('payload_schema'),
               'acceptance': step['accept'], 'error': entry.get('error'), 'native': None}
        if entry.get('native'):
            row['native'] = cached_native(store, entry)
        rows.append(row)
    return {'schema_version': 'experiment.campaign.report/0.1', 'campaign': summary(state),
             'provenance': {'plan_id': state['plan']['plan_id'], 'runtime': state['runtime']},
             'counts': {status: sum(r['status'] == status for r in rows) for status in sorted({r['status'] for r in rows})},
            'steps': rows}


def report(store, destination):
    state = store.read()
    value = snapshot(store, state)
    rows = value['steps']
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / 'report.json', value)
    text = ['# ' + state['plan']['name'], '', f"Campaign: `{state['campaign_id']}`", '',
            '| Step | State | Kind | Worker/profile | Native claims |', '|---|---|---|---|---|']
    stream = io.StringIO()
    writer = csv.DictWriter(stream, lineterminator='\n', fieldnames=['step', 'status', 'kind', 'worker', 'payload_schema', 'task_id',
                                               'termination', 'claim', 'feasible', 'objective', 'evidence'])
    writer.writeheader()
    for row in rows:
        native = row['native'] or {}
        claims = [result['outcome'].get('claim') for result in native.get('results', [])]
        text.append(f"| {row['step']} | {row['status']} | {row['kind']} | {row['worker'] or ''} {row['payload_schema'] or ''} | {', '.join(map(str, claims))} |")
        base = {k: row[k] for k in ['step', 'status', 'kind', 'worker', 'payload_schema']}
        for task in native.get('results', []) or [{}]:
            outcome = task.get('outcome', {})
            writer.writerow({**base, 'task_id': task.get('task_id'),
                             **{k: outcome.get(k) for k in ['termination', 'claim', 'feasible', 'objective']},
                             'evidence': canonical(outcome.get('evidence')).decode()})
    text += ['', 'Native results preserve their own claims, evidence and work counters. A completed run is not an optimality proof.',
             'No cross-profile ranking or home-fleet performance comparison is made. Declared slot-second reservations are admission bounds, not measured slot-hours.', '']
    atomic(destination / 'report.md', '\n'.join(text).encode())
    atomic(destination / 'results.csv', stream.getvalue().encode())
    return {'report': str(destination / 'report.json'), 'sha256': identity(value), 'counts': value['counts']}


def diff(before, after, pointer=''):
    # Compare JSON text, not Python values: true, 1 and 1.0 are different.
    if canonical(before) == canonical(after):
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in sorted(before.keys() | after.keys()):
            path = pointer + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in before or key not in after:
                out.append({'pointer': path, 'before': before.get(key), 'after': after.get(key),
                            'before_present': key in before, 'after_present': key in after})
            else:
                out += diff(before[key], after[key], path)
        return out
    if isinstance(before, list) and isinstance(after, list):
        out = []
        for index in range(max(len(before), len(after))):
            path = pointer + '/' + str(index)
            if index >= min(len(before), len(after)):
                out.append({'pointer': path, 'before': before[index] if index < len(before) else None,
                            'after': after[index] if index < len(after) else None,
                            'before_present': index < len(before), 'after_present': index < len(after)})
            else:
                out += diff(before[index], after[index], path)
        return out
    return [{'pointer': pointer, 'before': before, 'after': after}]
