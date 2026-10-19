# Project 7 COVID Research Search

Information Retrieval Project Assignments, Project 7: COVID Research Search.
Dataset: BEIR TREC-COVID / CORD-19. The application compares TF-IDF cosine similarity, BM25, Sentence Transformer retrieval, and complete-list Reciprocal Rank Fusion (k=60).

## Run on Windows

Use Python 3.11 or later and a Node version supported by Vite 7.

```powershell
cd C:\Users\Lenovo\IR-Project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
npm install
npm run dev
```

Open http://127.0.0.1:5173. The API runs at http://127.0.0.1:8000; API documentation is at http://127.0.0.1:8000/docs.

On this machine, the base Python already has the transformer dependencies and MiniLM model cache. The backend launcher reuses those installed dependencies when the active virtual environment lacks them; no reinstall is necessary in that case. A cold model import can take some time.

The first transformer run encodes every indexed title and abstract and saves a checkpoint every 256 papers. Subsequent runs reuse `data/cache/minilm-*.npy`. Interrupted indexing resumes automatically. Model revision, corpus contents, and input configuration identify each embedding cache. Query vectors are cached in memory. Evaluation is cached separately and invalidated when implementation or experiment inputs change.

The default is the first 20,000 corpus records, selected by source order and not by relevance judgments. For the full corpus (more CPU time and disk space):

```powershell
$env:IR_MAX_DOCS = "0"
npm run dev
```

The model is pinned to `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, with a 256-token maximum, normalized 384-dimensional embeddings, CPU inference, and exact cosine search over all indexed documents. Raw titles and abstracts go to MiniLM; sparse models use lowercasing, regex tokenization, stop-word removal, and simple suffix stemming.

Normal `npm run dev` explicitly enables the real transformer, even if an earlier terminal command set `IR_DISABLE_SENTENCE_TRANSFORMER=1`. If the model fails, startup reports the failure instead of silently substituting another algorithm.

## Evaluation and exports

```powershell
npm run test:retrieval
npm run evaluate
```

Run evaluation with a Python environment containing the full requirements. Reproducible results are written to `artifacts/experiment/evaluation.json`, `comparison.csv`, `precision-recall.csv`, `status.json`, and `example-search.json`.

- Precision@10 divides top-ten relevant hits by 10.
- Recall@100 divides top-100 relevant hits by all relevant documents in the original qrels.
- MAP averages AP over full returned rankings, not a top-100 truncation. Sparse lists include all matching papers; dense lists rank every indexed paper; RRF fuses complete lists.
- nDCG@10 uses graded gains `2^relevance - 1` and the ideal ranking from the original qrels.
- All queries with positive relevance judgments participate, including queries with no relevant document in the indexed subset; those queries contribute zero.
- The PR chart compares all four models using macro-averaged, 11-point interpolated precision against recall. These are true precision-versus-recall axes.

Subset scores are not full-corpus benchmark scores. Missing corpus documents stay in relevance denominators and can lower scores. The UI states corpus and query scope. JSON exports include per-query metrics, experiment ID, model revision, and evaluation definitions.

The interface offers score CSV and experiment JSON downloads. API exports:
`/api/evaluation/export?format=json`, `?format=csv`, or `?format=pr`.

## Lightweight demo only

For a constrained machine, install `backend/requirements-lite.txt` and run:

```powershell
npm run demo
```

This uses deterministic term vectors and displays a warning. It does **not** meet the assignment's Sentence Transformer requirement. The assignment evaluation exporter refuses to publish these scores as transformer results.

## Report

`Project_7_COVID_Research_Report.docx` is the completed eight-page Project 7 report, made from the supplied template with actual experiment results, two application screenshots, a workflow, and the PR graph. Student identity cells remain blank for completion. The original `IR_report formatt.docx` is unchanged. Supporting experiment data remains under `artifacts/experiment`.

## Data and methods

- Dataset package: https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/trec-covid-beir.zip
- Official task: https://ir.nist.gov/trec-covid/data.html
- Model: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- TF-IDF weighting convention: https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfTransformer.html

The system searches indexed research titles and abstracts. It does not generate medical answers. RBAC is outside Project 7's assignment requirements.
