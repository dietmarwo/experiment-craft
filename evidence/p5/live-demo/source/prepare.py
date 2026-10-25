"""Prepare the versioned LP model from an immutable declared input."""
import json
from pathlib import Path
model = json.loads(Path('model.json').read_text())
Path('prepared-model.json').write_text(json.dumps(model, sort_keys=True) + '\n')
