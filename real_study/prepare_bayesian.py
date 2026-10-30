"""Install pinned Optuna without changing existing package versions; no model calls."""
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
uv = Path.home() / '.local/bin/uv'
before = {d.metadata['Name'].lower(): d.version for d in importlib.metadata.distributions()}
constraints = root / 'pre_optuna_constraints.txt'
if 'optuna' not in before:
    constraints.write_text(''.join(f'{name}=={version}\n' for name, version in sorted(before.items())))
    subprocess.run([str(uv), 'pip', 'install', '--python', sys.executable, '--constraint', str(constraints),
                    'optuna==4.5.0'], check=True)
after = {d.metadata['Name'].lower(): d.version for d in importlib.metadata.distributions()}
assert all(after.get(name) == version for name, version in before.items()), 'Existing dependency version changed'
assert after.get('optuna') == '4.5.0', 'Unexpected Optuna version'
(root / 'bayesian_environment.json').write_text(json.dumps({'optuna': after['optuna'],
    'benchflow': after['benchflow'], 'existing_packages_unchanged': True,
    'added_packages': {n: v for n, v in after.items() if n not in before}, 'model_calls': 0}, indent=2) + '\n')
print('Optuna 4.5.0 ready; existing package versions unchanged; model calls: 0.')
