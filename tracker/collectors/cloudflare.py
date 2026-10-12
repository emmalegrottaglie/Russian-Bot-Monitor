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
        out.append((ts, float(v)))
    return out


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None) -> Result:
    if not settings.cloudflare_token:
        raise SourceSkipped("CLOUDFLARE_API_TOKEN not set")
    result = Result()
    headers = {"Authorization": f"Bearer {settings.cloudflare_token}"}
    for s in specs:
        params = {"asn": s.params["asn"], "aggInterval": "1h", "format": "json"}
        if start is None:
            params["dateRange"] = "2d"
        else:
            params["dateStart"] = _iso(start)
            params["dateEnd"] = _iso(now)
        try:
            r = await client.get(URL, params=params, headers=headers)
            r.raise_for_status()
            result.points[s.key] = parse(r.json())
        except (httpx.HTTPError, ValueError) as e:
            result.errors.append(f"{s.key}: {e}")
    return result
