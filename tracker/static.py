"""Static copy of the site, for free hosting (GitHub Pages, Cloudflare Pages).

`export` writes the website plus every API response it needs as plain files, so
the site works with no server. `publish` pushes that folder to a `gh-pages` branch
as a single fresh commit each time, so published data never piles up in git
history. The collector keeps running wherever the database lives (e.g. a home PC).
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, db, report
from .config import ROOT, Config, Settings

log = logging.getLogger(__name__)
DAY = 86400
HOURLY_DAYS = 90
DAILY_DAYS = 365


def _json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clear_readonly(func, path, _exc) -> None:
    # Git writes its object files read-only; on Windows rmtree cannot delete
    # them until the read-only bit is cleared.
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _rmtree(path: Path) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_readonly)
    else:
        shutil.rmtree(path, onerror=_clear_readonly)


def export(conn: sqlite3.Connection, config: Config, settings: Settings, out: Path, now: int | None = None) -> Path:
    now = now or int(time.time())
    if out.exists():
        _rmtree(out)
    shutil.copytree(ROOT / "web", out)
    (out / "design").mkdir()
    shutil.copy2(ROOT / "terminal-design-guide" / "terminal.css", out / "design" / "terminal.css")
    index = out / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace(
        '<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="data-mode" content="static">', 1), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")  # serve files as-is on GitHub Pages

    api = out / "api"
    _json(api / "snapshot.json", analysis.snapshot(conn, config, now))
    _json(api / "correlation.json", analysis.correlation_view(conn, config, now))
    _json(api / "alerts.json", db.recent_alerts(conn, limit=100))

    event_ts = [e.ts for e in config.events if e.ts <= now - 24 * 3600]
    daily_rows = []
    for s in db.list_series(conn, active_only=False):
        key = s["key"]
        hourly = db.points(conn, key, now - HOURLY_DAYS * DAY, now, 3600)
        daily = db.points(conn, key, now - DAILY_DAYS * DAY, now, DAY)
        _json(api / "series" / key / "hour.json", {"series": s, "bucket": "hour", "points": hourly})
        _json(api / "series" / key / "day.json", {"series": s, "bucket": "day", "points": daily})
        if event_ts:
            hours = analysis.hourly(db.points(conn, key, min(event_ts) - 8 * 7 * DAY, now))
            grid = analysis.robustness_grid(hours, event_ts, seed=key)
        else:
            grid = []
        _json(api / "series" / key / "event-study.json",
              {"events": [e.__dict__ for e in config.events if e.ts in event_ts], "grid": grid})
        csv_path = api / "export" / "series" / f"{key}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["time_utc", "series", "value"])
            w.writerows([_iso(t), key, round(v, 4)] for t, v in hourly)
        daily_rows.extend([_iso(t)[:10], key, s["platform"], s["unit"], "|".join(s["tags"]), round(v, 4)] for t, v in daily)

    with (api / "export" / "daily.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date_utc", "series", "platform", "unit", "tags", "daily_mean"])
        w.writerows(daily_rows)

    reports = report.list_reports(settings)
    _json(api / "reports.json", reports)
    src = report.reports_dir(settings)
    if reports:
        shutil.copytree(src, out / "reports", ignore=shutil.ignore_patterns("*.tmp"))
        (api / "reports").mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / reports[0]["date"] / "report.json", api / "reports" / "latest.json")
    log.info("static site exported to %s", out)
    return out


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def default_remote() -> str:
    try:
        return _git(["remote", "get-url", "origin"], ROOT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit("No git remote 'origin' in the project. Push the repo to GitHub first, "
                         "or pass --remote <url>.")


def push(out: Path, remote: str, branch: str = "gh-pages") -> None:
    """Force-push `out` as a single commit, replacing the branch each time."""
    _git(["init", "-q"], out)
    _git(["checkout", "-q", "-B", branch], out)
    _git(["add", "-A"], out)
    _git(["commit", "-q", "-m", f"Publish data {_iso(int(time.time()))}"], out)
    _git(["push", "-q", "--force", remote, f"{branch}:{branch}"], out)
    log.info("pushed %s to %s (%s)", out, remote, branch)
