#!/usr/bin/env python3
"""Reproduce the P0 baseline. This is development tooling, not a job runtime."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def verify_repo(path, entry):
    """Fail before building modified or incorrectly pinned source."""
    if git(path, 'rev-parse', 'HEAD') != entry['commit']:
        raise ValueError(f'{path}: HEAD differs from baseline-lock.json')
    if git(path, 'status', '--porcelain', '--untracked-files=normal'):
        raise ValueError(f'{path}: working tree is not clean; preserve your changes elsewhere')
    for name, expected in entry['files_sha256'].items():
        if digest(path / name) != expected:
            raise ValueError(f'{path / name}: checksum differs from baseline-lock.json')


def fetch_repo(path, entry):
    if path.exists():
        verify_repo(path, entry)
        return
    # Never reset or remove an existing checkout. A failed fetch stays for inspection.
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', str(path)], check=True)
    subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', entry['url']], check=True)
    subprocess.run(['git', '-C', str(path), 'fetch', '--depth', '1', 'origin', entry['commit']], check=True)
    subprocess.run(['git', '-C', str(path), 'checkout', '--detach', entry['commit']], check=True)
    verify_repo(path, entry)


def execute(name, argv, cwd, environment, output):
    """Capture the exact argv, status and output of a finite development check."""
    print(f'{name}: {" ".join(map(str, argv))}', flush=True)
    record = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd),
              'started_at': datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    with (output / f'{name}.log').open('w') as log:
        try:
            # Native harnesses own job supervision; do not implement another scheduler here.
            status = subprocess.run(argv, cwd=cwd, env=environment, stdout=log,
                                    stderr=subprocess.STDOUT).returncode
        except OSError as error:
            log.write(f'{error}\n')
            status = 127
    record.update(exit_code=status, status='passed' if status == 0 else 'failed',
                  elapsed_seconds=time.monotonic() - started, log=f'{name}.log')
    (output / f'{name}.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'{name}: {record["status"]} (see {output / record["log"]})', flush=True)
    return status == 0


def checks(repos):
    for repo, short in [('optimization-jobs', 'runner'), ('fcmaes-rust', 'fcmaes'),
                        ('LP-IP-craft', 'lp-ip'), ('SQP-craft', 'sqp')]:
        yield repo, short + '-fmt', ['cargo', '+1.88.0', 'fmt', '--all', '--', '--check']
        yield repo, short + '-clippy', ['cargo', '+1.88.0', 'clippy', '--locked', '--workspace', '--all-targets', '--', '-D', 'warnings']
        yield repo, short + '-tests', ['cargo', '+1.88.0', 'test', '--release', '--locked', '--workspace']
    yield 'optimization-jobs', 'runner-docs', ['cargo', '+1.88.0', 'doc', '--locked', '--no-deps']
    yield 'fcmaes-rust', 'fcmaes-doc-consistency', [sys.executable, 'scripts/check_doc_consistency.py']
    for name in ['review', 'mcp', 'integration']:
        yield 'optimization-jobs', name, [sys.executable, f'scripts/job-api/test_{name}.py', '-v']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fetch', 'verify', 'build', 'check', 'smoke', 'all'])
    parser.add_argument('--workspace', type=Path, default=PROJECT / '.baseline',
                        help='contains repos/ and target/; existing repositories must match the lock')
    parser.add_argument('--output', type=Path, help='new evidence directory (must not exist)')
    parser.add_argument('--jobs', type=int, default=2, help='Cargo compilation parallelism')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    lock = json.loads((PROJECT / 'baseline-lock.json').read_text())
    workspace = args.workspace.resolve()
    repos = workspace / 'repos'
    for name, entry in lock['repositories'].items():
        if args.action in {'fetch', 'all'}:
            fetch_repo(repos / name, entry)
        else:
            verify_repo(repos / name, entry)
    if args.action in {'fetch', 'verify'}:
        print('All four source revisions and locked files verified.')
        return 0
    output = (args.output or workspace / ('evidence-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(CARGO_TARGET_DIR=str(workspace / 'target'), CARGO_BUILD_JOBS=str(args.jobs),
               CARGO_NET_GIT_FETCH_WITH_CLI='true', JOB_API_TARGET=str(workspace / 'target/release'),
               JOB_API_REQUIRE_SCHEMA='1', JOB_API_REQUIRE_WORKER='1',
               JOB_API_TUTORIALS=str(repos / 'fcmaes-rust/tutorials/job-api'),
               RUSTDOCFLAGS='-D warnings', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    passed = True
    if args.action in {'build', 'all'}:
        # Build the current runner last; no worker build may select its older runner bin.
        for name, entry in lock['repositories'].items():
            if name == 'optimization-jobs':
                continue
            argv = ['cargo', '+1.88.0', 'build', '--release', '--locked', '-p', entry['worker_package']]
            if not execute('build-' + name, argv, repos / name, env, output):
                return 1
        if not execute('build-runner', ['cargo', '+1.88.0', 'build', '--release', '--locked'],
                       repos / 'optimization-jobs', env, output):
            return 1
    if args.action in {'check', 'all'}:
        for repo, name, argv in checks(repos):
            passed = execute(name, argv, repos / repo, env, output) and passed
    if args.action in {'smoke', 'all'}:
        passed = execute('smoke', [sys.executable, str(PROJECT / 'scripts/smoke.py'),
                                  '--bin-dir', str(workspace / 'target/release'),
                                  '--schemas', str(repos / 'optimization-jobs/docs/job-api/schemas'),
                                  '--output', str(output / 'smoke')], PROJECT, env, output) and passed
    for name, entry in lock['repositories'].items():
        verify_repo(repos / name, entry)
    print(f'Evidence: {output}')
    return 0 if passed else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'baseline: {error}', file=sys.stderr)
        sys.exit(1)

