"""Check native numerical results without changing their claim levels."""
import json
import math
from pathlib import Path
lp = json.loads(Path('lp.json').read_text())
sqp = json.loads(Path('sqp.json').read_text())
assert lp['schema_version'] == sqp['schema_version'] == 'optimization.result/0.2'
a, b = lp['results'][0]['outcome'], sqp['results'][0]['outcome']
assert a['claim'] == 'numerical_optimum' and a['feasible'] is True
assert b['claim'] == 'first_order' and b['feasible'] is True
assert math.isclose(a['objective'], 7.0, rel_tol=0, abs_tol=1e-12)
assert math.isclose(b['objective'], 0.25, rel_tol=0, abs_tol=1e-10)
Path('checks.json').write_text(json.dumps({'lp': a['claim'], 'sqp': b['claim'], 'checks': 'passed'}) + '\n')
