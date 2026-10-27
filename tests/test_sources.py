"""Parsers for each upstream API, against payloads shaped like the real responses."""

from datetime import datetime

import pytest

from tracker.collectors import arctic_shift, bluesky, cloudflare, ioda, reddit


def ts(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def test_ioda_parse_keeps_numeric_requested_signals():
    payload = {"data": [[
        {"datasource": "bgp", "subtype": "", "from": 1000, "step": 300, "values": [753, None, 752]},
        {"datasource": "ping-slash24", "subtype": "", "from": 1000, "step": 600, "values": [520, 110]},
        {"datasource": "upstream-delay-penult-asns", "subtype": "", "from": 1000, "step": 300, "values": [{"a": 1}]},
        {"datasource": "ping-slash24", "subtype": "latency", "from": 1000, "step": 600, "values": [5]},
    ]]}
    out = ioda.parse(payload, {"bgp", "ping-slash24"})
    assert out["bgp"] == [(1300, 753.0), (1900, 752.0)]  # stamped at each bin's end
    assert out["ping-slash24"] == [(1600, 520.0), (2200, 110.0)]
    assert "upstream-delay-penult-asns" not in out


def test_cloudflare_parse_bot_share():
    payload = {"success": True, "result": {"meta": {}, "serie_0": {
        "timestamps": ["2026-10-11T00:00:00Z", "2026-10-11T01:00:00Z"],
        "human": ["40.1", "41.0"], "bot": ["59.9", "59.0"]}}}
    assert cloudflare.parse(payload) == [(ts("2026-10-11T01:00:00Z"), 59.9), (ts("2026-10-11T02:00:00Z"), 59.0)]
    with pytest.raises(ValueError):
        cloudflare.parse({"result": {"serie_0": {"timestamps": [], "human": []}}})


ATOM = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><author><name>/u/example_a</name></author><id>t1_a</id><updated>2026-10-12T16:42:23+00:00</updated></entry>
<entry><author><name>/u/example_b</name></author><id>t3_b</id><published>2026-10-12T16:33:12+00:00</published>
<updated>2026-10-12T16:40:00+00:00</updated></entry>
</feed>"""


def test_reddit_atom_prefers_published_and_rejects_dtd():
    assert reddit.parse_atom(ATOM) == [ts("2026-10-12T16:42:23Z"), ts("2026-10-12T16:33:12Z")]
    with pytest.raises(ValueError):
        reddit.parse_atom('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><feed/>')


def test_reddit_listing():
    payload = {"data": {"children": [{"data": {"created_utc": 1791860543.0}}, {"data": {"created_utc": 1791859992}}]}}
    assert reddit.parse_listing(payload) == [1791860543.0, 1791859992.0]


def test_bluesky_uses_indexed_at():
    payload = {"posts": [{"indexedAt": "2026-10-12T16:42:23.000Z", "record": {"createdAt": "2020-01-01T00:00:00Z"}}]}
    assert bluesky.parse(payload) == [ts("2026-10-12T16:42:23Z")]


def test_arctic_shift_parse_and_error():
    payload = {"data": [{"created_utc": "2026-10-12T10:00:00.000Z", "count": "12"}]}
    assert arctic_shift.parse(payload) == [(ts("2026-10-12T13:00:00Z"), 12.0)]  # 12:00-13:00, stamped at its end
    with pytest.raises(ValueError, match="Timeout"):
        arctic_shift.parse({"data": None, "error": "Timeout. Maybe slow down a bit"})


def test_arctic_shift_corrects_early_labels():
    after, before = int(ts("2026-10-09T00:00:00Z")), int(ts("2026-10-10T00:00:00Z"))
    payload = {"data": [{"created_utc": "2026-10-08T22:00:00.000Z", "count": "172"},
                        {"created_utc": "2026-10-09T21:00:00.000Z", "count": "5"},
                        {"created_utc": "2026-10-09T22:00:00.000Z", "count": "9"}]}  # really 00:00 next day
    assert arctic_shift.parse(payload, after, before) == [(after + 3600, 172.0), (before, 5.0)]
    # Labels that start at `after` mean the archive changed how it labels: refuse.
    plain = {"data": [{"created_utc": "2026-10-09T00:00:00.000Z", "count": "4"}]}
    with pytest.raises(ValueError, match="no longer offset"):
        arctic_shift.parse(plain, after, before)


def test_arctic_shift_clock_changes():
    # Observed 2025-10-26 (clocks back at 01:00Z): label 23:00 held 01:00Z, 00:00 held 02:00Z,
    # 02:00 held 03:00Z; no bucket was labelled 01:00.
    for label, true in (("2025-10-25T23:00", "2025-10-26T01:00"), ("2025-10-26T00:00", "2025-10-26T02:00"),
                        ("2025-10-26T02:00", "2025-10-26T03:00")):
        assert arctic_shift.label_to_utc(int(ts(label + ":00Z"))) == ts(true + ":00Z")
    # Observed 2026-03-29 (clocks forward at 01:00Z): two buckets labelled 01:00 (02:00Z and 03:00Z).
    after, before = int(ts("2026-03-29T00:00:00Z")), int(ts("2026-03-29T05:00:00Z"))
    payload = {"data": [{"created_utc": f"2026-03-{d}:00:00.000Z", "count": c} for d, c in
                        (("28T23", "19"), ("29T00", "13"), ("29T01", "23"), ("29T01", "14"), ("29T02", "14"))]}
    out = dict(arctic_shift.parse(payload, after, before))
    assert out == {ts("2026-03-29T01:00:00Z"): 19.0, ts("2026-03-29T02:00:00Z"): 13.0,
                   ts("2026-03-29T05:00:00Z"): 14.0}  # 02:00-04:00Z left out: their labels collide


def test_arctic_shift_fills_quiet_hours_but_not_missing_days():
    day = 20000 * 86400
    pts = [(day + 3 * 3600, 5.0), (day + 2 * 86400 + 3600, 2.0)]  # day 0 and day 2; day 1 missing
    out = dict(arctic_shift.fill_quiet_hours(pts, end=day + 3 * 86400, begin=day))
    assert out[day + 3 * 3600] == 5.0 and out[day + 4 * 3600] == 0.0
    assert not any(day + 86400 < t <= day + 2 * 86400 for t in out)  # gap kept
    assert len(out) == 48


def _archive(bad):
    """Mock archive: one count per hour, 422 for any request overlapping a `bad` window."""
    import httpx

    def handler(request):
        after = int(ts(request.url.params["after"]))
        before = int(ts(request.url.params["before"]))
        if any(after < b and a < before for a, b in bad):
            return httpx.Response(422, json={"error": "Timeout. Maybe slow down a bit"})
        # labelled 2 h early, like the real archive in summer
        data = [{"created_utc": arctic_shift._iso(h - 7200), "count": 1} for h in range(after, before, 3600)]
        return httpx.Response(200, json={"data": data})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_arctic_shift_skips_a_failing_window_and_keeps_the_rest(monkeypatch):
    import asyncio

    monkeypatch.setattr(arctic_shift, "DELAY", 0)
    monkeypatch.setattr(arctic_shift, "COOLDOWNS", (0, 0))
    day = 20000 * 86400
    bad = [(day + 6 * 3600, day + 12 * 3600)]

    async def go():
        async with _archive(bad) as client:
            return await arctic_shift._range(client, "x", "comments", day, day + 2 * 86400, 86400)
    pts, gaps = asyncio.run(go())
    assert gaps == bad
    have = dict(pts)
    assert len(have) == 48 - 6
    assert not any(day + 6 * 3600 < h <= day + 12 * 3600 for h in have)
    # the skipped hours stay missing after quiet-hour filling, never zero
    filled = dict(arctic_shift.fill_quiet_hours(pts, day + 2 * 86400, gaps, begin=day))
    assert not any(day + 6 * 3600 < h <= day + 12 * 3600 for h in filled)
    assert len(filled) == 42


def test_arctic_shift_stops_when_the_archive_keeps_refusing(monkeypatch):
    import asyncio

    monkeypatch.setattr(arctic_shift, "DELAY", 0)
    monkeypatch.setattr(arctic_shift, "COOLDOWNS", (0,))
    day = 20000 * 86400
    end = day + 4 * 86400
    bad = [(day + 86400, end)]  # first day fine, then the archive refuses everything

    async def go():
        async with _archive(bad) as client:
            return await arctic_shift._range(client, "x", "comments", day, end, 86400)
    pts, gaps = asyncio.run(go())
    assert len(pts) == 24
    assert gaps[-1][1] == end and gaps[0][0] == day + 86400
    assert len(gaps) == arctic_shift.MAX_SKIPPED + 1  # skipped windows, then the untried rest


def test_bluesky_history_counts_quiet_hours_and_extrapolates_busy_ones():
    end = int(ts("2026-10-12T17:00:00Z"))
    quiet = [end - 3000, end - 100]  # two posts in the hour: an exact count
    assert bluesky.hour_rate(quiet, end) == 2.0
    busy = [end - 1800 + i * 18 for i in range(100)]  # a full page covering 30 minutes
    assert bluesky.hour_rate(busy, end) == pytest.approx(200, rel=0.01)


def test_quiet_hours_are_not_filled_before_the_fetched_range():
    day = 20000 * 86400
    begin = day + 20 * 3600  # the backfill started at 20:00
    pts = [(day + 22 * 3600, 5.0)]
    out = dict(arctic_shift.fill_quiet_hours(pts, end=day + 86400, begin=begin))
    assert min(out) == begin + 3600  # nothing before the first fetched hour
    assert out[day + 21 * 3600] == 0.0 and out[day + 22 * 3600] == 5.0


def test_refetch_replaces_only_complete_windows_and_only_as_far_as_the_source_reached(tmp_path, monkeypatch):
    import asyncio

    from tracker import collectors, db
    from tracker.config import Settings, load_config

    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "r.db"))
    settings, config = Settings.from_env(), load_config()
    good, bad = [s.key for s in config.series if s.platform == "ioda"][:2]
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        for key in (good, bad):
            db.upsert_points(conn, key, [(1000, 1.0), (1300, 2.0), (5000, 3.0)])

    async def fake_collect(client, specs, settings, now, start=None, end=None):
        key = specs[0].key
        if key == bad:
            return collectors.Result(errors=[f"{key}: timeout"])
        return collectors.Result(points={key: [(1300, 7.0), (1600, 8.0)]})

    monkeypatch.setattr(ioda, "collect", fake_collect)
    out = asyncio.run(collectors.refetch(config, settings, {good: (900, 6000), bad: (900, 6000)}))
    assert out[bad].startswith("kept old points")
    with db.session(settings.db_path) as conn:
        assert db.points(conn, good, 0, 9999) == [(1300, 7.0), (1600, 8.0), (5000, 3.0)]  # 5000 is past the new data
        assert db.points(conn, bad, 0, 9999) == [(1000, 1.0), (1300, 2.0), (5000, 3.0)]


def test_cloudflare_history_is_requested_a_week_at_a_time(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    import httpx

    calls = []

    def handler(request):
        p = request.url.params
        calls.append((p["dateStart"], p["dateEnd"]))
        if len(calls) == 2:
            return httpx.Response(400, json={"errors": [{"message": "too long"}]})
        stamp = p["dateStart"].replace(":00Z", ":00.000Z")
        return httpx.Response(200, json={"result": {"serie_0": {"timestamps": [stamp], "bot": ["50.0"]}}})

    spec = SimpleNamespace(key="cloudflare.asn1.bot-pct", params={"asn": 1})
    start, now = int(ts("2026-09-01T00:00:00Z")), int(ts("2026-09-20T00:00:00Z"))

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await cloudflare.collect(client, [spec], SimpleNamespace(cloudflare_token="t"), now, start=start)

    r = asyncio.run(go())
    assert calls == [("2026-09-01T00:00:00Z", "2026-09-08T00:00:00Z"), ("2026-09-08T00:00:00Z", "2026-09-15T00:00:00Z"),
                     ("2026-09-15T00:00:00Z", "2026-09-20T00:00:00Z")]
    assert [t for t, _ in r.points[spec.key]] == [start + 3600, int(ts("2026-09-15T01:00:00Z"))]  # refused week is a gap
    assert len(r.errors) == 1


def test_x_counts_become_hourly_metrics():
    from tracker.collectors import x

    h0, h1 = int(ts("2026-10-08T10:00:00Z")), int(ts("2026-10-08T11:00:00Z"))
    payload = {"data": [{"start": "2026-10-08T10:00:00.000Z", "end": "2026-10-08T11:00:00.000Z", "tweet_count": 30},
                        {"start": "2026-10-08T11:00:00.000Z", "end": "2026-10-08T12:00:00.000Z", "tweet_count": 0}]}
    orig = x.buckets(payload)
    assert orig == {h0: 30, h1: 0}
    minutes = {h0 + 60 * i: (20 if i < 5 else 1) for i in range(60)}  # a 5-minute burst: 100 of 155 posts
    out = x.metrics(orig, {h0: 90, h1: 0}, {h0: 6}, minutes)
    assert out["posts"] == [(h0 + 3600, 30.0), (h1 + 3600, 0.0)]  # stamped at each hour's end; zeros are Twitter's own
    assert out["reposts"] == [(h0 + 3600, 90.0), (h1 + 3600, 0.0)]
    assert out["repost-share"] == [(h0 + 3600, 75.0)]  # no share for an hour with no posts at all
    assert out["replies"] == [(h0 + 3600, 6.0)]
    assert out["burst"] == [(h0 + 3600, round(100 * 100 / 155, 2))]
    assert "burst" not in x.metrics(orig, {}, {}, {h0 + 60 * i: 0 for i in range(60)})  # too quiet to judge
    gap = x.metrics(orig, {h0: 90, h1: 0}, {}, minutes, gaps={h1})  # Twitter had no data at all in h1
    assert gap["posts"] == [(h0 + 3600, 30.0)] and gap["reposts"] == [(h0 + 3600, 90.0)]


def test_x_recent_window_follows_the_clock_not_the_pass():
    from tracker.collectors import x

    stop = int(ts("2026-10-21T20:00:00Z"))
    assert x.recent_start(stop, stop + 600) == stop - 7 * 86400 + 3600  # on time: the usual window
    late = int(ts("2026-10-21T22:41:00Z"))  # the pass reached Twitter two hours late
    begin = x.recent_start(stop, late)
    assert begin >= late - 7 * 86400 and begin % 3600 == 0


def test_x_daily_request_cap(tmp_path):
    from tracker.collectors import SourceSkipped, x

    budget = x._Budget(tmp_path / "usage.json", cap=2)
    budget.take()
    x._Budget(tmp_path / "usage.json", cap=2).take()  # the count survives a restart
    with pytest.raises(SourceSkipped, match="cap"):
        x._Budget(tmp_path / "usage.json", cap=2).take()


def test_x_mirrors_bluesky_searches_and_uses_original_posts_for_groups():
    from tracker import analysis
    from tracker.config import load_config

    config = load_config()
    bsky = [s for s in config.series if s.platform == "bluesky"]
    xs = [s for s in config.series if s.platform == "x"]
    primary = [s for s in xs if analysis.is_primary({"platform": s.platform, "key": s.key})]
    assert len(xs) == 5 * len(primary)
    # Every Bluesky search is on Twitter too; Twitter also has the x_only searches.
    searched = lambda specs: {(s.params["query"], s.params["lang"]) for s in specs}
    assert searched(bsky) < searched(primary) and all(s.key.endswith(".posts") for s in primary)


def test_search_labels_name_the_language_and_are_unique():
    from tracker.config import load_config

    searches = [s for s in load_config().series if s.platform in ("bluesky", "x") and s.key.endswith(".posts")]
    labels = [s.label for s in searches]
    assert len(set(labels)) == len(labels)  # Zelensky is searched in three languages
    assert 'BSKY "Zelensky" fr' in labels
    assert not any('""' in label for label in labels)  # exact phrases are not quoted twice


def test_x_only_search_is_counted_on_x_but_not_bluesky():
    from tracker.config import load_config

    keys = {s.key for s in load_config().series}
    assert "x.zelensky.it.posts" in keys and "bluesky.zelensky.it.posts" not in keys
    assert "bluesky.zelensky.fr.posts" in keys


def test_search_with_operators_uses_its_label_and_keeps_its_brackets():
    from tracker.config import load_config

    troon = next(s for s in load_config().series if s.key == "x.troon-or-troons.en.posts")
    assert troon.label == 'Twitter "troon(s)" en' and troon.tags == ("anti-trans",)
    # Twitter applies AND before OR, so the brackets must survive for lang: to cover both words.
    assert troon.params["query"] == "(troon OR troons)"


def test_archive_only_groups_have_comments_only_and_are_skipped_by_the_live_pass(tmp_path, monkeypatch):
    import asyncio

    from tracker import collectors
    from tracker.config import Settings, load_config

    config = load_config()
    keys = {s.key for s in config.series}
    assert "reddit.askconservatives.comments" in keys and "reddit.askconservatives.posts" not in keys
    assert "reddit.conservative.posts" in keys  # the original groups keep both counts
    live = next(s for s in config.series if s.key == "reddit.conservative.comments")
    assert not live.params.get("archive_only")

    seen = []

    async def fake_collect(client, specs, settings, now, start=None, end=None):
        seen.extend(s.key for s in specs)
        return collectors.Result()

    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "a.db"))
    monkeypatch.setattr(reddit, "collect", fake_collect)
    monkeypatch.setattr(arctic_shift, "collect", fake_collect)
    from tracker import db
    settings = Settings.from_env()
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
    asyncio.run(collectors.run(config, settings, platforms=("reddit",)))
    assert "reddit.conservative.comments" in seen and "reddit.askconservatives.comments" not in seen
    seen.clear()
    asyncio.run(collectors.run(config, settings, platforms=("reddit",), start=0, backfill=True))
    assert "reddit.askconservatives.comments" in seen


def test_lexicon_terms_are_sourced_and_israel_speech_is_not_counted():
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "config" / "lexicon.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len({r["term"] for r in rows}) == len(rows)
    for r in rows:
        assert r["status"] in ("candidate", "ambiguous", "excluded", "out of scope", "proposed")
        assert r["source"], r["term"]
        if r["status"] != "proposed":
            assert r["source_url"].startswith(("https://", "http://")), r["term"]
    status = {r["term"]: r["status"] for r in rows}
    for term in ("Zionist", "Israel Lobby", "deadly exchange", "dual citizen"):
        assert status[term] == "excluded"
    assert status["dual loyalty"] == status["open borders for Israel"] == "candidate"
    assert status["bankers"] == status["Federal Reserve"] == "ambiguous"
