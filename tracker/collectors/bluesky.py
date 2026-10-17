"""Bluesky post rate for a keyword, via the public AppView search endpoint.

Uses indexedAt (when Bluesky saw the post) rather than createdAt, which clients
can backdate.

History: the search takes `since`/`until`, but without a login it returns only the
first page (100 posts) of any window. So history is read one hour at a time: an
hour with fewer than 100 posts is counted exactly; a busier hour is extrapolated
from the span its newest 100 posts cover, the same method the live collector uses.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from ..config import SeriesSpec
from ..rates import hourly_rate
from . import Result
from .arctic_shift import fill_quiet_hours

URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
DELAY = 1.0
HISTORY_DELAY = 0.4  # seconds between hourly history requests
LIMIT = 100
RETRIES = (5, 30, 90)  # back-off, seconds, when a history request fails
HOUR = 3600
log = logging.getLogger(__name__)


def parse(payload: dict) -> list[float]:
    out = []
    for post in payload.get("posts") or []:
        stamp = post.get("indexedAt")
        if stamp:
            out.append(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())
    return out


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None) -> Result:
    if start is not None:
        return await history(client, specs, now, start)
    result = Result()
    for i, s in enumerate(specs):
        if i:
            await asyncio.sleep(DELAY)
        params = {"q": s.params["query"], "sort": "latest", "limit": 100}
        if s.params["lang"]:
            params["lang"] = s.params["lang"]
        try:
            r = await client.get(URL, params=params)
            r.raise_for_status()
            rate = hourly_rate(parse(r.json()), now)
        except (httpx.HTTPError, ValueError) as e:
            result.errors.append(f"{s.key}: {e}")
            continue
        if rate is not None:
            result.points[s.key] = [(now, round(rate, 2))]
    return result


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hour_rate(stamps: list[float], hour_end: int, limit: int = LIMIT) -> float:
    """Posts in the hour ending at `hour_end`, from one page of that hour's search."""
    if len(stamps) < limit:
        return float(len(stamps))  # the page holds every post of the hour
    return hourly_rate(stamps, hour_end) or 0.0


async def history(client: httpx.AsyncClient, specs: list[SeriesSpec], now: int, start: int) -> Result:
    """Hourly rates from `start` to the last full hour, one request per hour.

    A window that keeps failing is a gap, never a zero. Hours with no posts are
    zero only on UTC days that have some data (as for the Reddit archive)."""
    result = Result()
    begin, end = start // HOUR * HOUR, now // HOUR * HOUR
    for s in specs:
        pts, gaps = [], []
        for h in range(begin, end, HOUR):
            params = {"q": s.params["query"], "sort": "latest", "limit": LIMIT, "since": _iso(h), "until": _iso(h + HOUR)}
            if s.params["lang"]:
                params["lang"] = s.params["lang"]
            for wait in (*RETRIES, None):
                try:
                    r = await client.get(URL, params=params)
                    r.raise_for_status()
                    stamps = parse(r.json())
                    break
                except (httpx.HTTPError, ValueError) as e:
                    if wait is None:
                        log.warning("%s: %s to %s failed, left as a gap: %s", s.key, _iso(h), _iso(h + HOUR), e)
                        stamps = None
                        break
                    await asyncio.sleep(wait)
            if stamps is None:
                gaps.append((h, h + HOUR))
            elif stamps:
                pts.append((h + HOUR, round(hour_rate(stamps, h + HOUR), 2)))
            await asyncio.sleep(HISTORY_DELAY)
        for a, b in gaps:
            result.errors.append(f"{s.key}: no data {_iso(a)} to {_iso(b)}")
        if pts:
            result.points[s.key] = fill_quiet_hours(pts, end, gaps, begin=begin)
        log.info("%s: %d hourly points, %d gaps", s.key, len(result.points.get(s.key, [])), len(gaps))
    return result
