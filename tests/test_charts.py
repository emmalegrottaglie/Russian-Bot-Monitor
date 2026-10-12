"""Chart data (docs/CHARTS.md) against synthetic series with a known answer."""

import random

import pytest

from tracker import analysis, db
from tracker.config import Settings, load_config

HOUR, DAY = 3600, 86400
RIGHT = ("reddit.conservative.comments", "reddit.republican.comments", "reddit.conservatives.comments")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "charts.db"))
    settings, config = Settings.from_env(), load_config()
    now = max(e.ts for e in config.events) + 3 * DAY
    return settings, config, now


def _fill(settings, config, now, drop: float):
    """Hourly points with a daily cycle and 5% noise; after each strike the rate is
    multiplied by `drop` for 12 hours."""
    first = min(e.ts for e in config.events)
    strikes = [-(-e.ts // HOUR) * HOUR for e in config.events]
    rng = random.Random(7)
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        for i, key in enumerate(RIGHT):
            pts = []
            for h in range((first - 60 * DAY) // HOUR * HOUR, now, HOUR):
                v = (100 + 40 * ((h // HOUR) % 24 > 12)) * (1 + i) * rng.gauss(1, 0.05)
                if any(s < h + HOUR <= s + 12 * HOUR for s in strikes):
                    v *= drop
                pts.append((h + HOUR, v))  # stamped at the end of the hour, like the collectors
            db.upsert_points(conn, key, pts)


def _right(settings, config, now):
    with db.session(settings.db_path) as conn:
        out = analysis.strike_aligned(conn, config, now, smooth=1, draws=300)
    return out, next(g for g in out["groups"] if g["tag"] == "political-right")


def test_strike_aligned_drop_leaves_the_chance_band(setup):
    settings, config, now = setup
    _fill(settings, config, now, drop=0.6)
    out, right = _right(settings, config, now)
    assert right["band"] and right["band"]["pool"] >= analysis.MIN_POOL
    zero = out["offsets"].index(0)
    for i in range(zero + 2, zero + 10):  # inside the 12 h drop
        assert right["values"][i] < right["band"]["lo"][i], out["offsets"][i]
    assert 50 < right["values"][zero + 5] < 75


def test_strike_aligned_noise_stays_inside_the_band(setup):
    settings, config, now = setup
    _fill(settings, config, now, drop=1.0)
    out, right = _right(settings, config, now)
    inside = [lo <= v <= hi for v, lo, hi in zip(right["values"], right["band"]["lo"], right["band"]["hi"])
              if v is not None and lo is not None]
    assert len(inside) > 80 and sum(inside) / len(inside) >= 0.85


def test_strike_aligned_without_history_has_no_band(setup):
    settings, config, now = setup
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        out = analysis.strike_aligned(conn, config, now)
    assert all(g["band"] is None and set(g["values"]) == {None} for g in out["groups"])


def test_heatmap_lists_every_community_and_keeps_gaps(setup):
    settings, config, now = setup
    ref = range(config.reference_start, config.reference_end, HOUR)
    gap_day = now - 3 * DAY - now % DAY  # recent days stay clear of the reference period
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        db.upsert_points(conn, RIGHT[0], [(t, 50.0) for t in ref])
        db.upsert_points(conn, RIGHT[0], [(t, 25.0) for t in range(now - 5 * DAY - now % HOUR, now, HOUR)
                                          if not gap_day <= t < gap_day + DAY])
        out = analysis.heatmap(conn, config, now, days=5)
    primary = [s for s in config.series if s.kind == "community" and analysis.is_primary(
        {"platform": s.platform, "key": s.key})]
    assert len(out["rows"]) == len(primary)
    row = next(r for r in out["rows"] if r["key"] == RIGHT[0])
    day_i = out["days"].index(gap_day)
    assert row["values"][day_i] is None  # a missing day is missing, not zero
    assert row["values"][day_i - 1] == pytest.approx(50.0)  # half the pre-strike level
    empty = next(r for r in out["rows"] if r["key"] == "reddit.aww.comments")
    assert empty["coverage"] == 0 and set(empty["values"]) == {None}
    groups = [r["group"] for r in out["rows"]]
    assert groups.index("control") > groups.index("political-right")


def test_strike_hours_marks_the_strike_hour(setup):
    settings, config, now = setup
    _fill(settings, config, now, drop=0.6)
    with db.session(settings.db_path) as conn:
        out = analysis.strike_hours(conn, config, RIGHT[0], 0, now)
        assert analysis.strike_hours(conn, config, RIGHT[0], 99, now) is None
    first = analysis.past_events(config, now)[0]
    assert first.timed and out["strike_hour"] == (first.ts % DAY) // HOUR
    assert len(out["days"]) == 15 and all(len(d) == 24 for d in out["values"])
    # The 12 h drop starts at the first full hour after the strike.
    start = -(-first.ts // HOUR) * HOUR
    cells = {out["days"][d] + h * HOUR: v for d, row in enumerate(out["values"]) for h, v in enumerate(row)}
    during = [cells[start + i * HOUR] for i in range(12)]
    before = [cells[start - i * HOUR] for i in range(2, 14)]
    assert all(v is not None and v < 80 for v in during)
    assert all(v is not None and 80 < v < 120 for v in before)
