import time

import pytest
from fastapi.testclient import TestClient

from tracker import analysis, db
from tracker.api import create_app
from tracker.config import Settings, load_config


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "t.db"))
    settings, config = Settings.from_env(), load_config()
    now = int(time.time())
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        db.upsert_points(conn, "ioda.asn200350.ping-slash24", [(now - i * 600, 500.0) for i in range(30)])
        db.record_run(conn, "cloudflare", False, 0, "not configured: CLOUDFLARE_API_TOKEN not set")
    with TestClient(create_app(config, settings)) as c:
        yield c


def test_snapshot(client):
    r = client.get("/api/snapshot")
    assert r.status_code == 200
    assert r.headers["cache-control"].startswith("public")
    body = r.json()
    ref = next(s for s in body["series"] if s["key"] == "ioda.asn200350.ping-slash24")
    assert ref["latest"] == 500.0 and ref["fresh"]
    assert any(g["tag"] == "control" for g in body["groups"])
    assert body["events"]


def test_points_and_validation(client):
    r = client.get("/api/series/ioda.asn200350.ping-slash24/points?days=1&bucket=hour")
    assert r.status_code == 200 and all(v == 500.0 for _, v in r.json()["points"])
    assert client.get("/api/series/nope/points").status_code == 404
    assert client.get("/api/series/ioda.asn200350.ping-slash24/points?days=30&bucket=raw").status_code == 400
    assert client.get("/api/series/ioda.asn200350.ping-slash24/points?bucket=week").status_code == 422


def test_csv_exports(client):
    r = client.get("/api/export/series.csv?key=ioda.asn200350.ping-slash24&days=1&bucket=raw")
    assert r.status_code == 200 and r.text.splitlines()[0] == "time_utc,series,value"
    r = client.get("/api/export/daily.csv?days=2")
    assert r.text.startswith("date_utc,series,platform,unit,tags,daily_mean")


def test_static_site_and_design_kit(client):
    assert "Bot Traffic Monitor" in client.get("/").text
    assert client.get("/design/terminal.css").status_code == 200


def test_correlation_view(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "c.db"))
    settings, config = Settings.from_env(), load_config()
    now = int(time.time())
    ref_hours = range(config.reference_start, config.reference_start + 3 * 86400, 3600)
    today = now // 86400 * 86400
    recent_days = [today - d * 86400 for d in range(20, 0, -1)]  # 20 complete UTC days
    level = {t: 100.0 if i < 10 else 40.0 for i, t in enumerate(recent_days)}  # a step down halfway
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        for key, scale in (("ioda.asn200350.ping-slash24", 5.0), ("reddit.conservative.comments", 1.0),
                           ("reddit.republican.comments", 0.5)):
            db.upsert_points(conn, key, [(t, 100.0 * scale) for t in ref_hours])
            db.upsert_points(conn, key, [(t + h * 3600, v * scale * (1 + 0.01 * (i % 3)))
                                         for i, (t, v) in enumerate(level.items()) for h in range(1, 25)])
    with TestClient(create_app(config, settings)) as c:
        body = c.get("/api/correlation").json()
    assert len(body["days"]) == len(body["infra"]["values"])
    right = next(g for g in body["groups"] if g["tag"] == "political-right")
    assert right["r"] > 0.95 and right["r_days"] >= 7
    vals = [v for v in right["values"] if v is not None]
    assert max(vals) > 95 and min(vals) < 45  # indexed to the pre-strike mean


def test_group_day_needs_half_its_communities(tmp_path, monkeypatch):
    # Sources lag by different amounts. A day where only the fast sources are in must not
    # get a group value from them alone.
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "g.db"))
    settings, config = Settings.from_env(), load_config()
    now = int(time.time())
    today = now // 86400 * 86400
    ref_hours = range(config.reference_start, config.reference_start + 3 * 86400, 3600)
    keys = ["reddit.conservative.comments", "reddit.republican.comments", "reddit.conservatives.comments",
            "reddit.asktrumpsupporters.comments", "bluesky.afd.de.posts"]
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        for i, key in enumerate(keys):
            db.upsert_points(conn, key, [(t, 10.0) for t in ref_hours])
            days = [today - d * 86400 for d in range(5, 1 if i < 2 else 2, -1)]  # 2 of 5 have the last day
            db.upsert_points(conn, key, [(d + h * 3600, 10.0) for d in days for h in range(1, 25)])
        body = analysis.correlation_view(conn, config, now)
    right = next(g for g in body["groups"] if g["tag"] == "political-right")
    by_day = dict(zip(body["days"], right["values"]))
    assert by_day[today - 3 * 86400] == 100.0  # all 5 in
    assert by_day[today - 2 * 86400] is None   # only 2 of 5


def test_report_bundle(client, tmp_path):
    import zipfile

    from tracker import report

    settings, config = Settings.from_env(), load_config()
    with db.session(settings.db_path) as conn:
        out = report.write(conn, config, settings, int(time.time()))
        assert report.ensure_today(conn, config, settings, int(time.time())) is None  # already built today
    listed = client.get("/api/reports").json()
    assert listed[0]["date"] == out.name
    assert {"README.md", "groups.csv", "communities.csv", "infrastructure.csv", "daily.csv", "report.json"} <= set(listed[0]["files"])
    latest = client.get("/api/reports/latest").json()
    assert latest["report_date"] == out.name and latest["groups"]
    assert client.get(f"/reports/{out.name}/groups.csv").text.startswith("group,communities,")
    bundle = client.get(f"/reports/{out.name}/bot-traffic-report-{out.name}.zip")
    names = zipfile.ZipFile(__import__("io").BytesIO(bundle.content)).namelist()
    assert f"bot-traffic-report-{out.name}/README.md" in names


def test_static_export_mirrors_api(client, tmp_path):
    import json

    from tracker import static

    settings, config = Settings.from_env(), load_config()
    out = tmp_path / "site"
    with db.session(settings.db_path) as conn:
        static.export(conn, config, settings, out)
    assert 'name="data-mode" content="static"' in (out / "index.html").read_text(encoding="utf-8")
    assert (out / "design" / "terminal.css").exists() and (out / ".nojekyll").exists()
    snap = json.loads((out / "api" / "snapshot.json").read_text(encoding="utf-8"))
    assert snap["series"]
    hour = json.loads((out / "api" / "series" / "ioda.asn200350.ping-slash24" / "hour.json").read_text(encoding="utf-8"))
    assert hour["points"] and hour["bucket"] == "hour"
    assert (out / "api" / "export" / "daily.csv").read_text(encoding="utf-8").startswith("date_utc,series")
    for name in ("strike-aligned.json", "heatmap.json"):
        assert json.loads((out / "api" / name).read_text(encoding="utf-8"))
    assert (out / "api" / "series" / "reddit.conservative.comments" / "strike-hours-0.json").exists()


def test_chart_endpoints(client):
    aligned = client.get("/api/strike-aligned").json()
    assert aligned["offsets"][0] == -48 and aligned["groups"]
    heat = client.get("/api/heatmap").json()
    assert heat["rows"] and len(heat["rows"][0]["values"]) == len(heat["days"])
    hours = client.get("/api/series/reddit.conservative.comments/strike-hours?event=0").json()
    assert len(hours["values"]) == 15
    assert client.get("/api/series/reddit.conservative.comments/strike-hours?event=99").status_code == 404
    assert client.get("/api/series/nope/strike-hours").status_code == 404


def test_static_rmtree_removes_read_only_files(tmp_path):
    # A pushed site folder holds git objects that git marks read-only.
    import os
    import stat

    from tracker import static

    site = tmp_path / "site"
    (site / ".git" / "objects").mkdir(parents=True)
    obj = site / ".git" / "objects" / "ab"
    obj.write_text("x")
    os.chmod(obj, stat.S_IREAD)
    static._rmtree(site)
    assert not site.exists()
