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
        "ioda": _module(ok), "reddit": _module(boom), "cloudflare": _module(skipped), "bluesky": _module(ok),
        "x": _module(skipped)})
    asyncio.run(collectors.run(config, settings))

    with db.session(settings.db_path) as conn:
        runs = {r["platform"]: r for r in db.last_runs(conn)}
        assert runs["ioda"]["ok"] and runs["bluesky"]["ok"]
        assert not runs["reddit"]["ok"] and "upstream changed" in runs["reddit"]["error"]
        assert runs["cloudflare"]["error"].startswith("not configured")
        assert db.latest_point(conn, "ioda.asn200350.ping-slash24")[1] == 1.0
        assert db.latest_point(conn, "reddit.news.comments") is None


def test_backfill_order_interleaves_groups_quietest_first(tmp_path, monkeypatch):
    from tracker.__main__ import backfill_order

    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "o.db"))
    settings, config = Settings.from_env(), load_config()
    reddit = [s for s in config.series if s.platform == "reddit"]
    control = [s for s in reddit if s.tags[0] == "control" and s.key.endswith(".comments")]
    quiet, busy = control[0], control[1]
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        db.upsert_points(conn, busy.key, [(1_000_000, 900.0)])
        db.upsert_points(conn, quiet.key, [(1_000_000, 5.0)])
        order = backfill_order(reddit, conn, 1_000_000 + 3600)
    keys = [s.key for s in order]
    assert len(keys) == len(reddit)
    comments = [s for s in order if s.key.endswith(".comments")]
    assert all(s.key.endswith(".comments") for s in order[:len(comments)])  # comments before posts
    assert comments[0].key == quiet.key  # control group first, quietest community first
    first_round = [s.tags[0] for s in comments[:5]]
    assert len(set(first_round)) == 5  # one community from each group before any group repeats
