"""Collector registry and the collection pass.

Each collector module exposes
    async collect(client, specs, settings, now, start=None) -> Result
`start` is None for a live pass and a unix timestamp for a backfill.
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
    from . import arctic_shift, bluesky, cloudflare, ioda, reddit
    return {"ioda": ioda, "cloudflare": cloudflare, "reddit": reddit, "bluesky": bluesky,
            "arctic_shift": arctic_shift}


LIVE = ("ioda", "cloudflare", "reddit", "bluesky")
# Which collector backfills each platform's series.
BACKFILL = {"ioda": "ioda", "cloudflare": "cloudflare", "reddit": "arctic_shift"}


async def run(config: Config, settings: Settings, platforms=LIVE, start: int | None = None,
              backfill: bool = False) -> dict[str, Result]:
    """One pass over the given platforms. Writes points and a run record per platform."""
    modules = _modules()
    now = int(time.time())
    results: dict[str, Result] = {}
    async with httpx.AsyncClient(timeout=45, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for platform in platforms:
            specs = config.by_platform(platform)
            if not specs:
                continue
            name = BACKFILL.get(platform, platform) if backfill else platform
            if backfill and platform not in BACKFILL:
                continue
            # Backfills are long: write each series as it finishes so an interruption keeps progress.
            batches = [[s] for s in specs] if backfill else [specs]
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
                with db.session(settings.db_path) as conn:
                    for key, pts in part.points.items():
                        n += db.upsert_points(conn, key, pts)
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
