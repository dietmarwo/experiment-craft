"""Installed-package upgrade and rollback rehearsal: reviewed 0.3.0 -> 0.4.0 -> 0.3.0 -> 0.4.0.

Follows the upgrade and rollback steps of docs/operations.md with a real
campaign on a one-slot local node. Each client is an installed wheel in its own
venv, run from outside any checkout; the two versions never run at once.

    python rehearse_upgrade.py CLIENT_030 CLIENT_040 RUNNER OUT

CLIENT_* are the experiment-craft console scripts, RUNNER is optimization-run and
OUT is a new directory. Writes OUT/calls.json (every call: version, argv, exit
code, output) and OUT/summary.json (the checks and their results).
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

V030, V040, RUN, OUT = (Path(p).resolve() for p in sys.argv[1:5])
OUT.mkdir(parents=True, exist_ok=False)
NODE, WS, MARKS = OUT / 'node', OUT / 'campaign', OUT / 'marks'
CALLS, CHECKS = [], []


def rel(value):
    text = str(value)
    return text.replace(str(OUT), '$OUT').replace(str(RUN.parent), '$BIN')


def call(client, *argv, expect=0):
    version = '0.3.0' if client == V030 else '0.4.0'
    p = subprocess.run([str(client), *map(str, argv)], cwd=OUT, capture_output=True, text=True, timeout=300)
    out = p.stdout.strip().splitlines()
    try:
        value = json.loads(out[-1]) if out else None
    except ValueError:
        value = out[-1]  # --version prints the bare version
    error = json.loads(p.stderr) if p.returncode == 2 and p.stderr.strip().startswith('{') else None
    CALLS.append({'version': version, 'argv': [rel(a) for a in argv], 'exit': p.returncode,
                  'output': value if value is None or len(json.dumps(value)) < 4000 else {'keys': sorted(value)},
                  'error': error})
    assert p.returncode == expect, (version, argv, p.returncode, p.stdout, p.stderr)
    return value if p.returncode != 2 else error


def check(name, ok, detail=None):
    CHECKS.append({'check': name, 'passed': bool(ok), **({'detail': detail} if detail is not None else {})})


def runtime(*argv):
    p = subprocess.run([str(RUN), '--root', str(NODE), *map(str, argv)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def journals():
    return {p.parent.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(NODE.glob('jobs/*/events.jsonl'))}


def tree(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(path).rglob('*')) if p.is_file()}


def head():
    path = WS / 'head.json'
    return json.loads(path.read_text()) if path.exists() else None


def last_decision():
    return call(V040, 'workspace-check', '--workspace', WS)['last_decision']


# A sequential campaign of six trusted commands; s2 runs long enough to be in
# flight when dispatch is paused.
runtime('node', 'init', '--capacity', '1', '--allow-commands')
MARKS.mkdir()
steps = []
for i in range(6):
    code = (f"import time,pathlib; time.sleep({4 if i == 2 else 0.3}); p=pathlib.Path({str(MARKS)!r})/'s{i}'; "
            "p.write_text(p.read_text()+'x' if p.exists() else 'x')")
    steps.append({'id': f's{i}', **({'needs': [f's{i-1}']} if i else {}), 'job': {
        'schema_version': 'execution.command/0.1', 'argv': [sys.executable, '-c', code], 'env': {},
        'resources': {'cpu_slots': 1}, 'limits': {'wall_seconds': 30, 'grace_seconds': 1},
        'replay': 'never', 'inputs': [], 'outputs': []}})
(OUT / 'campaign.json').write_text(json.dumps({
    'schema_version': 'experiment.campaign/0.1', 'name': 'upgrade rehearsal', 'allow_commands': True,
    'budget': {'max_jobs': 20, 'max_wall_seconds': 3600, 'max_reserved_slot_seconds': 10000}, 'steps': steps}))

# 1. Under 0.3.0: two steps, then pause while the third is in flight.
call(V030, '--version')
call(V030, 'init', 'campaign.json', '--workspace', WS, '--runner', RUN, '--node-root', NODE, '--mode', 'foreground')
call(V030, 'continue', '--workspace', WS, '--once')
call(V030, 'continue', '--workspace', WS, '--once')
driver = subprocess.Popen([str(V030), 'continue', '--workspace', str(WS)], cwd=OUT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
end = time.monotonic() + 30
while time.monotonic() < end and not any(j.get('state') == 'running' for j in runtime('jobs', 'list')):
    time.sleep(0.05)
in_flight = [j['state'] for j in runtime('jobs', 'list')]
call(V030, 'pause-dispatch', '--workspace', WS, '--reason', 'upgrade to 0.4.0')
out, err = driver.communicate(timeout=60)
CALLS.append({'version': '0.3.0', 'argv': ['continue', '--workspace', '$OUT/campaign'], 'exit': driver.returncode,
              'output': None, 'error': json.loads(err) if err.strip() else None, 'note': 'driver running when paused'})
status = call(V030, 'status', '--workspace', WS)
check('0.3.0 pause stops the driver after the step in flight, without cancelling it',
      driver.returncode == 2 and json.loads(err)['error']['code'] == 'dispatch_paused'
      and status['steps'] == {'s0': 'succeeded', 's1': 'succeeded', 's2': 'succeeded', 's3': 'pending',
                              's4': 'pending', 's5': 'pending'}, {'jobs_when_paused': in_flight})
call(V030, 'maintenance-status', '--workspace', WS)
backup = call(V030, 'backup', '--workspace', WS, '--destination', OUT / 'backup-0.3.0.zip')
call(V030, 'report', '--workspace', WS, '--destination', OUT / 'report-0.3.0')
before = journals()

# 2. Install 0.4.0 and check before unpausing.
call(V040, '--version')
paused = call(V040, 'maintenance-status', '--workspace', WS)
call(V040, 'status', '--workspace', WS)
call(V040, 'report', '--workspace', WS, '--destination', OUT / 'report-0.4.0')
check('0.4.0 opens the 0.3.0 workspace paused', paused['paused'] is True)
check('the 0.4.0 report of the 0.3.0 state equals the 0.3.0 report',
      tree(OUT / 'report-0.3.0') == tree(OUT / 'report-0.4.0'))
first = call(V040, 'workspace-check', '--workspace', WS)
check('workspace-check finds nothing in a workspace without head.json',
      first['findings'] == [] and first['head'] is None, first['findings'])
call(V040, 'unpause-dispatch', '--workspace', WS)
call(V040, 'continue', '--workspace', WS, '--once')
recorded = head()
check('0.4.0 records its decisions in head.json', recorded is not None and recorded['seq'] == last_decision())
check('no native job was repeated or changed across the upgrade',
      all(journals().get(k) == v for k, v in before.items()))

# 3. Roll back to 0.3.0: paused, offline reads first, then 0.3.0 decides.
call(V040, 'pause-dispatch', '--workspace', WS, '--reason', 'rollback to 0.3.0')
rolled = journals()
for argv in [('status',), ('maintenance-status',), ('events', '--after', '0', '--limit', '1000')]:
    call(V030, *argv, '--workspace', WS)
call(V030, 'report', '--workspace', WS, '--destination', OUT / 'report-0.3.0-rollback')
check('0.3.0 reads a workspace that has head.json, and offline reads change no native journal',
      journals() == rolled)
call(V030, 'unpause-dispatch', '--workspace', WS)
call(V030, 'continue', '--workspace', WS, '--once')
call(V030, 'pause-dispatch', '--workspace', WS, '--reason', 'return to 0.4.0')
check('0.3.0 decisions leave head.json behind the database', head()['seq'] < last_decision(),
      {'head': head()['seq'], 'database': last_decision()})

# 4. Return to 0.4.0: the record behind the database is accepted; finish.
back = call(V040, 'workspace-check', '--workspace', WS)
check('0.4.0 accepts the older record', back['findings'] == [] and back['head']['matches'], back['findings'])
call(V040, 'maintenance-status', '--workspace', WS)
call(V040, 'unpause-dispatch', '--workspace', WS)
done = call(V040, 'continue', '--workspace', WS)
check('the campaign completes, each step ran once and no job was added',
      done['status'] == 'completed' and [(MARKS / f's{i}').read_text() for i in range(6)] == ['x'] * 6
      and len(runtime('jobs', 'list')) == 6)
check('head.json records the last decision again', head()['seq'] == last_decision())

# 5. Restore the 0.3.0 archive with 0.4.0: paused, and stale against the original.
restored = call(V040, 'restore', OUT / 'backup-0.3.0.zip', '--workspace', OUT / 'restored')
check_restored = call(V040, 'workspace-check', '--workspace', OUT / 'restored')
check('0.4.0 restores the 0.3.0 archive paused, with its backup id',
      restored['dispatch_paused'] and check_restored['restored_from'] == backup['backup_id']
      and check_restored['findings'] == [], check_restored['findings'])
refused = call(V040, 'unpause-dispatch', '--workspace', OUT / 'restored', expect=2)
check('unpausing the stale restore is refused, and nothing is launched',
      refused['error']['code'] == 'recovery_diverged' and len(runtime('jobs', 'list')) == 6)

# 6. The 0.4.0 dashboard attaches the workspace and stops cleanly.
dashboard = subprocess.Popen([str(V040), 'dashboard', '--workspace', str(WS), '--state-dir', str(OUT / 'ui'),
                              '--port', '0'], cwd=OUT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
listening = json.loads(dashboard.stdout.readline())
dashboard.send_signal(signal.SIGTERM)
out, err = dashboard.communicate(timeout=60)
stopped = json.loads(out)
CALLS.append({'version': '0.4.0', 'argv': ['dashboard', '--workspace', '$OUT/campaign', '--state-dir', '$OUT/ui',
              '--port', '0'], 'exit': dashboard.returncode, 'output': stopped, 'error': None, 'note': 'SIGTERM'})
check('the 0.4.0 dashboard attaches the workspace and stops with no checkpoint error',
      listening['status'] == 'dashboard_listening' and dashboard.returncode == 0
      and stopped == {'status': 'dashboard_stopped', 'checkpoint_errors': []})

(OUT / 'calls.json').write_text(rel(json.dumps(CALLS, indent=1)) + '\n')  # paths relative to OUT and the runner
summary = {'versions': ['0.3.0', '0.4.0', '0.3.0', '0.4.0'], 'native_jobs': len(runtime('jobs', 'list')),
           'checks': CHECKS, 'passed': all(c['passed'] for c in CHECKS)}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
print(json.dumps({'passed': summary['passed'], 'failed': [c['check'] for c in CHECKS if not c['passed']]}))
sys.exit(0 if summary['passed'] else 1)
