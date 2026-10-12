"""IODA (Georgia Tech) raw outage signals per ASN. No key required.

https://api.ioda.inetintel.cc.gatech.edu/v2/ — values are native-resolution
samples (BGP and telescope every 5 min, active probing every 10 min) stored at
the start of each bin.
"""

from __future__ import annotations

from collections import defaultdict

import httpx

from ..config import SeriesSpec
from . import Result

BASE = "https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/asn/{asn}"
LIVE_WINDOW = 6 * 3600
CHUNK = 7 * 86400


def parse(payload: dict, signals: set[str]) -> dict[str, list[tuple[int, float]]]:
    out: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for group in payload.get("data") or []:
        for s in group:
            ds = s.get("datasource")
            if ds not in signals or s.get("subtype"):
                continue
            start, step = int(s["from"]), int(s["step"])
            for i, v in enumerate(s.get("values") or []):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out[ds].append((start + i * step, float(v)))
    return dict(out)


async def fetch(client: httpx.AsyncClient, asn: int, start: int, end: int, signals: set[str]) -> dict:
    out: dict[str, list[tuple[int, float]]] = defaultdict(list)
    t = start
    while t < end:
        until = min(t + CHUNK, end)
        r = await client.get(BASE.format(asn=asn), params={"from": t, "until": until})
        r.raise_for_status()
        for ds, pts in parse(r.json(), signals).items():
            out[ds].extend(pts)
        t = until
    return out


async def collect(client: httpx.AsyncClient, specs: list[SeriesSpec], settings, now: int,
                  start: int | None = None) -> Result:
    by_asn: dict[int, list[SeriesSpec]] = defaultdict(list)
    for s in specs:
        by_asn[s.params["asn"]].append(s)
    result = Result()
    for asn, group in by_asn.items():
        signals = {s.params["signal"] for s in group}
        try:
            data = await fetch(client, asn, start if start is not None else now - LIVE_WINDOW, now, signals)
        except httpx.HTTPError as e:
            result.errors.append(f"AS{asn}: {e}")
            continue
        for s in group:
            pts = data.get(s.params["signal"], [])
            if pts:
                result.points[s.key] = pts
            else:
                result.errors.append(f"{s.key}: no data returned")
    return result
