"""Run the repository's CI mixed-node checks against pinned or checkout SDKs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parent
RUNTIME = BASE/'repos/optimization-jobs'
MODE = sys.argv[1]
PACKAGES = {'fcmaes-rust': 'fcmaes-job-worker', 'LP-IP-craft': 'lp-ip-job-worker', 'SQP-craft': 'sqp-job-worker'}
BINS = BASE/('bin' if MODE == 'pinned' else 'checkout-bin')
BINS.mkdir(exist_ok=True)

def run(argv, cwd=RUNTIME, env=None, capture=False, input=None):
    print(json.dumps({'cwd': str(cwd), 'argv': list(map(str, argv))}), flush=True)
    return subprocess.run(list(map(str, argv)), cwd=cwd, env=env, check=True,
                          input=input, text=True, stdout=subprocess.PIPE if capture else None).stdout

records = {}
for repo, package in PACKAGES.items():
    source = BASE/'repos'/repo
    flags = ['--locked']
    build_env = dict(os.environ)
    if MODE == 'checkout':
        source = BASE/'checkout-sdk'/repo
        if not source.exists():
            source.parent.mkdir(exist_ok=True)
            run(['git','clone','--quiet','--shared',BASE/'repos'/repo,source])
        url='https://github.com/dietmarwo/optimization-jobs'
        flags = [part for name in ('optimization-job-api','optimization-runner') for part in
                 ('--config',f'patch."{url}".{name}.path="{RUNTIME}/crates/{name}"')]
        build_env['CARGO_TARGET_DIR'] = str(BASE/'checkout-target')
        run(['cargo','+1.88.0','update',*flags,'-p','optimization-job-api','-p','optimization-runner'],source,build_env)
        run(['cargo','+1.88.0','build','--release',*flags,'-p',package],source,build_env)
        shutil.copy2(BASE/'checkout-target/release'/package,BINS/package)
    metadata = run(['cargo','+1.88.0','metadata','--format-version','1',*flags],source,build_env,True)
    run(['python3',RUNTIME/'scripts/job-api/sdk_source.py',MODE,RUNTIME,repo],input=metadata)
    sdk=[p for p in json.loads(metadata)['packages'] if p['name']=='optimization-job-api'][0]
    records[repo]={'commit':run(['git','rev-parse','HEAD'],source,capture=True).strip(),
                   'sdk_source':sdk['source'], 'sdk_manifest':sdk['manifest_path']}
for name in ('optimization-run','optimization-mcp'):
    if MODE == 'checkout':shutil.copy2(BASE/'bin'/name,BINS/name)
for name in ['optimization-run','optimization-mcp',*PACKAGES.values()]:
    data=(BINS/name).read_bytes()
    records[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
(BASE/'evidence'/f'p2-{MODE}-sources.json').write_text(json.dumps(records,indent=2)+'\n')
env=dict(os.environ,JOB_API_TARGET=str(BINS),JOB_API_REQUIRE_SCHEMA='1',JOB_API_REQUIRE_WORKER='1')
for suite in ('test_review.py','test_mcp.py','test_integration.py','test_commands.py'):
    run(['python3',RUNTIME/'scripts/job-api'/suite],env=env)
for package in PACKAGES.values():
    isolated=BASE/f'mcp-{MODE}-{package}'
    isolated.mkdir(exist_ok=True)
    for name in ('optimization-run','optimization-mcp',package):
        dest=isolated/name
        if not dest.exists():dest.symlink_to(BINS/name)
    run(['python3',RUNTIME/'scripts/job-api/test_mcp.py',
         'Jobs.test_a_real_worker_reports_claims_and_evidence',
         'Jobs.test_a_real_worker_runs_its_examples_over_mcp_only'],
        env=dict(env,JOB_API_TARGET=str(isolated)))
