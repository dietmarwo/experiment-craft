"""Campaign maintenance and checked backups; native recovery stays in Rust."""
from contextlib import closing, contextmanager
import hashlib
import itertools
from importlib.resources import files
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import zipfile
import zlib

import jsonschema

from . import __version__
from .campaign import ACTIVE, cached_native, checked_native, event, observe, pause_dispatch, runtime_for, verified_job
from .comparison import bound_protocol
from .storage import (Error, MAX_FILE, MAX_JSON, Store, canonical, fingerprint, identity,
                      loads, publish_directory, read_json, require)

DEFAULT_BYTES = 1024 ** 3
MAX_BYTES = 16 * 1024 ** 3
MAX_DB = 256 * 1024 ** 2
MAX_ENTRIES = 20000
ROOTS = {'files', 'requests', 'results'}


def pause(store, reason='operator'):
    require(isinstance(reason, str) and 1 <= len(reason) <= 1024, 'invalid_command', 'pause reason must be 1..1024 characters')
    return pause_dispatch(store, reason)


def audit(store):
    """Check retained scientific inputs/results and P6's three declaration anchors."""
    state = store.read()
    plan = read_json(store.root / 'plan.json')
    require(canonical(plan) == canonical(state['plan']), 'backup_integrity', 'retained plan differs from the database')
    require(plan['plan_id'] == identity({k: v for k, v in plan.items() if k != 'plan_id'}),
            'backup_integrity', 'scientific plan identity changed')
    for step in plan['steps']:
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}', step['id']) and
                re.fullmatch(r'[a-f0-9]{32}', state['steps'][step['id']]['job_id']),
                'backup_integrity', 'invalid retained step/handle')
        for item in step['job'].get('inputs', []):
            if 'from' not in item:
                require(re.fullmatch(r'[a-f0-9]{64}', item['sha256']), 'backup_integrity', 'invalid retained input hash')
                path = store.root / 'files' / item['sha256']
                require(not path.is_symlink() and not path.parent.is_symlink() and
                        fingerprint(path)['sha256'] == item['sha256'],
                        'input_changed', 'retained static input changed')
        if state['steps'][step['id']].get('native'):
            saved = state['steps'][step['id']]
            require(saved['native']['path'] == f"results/{step['id']}/native.json" and
                    not (store.root / 'results').is_symlink() and
                    not (store.root / 'results' / step['id']).is_symlink() and
                    not (store.root / saved['native']['path']).is_symlink(),
                    'backup_integrity', 'invalid retained native path')
            cached_native(store, saved)
    exists = store.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comparison_protocol'").fetchone()
    require(bool(exists) == bool(state.get('comparison_binding_id')), 'comparison_changed', 'comparison declaration is missing')
    if exists:
        bound_protocol(store)
    require(store.db.execute('PRAGMA integrity_check').fetchall() == [('ok',)],
            'backup_integrity', 'SQLite integrity check failed')
    require(not store.db.execute("SELECT name FROM sqlite_master WHERE type IN ('trigger','view')").fetchall(),
            'backup_integrity', 'unsupported database triggers or views')
    return state


def unpause(store):
    """Observe every planned handle before clearing a pause; never submit/repair."""
    with store.advance_lock():
        before = store.maintenance()
        if not before['paused']:
            return before
        state = audit(store)
        runtime = runtime_for(state)
        runtime.verify(state['plan'])
        for step in state['plan']['steps']:
            saved = store.read()['steps'][step['id']]
            if not saved['issued']:
                try:
                    runtime.get(saved['job_id'])
                except Error as exc:
                    if exc.code == 'unknown_job':
                        continue
                    raise
                raise Error('recovery_diverged', 'a never-issued handle exists on the node; keep paused and inspect a newer backup')
            job = verified_job(runtime, saved)
            if saved['status'] in ACTIVE:
                observe(store, runtime, step)
                current = store.read()['steps'][step['id']]
                require(current['status'] != 'unknown' and not current.get('error'), 'recovery_unverified',
                        'issued work remains uncertain; inspect the same native handle through optimization-jobs')
            else:
                require(job['state'] in {'completed', 'failed', 'cancelled', 'timed_out', 'interrupted'},
                        'recovery_unverified', 'a retained terminal job is no longer terminal on the node')
                record, _, data = checked_native(runtime, job)
                require(saved.get('native') and saved['native']['bytes'] == len(data) and
                        saved['native']['sha256'] == hashlib.sha256(data).hexdigest() and
                        saved.get('execution_identity') == record.get('identity'),
                        'recovery_unverified', 'terminal evidence differs from the backup')
        with store.edit(event('dispatch_unpaused', checked_steps=len(state['plan']['steps']))):
            value = store.maintenance()
            require(value['paused'] and value['generation'] == before['generation'],
                    'maintenance_changed', 'another pause was requested during reconciliation')
            value.update(paused=False, generation=value['generation'] + 1, reason=None)
            store.set_maintenance(value)
        return value


def path_name(name):
    require(isinstance(name, str) and 1 <= len(name) <= 1024 and re.fullmatch(r'[A-Za-z0-9_./-]+', name),
            'invalid_backup', 'invalid backup path')
    parts = name.split('/')
    require(all(part not in ['', '.', '..'] for part in parts), 'invalid_backup', 'backup path traversal')
    require(name in ['campaign.sqlite3', 'plan.json'] or len(parts) >= 2 and parts[0] in ROOTS,
            'invalid_backup', 'backup path is outside authoritative campaign files')
    return name


def limit(value):
    require(type(value) is int and 1 <= value <= MAX_BYTES, 'invalid_command', 'max-bytes must be 1..17179869184')
    return value


def tree_files(root):
    """Only authoritative campaign files, excluding live CLI logs and lock files."""
    yield root / 'plan.json'
    for name in sorted(ROOTS):
        directory = root / name
        require(not directory.is_symlink(), 'invalid_backup', 'backup directories cannot be symlinks')
        if not directory.exists():
            continue
        for current, dirs, names in os.walk(directory, followlinks=False):
            for child in dirs:
                require(not (Path(current) / child).is_symlink(), 'invalid_backup', 'backup contains a symlink directory')
            for child in sorted(names):
                if name == 'requests' and child in ['runner.stdout', 'runner.stderr']:
                    continue  # A surviving native process may still write transport logs.
                yield Path(current) / child


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stream_copy(source, destination, expected):
    digest, count = hashlib.sha256(), 0
    while block := source.read(65536):
        count += len(block)
        require(count <= expected['bytes'], 'backup_integrity', 'backup entry grew while copying')
        digest.update(block)
        destination.write(block)
    require(count == expected['bytes'] and digest.hexdigest() == expected['sha256'],
            'backup_integrity', 'backup entry size/digest mismatch')


def decisions(store):
    """What every decision changes: the last event and the state and maintenance rows."""
    rows = [store.db.execute('SELECT max(seq) FROM events').fetchone()[0],
            store.db.execute('SELECT value FROM state WHERE id=1').fetchone()[0]]
    if store.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance'").fetchone():
        rows.append(store.db.execute('SELECT value FROM maintenance WHERE id=1').fetchone())
    return identity(rows)


def backup(store, destination, max_bytes=DEFAULT_BYTES):
    max_bytes = limit(max_bytes)
    destination = Path(destination).absolute()
    require(not destination.exists() and not destination.is_symlink(), 'backup_exists', 'backup destination already exists')
    require(not destination.resolve().is_relative_to(store.root), 'invalid_backup', 'write the backup outside the campaign workspace')
    require(store.maintenance()['paused'], 'dispatch_not_paused', 'pause-dispatch before backing up')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with store.advance_lock(), tempfile.TemporaryDirectory(prefix='.backup-', dir=destination.parent) as directory:
        temp = Path(directory)
        require(not (store.root / 'campaign.sqlite3').is_symlink(), 'invalid_backup', 'campaign database cannot be a symlink')
        # Block decision writes only for the online SQLite snapshot. The
        # advancement lock keeps authoritative inputs/results stable afterward;
        # pause/stop commands remain responsive during archive compression.
        store.db.execute('BEGIN IMMEDIATE')
        try:
            require(store.maintenance()['paused'], 'dispatch_not_paused', 'pause-dispatch before backing up')
            with closing(sqlite3.connect(store.root / 'campaign.sqlite3')) as source:
                pages = source.execute('PRAGMA page_count').fetchone()[0]
                page_size = source.execute('PRAGMA page_size').fetchone()[0]
                require(pages * page_size <= MAX_DB, 'backup_size_limit', 'campaign database exceeds 256 MiB')
                with closing(sqlite3.connect(temp / 'campaign.sqlite3')) as target:
                    source.backup(target)
            snapshotted = decisions(store)
        finally:
            store.db.execute('ROLLBACK')
        with closing(Store(temp)) as snapshot:
            # plan and byte references live in the source workspace; the SQLite
            # snapshot is inspected separately below after its integrity check.
            state = snapshot.read()
            require(snapshot.db.execute('PRAGMA integrity_check').fetchall() == [('ok',)],
                    'backup_integrity', 'SQLite snapshot is not intact')
        audit(store)
        entries, sources, total = [], {}, 0
        for path in itertools.chain([temp / 'campaign.sqlite3'], tree_files(store.root)):
            name = 'campaign.sqlite3' if path.parent == temp else str(path.relative_to(store.root))
            path_name(name)
            require(not path.is_symlink(), 'invalid_backup', 'backup cannot include symlink files')
            meta = fingerprint(path, MAX_DB if name == 'campaign.sqlite3' else MAX_FILE)
            total += meta['bytes']
            require(total <= max_bytes and len(entries) < MAX_ENTRIES, 'backup_size_limit', 'backup exceeds byte/file bound')
            original = store.root / name if name == 'campaign.sqlite3' else path
            entries.append({'path': name, **meta, 'mode': stat.S_IMODE(original.stat().st_mode) & 0o777})
            sources[name] = path
        value = {'schema_version': 'experiment.campaign.backup/0.1', 'package_version': __version__,
                 'campaign_id': state['campaign_id'], 'plan_id': state['plan']['plan_id'],
                 'runtime_binding_id': identity(state['runtime']), 'total_bytes': total, 'entries': entries}
        value['backup_id'] = identity(value)
        data = canonical(value) + b'\n'
        require(len(data) <= MAX_JSON, 'backup_size_limit', 'backup manifest exceeds 4 MiB')
        archive = temp / 'archive.zip'
        archive.touch(mode=0o600, exist_ok=False)
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for item in entries:
                fd = os.open(sources[item['path']], os.O_RDONLY | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as source, output.open('data/' + item['path'], 'w') as target:
                    require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), 'invalid_backup', 'backup input is not regular')
                    stream_copy(source, target, item)
            output.writestr('BACKUP.json', data)
        with archive.open('rb') as stream:
            os.fsync(stream.fileno())
        # Stop and pause stay usable while the archive is written. A decision
        # committed after the snapshot is not in it, so such an archive is
        # refused instead of published: restoring it would undo that decision.
        store.db.execute('BEGIN IMMEDIATE')
        try:
            require(decisions(store) == snapshotted, 'backup_changed',
                    'the campaign changed during the backup (for example a stop); nothing was published, back up again')
            os.link(archive, destination)  # Atomic no-clobber file publication.
        finally:
            store.db.execute('ROLLBACK')
        sync_directory(destination.parent)
    return {'backup': str(destination), 'backup_id': value['backup_id'], 'campaign_id': value['campaign_id'],
            'files': len(entries), 'total_bytes': total, **fingerprint(destination, MAX_BYTES + 128 * 1024 ** 2)}


def inspect_archive(archive, max_bytes):
    max_bytes = limit(max_bytes)
    infos = archive.infolist()
    names = [info.filename for info in infos]
    require(len(names) == len(set(names)) and len(names) <= MAX_ENTRIES + 1,
            'invalid_backup', 'duplicate or excessive archive entries')
    require('BACKUP.json' in names, 'invalid_backup', 'backup manifest is missing')
    meta = archive.getinfo('BACKUP.json')
    require(meta.file_size <= MAX_JSON, 'backup_size_limit', 'backup manifest exceeds 4 MiB')
    with archive.open(meta) as source:
        value = loads(source.read(MAX_JSON + 1))
    schema = read_json(files('experiment_craft').joinpath('schemas/campaign-backup-0.1.schema.json'))
    try:
        jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        raise Error('invalid_backup', exc.message) from exc
    require(value['backup_id'] == identity({k: v for k, v in value.items() if k != 'backup_id'}),
            'backup_integrity', 'backup manifest identity changed')
    paths = [path_name(item['path']) for item in value['entries']]
    require(len(paths) == len(set(paths)) and {'campaign.sqlite3', 'plan.json'} <= set(paths),
            'invalid_backup', 'duplicate or missing campaign paths')
    listed = set(paths)
    require(not any('/'.join(name.split('/')[:i]) in listed for name in paths for i in range(1, len(name.split('/')))),
            'invalid_backup', 'backup file paths overlap their directories')
    require(set(names) == {'BACKUP.json', *('data/' + name for name in paths)},
            'invalid_backup', 'archive has unlisted entries')
    total = sum(item['bytes'] for item in value['entries'])
    require(total == value['total_bytes'] and total <= max_bytes, 'backup_size_limit', 'backup exceeds requested byte bound')
    for item in value['entries']:
        require(type(item['bytes']) is int and type(item['mode']) is int,
                'invalid_backup', 'backup sizes and modes must be integers')
        info = archive.getinfo('data/' + item['path'])
        mode = info.external_attr >> 16
        require(not info.is_dir() and stat.S_IFMT(mode) in [0, stat.S_IFREG] and not info.flag_bits & 1,
                'invalid_backup', 'archive entries must be unencrypted regular files')
        require(info.file_size == item['bytes'] and item['bytes'] <= (MAX_DB if item['path'] == 'campaign.sqlite3' else MAX_FILE),
                'backup_size_limit', 'archive entry exceeds its bound')
    return value


@contextmanager
def archive_source(path, max_bytes):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        require(stat.S_ISREG(info.st_mode), 'invalid_backup', 'backup archive must be a regular file')
        require(info.st_size <= limit(max_bytes) + 128 * 1024 ** 2, 'backup_size_limit', 'archive exceeds its byte bound')
        with zipfile.ZipFile(source) as archive:
            yield archive


def restore(source, workspace, max_bytes=DEFAULT_BYTES):
    workspace = Path(workspace).absolute()
    require(Path(source).is_file(), 'invalid_backup', f'the backup archive is not a readable file: {source}')
    require(not workspace.exists() and not workspace.is_symlink(), 'workspace_exists', 'restore needs a new workspace')
    workspace.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.restore-', dir=workspace.parent))
    try:
        try:
            with archive_source(source, max_bytes) as archive:
                value = inspect_archive(archive, max_bytes)
                for item in value['entries']:
                    target = temp / item['path']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open('data/' + item['path']) as stream, target.open('xb') as output:
                        stream_copy(stream, output, item)
                        output.flush()
                        os.fsync(output.fileno())
                    target.chmod(item['mode'])
        except (zipfile.BadZipFile, RuntimeError, EOFError, zlib.error) as exc:
            raise Error('invalid_backup', str(exc)) from exc
        with closing(Store(temp)) as store:
            state = audit(store)
            require(value['campaign_id'] == state['campaign_id'] and value['plan_id'] == state['plan']['plan_id']
                    and value['runtime_binding_id'] == identity(state['runtime']), 'backup_integrity', 'backup identity differs from SQLite')
            with store.edit(event('backup_restored', backup_id=value['backup_id'])):
                control = store.maintenance()
                control.update(paused=True, generation=control['generation'] + 1,
                               reason='restored; reconcile before dispatch', restored_from=value['backup_id'])
                store.set_maintenance(control)
            store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        for directory, _, _ in os.walk(temp, topdown=False):
            sync_directory(directory)
        publish_directory(temp, workspace)
        sync_directory(workspace.parent)
        return {'workspace': str(workspace), 'campaign_id': value['campaign_id'], 'backup_id': value['backup_id'],
                'dispatch_paused': True, 'runtime_contacted': False}
    finally:
        if temp.exists():
            shutil.rmtree(temp)
