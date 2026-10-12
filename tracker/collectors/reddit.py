"""Reddit comment and post rates per subreddit.

With REDDIT_CLIENT_ID/SECRET set, uses the OAuth Data API (application-only
grant). Without them, falls back to the public Atom feeds, which work from
residential IPs but are often refused from datacentre ranges. Only timestamps are
read; no usernames or content are stored.
"""

from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from ..config import SeriesSpec
from ..rates import hourly_rate
from . import Result

ATOM = "{http://www.w3.org/2005/Atom}"
PATHS = {"comments": "comments", "posts": "new"}
# Seconds between requests. OAuth allows ~100 requests/min; the public feeds are
# throttled much harder, so the fallback goes slowly (about 10 requests/min).
DELAY_OAUTH = 1.0
DELAY_FEED = 6.0
RETRY_AFTER_MAX = 120
REQUEST_TIMEOUT = 20      # seconds; a throttled feed can stall instead of refusing
MAX_FAILURES = 3          # consecutive failures before giving up on this pass
PASS_BUDGET = 10 * 60     # seconds; leave room before the next 15-minute pass

_token: dict = {"value": "", "expires": 0.0}


def parse_atom(text: str) -> list[float]:
    # Feeds never need a DTD; refusing one rules out entity-expansion tricks.
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise ValueError("feed contains a DTD")
    root = ET.fromstring(text)
    out = []
    for entry in root.iter(f"{ATOM}entry"):
        node = entry.find(f"{ATOM}published")
        if node is None:
            node = entry.find(f"{ATOM}updated")
        if node is not None and node.text:
            out.append(datetime.fromisoformat(node.text.replace("Z", "+00:00")).timestamp())
    return out


def parse_listing(payload: dict) -> list[float]:
    return [float(c["data"]["created_utc"]) for c in payload.get("data", {}).get("children", [])]


async def _oauth_token(client: httpx.AsyncClient, settings) -> str:
    if _token["value"] and _token["expires"] > time.time() + 60:
        return _token["value"]
    r = await client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(settings.reddit_client_id, settings.reddit_client_secret),
        headers={"User-Agent": settings.reddit_user_agent},
    )
    r.raise_for_status()
    body = r.json()
    _token.update(value=body["access_token"], expires=time.time() + float(body.get("expires_in", 3600)))
    return _token["value"]


async def fetch_timestamps(client: httpx.AsyncClient, settings, subreddit: str, metric: str) -> list[float]:
    path = PATHS[metric]
    headers = {"User-Agent": settings.reddit_user_agent}
    if settings.reddit_client_id and settings.reddit_client_secret:
        headers["Authorization"] = f"Bearer {await _oauth_token(client, settings)}"
        r = await client.get(f"https://oauth.reddit.com/r/{subreddit}/{path}", params={"limit": 100, "raw_json": 1},
                             headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return parse_listing(r.json())
    r = await client.get(f"https://www.reddit.com/r/{subreddit}/{path}/.rss", params={"limit": 100}, headers=headers,
                         timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return parse_atom(r.text)


async def _get_with_retry(client: httpx.AsyncClient, settings, subreddit: str, metric: str) -> list[float]:
    """One retry after a 429, honouring Retry-After (capped)."""
    try:
        return await fetch_timestamps(client, settings, subreddit, metric)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 429:
            raise
        wait = e.response.headers.get("Retry-After", "60")
        await asyncio.sleep(min(float(wait) if wait.replace(".", "", 1).isdigit() else 60.0, RETRY_AFTER_MAX))
        return await fetch_timestamps(client, settings, subreddit, metric)


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None) -> Result:
    result = Result()
    oauth = bool(settings.reddit_client_id and settings.reddit_client_secret)
    delay = DELAY_OAUTH if oauth else DELAY_FEED
    if not oauth:
        # The public feeds allow roughly one request a minute: spend them on comments,
        # the main metric. Post rates resume once OAuth keys are configured.
        specs = [s for s in specs if s.params["metric"] == "comments"]
    started, failures = time.monotonic(), 0
    for i, s in enumerate(specs):
        if time.monotonic() - started > PASS_BUDGET:
            result.errors.append(f"stopped: pass took over {PASS_BUDGET // 60} min, {len(specs) - i} series skipped")
            break
        if i:
            await asyncio.sleep(delay)
        try:
            stamps = await _get_with_retry(client, settings, s.params["subreddit"], s.params["metric"])
        except (httpx.HTTPError, ET.ParseError, KeyError, ValueError) as e:
            result.errors.append(f"{s.key}: {type(e).__name__}: {e}")
            failures += 1
            blocked = isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403, 429)
            if blocked or failures >= MAX_FAILURES:
                result.errors.append(f"stopped after {failures} consecutive failure(s)")
                break
            continue
        failures = 0
        rate = hourly_rate(stamps, int(time.time()))
        if rate is not None:
            result.points[s.key] = [(int(time.time()), round(rate, 2))]
    return result
