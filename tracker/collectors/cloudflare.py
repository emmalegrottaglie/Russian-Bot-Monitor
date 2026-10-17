"""Cloudflare Radar: share of HTTP requests from bots, originating in an ASN.

Needs CLOUDFLARE_API_TOKEN (custom token, Account > Radar > Read). Radar data is
licensed CC BY-NC 4.0. Note: for AS13238 this includes Yandex's own search
crawlers, so it measures automated traffic from the network, not bot farms.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..config import SeriesSpec
from . import Result, SourceSkipped

URL = "https://api.cloudflare.com/client/v4/radar/http/timeseries_groups/BOT_CLASS"
BOT_KEYS = ("bot", "likely_automated")

INTERVAL = 3600  # aggInterval=1h
# Radar refuses hourly data for long ranges (a month works, 50 days does not), so
# history is requested a week at a time.
CHUNK = 7 * 86400


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(payload: dict) -> list[tuple[int, float]]:
    serie = (payload.get("result") or {}).get("serie_0") or {}
    stamps = serie.get("timestamps") or []
    values = next((v for k, v in serie.items() if k.lower() in BOT_KEYS), None)
    if values is None:
        raise ValueError(f"no bot class in response keys {sorted(serie)}")
    out = []
    for stamp, v in zip(stamps, values):
        ts = int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())
        out.append((ts + INTERVAL, float(v)))  # Radar labels a bucket by its start; stamp its end
    return out


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None, end: int | None = None) -> Result:
    if not settings.cloudflare_token:
        raise SourceSkipped("CLOUDFLARE_API_TOKEN not set")
    result = Result()
    headers = {"Authorization": f"Bearer {settings.cloudflare_token}"}
    until = min(now, end) if end is not None else now
    for s in specs:
        base = {"asn": s.params["asn"], "aggInterval": "1h", "format": "json"}  # matches INTERVAL
        if start is None:
            windows = [{"dateRange": "2d"}]
        else:
            windows = [{"dateStart": _iso(t), "dateEnd": _iso(min(t + CHUNK, until))} for t in range(start, until, CHUNK)]
        pts: dict[int, float] = {}
        for w in windows:
            try:
                r = await client.get(URL, params=base | w, headers=headers)
                r.raise_for_status()
                pts.update(parse(r.json()))
            except (httpx.HTTPError, ValueError) as e:
                # One refused window is a gap in the history, not the end of it.
                result.errors.append(f"{s.key} {w}: {e}")
        if pts:
            result.points[s.key] = sorted(pts.items())
    return result
