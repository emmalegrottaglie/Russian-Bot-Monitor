"""Baselines, percentage changes, correlations and the dashboard snapshot.

Definitions (also shown on the site's ABOUT tab):
- change_7d:  activity in the last few hours vs the median of the same hours of
              day over the previous 7 days. Tracks sudden fluctuation.
- change_ref: mean over a recent window vs mean over the configured pre-strike
              reference period. Tracks the longer shift.
- r:          Pearson correlation of daily means against the reference signal.
- event study: activity in the WINDOW hours after each event vs the same weekday
              and hour 1, 2 and 3 weeks earlier, averaged over events with equal
              weight. Its p-value comes from a placebo test: the same statistic
              computed for random start times before the first event, so it
              answers "how often does a drop this size happen with no strike?".
"""

from __future__ import annotations

import math
import random
import sqlite3
import statistics
from collections import defaultdict

from . import db
from .config import Config

HOUR, DAY = 3600, 86400
# Hours in the "current" window: infrastructure moves in steps, community activity
# has a strong daily cycle, so it is averaged over a full day for change_ref.
CURRENT_HOURS = {"infrastructure": 3, "community": 24}
FRESH = 3 * HOUR  # a series with no point this recent counts as stale
FRESH_BY_PLATFORM = {"x": 26 * HOUR}  # X counts are fetched once a day


MIN_DAY_HOURS = 20  # a day needs this many hourly values before it gets a daily mean


def hourly(points: list[tuple[int, float]]) -> dict[int, float]:
    """Hourly means, keyed by the hour's start. Every collector stamps a point at the
    END of the period it measures, so a point stamped 13:00 belongs to 12:00-13:00."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for ts, v in points:
        buckets[(ts - 1) // HOUR * HOUR].append(v)
    return {h: sum(vs) / len(vs) for h, vs in buckets.items()}


def days_of(hours: dict[int, float], min_hours: int = MIN_DAY_HOURS) -> dict[int, float]:
    """Daily means of hourly values, keyed by the UTC day's start. A day with fewer than
    `min_hours` hourly values has no mean: averaging whatever hours exist would reflect
    the time of day they were collected, not the day's activity."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for h, v in hours.items():
        buckets[h - h % DAY].append(v)
    return {d: sum(vs) / len(vs) for d, vs in buckets.items() if len(vs) >= min_hours}


def daily(points: list[tuple[int, float]], min_hours: int = MIN_DAY_HOURS) -> dict[int, float]:
    return days_of(hourly(points), min_hours)


def change_vs_rolling(hours: dict[int, float], now: int, current_hours: int = 3, days: int = 7,
                      min_days: int = 3) -> float | None:
    """Ratio of recent hours to the same hours of day on previous days, minus 1."""
    current, baseline = 0.0, 0.0
    end = now - now % HOUR
    for h in range(end - (current_hours - 1) * HOUR, end + 1, HOUR):
        if h not in hours:
            continue
        past = [hours[h - d * DAY] for d in range(1, days + 1) if h - d * DAY in hours]
        if len(past) < min_days:
            continue
        current += hours[h]
        baseline += statistics.median(past)
    if baseline <= 0:
        return None
    return current / baseline - 1


def change_vs_reference(hours: dict[int, float], now: int, ref_start: int, ref_end: int,
                        current_hours: int = 24) -> float | None:
    cur = [v for h, v in hours.items() if now - current_hours * HOUR < h <= now]
    ref = [v for h, v in hours.items() if ref_start <= h <= ref_end]
    if len(ref) < 24 or len(cur) < max(1, current_hours // 4):
        return None
    ref_mean = sum(ref) / len(ref)
    if ref_mean <= 0:
        return None
    return (sum(cur) / len(cur)) / ref_mean - 1


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def correlate(ref_daily: dict[int, float], other_daily: dict[int, float], min_days: int = 7) -> tuple[float | None, int]:
    days = sorted(set(ref_daily) & set(other_daily))
    if len(days) < min_days:
        return None, len(days)
    return pearson([ref_daily[d] for d in days], [other_daily[d] for d in days]), len(days)


WEEK = 7 * DAY
EVENT_WINDOW = 12
PLACEBO_DRAWS = 500


def window_effect(hours: dict[int, float], start: int, window: int = EVENT_WINDOW, weeks: int = 3,
                  min_weeks: int = 2) -> float | None:
    """Sum over [start, start + window h) vs the same weekday-hours in previous weeks, minus 1.
    `start` is rounded up to the next full hour; needs 75% of hours with a baseline."""
    h0 = -(-start // HOUR) * HOUR
    actual = base = 0.0
    used = 0
    for h in range(h0, h0 + window * HOUR, HOUR):
        if h not in hours:
            continue
        past = [hours[h - w * WEEK] for w in range(1, weeks + 1) if h - w * WEEK in hours]
        if len(past) < min_weeks:
            continue
        actual += hours[h]
        base += sum(past) / len(past)
        used += 1
    if used < 0.75 * window or base <= 0:
        return None
    return actual / base - 1


def placebo_pool(hours: dict[int, float], event_ts: list[int], window: int) -> list[float]:
    cutoff = min(event_ts) - window * HOUR
    return [e for h in sorted(hours) if h <= cutoff and (e := window_effect(hours, h, window)) is not None]


def event_study(hours: dict[int, float], event_ts: list[int], window: int = EVENT_WINDOW, offset_h: int = 0,
                draws: int = PLACEBO_DRAWS, seed: str = "", pool: list[float] | None = None) -> dict:
    """Stacked event study with a placebo p-value (one-sided, for declines).

    Placebo starts are every hour before the first event whose window ends before it,
    so they are untouched by any strike. Each draw averages len(events) random starts,
    the same way the observed statistic averages the events."""
    per_event = [window_effect(hours, t + offset_h * HOUR, window) for t in event_ts]
    observed = [e for e in per_event if e is not None]
    combined = sum(observed) / len(observed) if observed else None
    out = {"window": window, "offset_h": offset_h, "per_event": [_r(e) for e in per_event],
           "effect": _r(combined), "p": None, "placebo_n": 0}
    if combined is None or not hours:
        return out
    if pool is None:
        pool = placebo_pool(hours, event_ts, window)
    out["placebo_n"] = len(pool)
    if len(pool) < 50:
        return out
    rng = random.Random(f"{seed}:{window}")  # reproducible per series and window
    k = len(observed)
    stats = [sum(rng.choice(pool) for _ in range(k)) / k for _ in range(draws)]
    out["p"] = _r((1 + sum(st <= combined for st in stats)) / (draws + 1))
    return out


GRID_WINDOWS = (6, 12, 24)
GRID_OFFSETS = (-3, 0, 3)


def robustness_grid(hours: dict[int, float], event_ts: list[int], seed: str = "") -> list[dict]:
    """The event study for each window length and start offset. A real effect should
    hold across the grid, not in one cell."""
    grid = []
    for w in GRID_WINDOWS:
        pool = placebo_pool(hours, event_ts, w)
        grid.extend(event_study(hours, event_ts, window=w, offset_h=o, seed=seed, pool=pool) for o in GRID_OFFSETS)
    return grid


MIN_EFFECT = 0.05  # a "decline" must be at least 5%: flat series make tiny moves look significant


def robust_cells(grid: list[dict], alpha: float = 0.05) -> int | None:
    """Cells showing a decline of at least MIN_EFFECT that random pre-strike windows
    rarely match. None when no cell could be computed."""
    if not any(c["effect"] is not None for c in grid):
        return None
    return sum(1 for c in grid
               if c["effect"] is not None and c["effect"] <= -MIN_EFFECT and c["p"] is not None and c["p"] < alpha)


def is_primary(series: dict) -> bool:
    """The one series per community that group statistics use: comments on Reddit,
    posts elsewhere (X has five metrics per keyword)."""
    return series["key"].endswith(".comments" if series["platform"] == "reddit" else ".posts")


def _r(x: float | None, digits: int = 4) -> float | None:
    return None if x is None else round(x, digits)


def snapshot(conn: sqlite3.Connection, config: Config, now: int, corr_days: int = 30) -> dict:
    """Everything the LIVE and COMMUNITIES tabs need, computed in one pass."""
    event_ts = [e.ts for e in config.events if e.ts <= now - EVENT_WINDOW * HOUR]
    # Placebo windows need three weeks of baseline before them, and some room to draw from.
    start = min(config.reference_start, now - max(corr_days, 8) * DAY,
                (min(event_ts) - 6 * WEEK) if event_ts else now)
    ref_key = config.correlation_ref
    ref_daily = daily(db.points(conn, ref_key, now - corr_days * DAY, now)) if ref_key else {}

    rows = []
    for s in db.list_series(conn):
        pts = db.points(conn, s["key"], start, now)
        hours = hourly(pts)
        latest = pts[-1] if pts else None
        cur_h = CURRENT_HOURS[s["kind"]]
        r, n = (None, 0)
        if ref_key and s["key"] != ref_key:
            r, n = correlate(ref_daily, daily([p for p in pts if p[0] > now - corr_days * DAY]))
        study = event_study(hours, event_ts, seed=s["key"]) if event_ts else {"effect": None, "p": None}
        rows.append({
            **s,
            "event_effect": study["effect"],
            "event_p": study["p"],
            "primary": is_primary(s),
            "latest": latest[1] if latest else None,
            "latest_ts": latest[0] if latest else None,
            "fresh": bool(latest and now - latest[0] <= FRESH_BY_PLATFORM.get(s["platform"], FRESH)),
            "change_7d": _r(change_vs_rolling(hours, now, current_hours=3)),
            "change_ref": _r(change_vs_reference(hours, now, config.reference_start, config.reference_end, cur_h)),
            "r": _r(r, 3),
            "r_days": n,
        })

    groups = []
    tags = sorted({t for row in rows if row["kind"] == "community" for t in row["tags"]})
    for tag in tags:
        members = [row for row in rows if row["kind"] == "community" and row["primary"] and tag in row["tags"]]
        c7 = [m["change_7d"] for m in members if m["change_7d"] is not None]
        cr = [m["change_ref"] for m in members if m["change_ref"] is not None]
        ev = [m for m in members if m["event_effect"] is not None]
        groups.append({
            "tag": tag,
            "members": len(members),
            "change_7d": _r(statistics.median(c7)) if c7 else None,
            "n_7d": len(c7),
            "change_ref": _r(statistics.median(cr)) if cr else None,
            "n_ref": len(cr),
            "event_effect": _r(statistics.median(m["event_effect"] for m in ev)) if ev else None,
            "n_event": len(ev),
            # Share of members whose own placebo test says "drop unlikely by chance" (p < 0.05).
            "share_sig": _r(sum(1 for m in ev if m["event_p"] is not None and m["event_p"] < 0.05) / len(ev), 3)
                         if ev else None,
        })

    runs = db.last_runs(conn)
    unconfigured = {r["platform"] for r in runs if (r["error"] or "").startswith("not configured")}
    counted = [row for row in rows if row["platform"] not in unconfigured]
    coverage = (sum(row["fresh"] for row in counted) / len(counted)) if counted else None

    return {
        "now": now,
        "reference": {"start": config.reference_start, "end": config.reference_end},
        "correlation_ref": ref_key,
        "series": rows,
        "groups": groups,
        "runs": runs,
        "coverage": _r(coverage, 3),
        "events": [e.__dict__ for e in config.events],
        "event_window": EVENT_WINDOW,
    }


def _ref_mean(hours: dict[int, float], config: Config) -> float | None:
    ref = [v for h, v in hours.items() if config.reference_start <= h <= config.reference_end]
    if len(ref) < 24:
        return None
    m = sum(ref) / len(ref)
    return m if m > 0 else None


def daily_index(conn: sqlite3.Connection, config: Config, key: str, first_day: int, now: int) -> dict[int, float]:
    """A series' daily means from `first_day` on, as an index: 100 = its mean over the
    pre-strike reference period. Empty when the reference period has too little data."""
    hours = hourly(db.points(conn, key, min(config.reference_start, first_day), now))
    base = _ref_mean(hours, config)
    if base is None:
        return {}
    return {d: v / base * 100 for d, v in days_of(hours).items() if d >= first_day}


def correlation_view(conn: sqlite3.Connection, config: Config, now: int, days: int = 45) -> dict:
    """Daily activity indices (100 = pre-strike mean) for the reference infrastructure
    series and each community group, plus each group's correlation with it.

    A group's index on a day is the median index of its communities that have data
    that day (at least two), so one large community cannot dominate the line."""
    first_day = (now - days * DAY) // DAY * DAY

    def index(key: str) -> dict[int, float]:
        return daily_index(conn, config, key, first_day, now)

    ref_key = config.correlation_ref
    ref_series = db.get_series(conn, ref_key) if ref_key else None
    ref_index = index(ref_key) if ref_series else {}

    members: dict[str, list[dict[int, float]]] = defaultdict(list)
    for s in db.list_series(conn):
        if s["kind"] != "community" or not is_primary(s):
            continue
        idx = index(s["key"])
        if idx:
            for tag in s["tags"]:
                members[tag].append(idx)

    day_list = list(range(first_day, now - now % DAY + 1, DAY))
    groups = []
    for tag in sorted(members):
        values, counts = [], []
        for d in day_list:
            vs = [m[d] for m in members[tag] if d in m]
            values.append(round(statistics.median(vs), 2) if len(vs) >= 2 else None)
            counts.append(len(vs))
        series = {d: v for d, v in zip(day_list, values) if v is not None}
        r, n = correlate(ref_index, series)
        groups.append({"tag": tag, "values": values, "n": counts, "members": len(members[tag]),
                       "r": _r(r, 3), "r_days": n})

    return {
        "days": day_list,
        "reference": {"start": config.reference_start, "end": config.reference_end},
        "infra": {
            "key": ref_key,
            "label": ref_series["label"] if ref_series else ref_key,
            "unit": ref_series["unit"] if ref_series else "",
            "values": [round(ref_index[d], 2) if d in ref_index else None for d in day_list],
        },
        "groups": groups,
        "events": [e.__dict__ for e in config.events],
    }


# ── Chart data (docs/CHARTS.md) ──────────────────────────────────────────────

GROUP_ORDER = ("political-right", "narratives", "anti-trans", "political", "regional", "south-america", "russia", "control")
ALIGNED_SPAN = 48  # hours either side of a strike; 72 changed nothing and shrinks the placebo pool (docs/CHARTS.md)
ALIGNED_SMOOTH = 3  # centred rolling mean, hours; 1 h left the band 28 to 86 points wide (docs/CHARTS.md)
MIN_POOL = 50  # placebo start times needed before a chance band is drawn


def past_events(config: Config, now: int) -> list:
    """Strikes at least a day old: earlier ones have no "after" to compare yet."""
    return [e for e in config.events if e.ts <= now - DAY]


def _ratios(hours: dict[int, float]) -> dict[int, float]:
    """Each hour vs the mean of the same weekday-hour 1-3 weeks earlier (2 of 3 needed),
    the baseline the event study uses."""
    out = {}
    for h, v in hours.items():
        past = [hours[h - w * WEEK] for w in (1, 2, 3) if h - w * WEEK in hours]
        if len(past) >= 2:
            base = sum(past) / len(past)
            if base > 0:
                out[h] = v / base
    return out


def _smooth(values: list[float | None], width: int) -> list[float | None]:
    """Centred rolling mean. A missing value stays missing, so gaps are not bridged."""
    if width <= 1:
        return values
    half = width // 2
    out = []
    for i, v in enumerate(values):
        if v is None:
            out.append(None)
            continue
        near = [x for x in values[max(0, i - half):i + half + 1] if x is not None]
        out.append(sum(near) / len(near))
    return out


def _aligned_curve(members: list[dict[int, float]], starts: list[int], offsets: list[int]) -> list[float | None]:
    """Median over communities (2 or more) of each community's ratio averaged over `starts`."""
    curve = []
    for o in offsets:
        per_member = []
        for r in members:
            vs = [r[s + o * HOUR] for s in starts if s + o * HOUR in r]
            if vs:
                per_member.append(sum(vs) / len(vs))
        curve.append(statistics.median(per_member) if len(per_member) >= 2 else None)
    return curve


def _quantile(sorted_vs: list[float], q: float) -> float:
    pos = q * (len(sorted_vs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vs) - 1)
    return sorted_vs[lo] + (sorted_vs[hi] - sorted_vs[lo]) * (pos - lo)


def _primary_members(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Primary community series by tag; a series with several tags is in each."""
    members: dict[str, list[dict]] = defaultdict(list)
    for s in db.list_series(conn):
        if s["kind"] == "community" and is_primary(s):
            for tag in s["tags"]:
                members[tag].append(s)
    return members


def _group_order(tags) -> list[str]:
    return sorted(tags, key=lambda t: (GROUP_ORDER.index(t) if t in GROUP_ORDER else len(GROUP_ORDER), t))


def strike_aligned(conn: sqlite3.Connection, config: Config, now: int, span: int = ALIGNED_SPAN,
                   smooth: int = ALIGNED_SMOOTH, draws: int = PLACEBO_DRAWS) -> dict:
    """Chart 1: each group's activity in the hours around the strikes, all strikes lined
    up at hour 0, as an index (100 = normal for that weekday-hour). The chance band is
    the 5th-95th percentile of the same curve built from random pre-strike start times."""
    events = past_events(config, now)
    offsets = list(range(-span, span + 1))
    out = {"offsets": offsets, "events": [e.__dict__ for e in events], "smoothing_h": smooth, "groups": []}
    if not events:
        return out
    starts = [-(-e.ts // HOUR) * HOUR for e in events]  # first full hour, as in window_effect
    first = min(starts)

    members_by_tag = _primary_members(conn)
    ratios: dict[str, dict[int, float]] = {}
    for series in members_by_tag.values():
        for s in series:
            if s["key"] not in ratios:
                ratios[s["key"]] = _ratios(hourly(db.points(conn, s["key"], first - 10 * WEEK, now)))

    for tag in _group_order(members_by_tag):
        members = [ratios[s["key"]] for s in members_by_tag[tag] if ratios[s["key"]]]
        curve = _smooth(_aligned_curve(members, starts, offsets), smooth)
        n = [sum(1 for r in members if any(s + o * HOUR in r for s in starts)) for o in offsets]

        # Placebo starts: the whole span ends before the first strike, and the span
        # starts no earlier than the first hour that has a baseline.
        earliest = min((min(r) for r in members), default=None)
        pool = [] if earliest is None else list(range(
            -(-(earliest + span * HOUR) // HOUR) * HOUR, first - span * HOUR, HOUR))
        band = None
        if len(pool) >= MIN_POOL and len(members) >= 2:
            rng = random.Random(f"aligned:{tag}:{span}")  # reproducible per group
            sims = [_smooth(_aligned_curve(members, [rng.choice(pool) for _ in starts], offsets), smooth)
                    for _ in range(draws)]
            lo, hi = [], []
            for i in range(len(offsets)):
                vs = sorted(c[i] for c in sims if c[i] is not None)
                ok = len(vs) >= MIN_POOL
                lo.append(round(_quantile(vs, 0.05) * 100, 2) if ok else None)
                hi.append(round(_quantile(vs, 0.95) * 100, 2) if ok else None)
            band = {"lo": lo, "hi": hi, "draws": draws, "pool": len(pool)}
        out["groups"].append({"tag": tag, "members": len(members), "n": n, "band": band,
                              "values": [None if v is None else round(v * 100, 2) for v in curve]})
    return out


def heatmap(conn: sqlite3.Connection, config: Config, now: int, days: int = 50) -> dict:
    """Chart 2: every community's daily index (100 = pre-strike mean), one row each,
    grouped. A community with several tags appears once, under its first tag."""
    first_day = (now - days * DAY) // DAY * DAY
    day_list = list(range(first_day, now - now % DAY + 1, DAY))
    rows = []
    for s in db.list_series(conn):
        if s["kind"] != "community" or not is_primary(s):
            continue
        idx = daily_index(conn, config, s["key"], first_day, now)
        values = [round(idx[d], 2) if d in idx else None for d in day_list]
        rows.append({"key": s["key"], "label": s["label"], "group": s["tags"][0] if s["tags"] else None,
                     "values": values, "coverage": round(sum(v is not None for v in values) / len(values), 3)})
    order = {t: i for i, t in enumerate(_group_order({r["group"] for r in rows if r["group"]}))}
    rows.sort(key=lambda r: (order.get(r["group"], len(order)), r["label"].lower()))
    return {"days": day_list, "events": [e.__dict__ for e in config.events], "rows": rows}


def strike_hours(conn: sqlite3.Connection, config: Config, key: str, event: int, now: int,
                 days_around: int = 7) -> dict | None:
    """Chart 5: one community, hour of day x day, for the days around one strike. Each
    cell is that hour vs the same weekday-hour 1-3 weeks earlier, as an index.
    None when the event index is out of range."""
    events = past_events(config, now)
    if not 0 <= event < len(events):
        return None
    e = events[event]
    day0 = e.ts - e.ts % DAY
    hours = hourly(db.points(conn, key, day0 - days_around * DAY - 4 * WEEK, day0 + (days_around + 1) * DAY))
    ratios = _ratios(hours)
    day_list = [day0 + d * DAY for d in range(-days_around, days_around + 1)]
    values = [[round(ratios[d + h * HOUR] * 100, 1) if d + h * HOUR in ratios else None
               for h in range(24)] for d in day_list]
    return {"key": key, "event": e.__dict__, "event_index": event, "days": day_list, "hours": list(range(24)),
            "values": values, "strike_hour": (e.ts % DAY) // HOUR if e.timed else None}
