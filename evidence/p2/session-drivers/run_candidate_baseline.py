"""Exact local commits behind canonical URLs; URL rewrites stay in this child."""
from pathlib import Path
import json,os,subprocess,sys
B=Path(__file__).resolve().parent
mirrors=B/'candidate-mirrors';mirrors.mkdir(exist_ok=True)
env=dict(os.environ);count=int(env.get('GIT_CONFIG_COUNT','0'))
for name in ['optimization-jobs','fcmaes-rust','LP-IP-craft','SQP-craft']:
 mirror=mirrors/(name+'.git')
 if not mirror.exists():subprocess.run(['git','clone','--quiet','--mirror',str(B/'repos'/name),str(mirror)],check=True)
 for suffix in ['.git','']:
  env[f'GIT_CONFIG_KEY_{count}']=f'url.{mirror.as_uri()}.insteadOf';env[f'GIT_CONFIG_VALUE_{count}']=f'https://github.com/dietmarwo/{name}{suffix}';count+=1
env['GIT_CONFIG_COUNT']=str(count);env['CARGO_NET_GIT_FETCH_WITH_CLI']='true'
workspace=B/'baseline-final';workspace.mkdir(exist_ok=True)
# New source checkout and evidence, reusing only compiled dependency cache.
if not (workspace/'target').exists():(workspace/'target').symlink_to(B/'baseline-before/target',target_is_directory=True)
argv=[sys.executable,str(B/'repos/experiment-craft/scripts/baseline.py'),'all','--workspace',str(workspace),'--jobs','4','--output',str(B/'evidence/baseline-final')]
print(json.dumps({'mode':'exact-local-candidates','argv':argv,'dependency_cache':'baseline-before/target'}),flush=True)
subprocess.run(argv,env=env,check=True)
