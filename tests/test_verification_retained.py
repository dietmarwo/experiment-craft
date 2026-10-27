"""Rebuild recorded views from read-only snapshots; no native runtime or campaign DB."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from experiment_craft.artifacts import catalog
from experiment_craft.storage import canonical
from experiment_craft.verification import build, render

EVIDENCE=Path(__file__).resolve().parents[1]/'evidence/verification-reports'


class Snapshot:
    def __init__(self,path):
        self.root=path/'snapshot'
        self.state=json.loads((self.root/'state.json').read_bytes())
    def read(self):return copy.deepcopy(self.state)


class Retained(unittest.TestCase):
    def check(self,problem):
        directory=EVIDENCE/problem
        metadata=json.loads((EVIDENCE/'files-sha256.json').read_bytes())[problem]
        for name,sha in metadata.items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),sha,name)
        store=Snapshot(directory)
        with patch('experiment_craft.runtime.Runtime.call',side_effect=AssertionError('retained view contacted runtime')):
            value=build(store,'accept');listing=catalog(store)
        self.assertEqual(canonical(value)+b'\n',(directory/'verification.json').read_bytes())
        for name,data in render(value).items():
            self.assertEqual(data,(directory/name).read_bytes(),name)
        self.assertEqual(value['status'],'reported_accepted');self.assertEqual(value['summary']['reported_accepted_arms'],9)
        self.assertEqual(listing['total_outputs'],8)
        self.assertFalse((store.root/'campaign.sqlite3').exists())

    def test_scalar_recorded_report(self):self.check('scalar-cuberoot')
    def test_pde_recorded_report(self):self.check('cahn-hilliard')


if __name__=='__main__':unittest.main()
