import asyncio
from types import SimpleNamespace

from tracker import collectors, db
from tracker.collectors import Result, SourceSkipped
from tracker.config import Settings, load_config


def _module(fn):
    return SimpleNamespace(collect=fn)


def test_run_writes_points_and_isolates_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "t.db"))
    settings, config = Settings.from_env(), load_config()
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)

    async def ok(client, specs, settings, now, start=None):
        return Result(points={s.key: [(now, 1.0)] for s in specs})

    async def boom(client, specs, settings, now, start=None):
        raise RuntimeError("upstream changed")

    async def skipped(client, specs, settings, now, start=None):
        raise SourceSkipped("no token")

    monkeypatch.setattr(collectors, "_modules", lambda: {
        "ioda": _module(ok), "reddit": _module(boom), "cloudflare": _module(skipped), "bluesky": _module(ok)})
    asyncio.run(collectors.run(config, settings))

    with db.session(settings.db_path) as conn:
        runs = {r["platform"]: r for r in db.last_runs(conn)}
        assert runs["ioda"]["ok"] and runs["bluesky"]["ok"]
        assert not runs["reddit"]["ok"] and "upstream changed" in runs["reddit"]["error"]
        assert runs["cloudflare"]["error"].startswith("not configured")
        assert db.latest_point(conn, "ioda.asn200350.ping-slash24")[1] == 1.0
        assert db.latest_point(conn, "reddit.news.comments") is None
