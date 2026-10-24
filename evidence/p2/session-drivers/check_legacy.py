import hashlib, json, os
from pathlib import Path
import subprocess
import tempfile
import jsonschema
BASE=Path(__file__).resolve().parent
RUNTIME=BASE/'repos/optimization-jobs'
runner=BASE/'bin/optimization-run'
worker=BASE/'baseline-before/target/release/fcmaes-native-worker'
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/'node'
    def call(*args):
        result=subprocess.run([str(runner),'--root',str(root),*map(str,args)],capture_output=True,text=True,check=True,timeout=30)
        return json.loads(result.stdout)
    call('node','init','--capacity','1')
    call('workers','add','--id','native','--executable',worker)
    spec=json.loads((BASE/'repos/fcmaes-rust/docs/runner-jobs/sphere-bite.json').read_text())
    spec['request_key']='p2-legacy-compatibility'
    spec['execution'].update(workers=1,retry_wave_size=1)
    spec['budget'].update(retries=1,evaluations_per_retry=100)
    path=Path(tmp)/'legacy.json';path.write_text(json.dumps(spec))
    job=call('run','--spec',path)
    assert job['state']=='completed',job
    record=call('jobs','execution',job['id'])
    schema=json.loads((RUNTIME/'docs/job-api/schemas/execution.record-0.1.schema.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(record)
    native=(Path(job['directory'])/'run.json').read_bytes()
    assert record['native_result']['schema_version']==1,record
    assert record['native_result']['sha256']==hashlib.sha256(native).hexdigest()
    (BASE/'evidence/p2-legacy-record.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Legacy fcmaes.job/0.1 completes; execution.record/0.1 validates; native schema 1 and attachment hash preserved.')
