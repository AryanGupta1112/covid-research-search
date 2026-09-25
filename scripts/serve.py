"""Start the API with existing dependencies; --demo is explicitly non-submission mode."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))
demo = '--demo' in sys.argv
os.environ['IR_DISABLE_SENTENCE_TRANSFORMER'] = '1' if demo else '0'
required = ['fastapi', 'uvicorn', 'numpy'] + ([] if demo else ['sentence_transformers'])
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing and sys.prefix != sys.base_prefix:
    base = Path(sys.base_prefix) / ('python.exe' if os.name == 'nt' else 'bin/python3')
    check = subprocess.run([str(base), '-c', 'import importlib.util,sys;sys.exit(not all(importlib.util.find_spec(m) for m in sys.argv[1:]))', *required], check=False)
    if check.returncode == 0:
        print('Reusing transformer dependencies already installed in the base Python environment.', flush=True)
        raise SystemExit(subprocess.call([str(base), str(Path(__file__).resolve()), *sys.argv[1:]]))
if missing:
    raise SystemExit('Missing Python dependencies: ' + ', '.join(missing) + '. Run python -m pip install -r backend/requirements.txt')
import uvicorn
uvicorn.run('backend.app.main:app', host='127.0.0.1', port=8000)
