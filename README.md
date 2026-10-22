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

If a matching project API is already running on port 8000, the launcher reuses it before loading the model again. That API stays managed by its original terminal. If another service occupies the port, or the existing API uses a different demo mode or corpus scope, startup explains which conflict to resolve. Stop the original service with Ctrl+C before retrying. The launcher never terminates another process automatically.

Vite excludes generated `artifacts/`, downloaded `data/`, Python environments/backend files, and report/presentation documents from watching. This prevents locked Office exports from crashing the frontend with `EBUSY` while keeping frontend source changes live.

If the active virtual environment lacks dependencies but its base Python already has them, the backend launcher can reuse that installation. A fresh checkout still needs the dependencies above, the dataset download, and the MiniLM model. Initial downloads and encoding can take time; datasets and caches are excluded from Git.

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

## Report and presentation

`Project_7_COVID_Research_Report.docx` is the ten-page report based on the supplied format. It includes actual experiment results, two application screenshots, a workflow, a worked RRF example, query coverage analysis, and the PR graph. `Project_7_COVID_Research_Presentation.pptx` contains ten slides using the approved MUJ presentation theme. Both deliverables identify Aryan Gupta, Shashwat Rana, and Rudra Pratap Singh; the presentation names Prof. Prashant Vats. The original `IR_report formatt.docx` remains unchanged.

The assignment deck specifies a similarity threshold below 10%, while the supplied report template says below 15%. The completed report follows the stricter assignment threshold. Actual plagiarism/similarity compliance requires an independent checker; a threshold printed in a document is not a measured result. The report's ten-page length follows the requested expansion.

## Assignment coverage and measured results

Project 7 requirements are in slide 9 of `Information Retrieval Project Assignments.pptx`, with shared evaluation and submission requirements in slides 2 and 24.

| Requirement | Project evidence |
| --- | --- |
| TREC-COVID / CORD-19 indexing and preprocessing | `backend/app/search_engine.py`: text cleaning, tokenization, stop-word removal, simple suffix stemming, postings and embeddings |
| TF-IDF, BM25, Sentence Transformer, Hybrid RRF | Independent full-index dense retrieval and complete-list fusion with k=60 |
| Precision@10, Recall, MAP, nDCG | P@10, R@100, full-ranking MAP and nDCG@10 against original qrels |
| Interactive interface, comparison table and PR graph | React application with four-model comparison and 11-point interpolated PR curves |
| Technical report and working demonstration | Report and presentation above; `npm run dev` for the live application |

The saved experiment is `024ac8ffbc9b667bf50f`, generated on 3 November 2026, with 20,000 of 171,332 papers and all 50 judged queries. Supporting JSON, CSV and PR figures are under `artifacts/experiment`.

| Model | P@10 | R@100 | MAP | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF | 0.058000 | 0.003222 | 0.001220 | 0.051184 |
| BM25 | **0.100000** | 0.005501 | **0.001890** | **0.072378** |
| Sentence Transformer | 0.080000 | 0.005382 | 0.001742 | 0.070707 |
| Hybrid RRF | 0.080000 | **0.005742** | 0.001826 | 0.068359 |

BM25 leads on three metrics; RRF leads on Recall@100. These results describe the declared subset. The assignment does not specify a minimum corpus size, and a full-corpus experiment remains a separate extension.

## Verification

`npm run test:retrieval` runs ten ranking/metric reference tests and five API-startup checks. `npm run test:startup` checks API reuse/conflicts and Vite's actual watcher exclusions. `npm run build` checks the production frontend build. With the normal application running, use `npm run test:ui` for Playwright checks of five viewport sizes, all four live rankers, keyboard search, downloads, validation, empty results and retry recovery. Chrome or Edge must be installed. Use real transformer mode for the assignment checks.

`PRODUCT.md` (including a lowercase `product.md` variant) and `PROJECT_FULL_EXPLANATION.md` are local working notes excluded from future Git tracking. The README contains the setup, requirements and experiment information needed by repository readers.

## Data and methods

- Dataset package: https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/trec-covid-beir.zip
- Official task: https://ir.nist.gov/trec-covid/data.html
- Model: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- TF-IDF weighting convention: https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfTransformer.html

The system searches indexed research titles and abstracts. It does not generate medical answers. RBAC is outside Project 7's assignment requirements.
