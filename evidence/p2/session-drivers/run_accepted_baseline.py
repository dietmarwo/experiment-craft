"""Rerun unchanged candidates after documented executable-cache mode repairs."""
from pathlib import Path
import json,os,subprocess,sys,time
B=Path(__file__).resolve().parent
summary=B/'evidence/baseline-final/summary.json'
end=time.monotonic()+300
while not summary.exists():
 if time.monotonic()>end:raise SystemExit('Initial candidate check has not completed; inspect its process/log.')
 time.sleep(.5)
initial=json.loads(summary.read_text());failures=[s['name'] for s in initial['steps'] if s['status']!='passed']
assert failures==['lp-ip-tests','sqp-tests'],failures
for label in failures:
 assert 'Permission denied (os error 13)' in (B/'evidence/baseline-final/checks'/(label+'.log')).read_text()
env=dict(os.environ);count=int(env.get('GIT_CONFIG_COUNT','0'))
for name in ['optimization-jobs','fcmaes-rust','LP-IP-craft','SQP-craft']:
 mirror=B/'candidate-mirrors'/(name+'.git')
 for suffix in ['.git','']:
  env[f'GIT_CONFIG_KEY_{count}']=f'url.{mirror.as_uri()}.insteadOf';env[f'GIT_CONFIG_VALUE_{count}']=f'https://github.com/dietmarwo/{name}{suffix}';count+=1
env['GIT_CONFIG_COUNT']=str(count)
argv=[sys.executable,str(B/'repos/experiment-craft/scripts/baseline.py'),'all','--workspace',str(B/'baseline-final'),'--jobs','4','--output',str(B/'evidence/baseline-accepted')]
print(json.dumps({'initial_failed_steps':failures,'source_changes':False,'argv':argv}),flush=True)
subprocess.run(argv,env=env,check=True)
