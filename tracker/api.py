"""HTTP API and static site. Optionally runs the collection loop in-process."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import alerts, analysis, collectors, db, pause, report
from .config import ROOT, Config, Settings

log = logging.getLogger(__name__)
CACHE_SECONDS = 60
BUCKETS = {"raw": 0, "hour": 3600, "day": 86400}


class SnapshotCache:
    """Snapshot-style views touch every series; compute each at most once a minute."""

    def __init__(self, config: Config, settings: Settings, build=analysis.snapshot):
        self.config, self.settings, self.build = config, settings, build
        self._value: dict | None = None
        self._at = 0.0
        self._lock = threading.Lock()

    def get(self) -> dict:
        with self._lock:
            if self._value is None or time.time() - self._at > CACHE_SECONDS:
                with db.session(self.settings.db_path) as conn:
                    self._value = self.build(conn, self.config, int(time.time()))
                self._at = time.time()
            return self._value

    def invalidate(self) -> None:
        with self._lock:
            self._value = None


def _daily_report(config: Config, settings: Settings) -> None:
    with db.session(settings.db_path) as conn:
        report.ensure_today(conn, config, settings, int(time.time()))


async def collection_loop(config: Config, settings: Settings, cache: SnapshotCache,
                          *derived: SnapshotCache) -> None:
    while True:
        started = time.time()
        try:
            await collectors.run(config, settings)
            for c in (cache, *derived):
                c.invalidate()
            snap = await asyncio.to_thread(cache.get)
            with db.session(settings.db_path) as conn:
                await alerts.run(conn, snap, settings)
            await asyncio.to_thread(_daily_report, config, settings)
        except Exception:
            log.exception("collection pass failed")
        await asyncio.sleep(max(60.0, settings.interval_min * 60 - (time.time() - started)))


def _csv(rows: list[list], header: list[str], filename: str) -> PlainTextResponse:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_app(config: Config, settings: Settings, collect: bool = False) -> FastAPI:
    cache = SnapshotCache(config, settings)
    correlation = SnapshotCache(config, settings, analysis.correlation_view)
    aligned = SnapshotCache(config, settings, analysis.strike_aligned)
    heat = SnapshotCache(config, settings, analysis.heatmap)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        with db.session(settings.db_path) as conn:
            db.init(conn, config.series)
        task = asyncio.create_task(collection_loop(config, settings, cache, correlation, aligned, heat)) if collect else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="Bot Traffic Monitor API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def cache_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/") and response.status_code == 200:
            # Lets a CDN (e.g. Cloudflare with a cache rule on /api/*) absorb traffic spikes.
            response.headers.setdefault("Cache-Control", f"public, max-age={CACHE_SECONDS}")
        return response

    @app.get("/api/snapshot")
    def get_snapshot() -> dict:
        return {**cache.get(), "paused": pause.state(settings)}

    @app.get("/api/correlation")
    def get_correlation() -> dict:
        """Daily indices (100 = pre-strike mean) for Yandex reachability and each group."""
        return correlation.get()

    @app.get("/api/strike-aligned")
    def get_strike_aligned() -> dict:
        """Each group's activity around the strikes, all strikes lined up at hour 0, with
        the range of ordinary days (5th-95th percentile of random pre-strike windows)."""
        return aligned.get()

    @app.get("/api/heatmap")
    def get_heatmap() -> dict:
        """Every community's daily index (100 = pre-strike mean), grouped."""
        return heat.get()

    @app.get("/api/series/{key}/strike-hours")
    def get_strike_hours(key: str, event: int = Query(0, ge=0)) -> dict:
        """Hour of day x day around one strike, vs the same weekday-hour 1-3 weeks earlier."""
        now = int(time.time())
        with db.session(settings.db_path) as conn:
            if db.get_series(conn, key) is None:
                raise HTTPException(404, f"unknown series {key!r}")
            out = analysis.strike_hours(conn, config, key, event, now)
        if out is None:
            raise HTTPException(404, f"no past strike with index {event}")
        return out

    @app.get("/api/series/{key}/points")
    def get_points(key: str, days: int = Query(30, ge=1, le=3650),
                   bucket: str = Query("hour", pattern="^(raw|hour|day)$")) -> dict:
        if bucket == "raw" and days > 14:
            raise HTTPException(400, "raw points are limited to 14 days; use bucket=hour or day")
        now = int(time.time())
        with db.session(settings.db_path) as conn:
            series = db.get_series(conn, key)
            if series is None:
                raise HTTPException(404, f"unknown series {key!r}")
            if bucket == "day":  # complete days only, as everywhere else
                pts = db.daily_points(conn, key, now - days * 86400, now, analysis.MIN_DAY_HOURS)
            else:
                pts = db.points(conn, key, now - days * 86400, now, BUCKETS[bucket])
        return {"series": series, "bucket": bucket, "points": pts}

    @app.get("/api/series/{key}/event-study")
    def get_event_study(key: str) -> dict:
        """Robustness grid: the stacked event study for several window lengths and
        start offsets. A real effect should hold across the grid, not in one cell."""
        now = int(time.time())
        events = [e for e in config.events if e.ts <= now - 24 * 3600]
        if not events:
            return {"events": [], "grid": []}
        with db.session(settings.db_path) as conn:
            if db.get_series(conn, key) is None:
                raise HTTPException(404, f"unknown series {key!r}")
            hours = analysis.hourly(db.points(conn, key, min(e.ts for e in events) - 8 * 7 * 86400, now))
        grid = analysis.robustness_grid(hours, [e.ts for e in events], seed=key)
        return {"events": [e.__dict__ for e in events], "grid": grid}

    @app.get("/api/alerts")
    def get_alerts(limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
        with db.session(settings.db_path) as conn:
            return db.recent_alerts(conn, limit=limit)

    @app.get("/api/export/series.csv")
    def export_series(key: str, days: int = Query(90, ge=1, le=3650),
                      bucket: str = Query("hour", pattern="^(raw|hour|day)$")):
        now = int(time.time())
        with db.session(settings.db_path) as conn:
            if db.get_series(conn, key) is None:
                raise HTTPException(404, f"unknown series {key!r}")
            pts = db.points(conn, key, now - days * 86400, now, BUCKETS[bucket])
        return _csv([[_iso(t), key, v] for t, v in pts], ["time_utc", "series", "value"], f"{key}.csv")

    @app.get("/api/export/daily.csv")
    def export_daily(days: int = Query(365, ge=1, le=3650)):
        now = int(time.time())
        rows = []
        with db.session(settings.db_path) as conn:
            for s in db.list_series(conn, active_only=False):
                for t, v in db.daily_points(conn, s["key"], now - days * 86400, now, analysis.MIN_DAY_HOURS):
                    rows.append([_iso(t)[:10], s["key"], s["platform"], s["unit"], "|".join(s["tags"]), round(v, 4)])
        return _csv(rows, ["date_utc", "series", "platform", "unit", "tags", "daily_mean"], "daily.csv")

    @app.get("/api/reports")
    def get_reports() -> list[dict]:
        """Archived daily reports, newest first. Files are served under /reports/<date>/."""
        return report.list_reports(settings)

    @app.get("/api/reports/latest")
    def get_latest_report() -> dict:
        reports = report.list_reports(settings)
        if not reports:
            raise HTTPException(404, "no report has been generated yet")
        path = report.reports_dir(settings) / reports[0]["date"] / "report.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "time": int(time.time())}

    reports_root = report.reports_dir(settings)
    reports_root.mkdir(parents=True, exist_ok=True)
    app.mount("/reports", StaticFiles(directory=reports_root), name="reports")
    app.mount("/design", StaticFiles(directory=ROOT / "terminal-design-system"), name="design")
    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
    return app
