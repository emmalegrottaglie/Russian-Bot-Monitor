"""Studies: fixed windows around events, built once and frozen (config/studies.toml).

A rolling chart drifts away from the event it is about as time passes, and its
comparison period moves with it. A study fixes both: the window around the event,
and the reference period every index is measured against. `build` runs the same
analysis the live site uses with "now" set to the window's end, so a study's numbers
do not change as new data arrives. `freeze` stores a build as a numbered version in
studies/<id>/, and the site shows the newest one. Building again is deliberate and
recorded with a note.
"""

from __future__ import annotations

import dataclasses
import json
import statistics
import subprocess
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import analysis, db
from .config import CONFIG_DIR, ROOT, Config

DAY = 86400
STUDIES_DIR = ROOT / "studies"


@dataclass(frozen=True)
class Study:
    id: str
    title: str
    events: tuple[str, ...]
    pre_days: int
    post_days: int
    reference_days: int
    question: str = ""


def load(directory: Path = CONFIG_DIR) -> list[Study]:
    path = directory / "studies.toml"
    if not path.exists():
        return []
    items = tomllib.loads(path.read_text(encoding="utf-8")).get("study", [])
    return [Study(id=s["id"], title=s["title"], events=tuple(s["events"]), pre_days=s.get("pre_days", 14),
                  post_days=s.get("post_days", 14), reference_days=s.get("reference_days", 21),
                  question=s.get("question", "")) for s in items]


def get(study_id: str | None = None, directory: Path = CONFIG_DIR) -> Study | None:
    """The study with this id, or the newest (last) study when no id is given."""
    studies = load(directory)
    if study_id is None:
        return studies[-1] if studies else None
    return next((s for s in studies if s.id == study_id), None)


def frame(study: Study, config: Config) -> dict:
    """Window, phases and reference of a study, as UTC timestamps."""
    events = sorted((e for e in config.events if e.short in study.events), key=lambda e: e.ts)
    missing = set(study.events) - {e.short for e in events}
    if missing:
        raise ValueError(f"study {study.id}: no event named {', '.join(sorted(missing))} in events.toml")
    first, last = events[0].ts // DAY * DAY, events[-1].ts // DAY * DAY
    return {
        "events": events,
        "start": first - study.pre_days * DAY,
        "end": last + (study.post_days + 1) * DAY - 1,
        "event_days": (first, last + DAY - 1),
        "reference": (first - study.reference_days * DAY, first - 1),
    }


def _phase_summary(days: list[int], values: list[float | None], f: dict) -> dict:
    """Mean daily index before, during and after the events, and the range of the
    ordinary days before them (the lowest and highest daily value)."""
    first, last = f["event_days"]
    phases = {"before": [], "during": [], "after": []}
    for d, v in zip(days, values):
        if v is None:
            continue
        phases["before" if d < first else "during" if d <= last else "after"].append(v)
    mean = lambda vs: round(statistics.mean(vs), 1) if vs else None
    before = phases["before"]
    return {
        **{k: mean(vs) for k, vs in phases.items()},
        "days": {k: len(vs) for k, vs in phases.items()},
        "before_range": [round(min(before), 1), round(max(before), 1)] if len(before) >= 3 else None,
    }


def build(conn, config: Config, study: Study, now: int | None = None) -> dict:
    """Every number the study page needs, computed as of the window's end (or as of
    now while the window is still open)."""
    now = now or int(time.time())
    f = frame(study, config)
    as_of = min(now, f["end"])
    cfg = dataclasses.replace(config, events=tuple(f["events"]),
                              reference_start=f["reference"][0], reference_end=f["reference"][1])
    window_days = (as_of - f["start"]) // DAY + 1
    corr = analysis.correlation_view(conn, cfg, as_of, days=window_days - 1)
    aligned = analysis.strike_aligned(conn, cfg, as_of)
    groups = []
    for g in corr["groups"]:
        groups.append({"tag": g["tag"], "members": g["members"], "r": g["r"], "r_days": g["r_days"],
                       **_phase_summary(corr["days"], g["values"], f)})
    order = {t: i for i, t in enumerate(analysis.GROUP_ORDER)}
    groups.sort(key=lambda g: order.get(g["tag"], len(order)))
    return {
        "id": study.id,
        "title": study.title,
        "question": study.question,
        "window": {"start": f["start"], "end": f["end"], "pre_days": study.pre_days, "post_days": study.post_days},
        "event_days": {"start": f["event_days"][0], "end": f["event_days"][1]},
        "reference": {"start": f["reference"][0], "end": f["reference"][1], "days": study.reference_days},
        "events": [e.__dict__ for e in f["events"]],
        "complete": now >= f["end"],
        "as_of": as_of,
        "built_at": now,
        "infra": {**corr["infra"], **_phase_summary(corr["days"], corr["infra"]["values"], f)},
        "days": corr["days"],
        "groups": groups,
        "daily": {g["tag"]: {"values": g["values"], "n": g["n"]} for g in corr["groups"]},
        "aligned": aligned,
    }


def versions(study_id: str) -> list[Path]:
    folder = STUDIES_DIR / study_id
    return sorted(folder.glob("v*.json"), key=lambda p: int(p.stem[1:])) if folder.exists() else []


def latest(study_id: str) -> dict | None:
    """The newest frozen version of a study, or None."""
    found = versions(study_id)
    return json.loads(found[-1].read_text(encoding="utf-8")) if found else None


def _commit() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        return r.stdout.strip() or None
    except OSError:
        return None


def freeze(built: dict, note: str) -> Path:
    """Store a build as the study's next version. A study whose window is still open
    cannot be frozen: its after-period is not complete."""
    if not built["complete"]:
        raise ValueError(f"study {built['id']} is still open: its window ends after the build time")
    n = len(versions(built["id"])) + 1
    path = STUDIES_DIR / built["id"] / f"v{n}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**built, "version": n, "note": note, "commit": _commit()},
                               separators=(",", ":")), encoding="utf-8")
    return path


def current(conn, config: Config, now: int | None = None) -> dict | None:
    """What the site shows: the newest study's latest frozen version, or a provisional
    build of it while none is frozen."""
    study = get()
    if study is None:
        return None
    frozen = latest(study.id)
    if frozen:
        return {**frozen, "provisional": False}
    return {**build(conn, config, study, now), "version": None, "provisional": True}


def listing() -> list[dict]:
    return [{"id": s.id, "title": s.title, "versions": len(versions(s.id))} for s in load()]
