"""Session command recorder; delivered baseline evidence uses repository tooling."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
TOOLS = BASE.parent / 'iteration-01/toolchains'
VENV = BASE.parent / 'iteration-01/venv'
parser = argparse.ArgumentParser()
parser.add_argument('--repo', default='optimization-jobs')
parser.add_argument('--timeout', type=int, default=3600)
parser.add_argument('name')
parser.add_argument('argv', nargs=argparse.REMAINDER)
args = parser.parse_args()
argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
env = os.environ.copy()
env.update(RUSTUP_HOME=str(TOOLS/'rustup'), CARGO_HOME=str(TOOLS/'cargo'),
           CARGO_TARGET_DIR=str(BASE/'target'), CARGO_BUILD_JOBS='4',
           CARGO_NET_GIT_FETCH_WITH_CLI='true', CARGO_TERM_COLOR='never',
           JOB_API_TARGET=str(BASE/'bin'), JOB_API_REQUIRE_SCHEMA='1', JOB_API_REQUIRE_WORKER='1',
           JOB_API_TUTORIALS=str(BASE/'repos/fcmaes-rust/tutorials/job-api'),
           RUSTDOCFLAGS='-D warnings', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
env['PATH'] = str(TOOLS/'cargo/bin') + os.pathsep + str(VENV/'bin') + os.pathsep + env['PATH']
cwd = BASE/'repos'/args.repo
record = dict(name=args.name, argv=argv, cwd=str(cwd), started_at=datetime.now(timezone.utc).isoformat())
started = time.monotonic()
log = BASE/'evidence'/(args.name+'.log')
with log.open('w') as stream:
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            code = 124
    except OSError as error:
        stream.write(str(error)+'\n')
        code = 127
record.update(exit_code=code, status='passed' if code==0 else 'failed', elapsed_seconds=round(time.monotonic()-started,2), log=log.name)
(BASE/'evidence'/(args.name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
print('\n'.join(log.read_text(errors='replace').splitlines()[-10:]),flush=True)
sys.exit(code)
