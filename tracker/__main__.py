"""Command line: python -m tracker {serve,collect,backfill,refetch,report,publish,pause,resume,watch,study}"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import time
from datetime import datetime, timezone

from . import alerts, analysis, collectors, db, pause, report, static, study
from .config import Settings, load_config


def backfill_order(series, conn, now: int) -> list:
    """Order for a backfill: infrastructure first, then comments (the main metric) before
    posts. Within each, take one community per group in turn, starting with the control
    group, so every group reaches the two communities its median needs early instead of
    one group finishing at a time. Within a group the quietest community goes first (by
    its recent live rate): small ones load in minutes."""
    def rate(spec) -> float:
        pts = db.points(conn, spec.key, now - 3 * 86400, now)
        return sum(v for _, v in pts) / len(pts) if pts else float("inf")

    out = [s for s in series if s.kind != "community"]
    rotation = ["control"] + [t for t in analysis.GROUP_ORDER if t != "control"]
    for posts in (False, True):
        queues: dict[str, list] = {}
        for spec in sorted((s for s in series if s.kind == "community" and s.key.endswith(".posts") == posts), key=rate):
            queues.setdefault(spec.tags[0] if spec.tags else "", []).append(spec)
        order = [t for t in rotation if t in queues] + [t for t in queues if t not in rotation]
        while any(queues.values()):
            for tag in order:
                if queues[tag]:
                    out.append(queues[tag].pop(0))
    return out


def collect_once(config, settings) -> None:
    """One collection pass, then the alert check and today's report if missing."""
    asyncio.run(collectors.run(config, settings))
    with db.session(settings.db_path) as conn:
        snap = analysis.snapshot(conn, config, int(time.time()))
        asyncio.run(alerts.run(conn, snap, settings))
        report.ensure_today(conn, config, settings, int(time.time()))
    closed = pause.close_study(config, settings)
    if closed:
        logging.info(closed)


def main() -> None:
    parser = argparse.ArgumentParser(prog="tracker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("serve", help="API + website, with the collection loop unless --no-collect")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-collect", action="store_true")

    sub.add_parser("collect", help="one collection pass, then alert check (for cron)")

    p = sub.add_parser("backfill", help="load history from IODA, Cloudflare Radar and Arctic Shift")
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--platform", action="append", choices=sorted(collectors.BACKFILL),
                   help="limit to one platform (repeatable)")
    p.add_argument("--missing-only", action="store_true",
                   help="skip series that already reach back to the start date (resume an interrupted run)")

    p = sub.add_parser("refetch", help="collect stored history again from its source and replace it (for repairs)")
    p.add_argument("--platform", action="append", required=True, choices=sorted(collectors.BACKFILL))
    p.add_argument("--series", action="append", help="limit to these series keys (repeatable)")
    p.add_argument("--from", dest="start", help="UTC date or time to start at (default: each series' first point)")
    p.add_argument("--to", dest="end", help="UTC date or time to end at (default: now)")

    sub.add_parser("report", help="build (or rebuild) today's shareable report under <db dir>/reports/")

    p = sub.add_parser("publish", help="export a static copy of the site and push it to GitHub Pages")
    p.add_argument("--collect", action="store_true", help="run a collection pass (and alerts, daily report) first")
    p.add_argument("--remote", help="git remote URL to push to (default: this repo's origin)")
    p.add_argument("--branch", default="gh-pages")
    p.add_argument("--no-push", action="store_true", help="only write the static site to <db dir>/site")

    p = sub.add_parser("pause", help="stop collecting until Yandex Cloud recovers (see tracker/pause.py)")
    p.add_argument("--reason", required=True, help="shown on the site")
    p = sub.add_parser("resume", help="collect again and fill the paused period from history")
    p.add_argument("--reason", required=True, help="recorded as an alert")
    p.add_argument("--event-date", help="open a study around this event (UTC date, YYYY-MM-DD); "
                                        "needs --event-short, --event-label and --event-source")
    p.add_argument("--event-short", help="chart label for the event, e.g. STRIKE")
    p.add_argument("--event-label", help="one line describing the event")
    p.add_argument("--event-source", help="who reported it, with the date and URL")
    p.add_argument("--event-status", default="reported", choices=["reported", "confirmed"])
    sub.add_parser("watch", help="daily check while paused: refresh Yandex data, resume if it has recovered")

    p = sub.add_parser("study", help="build a study (a fixed window around an event, config/studies.toml)")
    p.add_argument("action", choices=["build", "list"])
    p.add_argument("id", nargs="?", help="study id (default: the newest study)")
    p.add_argument("--freeze", action="store_true", help="store the build as the study's next version")
    p.add_argument("--note", default="", help="what this version changes (required with --freeze)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config, settings = load_config(), Settings.from_env()
    with db.session(settings.db_path) as conn:
        db.init(conn, config.series)

    if args.cmd == "serve":
        import uvicorn

        from .api import create_app
        uvicorn.run(create_app(config, settings, collect=not args.no_collect), host=args.host, port=args.port)
    elif args.cmd == "collect":
        collect_once(config, settings)
    elif args.cmd == "report":
        with db.session(settings.db_path) as conn:
            print(report.write(conn, config, settings, int(time.time())))
    elif args.cmd == "publish":
        if args.collect:
            collect_once(config, settings)
        out = settings.db_path.parent / "site"
        with db.session(settings.db_path) as conn:
            static.export(conn, config, settings, out)
        if not args.no_push:
            static.push(out, args.remote or static.default_remote(), args.branch)
    elif args.cmd == "pause":
        print(pause.pause(settings, args.reason))
    elif args.cmd == "resume":
        if pause.state(settings) is None:
            parser.error("collection is not paused")
        event = None
        if args.event_date or args.event_short or args.event_label or args.event_source:
            event = {"date": args.event_date, "short": args.event_short, "label": args.event_label,
                     "source": args.event_source, "status": args.event_status}
            missing = [k for k, v in event.items() if not v]
            if missing:
                parser.error("an event needs " + ", ".join(f"--event-{k}" for k in missing))
        opened = pause.resume(config, settings, args.reason, event=event)
        if opened:
            print(f"opened study {opened}")
    elif args.cmd == "watch":
        print(pause.watch(config, settings))
    elif args.cmd == "study":
        if args.action == "list":
            for s in study.listing():
                print(f"{s['id']}: {s['title']} ({s['versions']} frozen versions)")
            return
        chosen = study.get(args.id)
        if chosen is None:
            parser.error(f"no study {args.id!r} in config/studies.toml")
        if args.freeze and not args.note:
            parser.error("--freeze needs --note saying what this version is or changes")
        with db.session(settings.db_path) as conn:
            built = study.build(conn, config, chosen)
        print(f"{chosen.id}: {len(built['groups'])} groups, {'complete' if built['complete'] else 'window still open'}")
        for g in built["groups"]:
            print(f"  {g['tag']:16} before {g['before']}  during {g['during']}  after {g['after']}  "
                  f"(days {g['days']['before']}/{g['days']['during']}/{g['days']['after']}, range before {g['before_range']})")
        i = built["infra"]
        print(f"  Yandex Cloud     before {i['before']}  during {i['during']}  after {i['after']}")
        if args.freeze:
            print(f"frozen: {study.freeze(built, args.note)}")
    elif args.cmd == "backfill":
        platforms = tuple(args.platform or collectors.BACKFILL)
        start = int(time.time()) - args.days * 86400
        if args.missing_only:
            with db.session(settings.db_path) as conn:
                done = {s.key for s in config.series
                        if db.points(conn, s.key, 0, start + 2 * 86400)}
            config = dataclasses.replace(config, series=tuple(s for s in config.series if s.key not in done))
            logging.info("skipping %d series that are already backfilled", len(done))
        with db.session(settings.db_path) as conn:
            ordered = backfill_order(config.series, conn, int(time.time()))
        config = dataclasses.replace(config, series=tuple(ordered))
        asyncio.run(collectors.run(config, settings, platforms=platforms, start=start, backfill=True))
    elif args.cmd == "refetch":
        unknown = set(args.series or ()) - {s.key for s in config.series}
        if unknown:
            parser.error(f"unknown series: {', '.join(sorted(unknown))}")
        now = int(time.time())
        windows = {}
        with db.session(settings.db_path) as conn:
            for s in config.series:
                if s.platform not in args.platform or args.series and s.key not in args.series:
                    continue
                stored = db.point_range(conn, s.key)
                if stored is None:
                    continue
                # Start a day before the first point so the bin or hour it closes is re-read too.
                start = _utc(args.start) if args.start else stored[0] - 86400
                windows[s.key] = (start, _utc(args.end) if args.end else now)
        for key, outcome in asyncio.run(collectors.refetch(config, settings, windows)).items():
            print(f"{key}: {outcome}")


def _utc(text: str) -> int:
    t = datetime.fromisoformat(text)
    return int((t if t.tzinfo else t.replace(tzinfo=timezone.utc)).timestamp())


if __name__ == "__main__":
    main()
