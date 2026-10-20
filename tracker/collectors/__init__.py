"""Collector registry and the collection pass.

Each collector module exposes
    async collect(client, specs, settings, now, start=None, end=None) -> Result
`start` is None for a live pass and a unix timestamp for a backfill. A backfill
loads history from `start` up to `end` (default: as recent as the source allows).

A module that sets HOURLY_HISTORY = True returns history as exact hourly values,
which supersede any live sample taken inside the same hour (db.replace_hours).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from .. import db
from ..config import Config, Settings

log = logging.getLogger(__name__)
USER_AGENT = "bot-traffic-monitor/0.1 (research; read-only)"


class SourceSkipped(Exception):
    """The source is not configured (e.g. missing API key)."""


@dataclass
class Result:
    points: dict[str, list[tuple[int, float]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _modules() -> dict:
    from . import arctic_shift, bluesky, cloudflare, ioda, reddit, x
    return {"ioda": ioda, "cloudflare": cloudflare, "reddit": reddit, "bluesky": bluesky,
            "arctic_shift": arctic_shift, "x": x}


LIVE = ("ioda", "cloudflare", "reddit", "bluesky", "x")
# Which collector backfills each platform's series.
BACKFILL = {"ioda": "ioda", "cloudflare": "cloudflare", "reddit": "arctic_shift", "bluesky": "bluesky", "x": "x"}


async def run(config: Config, settings: Settings, platforms=LIVE, start: int | None = None,
              backfill: bool = False) -> dict[str, Result]:
    """One pass over the given platforms. Writes points and a run record per platform."""
    modules = _modules()
    now = int(time.time())
    results: dict[str, Result] = {}
    async with httpx.AsyncClient(timeout=45, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for platform in platforms:
            specs = config.by_platform(platform)
            if not backfill:  # archive-only series are filled by the daily catch-up
                specs = [s for s in specs if not s.params.get("archive_only")]
            if not specs:
                continue
            name = BACKFILL.get(platform, platform) if backfill else platform
            if backfill and platform not in BACKFILL:
                continue
            interval = getattr(modules[name], "MIN_INTERVAL", 0)
            if not backfill and interval:
                # Sources billed per request run less often than the pass (see the module).
                with db.session(settings.db_path) as conn:
                    last_ok = db.last_ok_run(conn, platform)
                if last_ok and now - last_ok < interval:
                    continue
            if not backfill:
                # Stalest series first: when a throttled source only gets partway through
                # a pass, the next pass picks up where it stopped.
                with db.session(settings.db_path) as conn:
                    last = {s.key: (db.latest_point(conn, s.key) or (0, 0))[0] for s in specs}
                specs = sorted(specs, key=lambda s: last[s.key])
            # Backfills are long: write each series as it finishes so an interruption keeps progress.
            batches = [[s] for s in specs] if backfill else [specs]
            key = getattr(modules[name], "batch_key", None)
            if backfill and key:  # series that share requests are fetched together
                grouped: dict = {}
                for s in specs:
                    grouped.setdefault(key(s), []).append(s)
                batches = list(grouped.values())
            result, n = Result(), 0
            for batch in batches:
                try:
                    part = await modules[name].collect(client, batch, settings, now, start=start)
                except SourceSkipped as e:
                    log.info("%s skipped: %s", platform, e)
                    if not backfill:
                        with db.session(settings.db_path) as conn:
                            db.record_run(conn, platform, False, 0, f"not configured: {e}")
                    break
                except Exception as e:  # one broken source must not stop the others
                    log.exception("%s failed", platform)
                    part = Result(errors=[f"{type(e).__name__}: {e}"])
                write = db.replace_hours if backfill and getattr(modules[name], "HOURLY_HISTORY", False) else db.upsert_points
                with db.session(settings.db_path) as conn:
                    for key, pts in part.points.items():
                        n += write(conn, key, pts)
                result.points.update(part.points)
                result.errors.extend(part.errors)
            else:
                if not backfill:
                    with db.session(settings.db_path) as conn:
                        db.record_run(conn, platform, bool(result.points), n,
                                      "; ".join(result.errors)[:2000] or None)
                for err in result.errors:
                    log.warning("%s: %s", platform, err)
                log.info("%s: %d points, %d errors", platform, n, len(result.errors))
                results[platform] = result
    return results


async def refetch(config: Config, settings: Settings, windows: dict[str, tuple[int, int]]) -> dict[str, str]:
    """Collect each series' window (start, end] again from its history source and replace
    the stored points of that window with the result. A series is replaced only when its
    window came back complete (no errors); otherwise it is left untouched and reported.
    Returns {key: outcome}."""
    modules = _modules()
    specs = {s.key: s for s in config.series}
    now = int(time.time())
    outcome: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=45, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for key, (start, end) in windows.items():
            spec = specs[key]
            module = modules[BACKFILL[spec.platform]]
            try:
                part = await module.collect(client, [spec], settings, now, start=start, end=end)
            except Exception as e:
                part = Result(errors=[f"{type(e).__name__}: {e}"])
            if part.errors or not part.points.get(key):
                outcome[key] = "kept old points: " + ("; ".join(part.errors)[:300] or "no data returned")
            else:
                # Replace only as far as the source reached: the Reddit archive, for one,
                # stops two days short of now, and live points after that must stay.
                pts = part.points[key]
                end = min(end, max(t for t, _ in pts))
                with db.session(settings.db_path) as conn:
                    old = len(db.points(conn, key, start + 1, end))
                    n = db.replace_range(conn, key, start, end, pts)
                outcome[key] = f"replaced {old} points with {n}"
            log.info("%s: %s", key, outcome[key])
    return outcome
