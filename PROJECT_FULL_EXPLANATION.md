# Project 7 COVID Research Search

This project implements **Project 7: COVID Research Search** from the Information Retrieval Project Assignments deck. It searches research records from the BEIR distribution of TREC-COVID / CORD-19. It is a document retrieval tool rather than a generative question-answering or medical-advice system.

## Assignment coverage

The implementation includes cleaning, tokenization, stop-word removal, stemming, epidemic-corpus indexing, TF-IDF, BM25, actual Sentence Transformer retrieval, Hybrid Reciprocal Rank Fusion, an interactive search interface, a comparison table, and a precision-versus-recall graph. It also exports a reproducible experiment and includes a project-specific technical report. User accounts and RBAC are not assignment requirements.

## Data and experiment scope

`data/trec-covid/corpus.jsonl` contains 171,332 records. The default experiment indexes the first 20,000 in source order. The subset is selected without relevance judgments. Queries come from `queries.jsonl`; graded judgments come from `qrels/test.tsv`.

All 50 judged queries participate in evaluation. Three queries have no relevant paper in the indexed subset; they contribute zero scores. Original qrels are retained, including relevant papers outside the index. These remain in recall and AP denominators and in the ideal nDCG ranking. The subset therefore has limited attainable recall. These measurements are not full-corpus benchmark scores.

Use `IR_MAX_DOCS=0` for a separate full-corpus experiment. Rebuild the index and regenerate all results and report figures after changing that setting.

## Preprocessing and indexing

Lexical inputs are lowercased, tokenized by regular expression, filtered using a fixed English stop-word list, and stemmed using explicit suffix rules. Internal digits and hyphens are retained for scientific terms, and tokens shorter than three characters are dropped. This is a simple custom stemmer, not Porter stemming.

Each document has a term-frequency counter and length. Document frequencies and inverted posting lists support lexical retrieval. Raw text is retained for semantic encoding and snippets.

## TF-IDF

Term weights use sublinear TF: `1 + ln(tf)`.

Smoothed IDF is `ln((1 + N)/(1 + df)) + 1`.

The score is cosine similarity between query and document TF-IDF vectors. Both vectors use the same index vocabulary and weights, and both norms are included. This corresponds to the TfidfTransformer convention with `sublinear_tf=True` and `norm="l2"`. Sparse rankings contain all documents matching an indexed query term; unknown query terms are ignored.

## BM25

BM25 uses `k1=1.5`, `b=0.75`, and document-length normalization. Its IDF is `ln(1 + (N - df + 0.5)/(df + 0.5))`. Term contributions are summed over query occurrences. BM25 and TF-IDF use separate IDF definitions.

## Sentence Transformer retrieval

Normal operation loads `sentence-transformers/all-MiniLM-L6-v2`, pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. It produces normalized 384-dimensional embeddings from raw titles and abstracts, with a maximum of 256 tokenizer tokens. Sparse stemming and stop-word removal are not applied to the transformer input.

Every indexed paper has an embedding. Query-vector dot products score the entire indexed corpus, independently of lexical candidate generation. This is actual dense retrieval rather than reranking only documents found by sparse models.

Embeddings are cached in `data/cache` using corpus contents, model revision, and encoding configuration. Checkpoints every 256 papers allow interrupted indexing to resume. Evaluation queries are batch encoded; interactive query vectors are reused in memory.

`npm run dev` enables the real model. A missing or failed transformer produces an explicit startup error rather than silent algorithm substitution. The separately invoked `npm run demo` uses deterministic term vectors and displays a warning that this mode does not satisfy the assignment's transformer requirement. The assignment evaluation exporter requires the actual transformer.

## Hybrid RRF

RRF combines complete TF-IDF, BM25, and dense rankings:

`RRF(d) = sum_m 1 / (60 + rank_m(d))`

Ranks start at one. Missing documents contribute zero for that ranker. Raw model scores are not normalized or averaged. Ties are resolved by document order for deterministic results. Displayed top-k results are slices of the complete ranking.

## Evaluation

- **Precision@10:** relevant hits in the first ten divided by ten.
- **Recall@100:** relevant hits in the first hundred divided by all relevant papers in original qrels.
- **AP:** sum of precision at each relevant hit in the full returned ranking, divided by all judged relevant papers.
- **MAP:** mean AP across all judged queries. Contributions beyond rank 100 are included.
- **nDCG@10:** graded gain `2^grade - 1`, discounted by `log2(rank + 1)`, normalized by the ideal original-qrels ranking.

The PR graph places recall on X and interpolated precision on Y. For each query, precision at a recall threshold is the maximum precision achieved at any retrieved prefix meeting that threshold, or zero when unreachable. Eleven recall thresholds from 0 through 1 are macro-averaged across the same 50 queries. All four models share one chart. For this subset, high recall thresholds are unreachable, so those points are zero.

The experiment cache includes implementation and input fingerprints. `artifacts/experiment/evaluation.json` records the experiment identifier, model revision, corpus scope, per-query metrics, and aggregate scores. Comparison CSV, PR CSV, status, and an example search accompany it. Do not copy sample Cranfield results or assume RRF wins every metric.

## Application and exports

React/Vite runs on port 5173 and proxies `/api` to FastAPI on port 8000. The API provides status, sample queries, search, evaluation, and evaluation downloads. OpenAPI documentation is available at `/docs` on port 8000.

The interface supports four model choices, 10/20/50 displayed results, topic shortcuts, paper links, per-model rank evidence, CSV and JSON downloads, loading states, query validation, service retry, and a responsive layout.

## Verification

`npm run test:retrieval` checks independently calculated ranking and metric examples, including AP beyond rank 100 and queries without relevant indexed papers. `npm run test:ui` runs Playwright against the live application at five sizes, checks real model searches, downloads, keyboard submission, errors, empty results, retry recovery, and the four-model chart. Chrome or Edge must already be installed.

`npm run evaluate` regenerates experiment artifacts, reusing cached document embeddings. The launcher can reuse existing base-Python transformer dependencies when the active virtual environment lacks them. Setup instructions are in README.md.

## Report and limitations

`Project_7_COVID_Research_Report.docx` is the completed report based on the supplied format, with measured results, two actual application screenshots, a workflow, and the PR graph. Student identity cells remain blank. The original report-format document remains unchanged.

The source-order subset is not random. The general-purpose encoder is not tuned for biomedical retrieval, long inputs are truncated by its token limit, and the lexical stemmer is simple. Full-corpus runs, alternative biomedical encoders, stronger preprocessing, and systematic latency/memory benchmarks are possible extensions, each requiring new measurements.
