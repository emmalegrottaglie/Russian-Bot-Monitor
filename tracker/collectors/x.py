"""X (Twitter) post volumes for a keyword, via the X API counts endpoints.

Counts only: no posts or accounts are read. Per keyword, four requests give
- original posts per hour (query -is:retweet), the series group statistics use;
- reposts per hour (is:retweet), and the repost share of all posts;
- replies per hour (is:reply);
- posts per minute, summarised per hour as the share of the hour's posts that fell in
  its busiest 5 minutes (8.3% if spread evenly; a weak sign of synchronised bursts).

X's archive has outages: on 2026-09-28 from 15:00 to 24:00 UTC every query counts
zero. So each pass also counts a probe query that matches millions of posts an hour;
an hour where even the probe is zero is a gap in X's data and gets no points at all,
never a zero.

Pay-per-use: $0.005 per recent-counts request, $0.010 per full-archive request (one
request covers up to 31 days, with pagination beyond). The live pass runs at most once
every MIN_INTERVAL and a hard cap, X_MAX_REQUESTS_PER_DAY, stops requests for the rest
of the UTC day. See docs/X-SAMPLING.md.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..config import SeriesSpec
from . import Result, SourceSkipped

RECENT = "https://api.x.com/2/tweets/counts/recent"
ALL = "https://api.x.com/2/tweets/counts/all"
HOUR = 3600
MIN_INTERVAL = 20 * HOUR  # live counts cover 7 days, so once a day is enough
BURST_MINUTES = 5
BURST_MIN_POSTS = 60  # hours quieter than this get no burst value: too few posts to mean anything
log = logging.getLogger(__name__)

PROBE = "(the OR to OR you) lang:en"  # about 2 million posts an hour in October 2026
PARTIAL = 0.1  # probe below this share of its median: X's coverage of that hour looks partial (logged)

# Count queries per keyword, appended to "<query> lang:<lang>".
VARIANTS = {"orig": " -is:retweet", "rt": " is:retweet", "reply": " is:reply"}


def batch_key(spec: SeriesSpec) -> tuple[str, str]:
    """Series that share one set of count requests: the five metrics of a keyword."""
    return spec.params["query"], spec.params["lang"]


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())


def buckets(payload: dict) -> dict[int, int]:
    """{bucket_start: count} from a counts response."""
    if payload.get("errors") and not payload.get("data"):
        raise ValueError(payload["errors"][0].get("message", "error"))
    return {_ts(d["start"]): int(d["tweet_count"]) for d in payload.get("data") or []}


def metrics(orig: dict[int, int], rt: dict[int, int], reply: dict[int, int],
            minutes: dict[int, int], gaps: set[int] = frozenset()) -> dict[str, list[tuple[int, float]]]:
    """Hourly points per metric, stamped at each hour's end. Hours in `gaps` (X had no
    data at all) are left out; otherwise X returns zero buckets explicitly, so a zero
    here is a real zero."""
    out: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for h in sorted(set(orig) - gaps):
        out["posts"].append((h + HOUR, float(orig[h])))
        if h in rt:
            out["reposts"].append((h + HOUR, float(rt[h])))
            total = orig[h] + rt[h]
            if total:
                out["repost-share"].append((h + HOUR, round(100 * rt[h] / total, 2)))
        if h in reply:
            out["replies"].append((h + HOUR, float(reply[h])))
    per_hour: dict[int, list[int]] = defaultdict(list)
    for m, n in minutes.items():
        if m - m % HOUR not in gaps:
            per_hour[m - m % HOUR].append(n)
    for h in sorted(per_hour):
        counts = per_hour[h]
        total = sum(counts)
        if len(counts) == 60 and total >= BURST_MIN_POSTS:  # complete hours only
            top = sum(sorted(counts, reverse=True)[:BURST_MINUTES])
            out["burst"].append((h + HOUR, round(100 * top / total, 2)))
    return dict(out)


_probe_cache: dict[tuple[str, int, int], dict[int, int]] = {}  # one probe per window per process


class _Budget:
    """Requests made per UTC day, kept in a small file next to the database."""

    def __init__(self, path: Path, cap: int):
        self.path, self.cap = path, cap
        try:
            self.state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.state = {}

    def take(self) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        used = self.state.get(day, 0)
        if used >= self.cap:
            raise SourceSkipped(f"daily X request cap reached ({self.cap})")
        self.state = {day: used + 1}
        self.path.write_text(json.dumps(self.state), encoding="utf-8")


async def _counts(client: httpx.AsyncClient, budget: _Budget, token: str, url: str, query: str,
                  start: int, end: int, granularity: str) -> dict[int, int]:
    out: dict[int, int] = {}
    params = {"query": query, "granularity": granularity, "start_time": _iso(start), "end_time": _iso(end)}
    while True:
        budget.take()
        r = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(f"{r.status_code}: {r.text[:200]}", request=r.request, response=r)
        payload = r.json()
        out.update(buckets(payload))
        token_next = (payload.get("meta") or {}).get("next_token")
        if not token_next:
            return out
        params["next_token"] = token_next


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None, end: int | None = None) -> Result:
    if not settings.x_bearer_token:
        raise SourceSkipped("X_BEARER_TOKEN not set")
    budget = _Budget(settings.db_path.parent / "x_usage.json", settings.x_max_requests_per_day)
    # Whole hours only, and X wants end_time at least 10 s in the past.
    stop = min(now - 15, end if end is not None else now) // HOUR * HOUR
    if start is None:
        url, begin = RECENT, stop - 7 * 24 * HOUR + HOUR  # the recent window is 7 days
    else:
        url, begin = ALL, start // HOUR * HOUR
    groups: dict[tuple[str, str], list[SeriesSpec]] = defaultdict(list)
    for s in specs:
        groups[batch_key(s)].append(s)
    result = Result()
    try:
        if (url, begin, stop) not in _probe_cache:  # a backfill calls collect once per keyword
            _probe_cache[(url, begin, stop)] = await _counts(client, budget, settings.x_bearer_token, url, PROBE, begin, stop, "hour")
        probe = _probe_cache[(url, begin, stop)]
    except SourceSkipped as e:
        result.errors.append(str(e))
        return result
    except (httpx.HTTPError, ValueError) as e:
        result.errors.append(f"X probe: {e}")  # without it, gaps can't be told from zeros
        return result
    gaps = {h for h, n in probe.items() if n == 0}
    if gaps:
        result.errors.append(f"X has no data for {len(gaps)} hours ({_iso(min(gaps))} to {_iso(max(gaps) + HOUR)}): left as gaps")
    if probe:
        typical = sorted(probe.values())[len(probe) // 2]
        thin = sorted(h for h, n in probe.items() if 0 < n < PARTIAL * typical)
        if thin:
            log.warning("X coverage looks partial in %d hours: %s", len(thin), ", ".join(_iso(h) for h in thin[:10]))
    for (query, lang), group in groups.items():
        base = f"{query} lang:{lang}" if lang else query
        try:
            got = {k: await _counts(client, budget, settings.x_bearer_token, url, base + v, begin, stop, "hour")
                   for k, v in VARIANTS.items()}
            minutes = await _counts(client, budget, settings.x_bearer_token, url, base, begin, stop, "minute")
        except SourceSkipped as e:
            result.errors.append(str(e))
            break
        except (httpx.HTTPError, ValueError) as e:
            result.errors.append(f"X {base!r}: {e}")
            continue
        by_metric = metrics(got["orig"], got["rt"], got["reply"], minutes, gaps)
        for s in group:
            pts = by_metric.get(s.params["metric"])
            if pts:
                result.points[s.key] = pts
            else:
                result.errors.append(f"{s.key}: no data returned")
    return result
