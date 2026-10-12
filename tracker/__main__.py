"""Command line: python -m tracker {serve,collect,backfill,report,publish}"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import time

from . import alerts, analysis, collectors, db, report, static
from .config import Settings, load_config


def collect_once(config, settings) -> None:
    """One collection pass, then the alert check and today's report if missing."""
    asyncio.run(collectors.run(config, settings))
    with db.session(settings.db_path) as conn:
        snap = analysis.snapshot(conn, config, int(time.time()))
        asyncio.run(alerts.run(conn, snap, settings))
        report.ensure_today(conn, config, settings, int(time.time()))


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

    sub.add_parser("report", help="build (or rebuild) today's shareable report under <db dir>/reports/")

    p = sub.add_parser("publish", help="export a static copy of the site and push it to GitHub Pages")
    p.add_argument("--collect", action="store_true", help="run a collection pass (and alerts, daily report) first")
    p.add_argument("--remote", help="git remote URL to push to (default: this repo's origin)")
    p.add_argument("--branch", default="gh-pages")
    p.add_argument("--no-push", action="store_true", help="only write the static site to <db dir>/site")

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
    elif args.cmd == "backfill":
        platforms = tuple(args.platform or collectors.BACKFILL)
        start = int(time.time()) - args.days * 86400
        if args.missing_only:
            with db.session(settings.db_path) as conn:
                done = {s.key for s in config.series
                        if db.points(conn, s.key, 0, start + 2 * 86400)}
            config = dataclasses.replace(config, series=tuple(s for s in config.series if s.key not in done))
            logging.info("skipping %d series that are already backfilled", len(done))
        # Primary series first (Reddit comments), so a partial run already covers the main metric.
        config = dataclasses.replace(config, series=tuple(sorted(config.series, key=lambda s: s.key.endswith(".posts"))))
        asyncio.run(collectors.run(config, settings, platforms=platforms, start=start, backfill=True))


if __name__ == "__main__":
    main()
