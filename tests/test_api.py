import time

import pytest
from fastapi.testclient import TestClient

from tracker import db
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
    recent_days = [now - d * 86400 for d in range(20, 0, -1)]
    level = {t: 100.0 if i < 10 else 40.0 for i, t in enumerate(recent_days)}  # a step down halfway
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        for key, scale in (("ioda.asn200350.ping-slash24", 5.0), ("reddit.conservative.comments", 1.0),
                           ("reddit.republican.comments", 0.5)):
            db.upsert_points(conn, key, [(t, 100.0 * scale) for t in ref_hours])
            db.upsert_points(conn, key, [(t, v * scale * (1 + 0.01 * (i % 3))) for i, (t, v) in enumerate(level.items())])
    with TestClient(create_app(config, settings)) as c:
        body = c.get("/api/correlation").json()
    assert len(body["days"]) == len(body["infra"]["values"])
    right = next(g for g in body["groups"] if g["tag"] == "political-right")
    assert right["r"] > 0.95 and right["r_days"] >= 7
    vals = [v for v in right["values"] if v is not None]
    assert max(vals) > 95 and min(vals) < 45  # indexed to the pre-strike mean


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
