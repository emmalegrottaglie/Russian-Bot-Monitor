"""Pausing collection between developments, and resuming it on its own.

Emma, 29 October 2026: with no news on the Yandex data centres, collection stops until
Yandex Cloud recovers or something major happens. While paused:

- the 30-minute collect-and-publish task and the daily catch-up are disabled;
- `tracker watch`, run once a day, reloads the last days of IODA and Cloudflare Radar
  (free), republishes the site so the Yandex chart stays current, and resumes
  collection once Yandex Cloud has been at RESUME_LEVEL of its pre-strike level for
  RESUME_DAYS complete UTC days in a row;
- a daily news check (a scheduled Claude task) can also resume it after a major event.

Resuming re-enables the tasks and fills the gap from history: Reddit (Arctic Shift),
Bluesky, IODA and Cloudflare for free, Twitter from its full archive (about 113
requests, roughly $1.13, approved by Emma on 29 October 2026). Nothing is invented for
the paused period: what history cannot supply stays a gap.

The pause is a small JSON file next to the database. Its absence means collecting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, collectors, db
from .config import Config, Settings

log = logging.getLogger(__name__)
DAY = 86400
RESUME_LEVEL = 50.0  # % of the pre-strike mean, Yandex Cloud reachability (daily index)
RESUME_DAYS = 2
WATCH_DAYS = 3  # IODA and Cloudflare history reloaded by each watch
GAP_MARGIN_DAYS = 2  # the Reddit archive runs about 2 days behind; reload a little before the pause
TASKS = ("BotTrafficMonitor", "BotTrafficMonitorCatchUp")  # Windows Task Scheduler, see docs/HOSTING.md


def path(settings: Settings) -> Path:
    return settings.db_path.parent / "pause.json"


def state(settings: Settings) -> dict | None:
    """The pause record ({"since", "reason", "resume_level", "resume_days"}) or None."""
    try:
        return json.loads(path(settings).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _set_tasks(enabled: bool) -> list[str]:
    """Enable or disable the collection tasks. Returns the tasks that could not be changed
    (none on a machine without them, such as a server running `tracker serve`)."""
    if sys.platform != "win32":
        return []
    failed = []
    for name in TASKS:
        r = subprocess.run(["schtasks", "/Change", "/TN", name, "/ENABLE" if enabled else "/DISABLE"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            failed.append(name)
            log.warning("could not %s task %s: %s", "enable" if enabled else "disable", name, r.stderr.strip())
    return failed


def pause(settings: Settings, reason: str, now: int | None = None) -> dict:
    record = {"since": now or int(time.time()), "reason": reason,
              "resume_level": RESUME_LEVEL, "resume_days": RESUME_DAYS}
    path(settings).write_text(json.dumps(record), encoding="utf-8")
    _set_tasks(False)
    log.info("collection paused: %s", reason)
    return record


def recovery(conn, config: Config, now: int, days: int = RESUME_DAYS) -> list[tuple[int, float]]:
    """Yandex Cloud's daily index (100 = pre-strike mean) for the last `days` complete UTC
    days, oldest first. A day without enough data is missing from the list."""
    today = now - now % DAY
    idx = analysis.daily_index(conn, config, config.correlation_ref, today - days * DAY, now)
    return [(d, idx[d]) for d in range(today - days * DAY, today, DAY) if d in idx]


def should_resume(levels: list[tuple[int, float]], days: int = RESUME_DAYS, level: float = RESUME_LEVEL) -> bool:
    """Every one of the last `days` complete days has a value, and each is at `level` or above.
    A missing day never counts as recovered."""
    return len(levels) == days and all(v >= level for _, v in levels)


def resume(config: Config, settings: Settings, reason: str, now: int | None = None) -> None:
    """Re-enable collection, record why, and fill the paused period from history."""
    now = now or int(time.time())
    record = state(settings)
    since = record["since"] if record else now
    failed = _set_tasks(True)
    path(settings).unlink(missing_ok=True)
    stamp = datetime.fromtimestamp(since, timezone.utc).strftime("%d %b %Y")
    text = f"BOT TRAFFIC MONITOR · Collection resumed after a pause since {stamp}: {reason}"
    with db.session(settings.db_path) as conn:
        db.add_alert(conn, now, text, [{"key": "collection", "label": "collection resumed", "change": None,
                                        "direction": "up"}])
        conn.commit()
    log.info("collection resumed: %s%s", reason, f" (tasks not re-enabled: {', '.join(failed)})" if failed else "")
    fill_gap(config, settings, since - GAP_MARGIN_DAYS * DAY)


def fill_gap(config: Config, settings: Settings, start: int) -> None:
    """Load history from `start` to now for every platform. Twitter's full-archive counts
    cover up to 31 days per request, so one request per query and metric; the live pass is
    then held off for a day (a recorded run), since both together would pass the daily cap."""
    asyncio.run(collectors.run(config, settings, platforms=("ioda", "cloudflare", "bluesky", "reddit"),
                               start=start, backfill=True))
    got = asyncio.run(collectors.run(config, settings, platforms=("x",), start=start, backfill=True)).get("x")
    if got is not None:
        errors = "; ".join(got.errors)
        with db.session(settings.db_path) as conn:
            db.record_run(conn, "x", bool(got.points), sum(len(p) for p in got.points.values()),
                          f"gap fill after pause: {errors}"[:2000] if errors else None)


def watch(config: Config, settings: Settings, now: int | None = None) -> str:
    """The daily check while paused. Returns what it did."""
    if state(settings) is None:
        return "not paused"
    now = now or int(time.time())
    asyncio.run(collectors.run(config, settings, platforms=("ioda", "cloudflare"),
                               start=now - WATCH_DAYS * DAY, backfill=True))
    with db.session(settings.db_path) as conn:
        levels = recovery(conn, config, now)
    shown = ", ".join(f"{datetime.fromtimestamp(d, timezone.utc):%d %b} {v:.0f}%" for d, v in levels) or "no complete days"
    if should_resume(levels):
        resume(config, settings, f"Yandex Cloud reachability back to {RESUME_LEVEL:.0f}% or more of its "
                                 f"pre-strike level for {RESUME_DAYS} days ({shown})", now)
        return f"resumed: {shown}"
    return f"still paused: Yandex Cloud {shown} (resumes at {RESUME_LEVEL:.0f}% for {RESUME_DAYS} days)"
