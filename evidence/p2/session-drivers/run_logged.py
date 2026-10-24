"""Record a task command while keeping toolchains and build output isolated."""
import argparse,json,os,signal,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--repo',default='optimization-jobs');p.add_argument('--timeout',type=int,default=3600);p.add_argument('name');p.add_argument('argv',nargs=argparse.REMAINDER);a=p.parse_args()
argv=a.argv[1:] if a.argv[:1]==['--'] else a.argv
env=dict(os.environ,CARGO_HOME=str(BASE/'toolchains/cargo'),RUSTUP_HOME=str(BASE/'toolchains/rustup'),CARGO_TARGET_DIR=str(BASE/'target'),CARGO_BUILD_JOBS='4',CARGO_TERM_COLOR='never',CARGO_NET_GIT_FETCH_WITH_CLI='true',JOB_API_TARGET=str(BASE/'bin'),JOB_API_REQUIRE_WORKER='1',JOB_API_REQUIRE_SCHEMA='1',JOB_API_TUTORIALS=str(BASE/'repos/fcmaes-rust/tutorials/job-api'),RUSTDOCFLAGS='-D warnings',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
env['PATH']=str(BASE/'toolchains/cargo/bin')+os.pathsep+str(BASE/'venv/bin')+os.pathsep+env['PATH']
record={'name':a.name,'argv':argv,'cwd':str(BASE/'repos'/a.repo),'started_at':datetime.now(timezone.utc).isoformat()};start=time.monotonic();log=BASE/'evidence'/(a.name+'.log')
with log.open('w') as stream:
 try:
  process=subprocess.Popen(argv,cwd=record['cwd'],env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=process.wait(timeout=a.timeout)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait();code=124
 except OSError as error:stream.write(str(error)+'\n');code=127
record.update(exit_code=code,status='passed' if code==0 else 'failed',elapsed_seconds=round(time.monotonic()-start,2),log=log.name)
(BASE/'evidence'/(a.name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record));print('\n'.join(log.read_text(errors='replace').splitlines()[-10:]));sys.exit(code)
