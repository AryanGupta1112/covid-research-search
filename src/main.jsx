import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, ArrowUpRight, BarChart3, BookOpen, Database, FileSearch, Gauge, GitMerge, Loader2, Search, Sparkles } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import "./styles.css";

const methods = [
  { id: "hybrid", label: "Hybrid RRF", icon: GitMerge, description: "Combines the rankings of all three retrieval models." },
  { id: "bm25", label: "BM25", icon: Gauge, description: "Keyword retrieval with term frequency and document length normalization." },
  { id: "tfidf", label: "TF-IDF", icon: BarChart3, description: "Cosine similarity with sublinear TF and smoothed inverse document frequency." },
  { id: "dense", label: "Dense (MiniLM)", icon: Sparkles, description: "Independent Sentence Transformer search across every indexed paper using MiniLM embeddings." },
];
const plotStyles = {
  tfidf: { color: "#596e9a", dash: "4 3" },
  bm25: { color: "#a9562a", dash: "7 3" },
  dense: { color: "#78618f", dash: "2 3" },
  hybrid: { color: "#254d40", dash: undefined },
};
const starterQueries = ["coronavirus transmission in children", "risk factors for severe covid pneumonia", "effectiveness of masks against SARS-CoV-2", "vaccine immune response neutralizing antibodies"];
const labelFor = (id) => methods.find((m) => m.id === id)?.label ?? id;
const fmt = (n) => typeof n === "number" ? n.toFixed(4) : "—";
const rankLabel = (n) => n ? `#${n}` : "not retrieved";

async function readApi(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error("The search service is unavailable. Check that the backend is running, then retry.");
  return response.json();
}

function App() {
  const [status, setStatus] = useState(null);
  const [samples, setSamples] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [query, setQuery] = useState(starterQueries[0]);
  const [method, setMethod] = useState("hybrid");
  const [limit, setLimit] = useState(10);
  const [searchData, setSearchData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const [evaluating, setEvaluating] = useState(true);
  const [serviceError, setServiceError] = useState("");
  const [evalError, setEvalError] = useState("");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const requestId = useRef(0);
  const controller = useRef(null);

  useEffect(() => {
    let active = true;
    setBooting(true);
    setServiceError("");
    Promise.all([readApi("/api/status"), readApi("/api/sample-queries?limit=8")])
      .then(([s, q]) => { if (active) { setStatus(s); setSamples(q.queries ?? []); } })
      .catch((e) => { if (active) setServiceError(e.message); })
      .finally(() => { if (active) setBooting(false); });
    setEvaluating(true);
    setEvalError("");
    readApi("/api/evaluation")
      .then((data) => { if (active) setEvaluation(data); })
      .catch(() => { if (active) setEvalError("Evaluation could not be loaded."); })
      .finally(() => { if (active) setEvaluating(false); });
    return () => { active = false; };
  }, [reload]);

  useEffect(() => {
    runSearch(starterQueries[0], "hybrid", 10);
    return () => controller.current?.abort();
  }, []);

  async function runSearch(nextQuery = query, nextMethod = method, nextLimit = limit) {
    const trimmed = nextQuery.trim();
    controller.current?.abort();
    const id = ++requestId.current;
    if (trimmed.length < 2 || trimmed.length > 500) {
      setError("Enter a research query between 2 and 500 characters.");
      setLoading(false);
      return;
    }
    controller.current = new AbortController();
    setLoading(true);
    setError("");
    try {
      const data = await readApi("/api/search", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmed, method: nextMethod, limit: nextLimit }),
        signal: controller.current.signal,
      });
      if (id === requestId.current) setSearchData(data);
    } catch (e) {
      if (e.name !== "AbortError" && id === requestId.current) setError(e.message);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }

  const activeMethod = methods.find((m) => m.id === method);
  const isFallback = status?.denseEngine?.includes("fallback");
  return <>
    <a className="skip-link" href="#search-input">Skip to search</a>
    <header className="topbar">
      <div className="topbar-inner">
        <a className="brand" href="#"><FileSearch size={23} /><span>COVID Research Search</span></a>
        <span className="dataset-tag">TREC-COVID / CORD-19</span>
        <span className={`connection ${serviceError ? "offline" : ""}`}><span className="status-dot" />{booting ? "Connecting to corpus" : serviceError ? "Service unavailable" : "Corpus ready"}</span>
      </div>
    </header>
    <main className="app-shell">
      <section className="intro">
        <div><h1>Explore the research. Compare the evidence.</h1><p>Search COVID-19 papers with four retrieval methods and inspect how each model ranks the results.</p></div>
        <div className="corpus-summary" aria-label="Corpus statistics">
          <span><Database size={16} /><strong>{status ? status.documents.toLocaleString() : "—"}</strong> papers</span>
          <span><BookOpen size={16} /><strong>{status?.queries ?? "—"}</strong> topics</span>
        </div>
      </section>
      {isFallback && <div className="error-state" role="alert">Demo mode: Sentence Transformers are disabled. These dense and hybrid results do not fulfill the assignment’s transformer requirement.</div>}
      {serviceError && <div className="error-state" role="alert"><span>{serviceError}</span><button onClick={() => { setReload((n) => n + 1); runSearch(); }}>Retry connection</button></div>}
      <section className="search-panel" aria-label="Research search">
        <form onSubmit={(e) => { e.preventDefault(); runSearch(); }}>
          <label htmlFor="search-input">Search the research corpus</label>
          <div className="search-box"><Search size={22} /><input id="search-input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask a question or enter research keywords" aria-describedby={error ? "search-error" : undefined} aria-invalid={!!error} /><button type="submit" disabled={loading}>{loading ? <Loader2 size={18} className="spin" /> : <Search size={18} />}{loading ? "Searching…" : "Search papers"}</button></div>
        </form>
        <div className="search-options">
          <div className="method-grid" role="group" aria-label="Ranking method">{methods.map(({ id, label, icon: Icon }) => <button key={id} aria-pressed={method === id} className={method === id ? "method active" : "method"} onClick={() => { setMethod(id); runSearch(query, id, limit); }}><Icon size={17} />{label}</button>)}</div>
          <label className="result-count">Show <select aria-label="Number of results" value={limit} onChange={(e) => { const n = Number(e.target.value); setLimit(n); runSearch(query, method, n); }}>{[10, 20, 50].map((n) => <option key={n} value={n}>{n} results</option>)}</select></label>
        </div>
        <p className="method-description">{activeMethod.description}</p>
        {error && <div id="search-error" className="error-state" role="alert">{error}</div>}
      </section>
      <div className="content-grid">
        <section className="results-section" aria-label="Ranked papers" aria-busy={loading}>
          <div className="section-heading"><div><h2>Ranked papers</h2><p aria-live="polite">{loading ? `Searching with ${activeMethod.label}…` : searchData ? `${searchData.results.length} results · ${labelFor(searchData.method)}` : "Your search results will appear here"}</p></div>{loading && <Loader2 size={20} className="spin" />}</div>
          {searchData && <p className="query-caption">Results for <strong>“{searchData.query}”</strong></p>}
          {loading ? <div className="loading-state" role="status"><Loader2 className="spin" size={25} /><h3>Finding relevant papers</h3><p>Comparing document rankings across the corpus.</p></div> : searchData?.results.length ? <div className="result-list">{searchData.results.map((result) => <article className="result" key={result.docId}>
            <span className="rank">{String(result.rank).padStart(2, "0")}</span><div className="result-body"><h3>{result.url ? <a href={result.url} target="_blank" rel="noreferrer">{result.title}<ArrowUpRight size={16} /></a> : result.title}</h3><p>{result.snippet}</p><div className="signals"><span className="score">Score {result.score}</span><span>TF-IDF {rankLabel(result.signals?.tfidfRank)}</span><span>BM25 {rankLabel(result.signals?.bm25Rank)}</span><span>Dense {rankLabel(result.signals?.denseRank)}</span></div>{result.url && <a className="paper-link" href={result.url} target="_blank" rel="noreferrer">Open paper <ArrowUpRight size={14} /></a>}</div>
          </article>)}</div> : <div className="empty-state"><FileSearch size={30} /><h3>{error ? "Search is unavailable" : searchData ? "No papers found" : "Start with a research question"}</h3><p>{error ? "Check the backend connection and try your search again." : "Try broader keywords or choose one of the suggested topics."}</p></div>}
        </section>
        <aside className="sidebar" aria-label="Evaluation and research topics">
          <section className="metrics-panel"><div className="section-heading"><div><h2>Model comparison</h2><p>{evaluation ? `${evaluation.evaluatedQueries}/${evaluation.totalQueries} queries · original qrels` : "Evaluation against relevance judgments"}</p></div>{evaluating && <Loader2 className="spin" size={18} />}</div>
            {evalError ? <div className="inline-error" role="alert">{evalError} <button onClick={() => setReload((n) => n + 1)}>Retry</button></div> : <>
              <div className="table-wrap"><table><caption className="sr-only">Retrieval model evaluation scores</caption><thead><tr><th scope="col">Model</th><th scope="col">P@10</th><th scope="col">R@100</th><th scope="col">MAP</th><th scope="col">nDCG@10</th></tr></thead><tbody>{(evaluation?.comparison ?? methods.map((m) => ({ method: m.id }))).map((row) => <tr key={row.method} className={row.method === method ? "selected-row" : ""}><th scope="row">{labelFor(row.method)}</th><td>{fmt(row.precisionAt10)}</td><td>{fmt(row.recallAt100)}</td><td>{fmt(row.map)}</td><td>{fmt(row.ndcgAt10)}</td></tr>)}</tbody></table></div>
              <p className="metric-note">{evaluation ? `${evaluation.indexedDocuments.toLocaleString()} of ${evaluation.corpusDocuments.toLocaleString()} papers indexed. ` : ""}MAP uses full rankings. Relevant papers outside the index remain in recall and AP denominators.</p>
              <div className="export-links"><a href="/api/evaluation/export?format=csv" download>Download scores</a><a href="/api/evaluation/export?format=json" download>Experiment JSON</a></div>
              <div className="chart-heading"><h3>Precision–Recall comparison</h3><div className="legend">{methods.map((m) => <span key={m.id}><i style={{ background: plotStyles[m.id].color }} />{m.label}</span>)}</div></div>
              <div className="chart-wrap" aria-label="Precision versus recall for all four retrieval models">{evaluation ? <ResponsiveContainer width="100%" height={240}><LineChart data={evaluation.precisionRecall} margin={{ top: 12, right: 12, bottom: 8, left: -18 }}><CartesianGrid stroke="#e0e5e1" strokeDasharray="3 3" vertical={false} /><XAxis type="number" domain={[0, 1]} dataKey="recall" tick={{ fontSize: 11, fill: "#59665f" }} tickLine={false} axisLine={false} /><YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "#59665f" }} tickLine={false} axisLine={false} label={{ value: "Precision", angle: -90, position: "insideLeft", dx: 18, style: { fontSize: 11, fill: "#59665f" } }} /><Tooltip labelFormatter={(value) => `Recall: ${Number(value).toFixed(1)}`} formatter={(value, name) => [Number(value).toFixed(3), name]} contentStyle={{ borderRadius: 6, borderColor: "#cdd5cf", fontSize: 12 }} />{methods.map((m) => <Line key={m.id} name={m.label} type="linear" dataKey={m.id} stroke={plotStyles[m.id].color} strokeDasharray={plotStyles[m.id].dash} strokeWidth={m.id === "hybrid" ? 2.5 : 1.8} dot={false} isAnimationActive={false} />)}</LineChart></ResponsiveContainer> : <p className="chart-loading">Calculating evaluation…</p>}</div><p className="axis-caption">Recall</p><p className="metric-note">11-point interpolated precision, averaged over all judged queries. Higher is better.</p>
            </>}
          </section>
          <section className="sample-panel"><div className="section-heading"><div><h2>Explore a topic</h2><p>Run a query from the research collection.</p></div></div><div className="sample-list">{(samples.length ? samples : starterQueries.map((text, i) => ({ id: i, text }))).map((item) => <button key={item.id} onClick={() => { setQuery(item.text); runSearch(item.text, method, limit); }}>{item.text}<ArrowUpRight size={16} /></button>)}</div></section>
          <div className="engine-note"><Sparkles size={17} /><div><strong>{isFallback ? "Lightweight dense mode" : "Dense retrieval engine"}</strong><p>{status?.denseEngine ?? "Checking engine availability…"}</p>{isFallback && <p>Install the full requirements and restart with transformer mode enabled for final evaluation.</p>}</div></div>
        </aside>
      </div>
      <footer><Activity size={15} /><span>TREC-COVID / CORD-19 · Ranked retrieval and qrels evaluation</span></footer>
    </main>
  </>;
}
createRoot(document.getElementById("root")).render(<App />);
