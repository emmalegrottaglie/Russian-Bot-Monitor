"""Historical Reddit counts from the Arctic Shift archive, for backfill only.

https://arctic-shift.photon-reddit.com — the aggregate endpoint returns hourly
counts. Busy subreddits can time out on long ranges, so ranges are split and
halved on failure. The archive lags live Reddit, so the most recent two days are
left to the live collector.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from ..config import SeriesSpec
from . import Result

BASE = "https://arctic-shift.photon-reddit.com/api/{kind}/search/aggregate"
log = logging.getLogger(__name__)
KINDS = {"comments": "comments", "posts": "posts"}
LAG = 2 * 86400
MIN_CHUNK = 6 * 3600
DELAY = 2.0
COOLDOWNS = (30, 90, 180)  # seconds to back off when even the smallest chunk fails


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(payload: dict, after: int | None = None, before: int | None = None,
          shift_hint: int = 0) -> tuple[list[tuple[int, float]], int]:
    """Returns ([(hour_end_ts, count)], shift).

    The archive buckets hours in a local timezone and labels them early by that
    offset (2 h in summer 2026): asking for after=00:00Z returns a first bucket
    labelled 22:00Z. A label earlier than `after` reveals the shift; when the first
    hours are empty it cannot be seen, so the last known shift is reused."""
    if payload.get("error"):
        raise ValueError(payload["error"])
    rows = [(int(datetime.fromisoformat(r["created_utc"].replace("Z", "+00:00")).timestamp()), float(r["count"]))
            for r in payload.get("data") or []]
    shift = shift_hint
    if rows and after is not None and rows[0][0] < after:
        shift = round((after - min(t for t, _ in rows)) / 3600) * 3600
    out = []
    for label, count in rows:
        start = label + shift
        if after is not None and start < after or before is not None and start >= before:
            continue
        # A count for [h, h+1h) is the rate for the hour ending at h+1h, matching live points.
        out.append((start + 3600, count))
    return out, shift


async def _range(client: httpx.AsyncClient, subreddit: str, metric: str, start: int, end: int,
                 chunk: int) -> list[tuple[int, float]]:
    """Walk [start, end) in chunks. On failure halve the chunk and keep the smaller
    size for the rest of the range: a busy subreddit stays busy."""
    out: list[tuple[int, float]] = []
    shift = 0
    strikes = 0
    t = start
    while t < end:
        until = min(t + chunk, end)
        params = {"aggregate": "created_utc", "frequency": "hour", "subreddit": subreddit,
                  "after": _iso(t), "before": _iso(until)}
        try:
            r = await client.get(BASE.format(kind=KINDS[metric]), params=params, timeout=90)
            r.raise_for_status()  # 422 = archive query timed out: halve and retry
            pts, shift = parse(r.json(), t, until, shift)
            out.extend(pts)
        except (httpx.HTTPError, ValueError) as e:
            if chunk <= MIN_CHUNK:
                # Small requests failing means the archive is asking us to slow down.
                if strikes >= len(COOLDOWNS):
                    raise
                log.info("r/%s %s: %s; backing off %d s", subreddit, metric, e, COOLDOWNS[strikes])
                await asyncio.sleep(COOLDOWNS[strikes])
                strikes += 1
                continue
            chunk = max(MIN_CHUNK, chunk // 2 // 3600 * 3600)  # whole hours keep the label shift detectable
            log.debug("r/%s %s: %s, retrying with %d h chunks", subreddit, metric, e, chunk // 3600)
            await asyncio.sleep(DELAY)
            continue
        t = until
        strikes = 0
        await asyncio.sleep(DELAY)
    return out


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None) -> Result:
    result = Result()
    end = (now - LAG) // 3600 * 3600
    begin = (start if start is not None else end - 7 * 86400) // 3600 * 3600
    for s in specs:
        try:
            pts = await _range(client, s.params["subreddit"], s.params["metric"], begin, end, 7 * 86400)
        except (httpx.HTTPError, ValueError) as e:
            log.warning("%s: gave up: %s", s.key, e)
            result.errors.append(f"{s.key}: {e}")
            continue
        result.points[s.key] = fill_quiet_hours(pts, end)
        log.info("%s: %d hourly points", s.key, len(result.points[s.key]))
    return result


def fill_quiet_hours(pts: list[tuple[int, float]], end: int) -> list[tuple[int, float]]:
    """Hours with no activity are absent from the aggregate. Fill them with zero, but
    only on UTC days that have some data: a whole missing day is more likely an
    archive gap than a silent community, and must stay a gap rather than a fake zero."""
    have = dict(pts)
    days = {(ts - 1) // 86400 for ts in have}
    out = []
    for day in sorted(days):
        for h in range(day * 86400 + 3600, day * 86400 + 86400 + 1, 3600):
            if h <= end:
                out.append((h, have.get(h, 0.0)))
    return out
