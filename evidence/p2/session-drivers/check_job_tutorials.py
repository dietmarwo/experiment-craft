"""Check worker examples and local job tutorials at the coordinated pins."""
from pathlib import Path
import json,os,shutil,subprocess,time
B=Path(__file__).resolve().parent;env=dict(os.environ,CARGO_BUILD_JOBS='2',CARGO_TARGET_DIR=str(B/'target'))
mirror=B/'candidate-mirrors/optimization-jobs.git';env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0=f'url.{mirror.as_uri()}.insteadOf',GIT_CONFIG_VALUE_0='https://github.com/dietmarwo/optimization-jobs')
records=[]
def run(label,argv,repo):
 start=time.monotonic();log=B/'evidence'/(label+'.log')
 with log.open('w') as stream:rc=subprocess.run(list(map(str,argv)),cwd=B/'repos'/repo,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=900).returncode
 records.append({'name':label,'argv':list(map(str,argv)),'repo':repo,'status':'passed' if rc==0 else 'failed','exit_code':rc,'elapsed_seconds':round(time.monotonic()-start,2),'log':log.name})
 (B/'evidence/job-tutorials-accepted.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records[-1]),flush=True)
 if rc:raise SystemExit(rc)
for repo,package in [('fcmaes-rust','fcmaes-job-worker'),('LP-IP-craft','lp-ip-job-worker'),('SQP-craft','sqp-job-worker')]:
 bins=B/'tutorial-bins'/repo;(bins/'examples').mkdir(parents=True,exist_ok=True)
 for name in ['optimization-run','optimization-mcp',package]:shutil.copy2(B/'baseline-final/bin'/name,bins/name)
 if repo!='LP-IP-craft':
  argv=['cargo','+1.88.0','build','--release','--locked','-p',package,'--example','custom_worker']
  if repo=='fcmaes-rust':argv+=['--example','simulation_worker']
  run('example-'+repo,argv,repo)
  shutil.copy2(B/'target/release/examples/custom_worker',bins/'examples/custom_worker')
  if repo=='fcmaes-rust':shutil.copy2(B/'target/release/examples/simulation_worker',bins/'examples/simulation_worker')
 run('job-tutorial-'+repo,['python3','tutorials/job-api/run.py','--root',B/'tutorial-runs-accepted'/repo,'--bin-dir',bins],repo)
 if repo=='fcmaes-rust':run('surrogate-tutorial',['python3','tutorials/surrogate/run.py','--root',B/'tutorial-runs-accepted/surrogate','--bin-dir',bins],repo)
