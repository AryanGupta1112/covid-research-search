from __future__ import annotations

import json
import hashlib
import logging
import math
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import blake2b
from pathlib import Path
from typing import Iterable
from threading import Lock
from datetime import datetime, timezone

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
LOGGER = logging.getLogger(__name__)

DATA_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/trec-covid-beir.zip"
DATA_MIRRORS = [
    DATA_URL,
    "http://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/trec-covid-beir.zip",
]
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as",
    "at", "be", "because", "been", "before", "being", "between", "both", "but", "by", "can", "did",
    "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has",
    "have", "having", "he", "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "itself", "just", "me", "more", "most", "my", "no", "nor", "not", "now",
    "of", "off", "on", "once", "only", "or", "other", "our", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "them", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with", "you",
    "your",
}


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    url: str = ""


def tokenize(text: str) -> list[str]:
    terms = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{1,}", text.lower())
    return [stem(t) for t in terms if t not in STOPWORDS and len(t) > 2]


def stem(term: str) -> str:
    for suffix in ("ization", "ational", "fulness", "ousness", "iveness", "tional", "ments", "ment", "ingly", "edly", "ing", "ed", "ies", "s"):
        if term.endswith(suffix) and len(term) > len(suffix) + 3:
            if suffix == "ies":
                return term[:-3] + "y"
            return term[: -len(suffix)]
    return term


def term_vector(term: str, dims: int = 96) -> np.ndarray:
    digest = blake2b(term.encode("utf-8"), digest_size=16).digest()
    seed = int.from_bytes(digest[:8], "little", signed=False)
    rng = np.random.default_rng(seed)
    return rng.normal(0, 1, dims).astype(np.float32)


class SearchEngine:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.data_dir = self.root / "data" / "trec-covid"
        self.max_docs = int(os.getenv("IR_MAX_DOCS", "20000"))
        self.docs: list[Document] = []
        self.doc_index: dict[str, int] = {}
        self.doc_terms: list[Counter[str]] = []
        self.doc_lens: np.ndarray = np.array([], dtype=np.float32)
        self._term_vectors: dict[str, np.ndarray] = {}
        self.df: Counter[str] = Counter()
        self.idf: dict[str, float] = {}
        self.tfidf_idf: dict[str, float] = {}
        self.tfidf_norms = np.array([], dtype=np.float64)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.dense: np.ndarray = np.empty((0, 96), dtype=np.float32)
        self.queries: dict[str, str] = {}
        self.qrels: dict[str, dict[str, int]] = {}
        self.ready = False
        self.load_seconds = 0.0
        self.dense_engine = "deterministic term-vector fallback"
        self.st_model = None
        self.cache_dir = self.root / "data" / "cache"
        self.corpus_documents = 0
        self.corpus_fingerprint = ""
        self.evaluation_lock = Lock()
        self._query_vectors: dict[str, np.ndarray] = {}

    def prepare(self) -> None:
        if self.ready:
            return
        started = time.perf_counter()
        self._ensure_dataset()
        self._load_dataset()
        self._init_sentence_transformer()
        self._build_indices()
        if self.st_model is not None:
            self._build_sentence_index()
        self.load_seconds = round(time.perf_counter() - started, 2)
        self.ready = True

    def status(self) -> dict:
        return {
            "ready": self.ready,
            "documents": len(self.docs),
            "queries": len(self.queries),
            "judgedQueries": len(self.qrels),
            "dataset": "BEIR TREC-COVID / CORD-19",
            "datasetUrl": DATA_URL,
            "officialReference": "https://ir.nist.gov/trec-covid/data.html",
            "maxDocs": self.max_docs if self.max_docs else "full",
            "denseEngine": self.dense_engine,
            "loadSeconds": self.load_seconds,
            "corpusDocuments": self.corpus_documents,
            "assignmentReady": self.st_model is not None,
            "modelRevision": MODEL_REVISION if self.st_model is not None else None,
            "denseSearchScope": "all indexed documents",
        }

    def sample_queries(self, limit: int) -> list[dict]:
        items = list(self.queries.items())[:limit]
        return [{"id": qid, "text": text, "relevantDocs": len(self.qrels.get(qid, {}))} for qid, text in items]

    def search(self, query: str, method: str, limit: int = 10) -> dict:
        self.prepare()
        rankings = self._rank_all(query)
        ranked = rankings[method][:limit]
        results = []
        for rank, (idx, score) in enumerate(ranked, start=1):
            doc = self.docs[idx]
            results.append(
                {
                    "rank": rank,
                    "docId": doc.doc_id,
                    "title": doc.title or "Untitled CORD-19 record",
                    "snippet": self._snippet(doc.text, query),
                    "url": doc.url,
                    "score": round(float(score), 5),
                    "signals": {
                        "tfidfRank": self._rank_position(rankings["tfidf"], idx),
                        "bm25Rank": self._rank_position(rankings["bm25"], idx),
                        "denseRank": self._rank_position(rankings["dense"], idx),
                    },
                }
            )
        return {
            "query": query,
            "method": method,
            "results": results,
            "modelSummaries": self._model_summaries(rankings),
            "denseEngine": self.dense_engine,
        }

    def evaluate(self) -> dict:
        """Full-list MAP, P@10, R@100, nDCG@10 and 11-point interpolated PR.

        Original qrels are retained even when only a corpus subset is indexed.
        Queries with no relevant documents in that subset contribute zero scores.
        """
        self.prepare()
        with self.evaluation_lock:
            fingerprint = hashlib.sha256()
            fingerprint.update(Path(__file__).read_bytes())
            fingerprint.update(self.corpus_fingerprint.encode())
            fingerprint.update(self.dense_engine.encode())
            for source in (self.data_dir / "queries.jsonl", self.data_dir / "qrels" / "test.tsv"):
                fingerprint.update(source.read_bytes())
            experiment_id = fingerprint.hexdigest()[:20]
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache = self.cache_dir / f"evaluation-{experiment_id}.json"
            if cache.exists():
                return json.loads(cache.read_text(encoding="utf-8"))
            methods = ("tfidf", "bm25", "dense", "hybrid")
            totals = {m: Counter() for m in methods}
            recall_levels = np.linspace(0.0, 1.0, 11)
            curves = {m: np.zeros(11, dtype=np.float64) for m in methods}
            per_query = []
            skipped = []
            covered = 0
            if self.st_model is not None:
                # Batch encode evaluation queries once; interactive queries reuse the cache.
                query_items = list(self.queries.items())
                encoded = self.st_model.encode(
                    [text for _, text in query_items], normalize_embeddings=True,
                    show_progress_bar=False, batch_size=32,
                )
                self._query_vectors.update({text: vec for (_, text), vec in zip(query_items, encoded)})
            for qid, query in self.queries.items():
                grades = self.qrels.get(qid, {})
                relevant = {doc_id for doc_id, rel in grades.items() if rel > 0}
                if not relevant:
                    skipped.append(qid)
                    continue
                in_index = len(relevant.intersection(self.doc_index))
                covered += int(in_index > 0)
                rankings = self._rank_all(query)
                row = {"queryId": qid, "query": query, "relevantDocuments": len(relevant),
                       "relevantInIndex": in_index, "metrics": {}}
                for method in methods:
                    doc_ids = [self.docs[idx].doc_id for idx, _ in rankings[method]]
                    metrics = self._metrics(doc_ids, relevant, grades)
                    totals[method].update(metrics)
                    curves[method] += self._interpolated_precision(doc_ids, relevant, recall_levels)
                    row["metrics"][method] = metrics
                per_query.append(row)
            count = len(per_query)
            comparison = [{"method": method, **{
                key: round(totals[method][key] / max(count, 1), 6)
                for key in ("precisionAt10", "recallAt100", "map", "ndcgAt10")
            }} for method in methods]
            points = [{"recall": round(float(recall), 1), **{
                method: round(float(curves[method][i] / max(count, 1)), 6)
                for method in methods
            }} for i, recall in enumerate(recall_levels)]
            result = {
                "experimentId": experiment_id,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "dataset": "BEIR TREC-COVID / CORD-19", "indexedDocuments": len(self.docs),
                "corpusDocuments": self.corpus_documents, "totalQueries": len(self.queries),
                "evaluatedQueries": count, "queriesWithRelevantInIndex": covered,
                "skippedQueries": skipped, "denseEngine": self.dense_engine,
                "assignmentReady": self.st_model is not None,
                "modelRevision": MODEL_REVISION if self.st_model is not None else None,
                "evaluationScope": "Original qrels; all judged queries; missing corpus documents remain in relevance denominators",
                "mapScope": "Full returned rankings; sparse lists contain all documents with a matching query term; dense ranks every indexed document; RRF fuses complete lists",
                "precisionRecallDefinition": "Macro-averaged 11-point interpolated precision at fixed recall levels",
                "comparison": comparison, "precisionRecall": points, "perQuery": per_query,
            }
            temporary = cache.with_suffix(".tmp")
            temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
            temporary.replace(cache)
            return result

    @staticmethod
    def _interpolated_precision(ranked_ids, relevant, recall_levels):
        if not relevant or not ranked_ids:
            return np.zeros(len(recall_levels), dtype=np.float64)
        hits = np.array([doc_id in relevant for doc_id in ranked_ids], dtype=np.float64)
        cumulative = np.cumsum(hits)
        precision = cumulative / np.arange(1, len(hits) + 1)
        recall = cumulative / len(relevant)
        return np.array([float(np.max(precision[recall >= level]))
                         if np.any(recall >= level) else 0.0 for level in recall_levels])

    def _ensure_dataset(self) -> None:
        corpus = self.data_dir / "corpus.jsonl"
        if corpus.exists():
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        archive = self.data_dir / "trec-covid-beir.zip"
        if archive.exists() and archive.stat().st_size < 1_000_000:
            archive.unlink()
        if not archive.exists():
            self._download_dataset(archive)
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(self.data_dir)
        except zipfile.BadZipFile:
            archive.unlink(missing_ok=True)
            self._download_dataset(archive)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(self.data_dir)
        nested = next(
            (path for path in (self.data_dir / "trec-covid", self.data_dir / "trec-covid-beir") if path.exists()),
            None,
        )
        if nested:
            for child in nested.iterdir():
                target = self.data_dir / child.name
                if not target.exists():
                    child.replace(target)

    def _download_dataset(self, archive: Path) -> None:
        if os.name == "nt" and self._download_with_curl(archive):
            return
        last_error: Exception | None = None
        for url in DATA_MIRRORS:
            for context in (None, ssl._create_unverified_context() if url.startswith("https") else None):
                if context is False:
                    continue
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "COVID-Research-Search/1.0"})
                    with urllib.request.urlopen(request, context=context, timeout=180) as response, archive.open("wb") as target:
                        while True:
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            target.write(chunk)
                    if archive.stat().st_size > 1_000_000:
                        return
                except Exception as exc:
                    last_error = exc
                    if archive.exists():
                        archive.unlink()
        if last_error:
            raise last_error

    def _download_with_curl(self, archive: Path) -> bool:
        try:
            if archive.exists():
                archive.unlink()
            result = subprocess.run(
                ["curl.exe", "-L", "--http1.1", "--fail", "--retry", "2", "--connect-timeout", "20", "-o", str(archive), DATA_URL],
                cwd=self.root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=240,
            )
            return result.returncode == 0 and archive.exists() and archive.stat().st_size > 1_000_000
        except Exception:
            if archive.exists():
                archive.unlink()
            return False

    def _load_dataset(self) -> None:
        corpus_path = self.data_dir / "corpus.jsonl"
        queries_path = self.data_dir / "queries.jsonl"
        qrels_path = self.data_dir / "qrels" / "test.tsv"
        limit = None if self.max_docs == 0 else self.max_docs

        digest = hashlib.sha256()
        with corpus_path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle):
                if limit and line_no >= limit:
                    break
                digest.update(line.encode("utf-8"))
                row = json.loads(line)
                doc_id = str(row.get("_id"))
                metadata = row.get("metadata") or {}
                self.doc_index[doc_id] = len(self.docs)
                self.docs.append(
                    Document(
                        doc_id=doc_id,
                        title=row.get("title") or metadata.get("title") or "",
                        text=row.get("text") or "",
                        url=metadata.get("url") or metadata.get("doi") or "",
                    )
                )

        self.corpus_fingerprint = digest.hexdigest()
        with corpus_path.open("rb") as corpus_file:
            self.corpus_documents = sum(1 for _ in corpus_file)

        with queries_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                self.queries[str(row.get("_id"))] = row.get("text") or ""

        with qrels_path.open("r", encoding="utf-8") as handle:
            next(handle, None)
            for line in handle:
                parts = line.strip().split("\t")
                if len(parts) == 4:
                    qid, _, doc_id, score = parts
                elif len(parts) == 3:
                    qid, doc_id, score = parts
                else:
                    continue
                self.qrels.setdefault(qid, {})[doc_id] = int(score)

    def _build_indices(self) -> None:
        vectors = []
        lengths = []
        for idx, doc in enumerate(self.docs):
            terms = Counter(tokenize(f"{doc.title} {doc.text}"))
            self.doc_terms.append(terms)
            lengths.append(sum(terms.values()))
            for term in terms:
                self.df[term] += 1
            for term, tf in terms.items():
                self.postings[term].append((idx, tf))

        self.doc_lens = np.array(lengths, dtype=np.float64)
        doc_count = max(len(self.docs), 1)
        avg_len = float(np.mean(self.doc_lens)) if len(self.doc_lens) else 1.0
        self.avg_len = max(avg_len, 1.0)
        self.idf = {term: math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0) for term, df in self.df.items()}

        self.tfidf_idf = {term: math.log((1 + doc_count) / (1 + df)) + 1
                          for term, df in self.df.items()}
        self.tfidf_norms = np.array([
            math.sqrt(sum(((1 + math.log(tf)) * self.tfidf_idf[term]) ** 2
                          for term, tf in terms.items()))
            for terms in self.doc_terms
        ], dtype=np.float64)
        if self.st_model is None:
            for terms in self.doc_terms:
                vec = np.zeros(96, dtype=np.float32)
                for term, tf in terms.items():
                    vec += self._vector_for(term) * ((1 + math.log(tf)) * self.tfidf_idf[term])
                norm = np.linalg.norm(vec)
                vectors.append(vec / norm if norm else vec)
            self.dense = np.vstack(vectors) if vectors else np.empty((0, 96), dtype=np.float32)

    def _build_sentence_index(self) -> None:
        """Cache true document embeddings for independent corpus-wide dense search."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256((self.corpus_fingerprint + MODEL_NAME + MODEL_REVISION
                              + "title+abstract;max_seq_length=256;normalized;v1").encode()).hexdigest()[:20]
        cache = self.cache_dir / f"minilm-{key}.npy"
        dims = self.st_model.get_embedding_dimension()
        if cache.exists():
            embeddings = np.load(cache, allow_pickle=False)
            if embeddings.shape == (len(self.docs), dims) and np.isfinite(embeddings).all():
                self.dense = embeddings
                LOGGER.info("Loaded %s cached transformer embeddings", len(self.docs))
                return
        LOGGER.info("Encoding %s documents with MiniLM; subsequent starts reuse this index", len(self.docs))
        # Checkpoint every 256 documents so interrupted first runs can resume.
        partial = cache.with_suffix(".partial.npy")
        progress = cache.with_suffix(".progress.json")
        completed = 0
        if partial.exists() and progress.exists():
            completed = json.loads(progress.read_text())["completed"]
        embeddings = np.lib.format.open_memmap(
            partial, mode="r+" if completed else "w+", dtype=np.float32,
            shape=(len(self.docs), dims),
        )
        for start in range(completed, len(self.docs), 256):
            batch = self.docs[start:start + 256]
            vectors = self.st_model.encode(
                [f"{doc.title}. {doc.text}" for doc in batch], normalize_embeddings=True,
                show_progress_bar=False, batch_size=int(os.getenv("IR_EMBED_BATCH_SIZE", "32")),
                convert_to_numpy=True,
            )
            embeddings[start:start + len(batch)] = vectors
            embeddings.flush()
            progress.write_text(json.dumps({"completed": start + len(batch)}))
            print(f"Transformer index: {start + len(batch)}/{len(self.docs)} documents", flush=True)
        del embeddings
        partial.replace(cache)
        progress.unlink(missing_ok=True)
        self.dense = np.load(cache, allow_pickle=False)

    def _rank_all(self, query: str, top_k: int | None = None) -> dict[str, list[tuple[int, float]]]:
        tfidf = self._tfidf(query, top_k)
        bm25 = self._bm25(query, top_k)
        dense = self._dense(query, top_k)
        hybrid = self._rrf([tfidf, bm25, dense], top_k)
        return {"tfidf": tfidf, "bm25": bm25, "dense": dense, "hybrid": hybrid}

    def _tfidf(self, query: str, top_k: int | None) -> list[tuple[int, float]]:
        q_terms = Counter(tokenize(query))
        weights = {term: (1 + math.log(tf)) * self.tfidf_idf[term]
                   for term, tf in q_terms.items() if term in self.tfidf_idf}
        norm = math.sqrt(sum(weight ** 2 for weight in weights.values()))
        if not norm:
            return []
        scores = defaultdict(float)
        for term, q_weight in weights.items():
            for idx, tf in self.postings[term]:
                scores[idx] += q_weight * (1 + math.log(tf)) * self.tfidf_idf[term]
        normalized = [(idx, score / (norm * self.tfidf_norms[idx]))
                      for idx, score in scores.items() if self.tfidf_norms[idx] > 0]
        return sorted(normalized, key=lambda item: (-item[1], item[0]))[:top_k]

    def _bm25(self, query: str, top_k: int | None) -> list[tuple[int, float]]:
        k1, b = 1.5, 0.75
        scores = defaultdict(float)
        for term in tokenize(query):
            idf = self.idf.get(term)
            if not idf:
                continue
            for idx, tf in self.postings.get(term, []):
                denom = tf + k1 * (1 - b + b * self.doc_lens[idx] / self.avg_len)
                scores[idx] += idf * (tf * (k1 + 1)) / denom
        return sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:top_k]

    def _dense(self, query: str, top_k: int | None) -> list[tuple[int, float]]:
        if self.st_model is not None:
            if query not in self._query_vectors:
                self._query_vectors[query] = self.st_model.encode(
                    [query], normalize_embeddings=True, show_progress_bar=False)[0]
                if len(self._query_vectors) > 512:
                    self._query_vectors.pop(next(iter(self._query_vectors)))
            q_vec = self._query_vectors[query]
        else:
            q_vec = np.zeros(96, dtype=np.float32)
            for term, tf in Counter(tokenize(query)).items():
                q_vec += self._vector_for(term) * ((1 + math.log(tf)) * self.tfidf_idf.get(term, 0.2))
            norm = np.linalg.norm(q_vec)
            if not norm:
                return []
            q_vec /= norm
        scores = self.dense @ q_vec
        # Stable sorting gives deterministic corpus-order tie breaking.
        ordered = np.argsort(-scores, kind="stable")[:top_k]
        return [(int(idx), float(scores[idx])) for idx in ordered]

    def _rrf(self, rankings: Iterable[list[tuple[int, float]]], top_k: int | None) -> list[tuple[int, float]]:
        scores = defaultdict(float)
        for ranking in rankings:
            for rank, (idx, _) in enumerate(ranking, start=1):
                scores[idx] += 1.0 / (60 + rank)
        return sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:top_k]

    def _vector_for(self, term: str) -> np.ndarray:
        vector = self._term_vectors.get(term)
        if vector is None:
            vector = term_vector(term)
            self._term_vectors[term] = vector
        return vector

    def _init_sentence_transformer(self) -> None:
        if os.getenv("IR_DISABLE_SENTENCE_TRANSFORMER") == "1":
            LOGGER.warning("Explicit lightweight demo mode: not the assignment Sentence Transformer model")
            return
        try:
            import torch
            from sentence_transformers import SentenceTransformer
            torch.set_num_threads(int(os.getenv("IR_TORCH_THREADS", "8")))
            options = {"revision": MODEL_REVISION, "device": "cpu"}
            try:
                self.st_model = SentenceTransformer(MODEL_NAME, local_files_only=True, **options)
            except OSError:
                self.st_model = SentenceTransformer(MODEL_NAME, **options)
            self.st_model.max_seq_length = 256
            self.dense_engine = "SentenceTransformer all-MiniLM-L6-v2 across all indexed documents"
        except Exception as exc:
            raise RuntimeError(
                "Project 7 requires Sentence Transformers. Install backend/requirements.txt and retry. "
                "For an explicitly limited demo only, set IR_DISABLE_SENTENCE_TRANSFORMER=1. "
                f"Model initialization failed: {exc}"
            ) from exc

    def _metrics(self, ranked_ids: list[str], relevant: set[str], grades: dict[str, int]) -> dict:
        top10 = ranked_ids[:10]
        hits = [1 if doc_id in relevant else 0 for doc_id in ranked_ids]
        precision_at_10 = sum(1 for doc_id in top10 if doc_id in relevant) / 10
        recall_at_100 = sum(hits[:100]) / max(len(relevant), 1)
        ap_total = 0.0
        found = 0
        for i, hit in enumerate(hits, start=1):
            if hit:
                found += 1
                ap_total += found / i
        average_precision = ap_total / max(len(relevant), 1)
        dcg = 0.0
        for i, doc_id in enumerate(ranked_ids[:10], start=1):
            gain = grades.get(doc_id, 0)
            dcg += (2**gain - 1) / math.log2(i + 1)
        ideal = sorted((rel for rel in grades.values() if rel > 0), reverse=True)[:10]
        idcg = sum((2**gain - 1) / math.log2(i + 1) for i, gain in enumerate(ideal, start=1))
        return {
            "precisionAt10": precision_at_10,
            "recallAt100": recall_at_100,
            "map": average_precision,
            "ndcgAt10": dcg / idcg if idcg else 0.0,
        }

    def _snippet(self, text: str, query: str, size: int = 360) -> str:
        if not text:
            return ""
        lowered = text.lower()
        positions = [lowered.find(term) for term in re.findall(r"[a-zA-Z]{3,}", query.lower())]
        positions = [p for p in positions if p >= 0]
        start = max(min(positions) - 80, 0) if positions else 0
        snippet = text[start : start + size].replace("\n", " ")
        return ("..." if start else "") + snippet + ("..." if start + size < len(text) else "")

    def _rank_position(self, ranking: list[tuple[int, float]], doc_idx: int) -> int | None:
        for pos, (idx, _) in enumerate(ranking, start=1):
            if idx == doc_idx:
                return pos
        return None

    def _model_summaries(self, rankings: dict[str, list[tuple[int, float]]]) -> list[dict]:
        return [
            {"method": method, "topScore": round(float(items[0][1]), 5) if items else 0, "candidates": len(items)}
            for method, items in rankings.items()
        ]
