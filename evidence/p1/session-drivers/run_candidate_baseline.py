"""Use exact local candidates for canonical GitHub URLs, scoped to this child process."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import hashlib
BASE=Path(__file__).resolve().parent
# The initial corrected-source run completes first; all failures must be
# understood before reusing its build cache for the complete rerun.
summary=BASE/'evidence/baseline-final/summary.json'
deadline=time.monotonic()+60
while not summary.exists() and time.monotonic()<deadline:
    time.sleep(1)
initial=json.loads(summary.read_text())
failed=[step['name'] for step in initial['steps'] if step['status']!='passed']
if failed != ['smoke']:
    raise RuntimeError(f'unexpected initial failures: {failed}')
repairs=[]
for path in (BASE/'baseline-final/target').rglob('*'):
    if not path.is_file() or path.suffix or os.access(path,os.X_OK):continue
    with path.open('rb') as stream:header=stream.read(4)
    if header!=b'\x7fELF':continue
    data=path.read_bytes();temporary=path.with_name(path.name+'.executable-tmp')
    temporary.write_bytes(data);temporary.chmod(0o755);os.replace(temporary,path)
    assert path.read_bytes()==data
    repairs.append({'path':str(path),'sha256_unchanged':hashlib.sha256(data).hexdigest(),'mode':'0755'})
(BASE/'evidence/executable-cache-repair.json').write_text(json.dumps(repairs,indent=2)+'\n')
print(json.dumps({'existing_elf_mode_repairs':repairs}),flush=True)
mirrors=BASE/'candidate-mirrors-final'
mirrors.mkdir(exist_ok=True)
env=dict(os.environ)
count=int(env.get('GIT_CONFIG_COUNT','0'))
for name in ('optimization-jobs','fcmaes-rust','LP-IP-craft','SQP-craft'):
    mirror=mirrors/(name+'.git')
    if not mirror.exists():
        subprocess.run(['git','clone','--quiet','--mirror',str(BASE/'repos'/name),str(mirror)],check=True)
    for suffix in ('.git',''):
        env[f'GIT_CONFIG_KEY_{count}']=f'url.{mirror.as_uri()}.insteadOf'
        env[f'GIT_CONFIG_VALUE_{count}']=f'https://github.com/dietmarwo/{name}{suffix}'
        count+=1
env['GIT_CONFIG_COUNT']=str(count)
env['CARGO_NET_GIT_FETCH_WITH_CLI']='true'
args=[sys.executable,str(BASE/'repos/experiment-craft/scripts/baseline.py'),'all',
      '--workspace',str(BASE/'baseline-final'),'--jobs','4',
      '--output',str(BASE/'evidence/baseline-accepted')]
print(json.dumps({'mode':'unpublished-local-candidates','mirrors':str(mirrors),'argv':args}),flush=True)
subprocess.run(args,env=env,check=True)
