"""Bluesky post rate for a keyword, via the public AppView search endpoint.

Uses indexedAt (when Bluesky saw the post) rather than createdAt, which clients
can backdate.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from ..config import SeriesSpec
from ..rates import hourly_rate
from . import Result

URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
DELAY = 1.0


def parse(payload: dict) -> list[float]:
    out = []
    for post in payload.get("posts") or []:
        stamp = post.get("indexedAt")
        if stamp:
            out.append(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())
    return out


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None) -> Result:
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
