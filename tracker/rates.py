"""Turn a feed of item timestamps into an activity rate (items per hour).

Feeds return the newest N items. If they reach back past the window we count
exactly; if all N items fall inside the window (a busy community) we extrapolate
from the span they cover.
"""

from __future__ import annotations

from typing import Iterable

MIN_SPAN = 60  # seconds; below this an extrapolated rate is noise


def hourly_rate(timestamps: Iterable[float], now: float, window: int = 3600) -> float | None:
    ts = sorted(t for t in timestamps if t <= now)
    if not ts:
        return None
    start = now - window
    if ts[0] <= start:
        return sum(1 for t in ts if t > start) * 3600 / window
    span = max(now - ts[0], MIN_SPAN)
    return len(ts) * 3600 / span
