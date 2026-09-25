from __future__ import annotations

import csv
import io
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .search_engine import SearchEngine

app = FastAPI(title="COVID Research Search API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SearchEngine()


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    method: str = Field(default="hybrid", pattern="^(tfidf|bm25|dense|hybrid)$")
    limit: int = Field(default=10, ge=1, le=50)


@app.on_event("startup")
def startup() -> None:
    engine.prepare()


@app.get("/api/status")
def status() -> dict:
    return engine.status()


@app.get("/api/sample-queries")
def sample_queries(limit: int = Query(default=8, ge=1, le=20)) -> dict:
    return {"queries": engine.sample_queries(limit)}


@app.post("/api/search")
def search(request: SearchRequest) -> dict:
    try:
        return engine.search(request.query, request.method, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/evaluation")
def evaluation() -> dict:
    return engine.evaluate()


@app.get("/api/evaluation/export")
def export_evaluation(format: str = Query(default="json", pattern="^(json|csv|pr)$")) -> Response:
    data = engine.evaluate()
    if format == "json":
        content = json.dumps(data, indent=2)
        extension, media_type = "json", "application/json"
    else:
        rows = data["precisionRecall" if format == "pr" else "comparison"]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        content = buffer.getvalue()
        extension, media_type = "csv", "text/csv"
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="project7-{data["experimentId"]}-{format}.{extension}"',
    })
