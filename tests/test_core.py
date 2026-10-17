import math

import pytest

from tracker import alerts, analysis
from tracker.config import load_config, parse_config
from tracker.rates import hourly_rate
from tracker.x_api import oauth1_header

H, D = 3600, 86400


# ── rates ────────────────────────────────────────────────────────────────────

def test_rate_counts_exactly_when_feed_reaches_past_window():
    now = 100 * H
    stamps = [now - 2 * H] + [now - i * 60 for i in range(30)]  # 30 in the last hour
    assert hourly_rate(stamps, now) == 30


def test_rate_extrapolates_for_busy_feed():
    now = 100 * H
    stamps = [now - i * 6 for i in range(100)]  # 100 items over ~10 minutes
    assert hourly_rate(stamps, now) == pytest.approx(100 * 3600 / (99 * 6))


def test_rate_unknown_for_empty_feed():
    assert hourly_rate([], 1000) is None


# ── analysis ─────────────────────────────────────────────────────────────────

def test_change_vs_rolling_uses_same_hours_on_previous_days():
    now = 30 * D + 12 * H
    hours = {}
    for d in range(1, 8):
        for h in range(10, 13):
            hours[now - d * D - (12 - h) * H] = 100.0
    for h in range(10, 13):
        hours[now - (12 - h) * H] = 50.0
    assert analysis.change_vs_rolling(hours, now, current_hours=3) == pytest.approx(-0.5)


def test_change_vs_rolling_needs_enough_history():
    now = 30 * D
    hours = {now: 50.0, now - D: 100.0, now - 2 * D: 100.0}
    assert analysis.change_vs_rolling(hours, now) is None


def test_change_vs_reference():
    ref_start, ref_end = 0, 2 * D - 1
    hours = {h: 200.0 for h in range(0, 2 * D, H)}
    now = 10 * D
    hours.update({now - i * H: 50.0 for i in range(24)})
    assert analysis.change_vs_reference(hours, now, ref_start, ref_end, 24) == pytest.approx(-0.75)
    assert analysis.change_vs_reference({now: 1.0}, now, ref_start, ref_end, 24) is None


def test_pearson_and_correlate():
    assert analysis.pearson([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)
    assert analysis.pearson([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)
    assert analysis.pearson([1, 1, 1], [1, 2, 3]) is None
    ref = {d * D: float(d) for d in range(10)}
    r, n = analysis.correlate(ref, {d * D: 2.0 * d for d in range(10)})
    assert (round(r, 6), n) == (1.0, 10)
    assert analysis.correlate(ref, {d * D: 1.0 for d in range(3)}) == (None, 3)


def test_hourly_and_daily_means():
    # Points are stamped at the end of what they measure: 60 s and 1 h both close hour 0.
    pts = [(60, 1.0), (H, 3.0), (H + 60, 10.0)]
    assert analysis.hourly(pts) == {0: 2.0, H: 10.0}
    day = [(h * H, 4.0) for h in range(1, 25)]  # 24 hours ending 01:00 ... 24:00
    assert analysis.daily(day) == {0: 4.0}  # the hour ending at midnight belongs to the day before it
    assert analysis.daily(day[:19]) == {}  # 19 hours: incomplete, no daily mean


# ── alerts ───────────────────────────────────────────────────────────────────

def _snap(infra_change, group_change, control=-0.02, n=5):
    return {
        "now": 1_791_820_800,
        "series": [{"key": "ioda.asn1.ping-slash24", "kind": "infrastructure", "label": "Yandex Cloud AS1",
                    "unit": "/24 BLOCKS ANSWERING", "fresh": True, "change_7d": infra_change}],
        "groups": [{"tag": "political-right", "change_7d": group_change, "n_7d": n},
                   {"tag": "control", "change_7d": control, "n_7d": n}],
    }


def test_detect_thresholds_and_ignores_control_group():
    hits = alerts.detect(_snap(-0.6, -0.35, control=-0.9))
    assert [h["key"] for h in hits] == ["ioda.asn1.ping-slash24", "group:political-right"]
    assert all(h["direction"] == "down" for h in hits)
    assert alerts.detect(_snap(-0.1, -0.1)) == []
    assert alerts.detect(_snap(None, -0.5, n=2)) == []  # group too small


def test_cooldown_suppresses_same_direction_only():
    hits = alerts.detect(_snap(-0.6, 0.0))
    recent = [{"details": [{"key": "ioda.asn1.ping-slash24", "direction": "down"}]}]
    assert alerts.not_in_cooldown(hits, recent) == []
    recent = [{"details": [{"key": "ioda.asn1.ping-slash24", "direction": "up"}]}]
    assert len(alerts.not_in_cooldown(hits, recent)) == 1


def test_compose_quotes_control_and_fits_a_post():
    snap = _snap(-0.6, -0.35)
    text = alerts.compose(alerts.detect(snap), snap)
    assert "Control communities −2%" in text
    assert "−60%" in text and len(text) <= 280
    many = [{"key": f"k{i}", "label": "x" * 60, "change": -0.5, "direction": "down"} for i in range(10)]
    long = alerts.compose(many, snap, url="https://example.org")
    assert len(long) <= 280 and long.endswith("https://example.org")


# ── X OAuth 1.0a: the worked example from X's "Creating a signature" docs ────

def test_oauth1_signature_matches_documented_example():
    header = oauth1_header(
        "POST", "https://api.twitter.com/1.1/statuses/update.json",
        consumer_key="xvz1evFS4wEEPTGEFPHBog",
        consumer_secret="kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
        token="370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
        token_secret="LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
        params={"include_entities": "true", "status": "Hello Ladies + Gentlemen, a signed OAuth request!"},
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", timestamp=1318622958,
    )
    assert 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in header


# ── config ───────────────────────────────────────────────────────────────────

def test_repository_config_parses():
    cfg = load_config()
    keys = {s.key for s in cfg.series}
    assert cfg.correlation_ref in keys
    assert any("control" in s.tags for s in cfg.series)
    assert cfg.reference_start < cfg.reference_end


def test_duplicate_keys_rejected():
    sources = {"analysis": {"reference_start": "2026-01-01", "reference_end": "2026-01-02"},
               "reddit": [{"subreddits": ["news"], "region": "US", "tags": []},
                          {"subreddits": ["News"], "region": "US", "tags": []}]}
    with pytest.raises(ValueError, match="duplicate"):
        parse_config(sources, {})


# ── event study ──────────────────────────────────────────────────────────────

def _weekly_series(weeks=8, level=100.0, noise_seed=1):
    import random
    rng = random.Random(noise_seed)
    start = 20000 * D
    return start, {start + h * H: level * (1 + 0.05 * rng.uniform(-1, 1)) for h in range(weeks * 7 * 24)}


def test_window_effect_matches_weekday_hours():
    start, hours = _weekly_series()
    t = start + 6 * 7 * D
    for h in range(12):
        hours[t + h * H] = 50.0
    assert analysis.window_effect(hours, t) == pytest.approx(-0.5, abs=0.05)
    assert analysis.window_effect({}, t) is None


def test_event_study_flags_real_drop_and_not_noise():
    start, hours = _weekly_series()
    events = [start + 6 * 7 * D + d * D for d in (0, 1, 3)]
    quiet = analysis.event_study(dict(hours), events, seed="x")
    assert quiet["p"] is not None and quiet["p"] > 0.05 and quiet["placebo_n"] >= 50
    for t in events:
        for h in range(12):
            hours[t + h * H] = 40.0
    hit = analysis.event_study(hours, events, seed="x")
    assert hit["effect"] == pytest.approx(-0.6, abs=0.05)
    assert hit["p"] < 0.01
    assert len(hit["per_event"]) == 3


def test_event_study_without_history_has_no_p():
    out = analysis.event_study({0: 1.0}, [10 * D])
    assert out["effect"] is None and out["p"] is None


def test_robust_cells():
    cell = lambda e, p: {"effect": e, "p": p}
    assert analysis.robust_cells([cell(None, None)] * 9) is None
    assert analysis.robust_cells([cell(-0.3, 0.01), cell(-0.01, 0.001), cell(0.2, 0.01), cell(-0.3, 0.2)]) == 1


def test_hourly_history_supersedes_live_samples_in_its_hours(tmp_path):
    from tracker import db

    with db.session(tmp_path / "t.db") as conn:
        db.init(conn, [])
        db.upsert_points(conn, "k", [(600, 30.0), (H + 600, 50.0), (2 * H + 600, 70.0), (3 * H + 600, 90.0)])  # live
        db.replace_hours(conn, "k", [(2 * H, 40.0), (3 * H, 60.0)])  # archive counts for the hours ending 2H and 3H
        assert db.points(conn, "k", 0, 5 * H) == [(600, 30.0), (2 * H, 40.0), (3 * H, 60.0), (3 * H + 600, 90.0)]
        # A re-collected stretch replaces everything inside it and nothing outside.
        db.replace_range(conn, "k", H, 3 * H, [(2 * H, 41.0), (3 * H, 61.0), (4 * H, 99.0)])
        assert db.points(conn, "k", 0, 5 * H) == [(600, 30.0), (2 * H, 41.0), (3 * H, 61.0), (3 * H + 600, 90.0)]


def test_daily_points_in_sql_match_daily_means(tmp_path):
    from tracker import db

    pts = [(h * H, float(h % 7)) for h in range(1, 24 * 3 + 1)]  # three days of hourly points
    pts += [(h * H - 600, 9.0) for h in range(3, 24 * 3, 5)]  # a second sample in some hours
    pts = [p for p in pts if not 30 * H < p[0] <= 40 * H]  # day 1 left with 14 hours
    with db.session(tmp_path / "d.db") as conn:
        db.init(conn, [])
        db.upsert_points(conn, "k", pts)
        got = db.daily_points(conn, "k", 0, 10 * 86400, analysis.MIN_DAY_HOURS)
    want = sorted(analysis.daily(pts).items())
    assert [d for d, _ in got] == [d for d, _ in want] == [0, 2 * 86400]
    assert [round(v, 9) for _, v in got] == [round(v, 9) for _, v in want]
