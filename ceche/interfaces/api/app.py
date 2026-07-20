from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ceche.config import Config
from ceche.engine import AppraisalEngine
from ceche.infrastructure.persistence.store import AppraisalStore
from ceche.interfaces.api.admin import _admin as admin_router, _db as _mysql_db


class AppraiseRequest(BaseModel):
    domain: str
    fresh: bool = False


class BulkRequest(BaseModel):
    domains: list[str]
    fresh: bool = False
    concurrency: int = 5


_engine: AppraisalEngine | None = None
_store: AppraisalStore | None = None


def _get_engine() -> AppraisalEngine:
    global _engine
    if _engine is None:
        from ceche.interfaces.cli import _build_engine
        cfg = Config.load()
        _engine = _build_engine(cfg)
    return _engine


def _get_store() -> AppraisalStore:
    global _store
    if _store is None:
        _store = AppraisalStore()
    return _store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _get_engine()
    _get_store()
    yield


app = FastAPI(
    title="Ceche Domain Appraisal API",
    version="0.3.2",
    lifespan=lifespan,
)

app.include_router(admin_router)


def create_app() -> FastAPI:
    return app


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {"status": "ok", "engine": _engine is not None}


# --- Public blog endpoints (no auth required) ---

@app.get("/blog")
async def public_blog_list() -> list[dict[str, Any]]:
    """List published blog posts."""
    conn = _mysql_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, slug, excerpt, featured_image, "
            "UNIX_TIMESTAMP(published_at) as published_at, "
            "UNIX_TIMESTAMP(created_at) as created_at "
            "FROM blog_posts WHERE status = 'published' "
            "ORDER BY published_at DESC"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@app.get("/blog/{slug}")
async def public_blog_post(slug: str) -> dict[str, Any]:
    """Get a single blog post by slug."""
    conn = _mysql_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM blog_posts WHERE slug = %s AND status = 'published'",
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        d = dict(row)
        if isinstance(d.get("content"), bytes):
            d["content"] = d["content"].decode()
        return d
    finally:
        conn.close()


@app.post("/appraise")
async def appraise_domain(req: AppraiseRequest) -> dict[str, Any]:
    engine = _get_engine()
    store = _get_store()
    try:
        result = await engine.appraise(req.domain, fresh=req.fresh)
        store.record_run(
            [req.domain], [result], [],
            fresh=req.fresh, version=result.version, command="api",
        )
        return _result_to_api(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/bulk")
async def bulk_appraise(req: BulkRequest) -> dict[str, Any]:
    from ceche.bulk_engine import BulkAppraisalEngine
    from ceche.infrastructure.rate.limiter import RateLimiter
    limiter = RateLimiter()
    from ceche.interfaces.cli import _build_engine
    cfg = Config.load()
    bulk_engine = BulkAppraisalEngine(
        _build_engine(cfg, rate_limiter=limiter),
        concurrency=req.concurrency, fresh=req.fresh,
    )
    report = await bulk_engine.run(req.domains)
    store = _get_store()
    failures_dict = [
        {"domain": f.domain, "error_type": f.error_type,
         "error_message": f.error_message}
        for f in report.failures
    ]
    store.record_run(
        req.domains, report.results, failures_dict,
        fresh=req.fresh, command="api",
    )
    return {
        "summary": {
            "total": report.summary.total,
            "succeeded": report.summary.succeeded,
            "failed": report.summary.failed,
            "duration_seconds": report.summary.duration_seconds,
        },
        "results": [_result_to_api(r) for r in report.results],
        "failures": [
            {"domain": f.domain, "error_type": f.error_type,
             "error_message": f.error_message}
            for f in report.failures
        ],
    }


@app.get("/stats")
async def get_stats(days: int = 30) -> dict[str, Any]:
    store = _get_store()
    return store.get_stats(days=days)


@app.get("/history")
async def get_history(days: int = 30) -> list[dict[str, Any]]:
    store = _get_store()
    return store.list_runs(days=days)


@app.get("/history/{domain}")
async def get_domain_history(domain: str, days: int = 90) -> list[dict[str, Any]]:
    store = _get_store()
    return store.get_domain_history(domain, days=days)


@app.get("/portfolios")
async def list_portfolios() -> list[dict[str, Any]]:
    from ceche.infrastructure.portfolio.store import PortfolioStore
    return PortfolioStore().list_all()


@app.post("/portfolios/{name}/appraise")
async def appraise_portfolio(
    name: str, fresh: bool = False, concurrency: int = 5,
) -> dict[str, Any]:
    from ceche.infrastructure.portfolio.store import PortfolioStore
    pf = PortfolioStore()
    data = pf.show(name)
    if not data:
        raise HTTPException(status_code=404, detail=f"Portfolio '{name}' not found")
    domains = [d["domain"] for d in data.get("domains", [])]
    bulk_data = await bulk_appraise(BulkRequest(
        domains=domains, fresh=fresh, concurrency=concurrency,
    ))
    for r in bulk_data.get("results", []):
        pf.update_domain_value(name, r["domain"], r.get("estimated_value"), r.get("confidence"))
    return bulk_data


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return _DASHBOARD_HTML


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ceche Dashboard</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0d1117; color: #c9d1d9; padding: 20px; }
h1 { color: #58a6ff; margin-bottom: 20px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
h2 { color: #f0f6fc; font-size: 18px; margin-bottom: 15px; }
.stats { display: flex; gap: 20px; flex-wrap: wrap; }
.stat { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 15px; min-width: 120px; text-align: center; }
.stat .value { font-size: 28px; font-weight: bold; color: #58a6ff; }
.stat .label { font-size: 12px; color: #8b949e; margin-top: 5px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d; }
th { color: #8b949e; font-size: 12px; text-transform: uppercase; }
td { font-size: 14px; }
input[type=text], select { background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; padding: 8px 12px; border-radius: 6px; }
button { background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
button:hover { background: #2ea043; }
a { color: #58a6ff; text-decoration: none; }
pre { background: #0d1117; padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
</style>
</head>
<body>
<h1>Ceche Domain Appraisal</h1>
<div class="card">
  <h2>Quick Appraise</h2>
  <input type="text" id="domain-input" placeholder="example.com" style="width: 300px;">
  <select id="fresh-select"><option value="false">Use Cache</option><option value="true">Fresh</option></select>
  <button onclick="appraise()">Appraise</button>
  <div id="result" style="margin-top: 15px;"></div>
</div>
<div class="card" id="stats-card">
  <h2>Statistics</h2>
  <div class="stats" id="stats-container"><div class="stat"><div class="value">-</div><div class="label">Loading...</div></div></div>
</div>
<div class="card">
  <h2>Recent History</h2>
  <div id="history-table"><p>Loading...</p></div>
</div>
<script>
async function appraise() {
  const domain = document.getElementById('domain-input').value;
  const fresh = document.getElementById('fresh-select').value === 'true';
  const res = await fetch('/appraise', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({domain, fresh}) });
  const data = await res.json();
  document.getElementById('result').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
}
async function loadStats() {
  const res = await fetch('/stats');
  const data = await res.json();
  document.getElementById('stats-container').innerHTML =
    '<div class="stat"><div class="value">'+data.total_appraisals+'</div><div class="label">Total</div></div>' +
    '<div class="stat"><div class="value">'+data.with_value+'</div><div class="label">With Value</div></div>' +
    '<div class="stat"><div class="value">$'+(data.avg_estimated_value ? data.avg_estimated_value.toLocaleString() : '-')+'</div><div class="label">Avg Value</div></div>';
}
async function loadHistory() {
  const res = await fetch('/history?days=7');
  const data = await res.json();
  let html = '<table><tr><th>Run</th><th>Date</th><th>Total</th><th>OK</th><th>Failed</th><th>Command</th></tr>';
  for (const r of data) {
    const d = new Date(r.started_at * 1000);
    html += '<tr><td>'+r.id.slice(0,8)+'</td><td>'+d.toLocaleDateString()+'</td><td>'+r.total+'</td><td>'+r.succeeded+'</td><td>'+r.failed+'</td><td>'+r.command+'</td></tr>';
  }
  html += '</table>';
  document.getElementById('history-table').innerHTML = html;
}
loadStats(); loadHistory();
</script>
</body>
</html>"""


def _result_to_api(r: Any) -> dict[str, Any]:
    mod_summary: dict[str, int] = {}
    for me in r.modules.values():
        s = me.get("status", "UNKNOWN")
        mod_summary[s] = mod_summary.get(s, 0) + 1
    return {
        "domain": r.domain,
        "estimated_value": r.estimated_value,
        "range": {"low": r.range_low, "high": r.range_high},
        "confidence": r.confidence,
        "completeness_ratio": r.completeness_ratio,
        "tld_score": r.tld_score,
        "weight_profile": r.weight_profile,
        "module_summary": mod_summary,
        "modules": r.modules,
    }
