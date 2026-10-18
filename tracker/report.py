"""Dated, shareable report snapshots.

Each report is a folder under <db dir>/reports/YYYY-MM-DD/ holding the summary
tables as CSV and JSON, the daily data, a README with methods and column
definitions, and a zip of all of it. Reports are built once a day by the
collection loop (or on demand with `python -m tracker report`) and then served as
static files, so publishing one costs nothing when traffic spikes. Old reports are
never rewritten after their day ends, which keeps them citable.
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, db
from .config import Config, Settings

log = logging.getLogger(__name__)
DAY = 86400

COMMUNITY_COLUMNS = [
    ("community", "Community name (r/… for Reddit, BSKY \"…\" and X \"…\" for a keyword search, with its language)"),
    ("series", "Series key used by the API"),
    ("platform", "reddit or bluesky"),
    ("region", "Country or region the community is about"),
    ("groups", "Research tags, | separated (political-right, narratives, political, regional, south-america, russia, control)"),
    ("unit", "What is counted"),
    ("main_metric", "yes for the series group statistics use (Reddit comments, Bluesky posts)"),
    ("pre_strike_mean", "Mean hourly rate over the pre-strike reference period"),
    ("last_7d_mean", "Mean hourly rate over the last 7 days"),
    ("change_vs_pre_strike", "Last 24 h vs pre-strike mean, as a fraction (-0.25 = 25% lower)"),
    ("change_vs_7d", "Last 3 h vs the same hours on the previous 7 days (median)"),
    ("strike_window_change", "Activity in the 12 h after each strike vs the same weekday-hours 1–3 weeks earlier, averaged over strikes"),
    ("strike_window_p", "Placebo p-value: share of random pre-strike windows with a drop at least as large"),
    ("robust_cells", "Grid cells (of 9: windows 6/12/24 h × start −3/0/+3 h) with a decline of at least 5% at p < 0.05"),
    ("r_vs_infrastructure", "Pearson correlation of daily means with the reference infrastructure series, last 30 days"),
    ("r_days", "Days used for r"),
    ("first_data_utc", "Earliest data point"),
    ("hours_of_data", "Hours with at least one data point since the first"),
]

GROUP_COLUMNS = [
    ("group", "Research tag"),
    ("communities", "Communities in the group (main metric only)"),
    ("median_change_vs_pre_strike", "Median of members' change_vs_pre_strike"),
    ("median_strike_window_change", "Median of members' strike_window_change"),
    ("share_p_below_0_05", "Share of members with strike_window_p < 0.05 (about 0.05 expected by chance)"),
    ("share_robust", "Share of members with a decline of at least 5% at p < 0.05 in at least 5 of 9 grid cells"),
    ("r_vs_infrastructure", "Pearson r of the group's daily median index with the reference infrastructure series"),
    ("r_days", "Days used for r"),
    ("latest_index", "Group's latest daily index, 100 = pre-strike mean"),
]

INFRA_COLUMNS = [
    ("signal", "Network and measurement"),
    ("series", "Series key"),
    ("unit", "What is measured"),
    ("latest", "Latest value"),
    ("latest_utc", "Time of latest value"),
    ("pre_strike_mean", "Mean over the pre-strike reference period"),
    ("change_vs_pre_strike", "Last 3 h vs pre-strike mean"),
    ("strike_window_change", "12 h after each strike vs same weekday-hours 1–3 weeks earlier"),
    ("strike_window_p", "Placebo p-value"),
]


def _iso(ts: int | None) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else ""


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 4) if xs else None


def build(conn: sqlite3.Connection, config: Config, settings: Settings, now: int) -> dict:
    snap = analysis.snapshot(conn, config, now)
    corr = analysis.correlation_view(conn, config, now)
    event_ts = [e.ts for e in config.events if e.ts <= now - analysis.EVENT_WINDOW * 3600]
    hist_start = min(config.reference_start, (min(event_ts) - 6 * 7 * DAY) if event_ts else now)

    communities, infrastructure = [], []
    robust: dict[str, int] = {}
    for s in snap["series"]:
        pts = db.points(conn, s["key"], hist_start, now)
        hours = analysis.hourly(pts)
        ref = [v for h, v in hours.items() if config.reference_start <= h <= config.reference_end]
        ref_mean = round(sum(ref) / len(ref), 4) if len(ref) >= 24 else None
        if s["kind"] == "infrastructure":
            infrastructure.append({
                "signal": s["label"], "series": s["key"], "unit": s["unit"], "latest": s["latest"],
                "latest_utc": _iso(s["latest_ts"]), "pre_strike_mean": ref_mean,
                "change_vs_pre_strike": s["change_ref"], "strike_window_change": s["event_effect"],
                "strike_window_p": s["event_p"],
            })
            continue
        grid = analysis.robustness_grid(hours, event_ts, seed=s["key"]) if event_ts and hours else []
        robust[s["key"]] = analysis.robust_cells(grid) if grid else None
        last7 = [v for h, v in hours.items() if h > now - 7 * DAY]
        first = db.points(conn, s["key"], 0, now)[:1]
        communities.append({
            "community": s["label"], "series": s["key"], "platform": s["platform"], "region": s["region"],
            "groups": "|".join(s["tags"]), "unit": s["unit"], "main_metric": "yes" if s["primary"] else "no",
            "pre_strike_mean": ref_mean,
            "last_7d_mean": round(sum(last7) / len(last7), 4) if last7 else None,
            "change_vs_pre_strike": s["change_ref"], "change_vs_7d": s["change_7d"],
            "strike_window_change": s["event_effect"], "strike_window_p": s["event_p"],
            "robust_cells": robust[s["key"]],
            "r_vs_infrastructure": s["r"], "r_days": s["r_days"],
            "first_data_utc": _iso(first[0][0]) if first else "", "hours_of_data": len(hours),
        })

    tag_order = {t: i for i, t in enumerate(analysis.GROUP_ORDER)}
    communities.sort(key=lambda c: (c["main_metric"] != "yes", tag_order.get(c["groups"].split("|")[0], 9),
                                    c["strike_window_change"] if c["strike_window_change"] is not None else 9))

    corr_by_tag = {g["tag"]: g for g in corr["groups"]}
    groups = []
    for g in snap["groups"]:
        members = [c for c in communities if c["main_metric"] == "yes" and g["tag"] in c["groups"].split("|")]
        with_p = [c for c in members if c["strike_window_p"] is not None]
        with_grid = [c for c in members if c["robust_cells"] is not None]
        cg = corr_by_tag.get(g["tag"], {})
        latest = next((v for v in reversed(cg.get("values", [])) if v is not None), None)
        groups.append({
            "group": g["tag"], "communities": len(members),
            "median_change_vs_pre_strike": g["change_ref"],
            "median_strike_window_change": g["event_effect"],
            "share_p_below_0_05": round(sum(c["strike_window_p"] < 0.05 for c in with_p) / len(with_p), 3) if with_p else None,
            "share_robust": round(sum(c["robust_cells"] >= 5 for c in with_grid) / len(with_grid), 3) if with_grid else None,
            "r_vs_infrastructure": cg.get("r"), "r_days": cg.get("r_days", 0),
            "latest_index": latest,
        })

    return {
        "title": "Bot Traffic Monitor report",
        "report_date": _iso(now)[:10],
        "generated_utc": _iso(now),
        "public_url": settings.public_url,
        "reference_period": {"start_utc": _iso(config.reference_start), "end_utc": _iso(config.reference_end)},
        "reference_infrastructure_series": config.correlation_ref,
        "events": [{**e.__dict__, "time_utc": _iso(e.ts)} for e in config.events],
        "groups": groups,
        "communities": communities,
        "infrastructure": infrastructure,
        "correlation": corr,
        "sources": [r for r in snap["runs"]],
    }


def _write_csv(path: Path, rows: list[dict], columns: list[tuple[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([c for c, _ in columns])
        for row in rows:
            w.writerow(["" if row.get(c) is None else row.get(c) for c, _ in columns])


def _write_daily(conn: sqlite3.Connection, path: Path, start: int, now: int) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date_utc", "series", "kind", "platform", "unit", "groups", "daily_mean"])
        for s in db.list_series(conn, active_only=False):
            for t, v in db.daily_points(conn, s["key"], start, now, analysis.MIN_DAY_HOURS):
                w.writerow([_iso(t)[:10], s["key"], s["kind"], s["platform"], s["unit"], "|".join(s["tags"]), round(v, 4)])


def _readme(report: dict) -> str:
    def table(columns):
        return "\n".join(f"| `{c}` | {d} |" for c, d in columns)

    events = "\n".join(f"- {e['time_utc']}: {e['label']} ({e['status']}). {e['source']}" for e in report["events"])
    cite_url = f", {report['public_url']}" if report["public_url"] else ""
    return f"""# {report['title']}, {report['report_date']}

Generated {report['generated_utc']}. Cite as: *Bot Traffic Monitor, report of {report['report_date']}{cite_url}.*

This bundle records how activity in online communities moved around reported strikes on Yandex
data centres, next to measurements of Yandex's network. It is a snapshot: later reports may revise
numbers as more history is collected, and this one will not change.

## Files

- `groups.csv`: one row per research group, the headline table.
- `communities.csv`: one row per community series.
- `infrastructure.csv`: one row per network signal.
- `daily.csv`: daily mean of every series, for your own analysis. Only days with at least 20 hourly values are listed.
- `report.json`: all of the above plus the correlation chart data.

## Method

- **Pre-strike reference period**: {report['reference_period']['start_utc'][:10]} to {report['reference_period']['end_utc'][:10]}.
- **Strike-window change**: total activity in the 12 hours after each strike, compared with the same weekday and hour one, two and three weeks earlier. Strikes are averaged with equal weight.
- **Placebo p-value**: the same statistic for random start times before the first strike (500 draws). It estimates how often a drop that size happens without a strike. Placebo windows overlap, so treat it as approximate. With many communities, about 5% will show p < 0.05 by chance.
- **Robustness**: the test is repeated for 6, 12 and 24 hour windows, each starting 3 hours early, on time and 3 hours late. `robust_cells` counts how many of the 9 show a decline of at least 5% at p < 0.05.
- **Correlation (r)**: Pearson correlation of daily values with `{report['reference_infrastructure_series']}` (IODA active probing of Yandex Cloud).
- **Groups** are editorial tags. The `control` group is non-political communities: a change that also shows up there is not specific to politics.

Correlation shows that activity moved with Yandex's outage; it does not by itself show why.

## Events

{events}

## Columns

### groups.csv

| Column | Meaning |
|---|---|
{table(GROUP_COLUMNS)}

### communities.csv

| Column | Meaning |
|---|---|
{table(COMMUNITY_COLUMNS)}

### infrastructure.csv

| Column | Meaning |
|---|---|
{table(INFRA_COLUMNS)}

## Sources and licences

- IODA, Georgia Tech Internet Intelligence Lab: Internet outage signals.
- Cloudflare Radar: CC BY-NC 4.0 (non-commercial use only).
- Reddit: activity counts from the Reddit Data API or public feeds, and history from the Arctic Shift archive. Only counts are included: no usernames or content.
- Bluesky: public AppView search, post counts only.
"""


def write(conn: sqlite3.Connection, config: Config, settings: Settings, now: int) -> Path:
    report = build(conn, config, settings, now)
    out = reports_dir(settings) / report["report_date"]
    out.mkdir(parents=True, exist_ok=True)
    start = min(config.reference_start, now - 90 * DAY)

    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    _write_csv(out / "groups.csv", report["groups"], GROUP_COLUMNS)
    _write_csv(out / "communities.csv", report["communities"], COMMUNITY_COLUMNS)
    _write_csv(out / "infrastructure.csv", report["infrastructure"], INFRA_COLUMNS)
    _write_daily(conn, out / "daily.csv", start, now)
    (out / "README.md").write_text(_readme(report), encoding="utf-8")

    bundle = out / f"bot-traffic-report-{report['report_date']}.zip"
    tmp = bundle.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("README.md", "groups.csv", "communities.csv", "infrastructure.csv", "daily.csv", "report.json"):
            z.write(out / name, f"bot-traffic-report-{report['report_date']}/{name}")
    tmp.replace(bundle)
    log.info("report written to %s", out)
    return out


def reports_dir(settings: Settings) -> Path:
    return settings.db_path.parent / "reports"


def list_reports(settings: Settings) -> list[dict]:
    root = reports_dir(settings)
    if not root.exists():
        return []
    out = []
    for d in sorted((p for p in root.iterdir() if p.is_dir() and (p / "report.json").exists()), reverse=True):
        out.append({"date": d.name, "files": sorted(f.name for f in d.iterdir() if f.is_file() and f.suffix != ".tmp")})
    return out


def ensure_today(conn: sqlite3.Connection, config: Config, settings: Settings, now: int) -> Path | None:
    """Build today's report if it does not exist yet."""
    today = _iso(now)[:10]
    if (reports_dir(settings) / today / "report.json").exists():
        return None
    return write(conn, config, settings, now)
