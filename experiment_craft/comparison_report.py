"""Descriptive scientific reports; no execution, ranking, or significance tests."""
from collections import Counter
import csv
from fractions import Fraction
import io
import itertools
import math
import os
from pathlib import Path
import shutil
import tempfile

from .comparison import at, bound_protocol, resolve
from .manifest import same_value
from .report import snapshot
from .storage import Error, atomic, canonical, exact, exchange_directories, identity, publish_directory, require


def numeric(value):
    return type(value) in (int, float) and (isinstance(value, int) or math.isfinite(value))


def as_number(value):
    if value.denominator == 1:
        return value.numerator
    try:
        number = float(value)
    except OverflowError as exc:
        raise Error('comparison_overflow', 'comparison arithmetic exceeds finite JSON numbers') from exc
    require(math.isfinite(number), 'comparison_overflow', 'comparison arithmetic exceeds finite JSON numbers')
    return number


def stats(values):
    if not values:
        return {'n': 0, 'minimum': None, 'maximum': None, 'mean': None, 'median': None}
    # JSON decimals, not a binary-float running sum. Raw observations remain
    # available to reconstruct these descriptive (not inferential) summaries.
    ordered = sorted(Fraction(exact(v)) for v in values)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {'n': len(ordered), 'minimum': as_number(ordered[0]), 'maximum': as_number(ordered[-1]),
            'mean': as_number(sum(ordered) / len(ordered)), 'median': as_number(median)}


def counts(values):
    return dict(sorted(Counter(values).items()))


def observation(unit, row, group):
    native = row['native'] or {}
    command = row['kind'] == 'command'
    tasks = native.get('results', [])
    task = tasks[0] if len(tasks) == 1 else {}
    outcome = task.get('outcome', {})
    work = native.get('work')
    accounting = (native.get('collection_attempted') is True and not native.get('output_errors')
                  if command else native.get('runner', {}).get('accounting_complete') is True)
    complete = row['status'] == 'succeeded' and (native.get('state') == 'completed' if command else
               native.get('status') == 'completed' and native.get('requested_tasks') == 1 and
               native.get('completed_tasks') == 1 and len(tasks) == 1 and accounting and
               native.get('worker') == row['worker'] and native.get('payload_schema') == row['payload_schema'])
    budget = group['budget']
    cap = 'time_limit' if budget['kind'] == 'fixed_time' else 'work_unknown'
    if budget['kind'] == 'fixed_work' and isinstance(work, dict):
        actual = work.get(budget['counter'])
        if type(actual) is int and actual >= 0 and accounting:
            cap = 'within_work_limit' if actual <= budget['limit'] else 'work_limit_exceeded'
    # A timed-out/partial/uncertain result can have a useful checked point;
    # show it separately and never let it silently enter the complete cohort.
    complete = bool(complete and (budget['kind'] != 'fixed_work' or cap == 'within_work_limit'))
    metrics = {}
    for metric in group['metrics']:
        present, value = at(task, metric['pointer'], strict=False)
        valid = present and numeric(value)
        feasible = outcome.get('feasible') is True
        available = valid and feasible
        reason = ('missing' if not present else 'not_numeric' if not valid else
                  'feasibility_not_true' if not feasible else 'incomplete' if not complete else None)
        target = metric.get('target')
        hit = (value <= target if metric['direction'] == 'minimize' else value >= target) if (
            complete and available and target is not None) else None
        metrics[metric['id']] = {'present': present, 'value': value if valid else None,
                                 'available_feasible': available, 'complete_feasible': complete and available,
                                 'excluded_reason': reason, 'target_hit': hit}
    return {**unit, 'status': row['status'], 'job_state': row['job_state'], 'job_id': row['job_id'],
            'error': row['error'], 'complete': complete, 'budget_observation': cap,
            'accounting_complete': bool(accounting), 'requested_tasks': native.get('requested_tasks'),
            'completed_tasks': native.get('completed_tasks'), 'feasible': outcome.get('feasible'),
            'termination': outcome.get('termination'), 'claim': outcome.get('claim'),
            'evidence': outcome.get('evidence'), 'work': work,
            'known_work_lower_bound': native.get('known_work_lower_bound'),
            'elapsed_seconds': native.get('elapsed_seconds'),
            'process': native.get('process'), 'outputs': native.get('outputs'),
            'output_errors': native.get('output_errors'), 'metrics': metrics}


def work_totals(observations, field, expected=None):
    keys = sorted({key for o in observations if isinstance(o[field], dict) for key in o[field]} |
                  ({expected} if expected else set()))
    result = {}
    for key in keys:
        values = [o[field][key] for o in observations if isinstance(o[field], dict) and
                  type(o[field].get(key)) is int and o[field][key] >= 0 and
                  (field == 'known_work_lower_bound' or o['accounting_complete'])]
        result[key] = {'known_total': sum(values), 'known_runs': len(values), 'unknown_runs': len(observations) - len(values)}
    return result


def arm_summary(observations, group):
    metrics = {}
    for metric in group['metrics']:
        name = metric['id']
        complete = [o['metrics'][name]['value'] for o in observations if o['metrics'][name]['complete_feasible']]
        available = [o['metrics'][name]['value'] for o in observations if o['metrics'][name]['available_feasible']]
        metrics[name] = {'definition': metric, 'complete_feasible': stats(complete),
                         'available_feasible': stats(available), 'excluded_from_complete': len(observations) - len(complete)}
        if 'target' in metric:
            known = [o['metrics'][name]['target_hit'] for o in observations if o['metrics'][name]['target_hit'] is not None]
            metrics[name]['target'] = {'attained': sum(known), 'not_attained': len(known) - sum(known),
                                      'unresolved': len(observations) - len(known), 'planned': len(observations)}
    return {'planned': len(observations), 'complete': sum(o['complete'] for o in observations),
            'statuses': counts(o['status'] for o in observations),
            'native_states': counts(o['job_state'] or 'unknown' for o in observations),
            'feasibility': counts('true' if o['feasible'] is True else 'false' if o['feasible'] is False else 'unknown'
                                  for o in observations),
            'terminations': counts(o['termination'] or 'unknown' for o in observations),
            'claims': counts(o['claim'] or 'unknown' for o in observations),
            'evidence_levels': counts((o['evidence'] or {}).get('level') or 'unknown' for o in observations),
            'work': work_totals(observations, 'work', group['budget'].get('counter')),
            'known_work_lower_bound': work_totals(observations, 'known_work_lower_bound', group['budget'].get('counter')),
            'elapsed_seconds': stats([o['elapsed_seconds'] for o in observations
                                      if numeric(o['elapsed_seconds']) and o['complete']]),
            'metrics': metrics}


def paired(arms, group):
    if group['design'] != 'paired':
        return []
    result = []
    for left, right in itertools.combinations(arms, 2):
        other = {same_value(o['sample']): o for o in right['observations']}
        for metric in group['metrics']:
            pairs, differences = [], []
            for a in left['observations']:
                b = other[same_value(a['sample'])]
                av, bv = a['metrics'][metric['id']], b['metrics'][metric['id']]
                eligible = av['complete_feasible'] and bv['complete_feasible']
                delta = as_number(Fraction(exact(av['value'])) - Fraction(exact(bv['value']))) if eligible else None
                if eligible:
                    differences.append(delta)
                pairs.append({'sample': a['sample'], 'left_step': a['step'], 'right_step': b['step'],
                              'eligible': eligible, 'left': av['value'], 'right': bv['value'], 'difference': delta})
            result.append({'left_arm': left['id'], 'right_arm': right['id'], 'metric': metric['id'],
                           'difference_definition': 'left minus right', 'planned': len(pairs),
                           'excluded': len(pairs) - len(differences), 'summary': stats(differences), 'pairs': pairs})
    return result


def build(store):
    state = store.read()
    binding = bound_protocol(store)
    require(binding['campaign_id'] == state['campaign_id'] and binding['plan_id'] == state['plan']['plan_id'],
            'comparison_changed', 'comparison belongs to another campaign')
    resolved = resolve(binding['protocol'], state)
    require(canonical(resolved) == canonical(binding['resolved']), 'comparison_changed', 'resolved comparison design changed')
    retained = snapshot(store, state)
    rows = {row['step']: row for row in retained['steps']}
    groups = []
    for spec, design in zip(binding['protocol']['groups'], resolved['groups']):
        arms = []
        observed_inputs = set()
        for arm in design['arms']:
            observations = [observation(unit, rows[unit['step']], spec) for unit in arm['units']]
            for unit in arm['units']:
                submitted = state['steps'][unit['step']].get('submitted_job')
                if submitted is not None:
                    # Equivalent preparation code is not proof of equal output
                    # bytes. Compare the hashes actually bound before dispatch.
                    inputs = [{k: v for k, v in item.items() if k != 'file'} for item in submitted.get('inputs', [])]
                    observed_inputs.add(identity(inputs))
            arms.append({'id': arm['id'], 'summary': arm_summary(observations, spec), 'observations': observations})
        require(len(observed_inputs) <= 1, 'incompatible_comparison',
                'actual staged input identities differ; retain the basic report and use separate scientific groups')
        groups.append({'id': spec['id'], 'description': spec['description'], 'kind': spec['kind'],
                       'compatibility_id': design['compatibility_id'], 'budget': spec['budget'],
                       'observed_input_id': next(iter(observed_inputs), None),
                       'replication': spec['replication'], 'design': spec['design'], 'arms': arms,
                       'paired_differences': paired(arms, spec)})
    return {'schema_version': 'experiment.comparison.report/0.1', 'binding': binding,
            'campaign_report': retained, 'groups': groups, 'excluded': resolved['excluded'],
            'interpretation': [
                'Descriptive summaries only; no ranking, significance test or optimality certification.',
                'Fixed-work and fixed-time protocols use declared caps; actual work and early termination remain visible.',
                'Complete-feasible metrics require an accepted complete single-task result, known accounting and feasibility=true.',
                'Available-feasible metrics may include partial or failed runs and are reported separately.',
                'Targets use all planned runs as the denominator; failures, missing and unknown outcomes are unresolved.',
                'Deterministic repeats measure timing reproducibility, not independent quality discoveries.',
                'Elapsed times describe this execution environment and are not home-fleet performance.',
            ]}


def cell(value):
    return str(value).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ').replace('`', "'")


REPORT_FILES = ('comparison.json', 'comparison.md', 'observations.csv')


def publish(destination, files):
    """Replace the report directory as a whole, so no reader sees a mix of runs.

    The destination is new, or a directory that holds nothing but an earlier
    comparison report; other files are never deleted or mixed in.
    """
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        require(destination.is_dir() and not destination.is_symlink(), 'invalid_destination',
                'the destination must be a new or report directory, not a file or symlink')
        require(set(os.listdir(destination)) <= set(REPORT_FILES), 'invalid_destination',
                'the destination holds other files; choose a new directory or an earlier comparison report')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.comparison-', dir=destination.parent))
    try:
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temp, 0o777 & ~umask)
        for name, data in files.items():
            atomic(temp / name, data)
        if destination.exists():
            exchange_directories(temp, destination)  # temp now holds the earlier report
        else:
            publish_directory(temp, destination)
        fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def report(store, destination):
    value = build(store)  # Validate all retained bytes before creating output.
    text = ['# ' + cell(value['binding']['protocol']['name']), '',
            'Protocol: `' + value['binding']['protocol_id'] + '`', '',
            '| Group | Common cap | Replication | Design | Description |', '|---|---|---|---|---|']
    for group in value['groups']:
        budget = group['budget']
        cap = (f"{budget['limit']} {budget['counter']}" if budget['kind'] == 'fixed_work' else
               f"{budget['seconds']} wall seconds")
        text.append('| ' + ' | '.join(cell(v) for v in [group['id'], cap, group['replication']['kind'],
                                                      group['design'], group['description']]) + ' |')
    text += ['',
            '| Group | Arm | Planned | Complete | Metric (unit) | Complete feasible n | Available feasible n | Mean (complete) | Median (complete) | Target hits / planned; unresolved |',
            '|---|---|---:|---:|---|---:|---:|---:|---:|---|']
    stream = io.StringIO()
    fields = ['group', 'arm', 'step', 'job_id', 'sample', 'status', 'job_state', 'error', 'complete', 'budget_observation',
              'feasible', 'termination', 'claim', 'evidence', 'accounting_complete', 'work',
              'known_work_lower_bound', 'elapsed_seconds', 'metric', 'metric_unit', 'metric_direction', 'target', 'value', 'complete_feasible',
              'available_feasible', 'excluded_reason', 'target_hit', 'process', 'outputs', 'output_errors']
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for group in value['groups']:
        for arm in group['arms']:
            summary = arm['summary']
            for name, metric in summary['metrics'].items() or [('', {'complete_feasible': stats([]), 'available_feasible': stats([])})]:
                s = metric['complete_feasible']
                target = metric.get('target')
                target_text = f"{target['attained']} / {target['planned']}; {target['unresolved']}" if target else ''
                label = name + (' (' + metric['definition']['unit'] + ')' if name else '')
                text.append('| ' + ' | '.join(cell(v) for v in [group['id'], arm['id'], summary['planned'],
                            summary['complete'], label, s['n'], metric['available_feasible']['n'],
                            s['mean'], s['median'], target_text]) + ' |')
            for obs in arm['observations']:
                base = {'group': group['id'], 'arm': arm['id'], **{k: obs[k] for k in fields if k in obs}}
                for name, metric in obs['metrics'].items() or [('', {})]:
                    definition = summary['metrics'][name]['definition'] if name else {}
                    row = {**base, 'metric': name, 'metric_unit': definition.get('unit'),
                           'metric_direction': definition.get('direction'), 'target': definition.get('target'),
                           **{k: metric[k] for k in fields if k in metric}}
                    for key in ['sample', 'error', 'evidence', 'work', 'known_work_lower_bound', 'process', 'outputs', 'output_errors']:
                        row[key] = canonical(row.get(key)).decode()
                    writer.writerow(row)
    text += ['', '## Declared paired differences', '',
             'Differences are left minus right; only complete feasible pairs enter these descriptive summaries.', '',
             '| Group | Left arm | Right arm | Metric | Planned | Included | Excluded | Mean difference |',
             '|---|---|---|---|---:|---:|---:|---:|']
    for group in value['groups']:
        for pair in group['paired_differences']:
            text.append('| ' + ' | '.join(cell(v) for v in [group['id'], pair['left_arm'], pair['right_arm'],
                        pair['metric'], pair['planned'], pair['summary']['n'], pair['excluded'], pair['summary']['mean']]) + ' |')
    text += ['', '## Native accounting and evidence', '',
             '| Group | Arm | Feasibility | Claims | Evidence levels | Known work and missing runs |', '|---|---|---|---|---|---|']
    for group in value['groups']:
        text += ['| ' + ' | '.join(cell(v) for v in [group['id'], arm['id'],
                 canonical(arm['summary']['feasibility']).decode(), canonical(arm['summary']['claims']).decode(),
                 canonical(arm['summary']['evidence_levels']).decode(), canonical(arm['summary']['work']).decode()]) + ' |'
                 for arm in group['arms']]
    text += ['', '## All campaign steps', '', '| Step | State | Included / exclusion |', '|---|---|---|']
    exclusions = {e['step']: e['reason'] for e in value['excluded']}
    for step in value['campaign_report']['steps']:
        text.append('| ' + ' | '.join(cell(v) for v in [step['step'], step['status'], exclusions.get(step['step'], 'included')]) + ' |')
    text += ['', *value['interpretation'], '']
    publish(destination, {'comparison.json': canonical(value) + b'\n', 'comparison.md': '\n'.join(text).encode(),
                          'observations.csv': stream.getvalue().encode()})
    return {'comparison': str(destination / 'comparison.json'), 'protocol_id': value['binding']['protocol_id'],
            'sha256': identity(value), 'counts': value['campaign_report']['counts']}
