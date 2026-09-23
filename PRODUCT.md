# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: FastAPI backend with a React and Vite frontend, chosen for a credible local IR demonstration with a polished browser interface.

## Users

The primary users are students and evaluators reviewing an Information Retrieval project demonstration. They need to run searches, compare ranking models, inspect retrieved COVID research documents, and verify evaluation results against relevance judgments.

## Product Purpose

The product demonstrates Project 7, COVID Research Search. It indexes TREC-COVID / CORD-19 research records and compares TF-IDF, BM25, dense semantic retrieval, and Reciprocal Rank Fusion hybrid search.

## Positioning

The app combines a working retrieval backend, query-time ranked results, relevance-aware metrics, and a frontend built for research inspection rather than a static demo.

## Operating Context

The project will be demonstrated locally. The report template requires dataset explanation, methodology, performance tables, and precision-recall graphs. The PowerPoint assignment requires an interactive search interface, preprocessing, epidemic corpus indexing, four ranking paradigms, Precision@10, Recall, MAP, nDCG, a comparison table, and precision-recall graphs.

## Capabilities and Constraints

The app should download or load the BEIR TREC-COVID dataset when available, cache processed files locally, support real indexing, expose API endpoints for status, search, evaluation, and sample queries, and keep the interface usable if a large model dependency is unavailable. Normal operation requires the actual Sentence Transformer model and independent dense retrieval across the indexed corpus. A separately invoked lightweight demo can use deterministic term vectors and must disclose that it does not meet the transformer requirement.

## Evidence on Hand

Information Retrieval Project Assignments.pptx defines Project 7 as COVID Research Search using TREC-COVID / CORD-19. IR_report formatt.docx provides the expected report structure. External dataset sources verified during implementation include the NIST TREC-COVID data page and the BEIR TREC-COVID package.

## Product Principles

Real retrieval behavior matters more than decorative output.
Every metric should trace back to qrels and ranked results.
The interface should help evaluators understand why each model retrieved a document.
Fallbacks must be honest and visible.
Local setup should be simple enough for a classroom demonstration.

## Accessibility & Inclusion

The web interface should support keyboard operation, readable contrast, responsive layouts, visible focus states, and clear error and loading states.
