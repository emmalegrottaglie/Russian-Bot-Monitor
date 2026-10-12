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
    assert out["bgp"] == [(1000, 753.0), (1600, 752.0)]
    assert out["ping-slash24"] == [(1000, 520.0), (1600, 110.0)]
    assert "upstream-delay-penult-asns" not in out


def test_cloudflare_parse_bot_share():
    payload = {"success": True, "result": {"meta": {}, "serie_0": {
        "timestamps": ["2026-10-11T00:00:00Z", "2026-10-11T01:00:00Z"],
        "human": ["40.1", "41.0"], "bot": ["59.9", "59.0"]}}}
    assert cloudflare.parse(payload) == [(ts("2026-10-11T00:00:00Z"), 59.9), (ts("2026-10-11T01:00:00Z"), 59.0)]
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
    assert arctic_shift.parse(payload) == ([(ts("2026-10-12T11:00:00Z"), 12.0)], 0)  # end of the hour
    with pytest.raises(ValueError, match="Timeout"):
        arctic_shift.parse({"data": None, "error": "Timeout. Maybe slow down a bit"})


def test_arctic_shift_corrects_early_labels():
    after, before = int(ts("2026-10-09T00:00:00Z")), int(ts("2026-10-10T00:00:00Z"))
    payload = {"data": [{"created_utc": "2026-10-08T22:00:00.000Z", "count": "172"},
                        {"created_utc": "2026-10-09T21:00:00.000Z", "count": "5"},
                        {"created_utc": "2026-10-09T22:00:00.000Z", "count": "9"}]}  # really 00:00 next day
    pts, shift = arctic_shift.parse(payload, after, before)
    assert shift == 7200
    assert pts == [(after + 3600, 172.0), (before, 5.0)]
    # first hours empty: shift invisible, so the previous one is reused
    late = {"data": [{"created_utc": "2026-10-09T03:00:00.000Z", "count": "4"}]}
    assert arctic_shift.parse(late, after, before, shift_hint=7200)[0] == [(int(ts("2026-10-09T06:00:00Z")), 4.0)]


def test_arctic_shift_fills_quiet_hours_but_not_missing_days():
    day = 20000 * 86400
    pts = [(day + 3 * 3600, 5.0), (day + 2 * 86400 + 3600, 2.0)]  # day 0 and day 2; day 1 missing
    out = dict(arctic_shift.fill_quiet_hours(pts, end=day + 3 * 86400))
    assert out[day + 3 * 3600] == 5.0 and out[day + 4 * 3600] == 0.0
    assert not any(day + 86400 < t <= day + 2 * 86400 for t in out)  # gap kept
    assert len(out) == 48
