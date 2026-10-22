"""Start the API with existing dependencies; --demo is explicitly non-submission mode."""
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

def check_existing_api(host: str, port: int, demo: bool, max_docs: int) -> bool:
    """Reuse a matching running project API; never terminate another process."""
    with socket.socket() as probe:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind((host, port))
            return False
        except OSError as exc:
            if exc.errno not in (98, 48, 10048) and getattr(exc, 'winerror', None) != 10048:
                raise
    address = f'http://{host}:{port}'
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(address + '/api/status', timeout=3) as response:
            status = json.load(response)
        with opener.open(address + '/openapi.json', timeout=3) as response:
            schema = json.load(response)
        is_project = (schema.get('info', {}).get('title') == 'COVID Research Search API'
                      and status.get('dataset') == 'BEIR TREC-COVID / CORD-19')
    except (OSError, ValueError, AttributeError):
        is_project = False
    if not is_project:
        raise RuntimeError(f'Port {port} is occupied by another service. Stop that service or '
                           f'close its terminal, then run npm run dev again. No process was stopped.')
    if not (status.get('ready') is True and status.get('assignmentReady') is (not demo)
            and status.get('maxDocs') == max_docs):
        raise RuntimeError(f'The API on port {port} uses a different mode or corpus scope. '
                           'Stop its original terminal with Ctrl+C, then run this command again.')
    print(f'Reusing the COVID Research Search API already running at {address}. '
          'It remains managed by its original terminal.', flush=True)
    return True
def main(args=None) -> int:
    args = sys.argv[1:] if args is None else args
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    demo = '--demo' in args
    os.environ['IR_DISABLE_SENTENCE_TRANSFORMER'] = '1' if demo else '0'
    try:
        if check_existing_api('127.0.0.1', 8000, demo, int(os.getenv('IR_MAX_DOCS', '20000'))):
            return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
    required = ['fastapi', 'uvicorn', 'numpy'] + ([] if demo else ['sentence_transformers'])
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing and sys.prefix != sys.base_prefix:
        base = Path(sys.base_prefix) / ('python.exe' if os.name == 'nt' else 'bin/python3')
        check = subprocess.run([str(base), '-c', 'import importlib.util,sys;sys.exit(not all(importlib.util.find_spec(m) for m in sys.argv[1:]))', *required], check=False)
        if check.returncode == 0:
            print('Reusing transformer dependencies already installed in the base Python environment.', flush=True)
            return subprocess.call([str(base), str(Path(__file__).resolve()), *args])
    if missing:
        print('Missing Python dependencies: ' + ', '.join(missing) + '. Run python -m pip install -r backend/requirements.txt', file=sys.stderr)
        return 1
    import uvicorn
    uvicorn.run('backend.app.main:app', host='127.0.0.1', port=8000)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
