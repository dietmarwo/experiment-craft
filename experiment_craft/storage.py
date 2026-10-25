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
            require(self.read()['schema_version'] == 'experiment.campaign.state/0.1',
                    'unsupported_state', 'unsupported campaign state version')

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
            self.db.execute('INSERT INTO events(value) VALUES (?)', (canonical(event).decode(),))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def events(self, after=0, limit=1000):
        require(type(after) is int and after >= 0 and type(limit) is int and 1 <= limit <= 10000,
                'invalid_command', 'events require after>=0 and limit 1..10000')
        return [{'seq': row[0], **loads(row[1])} for row in self.db.execute(
            'SELECT seq,value FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after, limit))]

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
