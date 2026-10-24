#!/usr/bin/env python3
"""Reproduce the pinned baseline: fetch, verify, build, smoke and check.

This is development tooling for experiment-craft, not a job runtime. The
native runner and the upstream harnesses own job supervision.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
ACTIONS = ['fetch', 'verify', 'build', 'smoke', 'check']
RUNNER = 'optimization-jobs'
RUNNER_BINARIES = ['optimization-run', 'optimization-mcp']
PIN = re.compile(r'github\.com/dietmarwo/optimization-jobs", rev = "([0-9a-f]{40})"')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def has_commit(path, commit):
    return subprocess.run(['git', '-C', str(path), 'cat-file', '-e', commit + '^{commit}'],
                          capture_output=True).returncode == 0


def verify_repo(path, entry):
    """Fail before building modified or incorrectly pinned source."""
    if not path.exists():
        raise ValueError(f'{path}: no checkout; run the fetch action')
    try:
        head = git(path, 'rev-parse', 'HEAD')
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f'{path}: not a complete checkout ({error}); '
                         'use a new workspace or remove this directory yourself') from error
    if head != entry['commit']:
        raise ValueError(f'{path}: HEAD differs from baseline-lock.json')
    if git(path, 'status', '--porcelain', '--untracked-files=normal'):
        raise ValueError(f'{path}: working tree is not clean; preserve your changes elsewhere')
    for name, expected in entry['files_sha256'].items():
        if digest(path / name) != expected:
            raise ValueError(f'{path / name}: checksum differs from baseline-lock.json')


def fetch_commit(path, commit):
    subprocess.run(['git', '-C', str(path), 'fetch', '-q', '--depth', '1', 'origin', commit], check=True)


def fetch_repo(path, entry):
    if path.exists():
        verify_repo(path, entry)
        return
    # Never reset or remove an existing checkout. A failed fetch stays for inspection.
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', entry['url']], check=True)
    fetch_commit(path, entry['commit'])
    subprocess.run(['git', '-C', str(path), 'checkout', '-q', '--detach', entry['commit']], check=True)
    verify_repo(path, entry)


def verify_pins(repos, lock):
    """Every tracked manifest and lockfile of a worker uses the recorded optimization-jobs revision.

    This mirrors the workers' shared-pin.yml, except its ancestry check: with
    depth-1 fetches, whether the pin is on optimization-jobs main is not known here.
    """
    pin = lock['contracts']['worker_job_api_revision']
    for name, entry in lock['repositories'].items():
        if name == RUNNER:
            continue
        path = repos / name
        if entry['job_api_revision'] != pin:
            raise ValueError(f'baseline-lock.json: {name} job_api_revision differs from worker_job_api_revision')
        files = git(path, 'ls-files', '*Cargo.toml', '*Cargo.lock').splitlines()
        revisions = set()
        for file in files:
            text = (path / file).read_text()
            if file.endswith('Cargo.toml'):
                revisions |= set(PIN.findall(text))
            for line in text.splitlines():
                if 'github.com/dietmarwo/optimization-jobs' in line and f'rev={pin}#{pin}' not in line \
                        and file.endswith('Cargo.lock'):
                    raise ValueError(f'{path / file}: optimization-jobs does not resolve to {pin}')
        if revisions != {pin}:
            raise ValueError(f'{path}: the Cargo.toml files pin optimization-jobs at {sorted(revisions)}, not {pin}')


def shared_changes(path, pin, paths):
    """Shared files that differ between the workers' pin and the runner checkout."""
    if not has_commit(path, pin):
        raise ValueError(f'{path}: the worker pin {pin} is not fetched; run the fetch action')
    return git(path, 'diff', '--name-only', pin, 'HEAD', '--', *paths).splitlines()


def verify_shared(repos, lock):
    contracts = lock['contracts']
    changed = shared_changes(repos / RUNNER, contracts['worker_job_api_revision'], contracts['shared_paths'])
    if changed:
        raise ValueError('optimization-jobs changed files shared with the workers since their pin: '
                         + ', '.join(changed))
    return {path: {commit: git(repos / RUNNER, 'rev-parse', f'{commit}:{path}')
                   for commit in [contracts['worker_job_api_revision'], 'HEAD']}
            for path in contracts['shared_paths']}


def verify_project(lock):
    toolchain = lock['toolchain']
    if digest(PROJECT / toolchain['python_requirements']) != toolchain['python_requirements_sha256']:
        raise ValueError(f'{toolchain["python_requirements"]}: checksum differs from baseline-lock.json')


def prepare_sources(repos, lock, fetch):
    for name, entry in lock['repositories'].items():
        (fetch_repo if fetch else verify_repo)(repos / name, entry)
    pin = lock['contracts']['worker_job_api_revision']
    if fetch and not has_commit(repos / RUNNER, pin):
        fetch_commit(repos / RUNNER, pin)  # adds an object; the checkout is unchanged
    verify_pins(repos, lock)
    return verify_shared(repos, lock)


def probe(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return {'argv': argv, 'exit_code': result.returncode,
                'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'argv': argv, 'error': str(error)}


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def environment():
    return {'platform': platform.platform(), 'machine': platform.machine(),
            'python': platform.python_version(), 'cpu_count': os.cpu_count(),
            'cpu_affinity_count': len(os.sched_getaffinity(0)),
            'cgroup_cpu_max': read_text('/sys/fs/cgroup/cpu.max'),
            'cgroup_memory_max': read_text('/sys/fs/cgroup/memory.max'),
            'git': probe(['git', '--version']), 'cc': probe(['cc', '--version']),
            # Exit 0 alone is not evidence of a usable user manager; keep the output.
            'systemd_user': probe(['systemctl', '--user', 'is-system-running'])}


def toolchains(build, lint, actions):
    """Exact versions of the toolchains the selected actions use."""
    used = {}
    if {'build', 'check'} & set(actions):
        used['build'] = {'requested': build, 'rustc': probe(['rustc', f'+{build}', '-Vv']),
                         'cargo': probe(['cargo', f'+{build}', '-V'])}
    if 'check' in actions:
        used['lint'] = {'requested': lint, 'rustc': probe(['rustc', f'+{lint}', '-V']),
                        'clippy': probe(['cargo', f'+{lint}', 'clippy', '-V']),
                        'rustfmt': probe(['cargo', f'+{lint}', 'fmt', '--version'])}
    return used


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def execute(name, argv, cwd, env, output, steps):
    """Capture the exact argv, status and output of a finite development check."""
    print(f'{name}: {" ".join(map(str, argv))}', flush=True)
    record = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd),
              'started_at': datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    with (output / 'checks' / f'{name}.log').open('w') as log:
        try:
            # Native harnesses own job supervision; do not implement another scheduler here.
            status = subprocess.run(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        except OSError as error:
            log.write(f'{error}\n')
            status = 127
    record.update(exit_code=status, status='passed' if status == 0 else 'failed',
                  elapsed_seconds=round(time.monotonic() - started, 1), log=f'{name}.log')
    write_json(output / 'checks' / f'{name}.json', record)
    steps.append({key: record[key] for key in ['name', 'status', 'exit_code', 'elapsed_seconds']})
    print(f'{name}: {record["status"]} (see {output / "checks" / record["log"]})', flush=True)
    return status == 0


def binary_names(lock):
    workers = [entry['worker_package'] for name, entry in lock['repositories'].items() if name != RUNNER]
    return RUNNER_BINARIES + workers


def stage_binaries(target, destination, names):
    """Copy the built executables so later checks cannot replace what smoke tests."""
    destination.mkdir(parents=True, exist_ok=True)
    staged = {}
    for name in names:
        source = target / name
        if not source.is_file():
            raise ValueError(f'missing built executable: {source}')
        if not os.access(source, os.X_OK):
            raise ValueError(f'built file is not executable: {source}')
        temporary = destination / f'.{name}.tmp'
        shutil.copy2(source, temporary)
        os.replace(temporary, destination / name)
        staged[name] = {'sha256': digest(destination / name), 'size': (destination / name).stat().st_size}
    return staged


def staged_manifest(bins, lock):
    """The manifest of WORKSPACE/bin, after checking that the files still match it."""
    path = bins / 'manifest.json'
    if not path.is_file():
        raise ValueError(f'{bins}: no staged executables; run the build action first')
    manifest = json.loads(path.read_text())
    if manifest['sources'] != {name: entry['commit'] for name, entry in lock['repositories'].items()}:
        raise ValueError(f'{bins}: staged from other commits than baseline-lock.json; run the build action')
    for name in binary_names(lock):
        expected = manifest['files'].get(name, {}).get('sha256')
        if not (bins / name).is_file() or digest(bins / name) != expected:
            raise ValueError(f'{bins / name}: missing or changed since it was staged; run the build action')
        if not os.access(bins / name, os.X_OK):
            raise ValueError(f'staged file is not executable: {bins / name}')
    return manifest


def checks(repos, build, lint):
    """Upstream checks. Format and lint use the toolchain of the repositories' CI gate."""
    for repo, short in [(RUNNER, 'runner'), ('fcmaes-rust', 'fcmaes'),
                        ('LP-IP-craft', 'lp-ip'), ('SQP-craft', 'sqp')]:
        yield repo, short + '-fmt', ['cargo', f'+{lint}', 'fmt', '--all', '--', '--check']
        # --keep-going reports every crate's diagnostics instead of stopping at the first.
        yield repo, short + '-clippy', ['cargo', f'+{lint}', 'clippy', '--locked', '--workspace',
                                        '--all-targets', '--keep-going', '--', '-D', 'warnings']
        yield repo, short + '-tests', ['cargo', f'+{build}', 'test', '--release', '--locked', '--workspace']
    yield RUNNER, 'runner-docs', ['cargo', f'+{lint}', 'doc', '--locked', '--no-deps']
    yield 'fcmaes-rust', 'fcmaes-doc-consistency', [sys.executable, 'scripts/check_doc_consistency.py']
    for name in ['review', 'mcp', 'integration', 'commands']:
        yield RUNNER, name, [sys.executable, f'scripts/job-api/test_{name}.py', '-v']


def selected(names):
    chosen = set(ACTIONS[:1] + ACTIONS[2:]) if 'all' in names else set(names)
    return [action for action in ACTIONS if action in chosen]


def run(args, lock):
    actions = selected(args.actions)
    workspace = args.workspace.resolve()
    repos, bins = workspace / 'repos', workspace / 'bin'
    verify_project(lock)
    trees = prepare_sources(repos, lock, 'fetch' in actions)
    if set(actions) <= {'fetch', 'verify'}:
        print(f'All {len(lock["repositories"])} source revisions, locked files and the shared pin verified.')
        return 0
    rust = lock['toolchain']['rust']
    build, lint = args.build_toolchain or rust['build'], args.lint_toolchain or rust['lint']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = (args.output or workspace / f'evidence-{stamp}').resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'checks').mkdir()
    write_json(output / 'sources.json', {
        'repositories': {name: {'commit': entry['commit'], 'files_sha256': entry['files_sha256']}
                         for name, entry in lock['repositories'].items()},
        'worker_job_api_revision': lock['contracts']['worker_job_api_revision'],
        'shared_tree_ids': trees, 'shared_paths_unchanged': True})
    write_json(output / 'environment.json', environment())
    write_json(output / 'toolchains.json', toolchains(build, lint, actions))
    env = os.environ.copy()
    env.update(CARGO_TARGET_DIR=str(workspace / 'target'), CARGO_BUILD_JOBS=str(args.jobs),
               CARGO_NET_GIT_FETCH_WITH_CLI='true', CARGO_TERM_COLOR='never',
               JOB_API_TARGET=str(bins), JOB_API_REQUIRE_SCHEMA='1', JOB_API_REQUIRE_WORKER='1',
               JOB_API_TUTORIALS=str(repos / 'fcmaes-rust/tutorials/job-api'),
               RUSTDOCFLAGS='-D warnings', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    steps, passed = [], True
    summary = {'actions': actions, 'toolchains': {}, 'steps': steps}
    if {'build', 'check'} & set(actions):
        summary['toolchains']['build'] = build
    if 'check' in actions:
        summary['toolchains']['lint'] = lint
    try:
        if 'build' in actions:
            for name, entry in lock['repositories'].items():
                if name == RUNNER:
                    continue
                argv = ['cargo', f'+{build}', 'build', '--release', '--locked', '-p', entry['worker_package']]
                if not execute('build-' + name, argv, repos / name, env, output, steps):
                    summary['status'] = 'failed'
                    return 1
            # Build the current runner last; no worker build may select its pinned runner binary.
            if not execute('build-runner', ['cargo', f'+{build}', 'build', '--release', '--locked'],
                           repos / RUNNER, env, output, steps):
                summary['status'] = 'failed'
                return 1
            staged = stage_binaries(workspace / 'target/release', bins, binary_names(lock))
            write_json(bins / 'manifest.json', {'toolchain': build, 'staged_at': datetime.now(timezone.utc).isoformat(),
                                                'sources': {name: entry['commit'] for name, entry in lock['repositories'].items()},
                                                'files': staged})
        if {'smoke', 'check'} & set(actions):
            # Record the executables actually tested, which an earlier run may have staged.
            manifest = staged_manifest(bins, lock)
            summary['toolchains']['binaries'] = manifest['toolchain']
            write_json(output / 'binaries.json', {'directory': str(bins), **manifest})
        if 'smoke' in actions:
            passed = execute('smoke', [sys.executable, str(PROJECT / 'scripts/smoke.py'),
                                       '--bin-dir', str(bins),
                                       '--schemas', str(repos / RUNNER / 'docs/job-api/schemas'),
                                       '--output', str(output / 'smoke')],
                             PROJECT, env, output, steps) and passed
        if 'check' in actions:
            for repo, name, argv in checks(repos, build, lint):
                passed = execute(name, argv, repos / repo, env, output, steps) and passed
            passed = execute('command-example', [sys.executable,
                str(repos / RUNNER / 'examples/commands/build_run_collect.py'),
                '--runner', str(bins / 'optimization-run'), '--output', str(output / 'command-example')],
                repos / RUNNER, env, output, steps) and passed
        for name, entry in lock['repositories'].items():
            verify_repo(repos / name, entry)
        summary['status'] = 'passed' if passed else 'failed'
    finally:
        summary.setdefault('status', 'error')
        write_json(output / 'summary.json', summary)
        print(f'Evidence: {output}')
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actions', nargs='+', choices=ACTIONS + ['all'],
                        help='run in the order fetch, verify, build, smoke, check; all = every action')
    parser.add_argument('--workspace', type=Path, default=PROJECT / '.baseline',
                        help='contains repos/, target/ and bin/; existing repositories must match the lock')
    parser.add_argument('--output', type=Path, help='new evidence directory (must not exist)')
    parser.add_argument('--jobs', type=int, default=2, help='Cargo compilation parallelism')
    parser.add_argument('--build-toolchain', help='Rust toolchain for builds and tests (default: the lock)')
    parser.add_argument('--lint-toolchain', help='Rust toolchain for fmt, clippy and docs (default: the lock)')
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    return run(args, json.loads((PROJECT / 'baseline-lock.json').read_text()))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'baseline: {error}', file=sys.stderr)
        sys.exit(1)
