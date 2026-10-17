"""SQLite storage: series metadata, time-series points, collection runs and alerts."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from .config import SeriesSpec

SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    key        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    platform   TEXT NOT NULL,
    label      TEXT NOT NULL,
    unit       TEXT NOT NULL,
    region     TEXT NOT NULL,
    tags       TEXT NOT NULL,   -- JSON array
    active     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS points (
    key   TEXT NOT NULL,
    ts    INTEGER NOT NULL,     -- unix seconds, UTC; value covers the hour ending at ts
    value REAL NOT NULL,
    PRIMARY KEY (key, ts)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS runs (
    id       INTEGER PRIMARY KEY,
    ts       INTEGER NOT NULL,
    platform TEXT NOT NULL,
    ok       INTEGER NOT NULL,
    points   INTEGER NOT NULL,
    error    TEXT
);
CREATE INDEX IF NOT EXISTS runs_platform_ts ON runs (platform, ts);
CREATE TABLE IF NOT EXISTS alerts (
    id      INTEGER PRIMARY KEY,
    ts      INTEGER NOT NULL,
    message TEXT NOT NULL,
    details TEXT NOT NULL,      -- JSON: [{key, label, change, direction}]
    posted  INTEGER NOT NULL DEFAULT 0,
    post_id TEXT,
    error   TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def session(path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init(conn: sqlite3.Connection, specs: Iterable[SeriesSpec]) -> None:
    """Create tables and sync series metadata with the config. Series removed from
    the config are kept (their history stays queryable) but marked inactive."""
    conn.executescript(SCHEMA)
    specs = list(specs)
    conn.execute("UPDATE series SET active = 0")
    conn.executemany(
        """INSERT INTO series (key, kind, platform, label, unit, region, tags, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1)
           ON CONFLICT (key) DO UPDATE SET kind=excluded.kind, platform=excluded.platform,
             label=excluded.label, unit=excluded.unit, region=excluded.region,
             tags=excluded.tags, active=1""",
        [(s.key, s.kind, s.platform, s.label, s.unit, s.region, json.dumps(list(s.tags))) for s in specs],
    )


def upsert_points(conn: sqlite3.Connection, key: str, points: Iterable[tuple[int, float]]) -> int:
    rows = [(key, int(ts), float(v)) for ts, v in points]
    conn.executemany(
        "INSERT INTO points (key, ts, value) VALUES (?, ?, ?) "
        "ON CONFLICT (key, ts) DO UPDATE SET value = excluded.value",
        rows,
    )
    return len(rows)


def replace_hours(conn: sqlite3.Connection, key: str, points: Iterable[tuple[int, float]]) -> int:
    """Store hourly values (stamped at each hour's end) as the only value of their hour.

    For history read from a source that counts every hour exactly (the Reddit archive,
    Bluesky search by hour): any other sample inside a covered hour, such as a live
    estimate taken during that hour, is superseded and removed. Hours not in `points`
    keep whatever they had."""
    points = [(int(ts), float(v)) for ts, v in points]
    conn.executemany("DELETE FROM points WHERE key = ? AND ts > ? AND ts < ?", [(key, ts - 3600, ts) for ts, _ in points])
    return upsert_points(conn, key, points)


def replace_range(conn: sqlite3.Connection, key: str, start: int, end: int,
                  points: Iterable[tuple[int, float]]) -> int:
    """Replace every point of `key` in (start, end] with `points`. Callers pass a complete
    re-collection of that stretch; run inside one transaction (db.session) so a failure
    leaves the old points in place."""
    points = [(int(ts), float(v)) for ts, v in points if start < ts <= end]
    conn.execute("DELETE FROM points WHERE key = ? AND ts > ? AND ts <= ?", (key, start, end))
    return upsert_points(conn, key, points)


def point_range(conn: sqlite3.Connection, key: str) -> tuple[int, int] | None:
    row = conn.execute("SELECT MIN(ts), MAX(ts) FROM points WHERE key = ?", (key,)).fetchone()
    return (row[0], row[1]) if row[0] is not None else None


def record_run(conn: sqlite3.Connection, platform: str, ok: bool, points: int, error: str | None = None) -> None:
    conn.execute(
        "INSERT INTO runs (ts, platform, ok, points, error) VALUES (?, ?, ?, ?, ?)",
        (int(time.time()), platform, int(ok), points, error),
    )


def list_series(conn: sqlite3.Connection, active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM series" + (" WHERE active = 1" if active_only else "") + " ORDER BY kind DESC, key"
    out = []
    for row in conn.execute(sql):
        d = dict(row)
        d["tags"] = json.loads(d["tags"])
        d["active"] = bool(d["active"])
        out.append(d)
    return out


def get_series(conn: sqlite3.Connection, key: str) -> dict | None:
    row = conn.execute("SELECT * FROM series WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    d["active"] = bool(d["active"])
    return d


def points(conn: sqlite3.Connection, key: str, start: int, end: int, bucket: int = 0) -> list[tuple[int, float]]:
    """Points in [start, end]. With bucket > 0, mean per bucket labelled by the bucket's
    start. Points are stamped at the end of what they measure, hence ts - 1."""
    if bucket:
        rows = conn.execute(
            "SELECT ((ts - 1) / ?) * ? AS b, AVG(value) FROM points WHERE key = ? AND ts BETWEEN ? AND ? "
            "GROUP BY b ORDER BY b",
            (bucket, bucket, key, start, end),
        )
    else:
        rows = conn.execute(
            "SELECT ts, value FROM points WHERE key = ? AND ts BETWEEN ? AND ? ORDER BY ts",
            (key, start, end),
        )
    return [(int(t), float(v)) for t, v in rows]


def latest_point(conn: sqlite3.Connection, key: str) -> tuple[int, float] | None:
    row = conn.execute("SELECT ts, value FROM points WHERE key = ? ORDER BY ts DESC LIMIT 1", (key,)).fetchone()
    return (int(row[0]), float(row[1])) if row else None


def last_runs(conn: sqlite3.Connection) -> list[dict]:
    """Most recent run per platform, plus the most recent successful one."""
    rows = conn.execute(
        """SELECT r.platform, r.ts, r.ok, r.points, r.error,
                  (SELECT MAX(ts) FROM runs s WHERE s.platform = r.platform AND s.ok = 1) AS last_ok
           FROM runs r
           WHERE r.id = (SELECT MAX(id) FROM runs x WHERE x.platform = r.platform)
           ORDER BY r.platform"""
    )
    return [dict(r) for r in rows]


def add_alert(conn: sqlite3.Connection, ts: int, message: str, details: list[dict]) -> int:
    cur = conn.execute(
        "INSERT INTO alerts (ts, message, details) VALUES (?, ?, ?)", (ts, message, json.dumps(details))
    )
    return int(cur.lastrowid)


def mark_alert(conn: sqlite3.Connection, alert_id: int, posted: bool, post_id: str | None, error: str | None) -> None:
    conn.execute(
        "UPDATE alerts SET posted = ?, post_id = ?, error = ? WHERE id = ?", (int(posted), post_id, error, alert_id)
    )


def recent_alerts(conn: sqlite3.Connection, since: int = 0, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM alerts WHERE ts >= ? ORDER BY ts DESC, id DESC LIMIT ?", (since, limit)
    )
    out = []
    for r in rows:
        d = dict(r)
        d["details"] = json.loads(d["details"])
        d["posted"] = bool(d["posted"])
        out.append(d)
    return out


def posts_since(conn: sqlite3.Connection, since: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM alerts WHERE posted = 1 AND ts >= ?", (since,)).fetchone()[0]
