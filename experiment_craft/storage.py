"""Strict bounded JSON, checked local snapshots and transactional decisions."""
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile

MAX_JSON = 4 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
HEAD_FILE = 'head.json'
HEAD_VERSION = 'experiment.campaign.head/0.1'


class Error(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, code, message):
    if not condition:
        raise Error(code, message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def exact(value):
    """The decimal a JSON number denotes; a float by its shortest representation."""
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


def number(value, real):
    """A decimal as a JSON number: a float when any operand was one, as Python would give."""
    return float(value) if real else int(value)


def identity(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def loads(data):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'invalid_json', f'duplicate JSON key: {key}')
            out[key] = value
        return out
    try:
        value = json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              Error('invalid_json', f'non-finite number: {value}')))
        json.dumps(value, allow_nan=False)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Error('invalid_json', str(exc)) from exc


def read_json(path):
    data = regular_bytes(path, MAX_JSON)
    require(len(data) <= MAX_JSON, 'size_limit', 'JSON exceeds 4 MiB')
    return loads(data)


def fingerprint(path, limit=MAX_FILE):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'invalid_input', f'not a regular file: {path}')
        size, digest = 0, hashlib.sha256()
        while block := stream.read(65536):
            size += len(block)
            require(size <= limit, 'size_limit', f'file exceeds {limit} bytes: {path}')
            digest.update(block)
    return {'bytes': size, 'sha256': digest.hexdigest()}


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, value):
    atomic(path, canonical(value) + b'\n')


def snapshot(source, destination, meta):
    source, destination = Path(source), Path(destination)
    require(fingerprint(source) == meta, 'input_changed', f'input changed: {source}')
    # Transfer validation and node staging still belong to optimization-jobs.
    # This is the campaign's immutable local source snapshot.
    data = regular_bytes(source, MAX_FILE)
    require(len(data) <= MAX_FILE, 'size_limit', 'snapshot grew beyond 64 MiB')
    atomic(destination, data)
    require(fingerprint(destination) == meta, 'input_changed', 'snapshot changed while reading')


def read_head(root):
    """The last decision a workspace recorded outside SQLite, if any."""
    path = Path(root) / HEAD_FILE
    require(not path.is_symlink(), 'invalid_head', f'{HEAD_FILE} cannot be a symlink')
    try:
        value = read_json(path)
    except FileNotFoundError:
        return None
    except (Error, OSError) as exc:
        raise Error('invalid_head', f'{HEAD_FILE} cannot be read ({exc}); keep the workspace unchanged and inspect it') from exc
    require(isinstance(value, dict) and set(value) == {'schema_version', 'campaign_id', 'seq', 'event_sha256'}
            and value['schema_version'] == HEAD_VERSION and isinstance(value['campaign_id'], str)
            and type(value['seq']) is int and value['seq'] >= 1 and isinstance(value['event_sha256'], str)
            and len(value['event_sha256']) == 64 and all(c in 'abcdef0123456789' for c in value['event_sha256']),
            'invalid_head', f'{HEAD_FILE} is not a campaign head record; keep the workspace unchanged and inspect it')
    return value


class Store:
    def __init__(self, workspace, create=False):
        self.root = Path(workspace).resolve()
        path = self.root / 'campaign.sqlite3'
        require(create or path.is_file(), 'unknown_campaign', 'campaign database is missing')
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA foreign_keys=ON')
        if create:
            self.db.executescript('''CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT NOT NULL);''')
        else:
            try:
                # Read the record before the database: a decision committed in
                # between only makes the database newer than the record.
                head = read_head(self.root)
                state = self.read()
                require(state['schema_version'] == 'experiment.campaign.state/0.1',
                        'unsupported_state', 'unsupported campaign state version')
                if head is not None:
                    self.require_head(head, state['campaign_id'])
            except BaseException:
                self.db.close()
                raise

    def close(self):
        self.db.close()

    def read(self):
        row = self.db.execute('SELECT value FROM state WHERE id=1').fetchone()
        require(row is not None, 'incomplete_campaign', 'campaign initialization did not finish; preserve it and choose a new workspace')
        return loads(row[0])

    @contextmanager
    def edit(self, event):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT value FROM state WHERE id=1').fetchone()
            state = loads(row[0]) if row else {}
            yield state
            self.db.execute('INSERT OR REPLACE INTO state VALUES (1,?)', (canonical(state).decode(),))
            value = canonical(event).decode()
            seq = self.db.execute('INSERT INTO events(value) VALUES (?)', (value,)).lastrowid
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        self.record_head(state.get('campaign_id'), seq, value)

    def require_head(self, head, campaign_id):
        """Refuse a database that lacks, or differs in, the last decision the workspace recorded."""
        require(head['campaign_id'] == campaign_id, 'campaign_conflict',
                f'{HEAD_FILE} records a decision of another campaign: the database or the record was copied from '
                'another workspace; keep both unchanged')
        row = self.db.execute('SELECT value FROM events WHERE seq=?', (head['seq'],)).fetchone()
        if row is None:
            last = self.db.execute('SELECT max(seq) FROM events').fetchone()[0] or 0
            raise Error('state_regressed',
                        f"the database ends at decision {last}, but this workspace recorded decision {head['seq']}: "
                        'the database is an earlier copy, for example one made without campaign.sqlite3-wal. Keep '
                        'this copy unchanged and continue from the complete workspace or a backup')
        require(hashlib.sha256(row[0].encode()).hexdigest() == head['event_sha256'], 'state_regressed',
                f"decision {head['seq']} in the database differs from the one this workspace recorded: the "
                'database comes from another copy of the campaign; keep both unchanged')

    def record_head(self, campaign_id, seq, event):
        """Record a committed decision outside SQLite, as far as possible.

        The record follows its commit, so it is never ahead of the database. A
        record that is missing or behind only leaves a copy less checked: a
        client stopped between the two, a failed write, or a client recording
        an older decision after another client's newer one. A failed write
        therefore does not fail the decision, which is already committed.
        """
        if not isinstance(campaign_id, str):
            return
        try:
            try:
                previous = read_head(self.root)
            except Error:
                previous = None
            if previous and previous['campaign_id'] == campaign_id and previous['seq'] >= seq:
                return
            data = canonical({'schema_version': HEAD_VERSION, 'campaign_id': campaign_id, 'seq': seq,
                              'event_sha256': hashlib.sha256(event.encode()).hexdigest()}) + b'\n'
            database = os.stat(self.root / 'campaign.sqlite3')
            fd, name = tempfile.mkstemp(prefix='.head-', dir=self.root)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    # Whoever can open the database can read the record: like
                    # SQLite's WAL, it takes the database's mode and, when
                    # written by root, its owner.
                    os.fchmod(stream.fileno(), stat.S_IMODE(database.st_mode) & 0o666)
                    if os.geteuid() == 0:
                        os.fchown(stream.fileno(), database.st_uid, database.st_gid)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                # A crash that loses the rename leaves the older record.
                os.replace(name, self.root / HEAD_FILE)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        except OSError:
            pass

    def events(self, after=0, limit=1000):
        require(type(after) is int and after >= 0 and type(limit) is int and 1 <= limit <= 10000,
                'invalid_command', 'events require after>=0 and limit 1..10000')
        return [{'seq': row[0], **loads(row[1])} for row in self.db.execute(
            'SELECT seq,value FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after, limit))]

    def maintenance(self):
        campaign_id = self.read()['campaign_id']
        exists = self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance'").fetchone()
        if not exists:
            return {'schema_version': 'experiment.campaign.maintenance/0.1', 'campaign_id': campaign_id,
                    'paused': False, 'generation': 0, 'reason': None, 'restored_from': None}
        row = self.db.execute('SELECT value FROM maintenance WHERE id=1').fetchone()
        require(row is not None, 'invalid_maintenance', 'maintenance state is missing')
        value = loads(row[0])
        require(isinstance(value, dict) and value.get('schema_version') == 'experiment.campaign.maintenance/0.1'
                and value.get('campaign_id') == campaign_id and type(value.get('paused')) is bool
                and type(value.get('generation')) is int and value['generation'] >= 1
                and set(value) == {'schema_version', 'campaign_id', 'paused', 'generation', 'reason', 'restored_from'}
                and (value['reason'] is None or isinstance(value['reason'], str) and 1 <= len(value['reason']) <= 1024)
                and (value['restored_from'] is None or isinstance(value['restored_from'], str) and
                     len(value['restored_from']) == 64 and all(c in 'abcdef0123456789' for c in value['restored_from'])),
                'invalid_maintenance', 'maintenance state does not match this campaign')
        return value

    def set_maintenance(self, value):
        require(self.db.in_transaction, 'invalid_maintenance', 'maintenance updates need a decision transaction')
        self.db.execute('CREATE TABLE IF NOT EXISTS maintenance (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
        self.db.execute('INSERT OR REPLACE INTO maintenance VALUES (1,?)', (canonical(value).decode(),))

    def require_dispatch(self):
        exists = self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance'").fetchone()
        if not exists:
            return
        require(not self.maintenance()['paused'], 'dispatch_paused',
                'campaign dispatch is paused; reconcile with unpause-dispatch before continuing')

    @contextmanager
    def advance_lock(self):
        with (self.root / 'advance.lock').open('a') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Error('campaign_busy', 'another client is advancing this campaign') from exc
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _renameat2(source, destination, flags):
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), flags):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def publish_directory(source, destination):
    """Atomic Linux no-clobber directory publication."""
    _renameat2(source, destination, 1)  # RENAME_NOREPLACE


def exchange_directories(source, destination):
    """Atomically swap two existing directories (Linux RENAME_EXCHANGE)."""
    _renameat2(source, destination, 2)


def regular_bytes(path, limit=MAX_FILE):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'invalid_input', f'not a regular file: {path}')
        data = stream.read(limit + 1)
    require(len(data) <= limit, 'size_limit', f'file exceeds {limit} bytes: {path}')
    return data
