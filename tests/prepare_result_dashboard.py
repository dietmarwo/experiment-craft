"""Prepare UI test campaigns. Commands copy fixtures; no checker or proof is run."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from experiment_craft.campaign import initialize,drive
from experiment_craft.storage import Store
from contextlib import closing
from test_campaign import campaign
from verification_fixture import steps


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    root=args.output.absolute();root.mkdir(parents=True,exist_ok=False)
    node=root/'node'
    subprocess.run([str(args.runner),'--root',str(node),'node','init','--capacity','1','--allow-commands'],check=True,capture_output=True)
    cases=[]
    for name,options in [('Accepted audit',{}),('Rejected audit',{'rejected':True}),
                         ('Unconfirmed audit',{'code':7}),('Pending audit',{})]:
        directory=root/str(len(cases));directory.mkdir()
        value=campaign(steps(directory,**options));value['name']=name
        source=directory/'campaign.json';source.write_text(json.dumps(value))
        workspace=directory/'workspace';initialize(source,workspace,args.runner,node,'foreground')
        with closing(Store(workspace)) as store:
            if not name.startswith('Pending'):drive(store)
            state=store.read()
            cases.append({'id':state['campaign_id'],'name':name,'workspace':str(workspace)})
    jobs=json.loads(subprocess.check_output([str(args.runner),'--root',str(node),'jobs','list']))
    result={'cases':cases,'node':str(node),'native_jobs':len(jobs),'kind':'fixture copying commands; not proof execution'}
    (root/'prepared.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
