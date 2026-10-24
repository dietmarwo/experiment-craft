from pathlib import Path
import json,os,re,subprocess
BASE=Path(__file__).resolve().parent
repos=BASE/'repos'
runtime=repos/'optimization-jobs'
pin=subprocess.check_output(['git','-C',str(runtime),'rev-parse','HEAD'],text=True).strip()
old='70e210fbf562900c1be8f278e2ab2852ef5934e3'
for mode in ['pinned','checkout']:
 assert json.loads((BASE/'evidence'/f'compatibility-{mode}-accepted.json').read_text())['status']=='passed'
mirrors=BASE/'candidate-mirrors';mirrors.mkdir(exist_ok=True)
mirror=mirrors/'optimization-jobs.git'
if not mirror.exists():subprocess.run(['git','clone','--quiet','--mirror',runtime,mirror],check=True)
env=dict(os.environ,GIT_CONFIG_COUNT='2',GIT_CONFIG_KEY_0=f'url.{mirror.as_uri()}.insteadOf',GIT_CONFIG_VALUE_0='https://github.com/dietmarwo/optimization-jobs.git',GIT_CONFIG_KEY_1=f'url.{mirror.as_uri()}.insteadOf',GIT_CONFIG_VALUE_1='https://github.com/dietmarwo/optimization-jobs')
records={}
for name in ['fcmaes-rust','LP-IP-craft','SQP-craft']:
 repo=repos/name
 if subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()!='iteration-03/command-runtime-pin':
  subprocess.run(['git','switch','-c','iteration-03/command-runtime-pin'],cwd=repo,check=True)
 files=subprocess.check_output(['git','ls-files'],cwd=repo,text=True).splitlines()
 manifests=[]
 for relative in files:
  if not (relative.endswith(('Cargo.toml','Cargo.lock')) or relative=='docs/job-api/models.md'):continue
  path=repo/relative;text=path.read_text()
  if old not in text and pin not in text:continue
  text=text.replace(old,pin)
  if relative.endswith('Cargo.toml'):manifests.append(path)
  if relative.endswith('Cargo.lock'):
   def deps(m):
    lines=m[2].splitlines(True)
    if ' "sha2",\n' not in lines:lines.append(' "sha2",\n')
    return m[1]+''.join(sorted(lines))+m[3]
   text=re.sub(r'(\[\[package\]\]\nname = "optimization-runner"[\s\S]*?dependencies = \[\n)(.*?)(\]\n)',deps,text,flags=re.S)
  path.write_text(text)
 p=repo/'CHANGELOG.md';text=p.read_text();idx=text.index('### Changed',text.index('## [Unreleased]'))+len('### Changed')
 end=text.find('unchanged.',idx)
 if f'pin to `{pin[:7]}`' in text[idx:end+10]:text=text[:idx]+text[end+len('unchanged.'):]
 text=text[:idx]+f'''\n\n- Move the optimization-jobs pin to `{pin[:7]}` (source after 0.3.0):
  opt-in trusted command jobs and verified binary staging/collection in the
  shared runner. Command/file operations use the CLI; the optimization SDK,
  numerical algorithms, envelopes, worker protocols and result claims are unchanged.'''+text[idx:];p.write_text(text)
 p=repo/'ai-context.md';text=p.read_text();text=text.replace('`70e210f`',f'`{pin[:7]}`',1).replace('which adds\n`node capabilities` and `jobs execution JOB_ID`','which adds\nopt-in trusted local command jobs and verified binary file operations through\nthe CLI, plus `node capabilities` and `jobs execution JOB_ID`',1);p.write_text(text)
 records[name]=[]
 for manifest in manifests:
  meta=json.loads(subprocess.check_output(['cargo','+1.88.0','metadata','--locked','--format-version','1','--manifest-path',str(manifest),*(['--features','job-worker'] if manifest.parent!=repo else [])],cwd=repo,env=env,text=True))
  sdk=[x for x in meta['packages'] if x['name']=='optimization-job-api'][0]
  assert sdk['source'].endswith('#'+pin),sdk
  records[name].append({'manifest':str(manifest.relative_to(repo)),'sdk_source':sdk['source']})
 subprocess.run(['git','diff','--check'],cwd=repo,check=True)
 subprocess.run(['git','add','-A'],cwd=repo,check=True)
 subprocess.run(['git','-c','user.name=Codex','-c','user.email=codex@openai.com','commit','-m','Update runtime pin for command jobs and binary files'],cwd=repo,check=True)
(BASE/'evidence/pin-validation.json').write_text(json.dumps({'runtime_pin':pin,'checks':records},indent=2)+'\n')
