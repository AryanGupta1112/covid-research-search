"""Reproduce Project 7 results; refuse to publish fallback scores as transformer results."""
import csv
import json
import sys
import os
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if importlib.util.find_spec('sentence_transformers') is None and sys.prefix != sys.base_prefix:
    base = Path(sys.base_prefix) / ('python.exe' if os.name == 'nt' else 'bin/python3')
    check = subprocess.run([str(base), '-c', "import importlib.util,sys; sys.exit(importlib.util.find_spec('sentence_transformers') is None)"], check=False)
    if check.returncode == 0:
        raise SystemExit(subprocess.call([str(base), str(Path(__file__).resolve())]))
from backend.app.search_engine import SearchEngine

def main():
    os.environ["IR_DISABLE_SENTENCE_TRANSFORMER"] = "0"
    engine = SearchEngine()
    engine.prepare()
    if engine.st_model is None:
        raise SystemExit('Unset IR_DISABLE_SENTENCE_TRANSFORMER to export assignment results.')
    result = engine.evaluate()
    output = ROOT / 'artifacts' / 'experiment'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'evaluation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (output / 'status.json').write_text(json.dumps(engine.status(), indent=2), encoding='utf-8')
    for name, rows in [('comparison', result['comparison']), ('precision-recall', result['precisionRecall'])]:
        with (output / f'{name}.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    example = engine.search('coronavirus transmission in children', 'hybrid', 10)
    (output / 'example-search.json').write_text(json.dumps(example, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('experimentId', 'indexedDocuments', 'evaluatedQueries', 'denseEngine', 'comparison')}, indent=2))

if __name__ == '__main__':
    main()
