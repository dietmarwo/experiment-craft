"""Build the changed standalone worker manifests with their CI stable toolchain."""
from pathlib import Path
import json,os,subprocess,time
B=Path(__file__).resolve().parent;repo=B/'repos/fcmaes-rust';env=dict(os.environ,CARGO_TARGET_DIR=str(B/'tutorial-target'),CARGO_BUILD_JOBS='2')
mirror=B/'candidate-mirrors/optimization-jobs.git';env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0=f'url.{mirror.as_uri()}.insteadOf',GIT_CONFIG_VALUE_0='https://github.com/dietmarwo/optimization-jobs')
records=[]
for name in ['energy-hub-bilevel','gtoc1-route-search','nexosim-production-line','rapier-trebuchet']:
 argv=['cargo','+stable','build','--release','--locked','--features','job-worker','--manifest-path',str(repo/'tutorials'/name/'Cargo.toml')]
 start=time.monotonic();print(json.dumps({'tutorial':name,'argv':argv}),flush=True)
 log=B/'evidence'/('tutorial-'+name+'.log')
 with log.open('w') as stream:rc=subprocess.run(argv,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=1800).returncode
 records.append({'tutorial':name,'argv':argv,'status':'passed' if rc==0 else 'failed','exit_code':rc,'elapsed_seconds':round(time.monotonic()-start,2),'log':log.name})
 (B/'evidence/tutorial-builds.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps(records[-1]),flush=True)
 if rc:raise SystemExit(rc)
