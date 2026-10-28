"""Reproduce the ways a campaign workspace can reopen at an earlier state.

Every scenario runs real campaigns of short sequential command steps against a
real optimization-run, and compares what a separate SQLite connection saw
committed (the highest event seq) with what a reopened workspace or copy holds.
Results are printed and written to OUT/results.json.

    python reproduce.py PROJECT RUNNER OUT [scenario ...]

PROJECT is an experiment-craft checkout, RUNNER the optimization-run binary and
OUT a new directory. Without scenario names, all run.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import random
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

PROJECT, RUN, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'tests'))
from experiment_craft.campaign import initialize  # noqa: E402
from test_campaign import campaign, command  # noqa: E402

RESULTS = {}


def runtime(node, *argv):
    p = subprocess.run([str(RUN), '--root', str(node), *map(str, argv)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def cli(*argv, check=True):
    p = subprocess.run([sys.executable, '-m', 'experiment_craft', *map(str, argv)], cwd=PROJECT,
                       capture_output=True, text=True, timeout=120)
    if check:
        assert p.returncode in (0, 1), (argv, p.stderr)
    return p


def popen_continue(ws):
    return subprocess.Popen([sys.executable, '-m', 'experiment_craft', 'continue', '--workspace', str(ws)],
                            cwd=PROJECT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def setup(name, steps=8, sleep=0.15):
    base = OUT / name
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    node, ws = base / 'node', base / 'campaign'
    runtime(node, 'node', 'init', '--capacity', '1', '--allow-commands')
    marks = base / 'marks'
    marks.mkdir()
    rows = []
    for i in range(steps):
        code = (f"import time,pathlib; time.sleep({sleep}); p=pathlib.Path({str(marks)!r})/'s{i}'; "
                "p.write_text(p.read_text()+'x' if p.exists() else 'x')")
        job = command([sys.executable, '-c', code])
        job['limits']['wall_seconds'] = 30
        rows.append({'id': f's{i}', 'job': job, **({'needs': [f's{i-1}']} if i else {})})
    value = campaign(rows)
    value['budget'] = {'max_jobs': 50, 'max_wall_seconds': 600, 'max_reserved_slot_seconds': 10000}
    (base / 'campaign.json').write_text(json.dumps(value))
    initialize(base / 'campaign.json', ws, RUN, node, 'foreground')
    return base, node, ws, marks


def head(db_path):
    """Max event seq and step statuses of a database file, read in place."""
    with closing(sqlite3.connect(db_path, timeout=5)) as db:
        seq = db.execute('SELECT max(seq) FROM events').fetchone()[0]
        state = json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
        paused = None
        if db.execute("SELECT name FROM sqlite_master WHERE name='maintenance'").fetchone():
            paused = json.loads(db.execute('SELECT value FROM maintenance').fetchone()[0])['paused']
    return {'seq': seq, 'steps': ''.join(v['status'][0] for v in state['steps'].values()),
            'stop': state['stop_requested'], 'paused': paused}


def copy_workspace(ws, dest, files=('campaign.sqlite3',), tree=True):
    """Copy plan.json, head.json, files/, requests/, results/ and the named SQLite files."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if tree:
        for name in ['plan.json', 'head.json']:  # head.json exists from the fix on
            if (ws / name).exists():
                shutil.copy2(ws / name, dest / name)
        for name in ['files', 'requests', 'results']:
            if (ws / name).exists():
                shutil.copytree(ws / name, dest / name)
    for name in files:
        if (ws / name).exists():
            shutil.copyfile(ws / name, dest / name)
    return dest


def sidecars(ws):
    return {s: (ws / f'campaign.sqlite3{s}').stat().st_size if (ws / f'campaign.sqlite3{s}').exists() else None
            for s in ['', '-wal', '-shm']}


class Observer:
    """A separate connection that records the highest committed event seq."""
    def __init__(self, ws):
        self.db = sqlite3.connect(ws / 'campaign.sqlite3', timeout=5, isolation_level=None)
        self.max = 0

    def poll(self):
        self.max = max(self.max, self.db.execute('SELECT max(seq) FROM events').fetchone()[0] or 0)
        return self.max

    def close(self):
        self.db.close()


def wait_seq(observer, target, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if observer.poll() >= target:
            return observer.max
        time.sleep(0.01)
    raise RuntimeError('timeout')


def finish(ws):
    p = cli('continue', '--workspace', ws, check=False)
    return p.returncode, (json.loads(p.stdout)['status'] if p.stdout.strip() else json.loads(p.stderr)['error']['code'])


def runs(marks, n):
    """How often each step's command ran."""
    return [len((marks / f's{i}').read_text()) if (marks / f's{i}').exists() else 0 for i in range(n)]


def s_kill(trials=12):
    """SIGKILL the client at random points; committed decisions must survive."""
    rows = []
    for t in range(trials):
        base, node, ws, marks = setup(f'kill-{t}', steps=6)
        proc = popen_continue(ws)
        obs = Observer(ws)
        deadline = time.monotonic() + random.uniform(0.2, 2.0)
        while time.monotonic() < deadline and proc.poll() is None:
            obs.poll()
            time.sleep(0.003)
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait()
        seen = obs.poll()
        files = sidecars(ws)
        main_only = head(copy_workspace(ws, base / 'main-only') / 'campaign.sqlite3')
        obs.close()
        reopened = head(ws / 'campaign.sqlite3')
        code, status = finish(ws)
        jobs = runtime(node, 'jobs', 'list')
        rows.append({'trial': t, 'seen_seq': seen, 'reopened_seq': reopened['seq'], 'wal_bytes_after_kill': files['-wal'],
                     'main_only_copy_seq': main_only['seq'], 'continue_after_kill': [code, status], 'jobs': len(jobs),
                     'runs_per_step': runs(marks, 6)})
    RESULTS['kill'] = rows
    lost = [r for r in rows if r['reopened_seq'] < r['seen_seq']]
    # A kill between a dispatch intent and the launch leaves that step uncertain:
    # continue observes it and never launches it again.
    print('kill: trials', trials, 'lost committed decisions in', len(lost), 'trials;',
          'main-only copy behind in', sum(r['main_only_copy_seq'] < r['seen_seq'] for r in rows), 'trials;',
          'a step ran twice in', sum(max(r['runs_per_step']) > 1 for r in rows), 'trials;',
          'continue after the kill:', sorted(r['continue_after_kill'][1] for r in rows))


def s_copy_live():
    """Copies taken while a client advances the campaign."""
    rows = {}
    base, node, ws, marks = setup('copy-live', steps=8)
    proc = popen_continue(ws)
    obs = Observer(ws)
    wait_seq(obs, 12)
    a = copy_workspace(ws, base / 'main-only')
    seen_a = obs.poll()
    b = copy_workspace(ws, base / 'all-three', files=('campaign.sqlite3', 'campaign.sqlite3-wal', 'campaign.sqlite3-shm'))
    seen_b = obs.poll()
    proc.wait(timeout=120)
    obs.close()
    final = head(ws / 'campaign.sqlite3')
    rows['main_only'] = {'seen_at_copy': seen_a, 'copy': head(a / 'campaign.sqlite3'), 'final': final}
    rows['main_wal_shm'] = {'seen_at_copy': seen_b, 'copy': head(b / 'campaign.sqlite3')}
    RESULTS['copy_live'] = rows
    print('copy while running:', json.dumps(rows))


def s_copy_torn(trials=30):
    """Main and WAL copied one after the other while a client writes."""
    outcomes = {}
    base, node, ws, marks = setup('copy-torn', steps=30, sleep=0.05)
    proc = popen_continue(ws)
    obs = Observer(ws)
    for t in range(trials):
        if proc.poll() is not None:
            break
        dest = base / f'torn-{t}'
        dest.mkdir()
        before = obs.poll()
        shutil.copyfile(ws / 'campaign.sqlite3', dest / 'campaign.sqlite3')
        time.sleep(random.uniform(0, 0.3))
        if (ws / 'campaign.sqlite3-wal').exists():
            shutil.copyfile(ws / 'campaign.sqlite3-wal', dest / 'campaign.sqlite3-wal')
        after = obs.poll()
        try:
            seq = head(dest / 'campaign.sqlite3')['seq']
            ok = sqlite3.connect(dest / 'campaign.sqlite3').execute('PRAGMA integrity_check').fetchone()[0]
            kind = 'current' if seq >= before else 'earlier'
            if ok != 'ok':
                kind = 'corrupt'
        except sqlite3.DatabaseError as exc:
            kind = 'unreadable: ' + str(exc)
        outcomes[kind] = outcomes.get(kind, 0) + 1
    proc.wait(timeout=300)
    obs.close()
    RESULTS['copy_torn'] = outcomes
    print('main then WAL copied separately:', outcomes)


def checkpoint(path, mode):
    with closing(sqlite3.connect(path, timeout=1, isolation_level=None)) as db:
        try:
            return list(db.execute(f'PRAGMA wal_checkpoint({mode})').fetchone())
        except sqlite3.OperationalError as exc:
            return str(exc)


def s_checkpoint():
    """An explicit checkpoint, then a copy of the main file only."""
    rows = {}
    # (a) checkpoint while the client still advances, then copy main only.
    base, node, ws, marks = setup('ckpt-live', steps=8)
    proc = popen_continue(ws)
    obs = Observer(ws)
    wait_seq(obs, 12)
    obs.close()
    result = checkpoint(ws / 'campaign.sqlite3', 'TRUNCATE')
    a = copy_workspace(ws, base / 'main-only')
    proc.wait(timeout=120)
    rows['while_running'] = {'checkpoint': result, 'copy': head(a / 'campaign.sqlite3'), 'final': head(ws / 'campaign.sqlite3')}
    # (b) clients stopped, but a reader keeps an older snapshot open.
    base, node, ws, marks = setup('ckpt-reader', steps=3)
    cli('continue', '--workspace', ws)
    reader = sqlite3.connect(ws / 'campaign.sqlite3', isolation_level=None)
    reader.execute('BEGIN')
    reader.execute('SELECT count(*) FROM events').fetchone()
    cli('pause-dispatch', '--workspace', ws, '--reason', 'archive')  # a decision after the reader's snapshot
    passive = checkpoint(ws / 'campaign.sqlite3', 'PASSIVE')
    truncate = checkpoint(ws / 'campaign.sqlite3', 'TRUNCATE')
    b = copy_workspace(ws, base / 'main-only')
    reader.execute('ROLLBACK')
    reader.close()
    rows['reader_open'] = {'passive': passive, 'truncate': truncate, 'copy': head(b / 'campaign.sqlite3'),
                           'final': head(ws / 'campaign.sqlite3')}
    # (c) every client closed: SQLite already checkpointed and removed the WAL.
    files = sidecars(ws)
    c = copy_workspace(ws, base / 'main-only-closed')
    rows['all_closed'] = {'sidecars': files, 'copy': head(c / 'campaign.sqlite3')}
    RESULTS['checkpoint'] = rows
    print('checkpoint:', json.dumps(rows))


def s_kill_then_close():
    """After a kill the WAL stays; the next client to close folds it in."""
    base, node, ws, marks = setup('kill-close', steps=6)
    proc = popen_continue(ws)
    time.sleep(1.0)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    files = sidecars(ws)
    a = head(copy_workspace(ws, base / 'main-only-after-kill') / 'campaign.sqlite3')
    status = json.loads(cli('status', '--workspace', ws).stdout)['status']
    files_after = sidecars(ws)
    b = head(copy_workspace(ws, base / 'main-only-after-status') / 'campaign.sqlite3')
    RESULTS['kill_then_close'] = {'after_kill': files, 'main_only_after_kill': a, 'status': status,
                                  'after_status': files_after, 'main_only_after_status': b,
                                  'workspace': head(ws / 'campaign.sqlite3')}
    print('kill then close:', json.dumps(RESULTS['kill_then_close']))


def s_backup():
    base, node, ws, marks = setup('backup', steps=4)
    proc = popen_continue(ws)
    obs = Observer(ws)
    wait_seq(obs, 6)
    obs.close()
    paused = cli('pause-dispatch', '--workspace', ws, '--reason', 'archive')
    proc.wait(timeout=120)
    before = head(ws / 'campaign.sqlite3')
    out = cli('backup', '--workspace', ws, '--destination', base / 'backup.zip')
    restored = cli('restore', base / 'backup.zip', '--workspace', base / 'restored')
    after = head(base / 'restored' / 'campaign.sqlite3')
    RESULTS['backup'] = {'pause': paused.returncode, 'backup': out.returncode, 'restore': restored.returncode,
                         'original': before, 'restored': after}
    print('backup/restore:', json.dumps(RESULTS['backup']))


def s_continue_stale():
    """What experiment-craft does with a copy that missed decisions."""
    rows = {}

    def outcome(copy):
        p = cli('continue', '--workspace', copy, check=False)
        return [p.returncode, json.loads(p.stdout)['status'] if p.returncode in (0, 1) else json.loads(p.stderr)['error']['code']]

    # (a) A copy without its WAL, taken while the original advanced.
    base, node, ws, marks = setup('stale-launch', steps=6)
    proc = popen_continue(ws)
    obs = Observer(ws)
    wait_seq(obs, 8)
    copy = copy_workspace(ws, base / 'copy')
    proc.wait(timeout=120)
    obs.close()
    copy_head = head(copy / 'campaign.sqlite3')
    rows['missed_launches'] = {'copy': copy_head, 'continue': outcome(copy), 'jobs': len(runtime(node, 'jobs', 'list')),
                               'runs_per_step': runs(marks, 6)}
    # (b) A copy without its WAL that missed a stop: any open client keeps the stop in the WAL.
    base, node, ws, marks = setup('stale-stop', steps=6)
    cli('continue', '--workspace', ws, '--once')
    cli('continue', '--workspace', ws, '--once')
    reader = sqlite3.connect(ws / 'campaign.sqlite3', isolation_level=None)
    reader.execute('SELECT count(*) FROM events').fetchone()  # a connection counts once it has read
    stopped = json.loads(cli('stop', '--workspace', ws).stdout)
    copy = copy_workspace(ws, base / 'copy')
    reader.close()
    before = len(runtime(node, 'jobs', 'list'))
    rows['missed_stop_in_wal'] = {'original_after_stop': stopped['status'], 'jobs_before': before,
                                  'copy': head(copy / 'campaign.sqlite3'), 'copy_continue': outcome(copy),
                                  'jobs_after': len(runtime(node, 'jobs', 'list')),
                                  'steps_ran': sorted(p.name for p in marks.iterdir())}
    # (c) A complete copy of the whole directory taken before the stop: an
    # earlier workspace, not a damaged one.
    base, node, ws, marks = setup('earlier-copy', steps=6)
    cli('continue', '--workspace', ws, '--once')
    cli('continue', '--workspace', ws, '--once')
    copy = copy_workspace(ws, base / 'copy')
    stopped = json.loads(cli('stop', '--workspace', ws).stdout)
    before = len(runtime(node, 'jobs', 'list'))
    rows['earlier_whole_copy'] = {'original_after_stop': stopped['status'], 'jobs_before': before,
                                  'copy_continue': outcome(copy), 'jobs_after': len(runtime(node, 'jobs', 'list')),
                                  'steps_ran': sorted(p.name for p in marks.iterdir())}
    RESULTS['continue_stale'] = rows
    print('continue a stale copy:', json.dumps(rows))


def s_check():
    """workspace-check on a live workspace, a copy without its WAL and the dashboard's start."""
    import experiment_craft.operations
    if not hasattr(experiment_craft.operations, 'check_workspace'):
        RESULTS['check'] = 'workspace-check does not exist at this commit'
        return
    base, node, ws, marks = setup('check', steps=6)
    proc = popen_continue(ws)
    obs = Observer(ws)
    wait_seq(obs, 8)
    live = json.loads(cli('workspace-check', '--workspace', ws).stdout)
    copy = copy_workspace(ws, base / 'copy')
    proc.wait(timeout=120)
    obs.close()
    copied = json.loads(cli('workspace-check', '--workspace', copy).stdout)
    done = json.loads(cli('workspace-check', '--workspace', ws).stdout)
    dash = cli('dashboard', '--workspace', ws, '--workspace', copy, '--state-dir', base / 'ui', '--port', '0', check=False)
    keep = ['findings', 'last_decision', 'main_file_alone', 'head', 'unissued_with_results', 'unrecorded_results', 'advancing']
    RESULTS['check'] = {'while_running': {k: live[k] for k in keep}, 'copy_without_wal': {k: copied[k] for k in keep},
                        'after_the_client_closed': {k: done[k] for k in keep},
                        'dashboard_with_the_copy': [dash.returncode, (json.loads(dash.stderr)['error'] if dash.stderr.strip() else None)]}
    print('workspace-check:', json.dumps(RESULTS['check']))


def s_dashboard_kill(trials=6):
    """SIGKILL a dashboard that advances while CLI clients read and pause."""
    import http.client
    from urllib.parse import urlsplit
    rows = []
    for t in range(trials):
        base, node, ws, marks = setup(f'dash-kill-{t}', steps=6)
        proc = subprocess.Popen([sys.executable, '-m', 'experiment_craft', 'dashboard', '--workspace', str(ws),
                                 '--state-dir', str(base / 'ui'), '--port', '0'], cwd=PROJECT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        url = urlsplit(json.loads(proc.stdout.readline())['url'])
        token = url.fragment.split('=', 1)[1]
        cid = json.loads(cli('status', '--workspace', ws).stdout)['campaign_id']
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
        connection.request('POST', f'/api/campaigns/{cid}/continue', body='{}', headers={
            'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
            'Origin': f'{url.scheme}://{url.netloc}'})
        status = connection.getresponse().status
        connection.close()
        obs = Observer(ws)
        deadline = time.monotonic() + random.uniform(0.5, 2.5)
        while time.monotonic() < deadline:
            obs.poll()
            cli('status', '--workspace', ws)
            if t % 2 and time.monotonic() > deadline - 0.3:
                cli('pause-dispatch', '--workspace', ws, '--reason', 'test')
                break
        seen = obs.poll()
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait()
        seen = max(seen, obs.poll())
        wal = sidecars(ws)['-wal']
        obs.close()
        reopened = head(ws / 'campaign.sqlite3')
        rows.append({'trial': t, 'continue_http': status, 'seen_seq': seen, 'reopened_seq': reopened['seq'],
                     'wal_bytes_after_kill': wal, 'reopened': reopened})
    RESULTS['dashboard_kill'] = rows
    print('dashboard kill: lost committed decisions in', sum(r['reopened_seq'] < r['seen_seq'] for r in rows),
          'of', trials, 'trials:', json.dumps([(r['seen_seq'], r['reopened_seq'], r['reopened']['paused']) for r in rows]))


SCENARIOS = {'dashboard_kill': s_dashboard_kill, 'kill': s_kill, 'copy_live': s_copy_live, 'copy_torn': s_copy_torn, 'checkpoint': s_checkpoint,
             'kill_then_close': s_kill_then_close, 'backup': s_backup, 'continue_stale': s_continue_stale,
             'check': s_check}

if __name__ == '__main__':
    random.seed(20261028)
    names = sys.argv[4:] or list(SCENARIOS)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        SCENARIOS[name]()
    (OUT / 'results.json').write_text(json.dumps(RESULTS, indent=1))
