import json
from pathlib import Path

def load_manifest(root=Path(__file__).resolve().parent/'prepared'):
    root=Path(root).resolve()
    rows=json.loads((root/'manifest.json').read_text())
    for row in rows:
        if not (root/row['path']).resolve().is_relative_to(root): raise ValueError('Unsafe manifest path')
    return rows
