"""Detect sharp moves in the snapshot and log (and optionally post) one alert.

An alert fires when
- an infrastructure series moves at least INFRA_THRESHOLD against its 7-day
  same-hour baseline, or
- the median of a community tag group (at least MIN_GROUP series) moves at least
  GROUP_THRESHOLD,
and the same series/group has not alerted in the same direction within COOLDOWN.
Every alert quotes the control group so readers can see whether the move is
specific to political communities.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone

import httpx

from . import db, x_api

log = logging.getLogger(__name__)

INFRA_THRESHOLD = 0.25
GROUP_THRESHOLD = 0.30
MIN_GROUP = 3
COOLDOWN = 12 * 3600
MAX_LEN = 280


def _pct(x: float) -> str:
    return f"{x * 100:+.0f}%".replace("-", "−")


def detect(snap: dict) -> list[dict]:
    hits = []
    for s in snap["series"]:
        c = s["change_7d"]
        if s["kind"] == "infrastructure" and s["fresh"] and c is not None and abs(c) >= INFRA_THRESHOLD:
            hits.append({"key": s["key"], "label": f"{s['label']} {s['unit'].lower()}", "change": c})
    for g in snap["groups"]:
        c = g["change_7d"]
        if g["tag"] != "control" and g["n_7d"] >= MIN_GROUP and c is not None and abs(c) >= GROUP_THRESHOLD:
            hits.append({"key": f"group:{g['tag']}", "label": f"{g['tag']} communities (median of {g['n_7d']})",
                         "change": c})
    for h in hits:
        h["direction"] = "down" if h["change"] < 0 else "up"
    return hits


def not_in_cooldown(hits: list[dict], recent: list[dict]) -> list[dict]:
    seen = {(d["key"], d["direction"]) for a in recent for d in a["details"]}
    return [h for h in hits if (h["key"], h["direction"]) not in seen]


def compose(hits: list[dict], snap: dict, url: str = "") -> str:
    stamp = datetime.fromtimestamp(snap["now"], timezone.utc).strftime("%H:%M UTC")
    head = f"BOT TRAFFIC MONITOR · {stamp}"
    body = [f"{'▼' if h['direction'] == 'down' else '▲'} {h['label']} {_pct(h['change'])} vs 7-day baseline"
            for h in hits]
    control = next((g for g in snap["groups"] if g["tag"] == "control"), None)
    tail = [f"Control communities {_pct(control['change_7d'])}"
            if control and control["change_7d"] is not None else "Control communities: no baseline yet",
            "Correlation, not proof of cause."]
    if url:
        tail.append(url)
    while True:
        text = "\n".join([head, *body, *tail])
        if len(text) <= MAX_LEN or len(body) <= 1:
            return text[:MAX_LEN]
        body.pop()


async def run(conn: sqlite3.Connection, snap: dict, settings, include_url: bool = False) -> dict | None:
    now = snap["now"]
    hits = not_in_cooldown(detect(snap), db.recent_alerts(conn, since=now - COOLDOWN))
    if not hits:
        return None
    text = compose(hits, snap, settings.public_url if include_url else "")
    details = [{k: h[k] for k in ("key", "label", "change", "direction")} for h in hits]
    alert_id = db.add_alert(conn, now, text, details)
    conn.commit()
    log.info("alert %d: %s", alert_id, text.replace("\n", " | "))

    if not (settings.post_alerts and settings.x_configured):
        return {"id": alert_id, "message": text, "posted": False}
    if db.posts_since(conn, int(time.time()) - 86400) >= settings.max_posts_per_day:
        db.mark_alert(conn, alert_id, False, None, "daily post cap reached")
        return {"id": alert_id, "message": text, "posted": False}
    try:
        post_id = await x_api.post(settings, text)
    except httpx.HTTPError as e:
        body = getattr(getattr(e, "response", None), "text", "")
        db.mark_alert(conn, alert_id, False, None, f"{e} {body[:300]}")
        log.error("posting alert %d failed: %s", alert_id, e)
        return {"id": alert_id, "message": text, "posted": False}
    db.mark_alert(conn, alert_id, True, post_id, None)
    return {"id": alert_id, "message": text, "posted": True}
