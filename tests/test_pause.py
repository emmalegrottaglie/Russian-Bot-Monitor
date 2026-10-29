import time

import pytest
from fastapi.testclient import TestClient

from tracker import collectors, db, pause
from tracker.api import create_app
from tracker.config import Settings, load_config

D, H = 86400, 3600
REF = "ioda.asn200350.ping-slash24"


def test_resumes_only_after_enough_complete_days_at_the_level():
    assert pause.should_resume([(0, 50.0), (D, 61.0)])
    assert not pause.should_resume([(0, 49.9), (D, 80.0)])
    assert not pause.should_resume([(D, 80.0)])  # a day without data never counts as recovered
    assert not pause.should_resume([])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "p.db"))
    settings, config = Settings.from_env(), load_config()
    calls = {"tasks": [], "gap": []}
    monkeypatch.setattr(pause, "_set_tasks", lambda enabled: calls["tasks"].append(enabled) or [])
    monkeypatch.setattr(pause, "fill_gap", lambda config, settings, start: calls["gap"].append(start))

    async def no_network(*args, **kwargs):
        return {}
    monkeypatch.setattr(collectors, "run", no_network)
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        db.upsert_points(conn, REF, [(t, 500.0) for t in range(config.reference_start,
                                                               config.reference_start + 3 * D, H)])
    return settings, config, calls


def _recent(settings, value: float, now: int) -> None:
    today = now - now % D
    with db.session(settings.db_path) as conn:
        db.upsert_points(conn, REF, [(today - d * D + h * H, value) for d in (1, 2) for h in range(1, 25)])


def test_watch_does_nothing_while_collecting(setup):
    settings, config, calls = setup
    assert pause.watch(config, settings) == "not paused"
    assert calls == {"tasks": [], "gap": []}


def test_watch_stays_paused_below_the_level(setup):
    settings, config, calls = setup
    now = int(time.time())
    pause.pause(settings, "No news.", now - 5 * D)
    _recent(settings, 150.0, now)  # 30% of the pre-strike level
    assert pause.watch(config, settings, now).startswith("still paused")
    assert pause.state(settings) is not None and calls["tasks"] == [False]


def test_watch_resumes_and_fills_the_gap(setup):
    settings, config, calls = setup
    now = int(time.time())
    since = now - 5 * D
    pause.pause(settings, "No news.", since)
    _recent(settings, 300.0, now)  # 60%
    assert pause.watch(config, settings, now).startswith("resumed")
    assert pause.state(settings) is None
    assert calls["tasks"] == [False, True]
    assert calls["gap"] == [since - pause.GAP_MARGIN_DAYS * D]
    with db.session(settings.db_path) as conn:
        assert "Collection resumed" in db.recent_alerts(conn, limit=1)[0]["message"]


def test_snapshot_says_when_collection_is_paused(setup):
    settings, config, _ = setup
    with TestClient(create_app(config, settings)) as c:
        assert c.get("/api/snapshot").json()["paused"] is None
        pause.pause(settings, "No news.")
        assert c.get("/api/snapshot").json()["paused"]["reason"] == "No news."
