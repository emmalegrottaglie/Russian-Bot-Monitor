"""Prototype: coordination-like and new-account shares of a Bluesky keyword, per hour.

Reads every public post matching a keyword over a period, computes hourly totals in
memory, and writes only those totals. Post text and account identifiers are held in
memory while a keyword is processed and are never written or logged. Method and
sources: docs/BOT-SIGNALS.md.

    python -m research.coordination fetch --query MAGA --lang en --from 2026-09-20 --to 2026-10-18
    python -m research.coordination analyze

Not part of the site: results go to data/research/ only.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from tracker.collectors import bluesky
from tracker.config import load_config

HOUR = 3600
DAY = 86400
LIMIT = 100  # the most one unauthenticated search returns
MIN_SPLIT = 60  # seconds: a window this short that still fills a page is recorded as incomplete
WINDOWS = (10, 30, 60)  # coordination windows in seconds, all computed in one pass (docs/BOT-SIGNALS.md)
SIMILARITY = 0.7  # Jaccard similarity of character 5-grams for "near-identical"
MIN_ACCOUNTS = 3  # distinct accounts for a cluster to count
MIN_CHARS = 20  # shorter normalised texts (a bare hashtag, "MAGA") match too easily to mean anything
NEW_ACCOUNT_DAYS = 30
MEASURES = ("coord10", "coord30", "coord60", "new_accounts", "no_avatar")
OUT = Path(__file__).resolve().parent.parent / "data" / "research"
DELAY = 0.35

_URL = re.compile(r"https?://\S+|www\.\S+")
_MENTION = re.compile(r"@[\w.-]+")
_PUNCT = re.compile(r"[^\w\s]")


def normalise(text: str) -> str:
    """Lower case, without links, mentions or punctuation, single spaces."""
    t = _MENTION.sub(" ", _URL.sub(" ", text.lower()))
    return " ".join(_PUNCT.sub(" ", t).split())


def _grams(text: str, k: int = 5) -> frozenset[str]:
    return frozenset(text[i:i + k] for i in range(max(1, len(text) - k + 1)))


def similar(a: tuple[str, frozenset], b: tuple[str, frozenset]) -> bool:
    if a[0] == b[0]:
        return True
    inter = len(a[1] & b[1])
    return inter / (len(a[1]) + len(b[1]) - inter) >= SIMILARITY


def coordinated(posts: list[dict], window: int) -> set[int]:
    """Indices of posts in near-identical clusters spanning at least MIN_ACCOUNTS accounts.

    Two posts are linked when they come from different accounts, are at most `window`
    seconds apart and their normalised texts are near-identical. Linked posts form a
    cluster (union-find)."""
    order = sorted(range(len(posts)), key=lambda i: posts[i]["ts"])
    parent = list(range(len(posts)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    keys = [(p["norm"], _grams(p["norm"])) if len(p["norm"]) >= MIN_CHARS else None for p in posts]
    lo = 0
    for pos, i in enumerate(order):
        while posts[i]["ts"] - posts[order[lo]]["ts"] > window:
            lo += 1
        if keys[i] is None:
            continue
        for j in order[lo:pos]:
            if keys[j] is not None and posts[j]["author"] != posts[i]["author"] and similar(keys[i], keys[j]):
                parent[find(i)] = find(j)
    members: dict[int, list[int]] = {}
    for i in range(len(posts)):
        members.setdefault(find(i), []).append(i)
    out: set[int] = set()
    for group in members.values():
        if len({posts[i]["author"] for i in group}) >= MIN_ACCOUNTS:
            out.update(group)
    return out


def hourly(posts: list[dict], incomplete: set[int]) -> list[list]:
    """[[hour_end, posts, coord10, coord30, coord60, new_accounts, no_avatar, complete], ...]

    Hours are stamped at their end, like every series in the tracker."""
    flagged = {w: coordinated(posts, w) for w in WINDOWS}
    rows: dict[int, list] = {}
    for i, p in enumerate(posts):
        end = (p["ts"] - 1) // HOUR * HOUR + HOUR
        r = rows.setdefault(end, [end, 0, 0, 0, 0, 0, 0, True])
        r[1] += 1
        for k, w in enumerate(WINDOWS):
            r[2 + k] += i in flagged[w]
        r[5] += p["author_created"] is not None and p["ts"] - p["author_created"] < NEW_ACCOUNT_DAYS * DAY
        r[6] += not p["avatar"]
    for end in incomplete:
        rows.setdefault(end, [end, 0, 0, 0, 0, 0, 0, True])[7] = False
    return [rows[k] for k in sorted(rows)]


def _ts(stamp: str | None) -> int | None:
    if not stamp:
        return None
    t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return int((t if t.tzinfo else t.replace(tzinfo=timezone.utc)).timestamp())


def _search(client: httpx.Client, q: str, lang: str, a: int, b: int) -> list[dict]:
    params = {"q": q, "sort": "latest", "limit": LIMIT, "since": bluesky._iso(a), "until": bluesky._iso(b)}
    if lang:
        params["lang"] = lang
    for wait in (5, 30, 90, None):
        try:
            r = client.get(bluesky.URL, params=params)
            r.raise_for_status()
            time.sleep(DELAY)
            return r.json().get("posts") or []
        except httpx.HTTPError:
            if wait is None:
                raise
            time.sleep(wait)
    return []


def fetch(client: httpx.Client, q: str, lang: str, start: int, end: int) -> tuple[list[dict], set[int], list[int]]:
    """Every post in [start, end): hour windows are split in half until each holds fewer
    than LIMIT posts. Returns (posts, hour ends whose count is incomplete, hour ends that failed)."""
    posts: list[dict] = []
    incomplete: set[int] = set()
    failed: list[int] = []
    seen: set[str] = set()

    def walk(a: int, b: int) -> None:
        got = _search(client, q, lang, a, b)
        if len(got) >= LIMIT and b - a > MIN_SPLIT:
            mid = (a + b) // 2
            walk(a, mid)
            walk(mid, b)
            return
        if len(got) >= LIMIT:
            incomplete.add((a // HOUR) * HOUR + HOUR)
        for p in got:
            if p["uri"] in seen:
                continue
            seen.add(p["uri"])
            ts = _ts(p.get("indexedAt"))
            if ts is None or not a <= ts < b:
                continue
            posts.append({
                "ts": ts,
                "author": p["author"]["did"],  # in memory only, to tell accounts apart
                "norm": normalise((p.get("record") or {}).get("text", "")),
                "author_created": _ts(p["author"].get("createdAt")),
                "avatar": bool(p["author"].get("avatar")),
            })

    for h in range(start, end, HOUR):
        try:
            walk(h, h + HOUR)
        except httpx.HTTPError as e:
            failed.append(h + HOUR)
            print(f"{q} {bluesky._iso(h)}: failed, left as a gap ({type(e).__name__})", file=sys.stderr)
        if (h - start) % DAY == 0:
            print(f"{q} {lang}: {bluesky._iso(h)[:10]}, {len(posts)} posts so far", file=sys.stderr, flush=True)
    return posts, incomplete, failed


def _day(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


def cmd_fetch(args) -> None:
    start, end = _day(args.start), _day(args.end)
    with httpx.Client(timeout=45, headers={"User-Agent": "bot-traffic-monitor/0.1 (research; read-only)"}) as client:
        posts, incomplete, failed = fetch(client, args.query, args.lang, start, end)
    rows = hourly(posts, incomplete)
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"coordination-{re.sub(r'[^a-z0-9]+', '-', args.query.lower()).strip('-')}-{args.lang or 'all'}.json"
    meta = {"query": args.query, "lang": args.lang, "start": start, "end": end, "windows": WINDOWS,
            "similarity": SIMILARITY, "min_accounts": MIN_ACCOUNTS, "min_chars": MIN_CHARS,
            "new_account_days": NEW_ACCOUNT_DAYS, "failed_hours": failed,
            "columns": ["hour_end", "posts", "coord10", "coord30", "coord60", "new_accounts", "no_avatar", "complete"]}
    (OUT / name).write_text(json.dumps({**meta, "hours": rows}), encoding="utf-8")
    print(f"wrote {OUT / name}: {len(rows)} hours, {sum(r[1] for r in rows)} posts, "
          f"{len(incomplete)} incomplete hours, {len(failed)} failed hours")


def shares(rows: list[list], a: int, b: int) -> dict[str, float | int | None]:
    """Share of posts in (a, b] per measure over complete hours, plus the raw counts."""
    sel = [r for r in rows if a < r[0] <= b and r[7]]
    total = sum(r[1] for r in sel)
    out: dict[str, float | int | None] = {"posts": total}
    for k, n in enumerate(MEASURES):
        count = sum(r[2 + k] for r in sel)
        out[n] = count / total if total else None
        out[n + "_n"] = count
    return out


def percentile(value: float, others: list[float]) -> float | None:
    """Mid-rank percentile of `value` among `others` (ties count half): 50 = typical, low = unusually low."""
    if value is None or not others:
        return None
    below = sum(v < value for v in others)
    ties = sum(v == value for v in others)
    return 100 * (below + ties / 2) / len(others)


def cmd_analyze(args) -> None:
    """For each keyword file: shares before, during and after the strikes, and where the
    strike-window share falls among same-length windows starting on pre-strike days."""
    config = load_config()
    strikes = sorted(e.ts for e in config.events)
    s0, s1 = strikes[0] // DAY * DAY, strikes[-1] // DAY * DAY + DAY
    span = s1 - s0
    fmt = lambda x: "-" if x is None else f"{100 * x:5.2f}%"
    for f in sorted(OUT.glob("coordination-*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rows = d["hours"]
        pre, during, post = shares(rows, d["start"], s0), shares(rows, s0, s1), shares(rows, s1, d["end"])
        placebo = [shares(rows, t, t + span) for t in range(d["start"], s0 - span + 1, DAY)]
        print(f"\n{d['query']} ({d['lang']}): {pre['posts']} posts before, {during['posts']} during, {post['posts']} after;"
              f" {len(placebo)} pre-strike windows of {span // DAY} days to compare")
        for m in MEASURES:
            pct = percentile(during[m], [p[m] for p in placebo if p[m] is not None])
            print(f"  {m:13} before {fmt(pre[m])} ({pre[m + '_n']})  strikes {fmt(during[m])} ({during[m + '_n']})"
                  f"  after {fmt(post[m])} ({post[m + '_n']})  | strike window at percentile {'-' if pct is None else round(pct)}")


def cmd_show(args) -> None:
    """Print the near-identical clusters in a window to the terminal, for a manual check
    of what they are. Shows text only (no handles or IDs) and writes nothing; do not
    redirect this output to a file."""
    start, end = _ts(args.start), _ts(args.end)
    with httpx.Client(timeout=45, headers={"User-Agent": "bot-traffic-monitor/0.1 (research; read-only)"}) as client:
        posts, _, _ = fetch(client, args.query, args.lang, start, end)
    flagged = coordinated(posts, args.window)
    groups: dict[str, list[dict]] = {}
    for i in sorted(flagged, key=lambda i: posts[i]["ts"]):
        groups.setdefault(posts[i]["norm"][:60], []).append(posts[i])
    for k, (key, ps) in enumerate(groups.items(), 1):
        accounts = len({p["author"] for p in ps})
        new = sum(p["author_created"] is not None and p["ts"] - p["author_created"] < NEW_ACCOUNT_DAYS * DAY for p in ps)
        print(f"{k}. {len(ps)} posts, {accounts} accounts, {new} from new accounts, "
              f"{bluesky._iso(ps[0]['ts'])}: {ps[0]['norm'][:180]}")


def main() -> None:
    p = argparse.ArgumentParser(prog="research.coordination")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--query", required=True)
    f.add_argument("--lang", default="")
    f.add_argument("--from", dest="start", required=True, help="UTC date, inclusive")
    f.add_argument("--to", dest="end", required=True, help="UTC date, exclusive")
    sub.add_parser("analyze")
    sh = sub.add_parser("show", help="print clustered texts in a window to the terminal (not saved)")
    sh.add_argument("--query", required=True)
    sh.add_argument("--lang", default="")
    sh.add_argument("--from", dest="start", required=True, help="UTC time, e.g. 2026-10-01T12:00")
    sh.add_argument("--to", dest="end", required=True)
    sh.add_argument("--window", type=int, default=60)
    args = p.parse_args()
    {"fetch": cmd_fetch, "analyze": cmd_analyze, "show": cmd_show}[args.cmd](args)


if __name__ == "__main__":
    main()
