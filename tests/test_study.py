import json
from datetime import datetime, timezone

import pytest

from tracker import db, study
from tracker.config import Settings, load_config

D = 86400
REF = "ioda.asn200350.ping-slash24"


def test_strikes_study_window_and_reference():
    config = load_config()
    s = study.get("strikes-2026-10")
    f = study.frame(s, config)
    day = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
    # The first strike (Sasovo) is at 23:30 UTC on 7 October, so its UTC day is the 7th.
    assert (day(f["start"]), day(f["end"])) == ("2026-09-23", "2026-10-25")
    assert (day(f["reference"][0]), day(f["reference"][1])) == ("2026-09-16", "2026-10-06")
    assert [e.short for e in f["events"]] == ["SASOVO", "KALUGA", "VLADIMIR"]


def test_phase_summary_splits_before_during_after():
    s = study.Study(id="t", title="t", events=("A",), pre_days=3, post_days=3, reference_days=21)
    f = {"event_days": (10 * D, 11 * D - 1)}
    days = [d * D for d in range(7, 15)]
    out = study._phase_summary(days, [100, 90, 110, 50, 120, None, 130, 140], f)
    assert (out["before"], out["during"], out["after"]) == (100.0, 50.0, 130.0)
    assert out["days"] == {"before": 3, "during": 1, "after": 3} and out["before_range"] == [90, 110]


@pytest.fixture
def frozen_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(study, "STUDIES_DIR", tmp_path / "studies")
    return tmp_path / "studies"


def test_freeze_numbers_versions_and_refuses_open_windows(frozen_dir):
    with pytest.raises(ValueError):
        study.freeze({"id": "x", "complete": False}, "too early")
    study.freeze({"id": "x", "complete": True, "groups": []}, "first")
    path = study.freeze({"id": "x", "complete": True, "groups": [1]}, "second")
    assert path.name == "v2.json"
    latest = study.latest("x")
    assert latest["version"] == 2 and latest["note"] == "second" and latest["groups"] == [1]


def test_build_is_fixed_at_the_window_end(tmp_path, monkeypatch, frozen_dir):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "s.db"))
    settings, config = Settings.from_env(), load_config()
    s = study.get("strikes-2026-10")
    f = study.frame(s, config)
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        db.upsert_points(conn, REF, [(t, 500.0 if t < f["event_days"][0] else 100.0)
                                     for t in range(f["reference"][0], f["end"] + 10 * D, 3600)])
        built = study.build(conn, config, s, now=f["end"] + 10 * D)
        later = study.build(conn, config, s, now=f["end"] + 40 * D)
    assert built["complete"] and built["as_of"] == f["end"]
    assert built["infra"]["before"] == pytest.approx(100, abs=1) and built["infra"]["after"] == pytest.approx(20, abs=1)
    assert json.dumps(built["infra"]) == json.dumps(later["infra"])  # new days do not move a closed study
    assert built["days"][0] == f["start"] and built["days"][-1] == f["end"] - D + 1



def test_open_study_adds_a_sourced_event_and_a_study(tmp_path):
    for name in ("events.toml", "studies.toml", "sources.toml"):
        (tmp_path / name).write_text((study.CONFIG_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    event = {"date": "2026-11-20", "short": "recovery", "label": "Yandex Cloud back", "status": "confirmed",
             "source": "IODA, measured by this tracker"}
    sid = study.open_study(event, "Did it change?", tmp_path)
    assert sid == "recovery-2026-11-20" and study.get(directory=tmp_path).id == sid
    assert study.open_study(event, "Did it change?", tmp_path) == sid  # running it twice adds nothing
    config = load_config(tmp_path)
    assert [e.short for e in study.frame(study.get(directory=tmp_path), config)["events"]] == ["RECOVERY"]
    assert config.events[-1].status == "confirmed" and config.events[-1].source == "IODA, measured by this tracker"
    later = study.open_study({**event, "date": "2027-01-05"}, "Again?", tmp_path)
    assert study.get(later, tmp_path).events == ("RECOVERY 01-05",)  # shorts stay unique
    with pytest.raises(ValueError):
        study.open_study({**event, "source": ""}, "No source", tmp_path)


def test_close_if_done_waits_for_the_after_period(tmp_path, monkeypatch, frozen_dir):
    monkeypatch.setenv("TRACKER_DB", str(tmp_path / "s.db"))
    settings, config = Settings.from_env(), load_config()
    s = study.get()
    end = study.frame(s, config)["end"]
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)
        assert study.close_if_done(conn, config, now=end + D) is None  # the archive is still behind
        assert study.close_if_done(conn, config, now=end + 4 * D)["id"] == s.id
        assert study.latest(s.id)["note"].startswith("Frozen automatically")
        assert study.close_if_done(conn, config, now=end + 5 * D) is None  # frozen already
