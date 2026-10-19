---
name: COVID Research Search
description: Search-first research workbench for comparing COVID retrieval models
colors:
  ink: "#202f28"
  paper: "#f4f6f3"
  field: "#ffffff"
  muted: "#59665f"
  border: "#dce2dc"
  green: "#254d40"
  selected: "#e9f1eb"
  signal: "#a9562a"
  error: "#87351f"
  error-surface: "#fff1ec"
rounded:
  control: "4px"
  input: "6px"
  panel: "8px"
typography:
  display:
    fontFamily: "Georgia, serif"
    fontSize: "clamp(27px, 2.5vw, 36px)"
    fontWeight: 500
    lineHeight: 1.2
  body:
    fontFamily: "Segoe UI, Aptos, system-ui, sans-serif"
    fontSize: "15px"
    lineHeight: 1.55
  section:
    fontSize: "19px"
    fontWeight: 650
  result:
    fontSize: "17px"
    fontWeight: 600
  supporting:
    fontSize: "13px"
  measurement:
    fontSize: "12px"
---

# Research workbench

The main task is searching an indexed research corpus, comparing rankers, and inspecting papers. Search appears in the first viewport at all supported widths. There is no introductory full-screen hero or ornamental motion.

Use a quiet paper background, white search surface, forest green for interactive and selected states, and four distinguishable line colors and dash patterns for the model-comparison PR chart. Serif type belongs only to the introductory heading. Operational text uses the system sans stack. Metrics use tabular numerals.

The page has a compact identity header, one introductory sentence with live corpus counts, a full-width search form with four ranking controls, and a results column beside the evaluation column. The desktop container is at most 1440px. Below 820px the results and evaluation stack in DOM order. Phone search submission spans the full input width, and the model choices form a two-column grid.

Keep titles readable, snippets at a comfortable reading measure, and rank evidence subordinate to paper content. Do not invent metadata or metrics. The active dense engine and fallback must remain visible. Evaluation uses all judged queries and original qrels; relevant documents outside the indexed subset remain in relevance denominators. The four-model chart plots interpolated precision against recall. Display metric scores to four decimal places so nearby results remain distinguishable.

Loading replaces the result list with an explicit search state. Empty results, unavailable service, unavailable evaluation, and invalid queries have distinct messages. Service and evaluation errors offer retry controls. Outdated search requests are aborted so rapid model changes cannot overwrite the latest result.

Keyboard focus, labeled inputs, semantic table headers, a search skip link, live search status, and reduced-motion preferences are supported. Maintain at least 42px controls, 44px phone model controls, and no page-level horizontal overflow at 320px.
