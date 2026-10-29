# Bot Traffic Monitor

An open dashboard for one question: **when Yandex data centres go offline, does activity in online political communities change, and does it change more than in non-political ones?**

In October 2026, reported strikes on Yandex data centres (Sasovo on Oct 8, Kaluga on Oct 9, Vladimir on Oct 11) coincided with sharp drops in Yandex Cloud reachability. In the same days, people reported lower activity in political subreddits and right-wing social media. This project records both kinds of signal side by side, keeps the history, and makes it downloadable, so the claim can be checked rather than repeated.

It collects data on its own every 15 minutes and logs an alert when a signal moves sharply. It can also post those alerts to an Twitter account.

**Live site: <https://emmalegrottaglie.github.io/Russian-Bot-Monitor/>**. This is a static snapshot, refreshed about every 30 minutes; see [Deploying](#deploying).

## What we have found so far

As of 21 October 2026. The Reddit history is still being backfilled, so these are first results, not conclusions.

- **No drop in right-wing activity after the strikes.** In the 48 hours after the strikes, the right-wing Reddit communities ran above their normal range in 37 of 49 hours, while the non-political control group ran below its range in 38 ([docs/CHARTS.md](docs/CHARTS.md)). Bluesky and Twitter searches show no drop either.
- **The r/theydidthemath post did not find a drop either.** Its headline was 90 of 968 subreddits declining after all three strikes, but the author found none of them held across every timing check and called it an exploratory screen, not a test. In its own data about 45% of subreddits declined at each strike, so about 95 would decline at all three by chance, and 77 rose at all three ([docs/SYFTEN-CHECK.md](docs/SYFTEN-CHECK.md)).
- **Independent checks agree.** Graphika (via Texty), Cloudflare and Lawfare each found no measured drop in political activity ([docs/DROP-CLAIMS.md](docs/DROP-CLAIMS.md)).
- **The data itself checks out.** Its hourly Reddit counts agree with an independent provider (Syften) to within a few percent (median hourly correlation 0.958).

Correlation is not attribution: a drop after an outage could also come from news cycles, moderation or Russian users losing service, which is why every group is compared with a non-political control.

## What it measures

| Signal | Source | Key needed |
|---|---|---|
| Yandex Cloud (AS200350) /24 blocks answering pings, BGP prefixes, telescope traffic | [IODA](https://ioda.inetintel.cc.gatech.edu) | no |
| Yandex (AS13238) BGP prefixes | IODA | no |
| Share of HTTP requests from AS13238 classified as bots | [Cloudflare Radar](https://radar.cloudflare.com) | free token |
| Comments and posts per hour in selected subreddits | Reddit API (or public feeds) | OAuth recommended |
| Historical subreddit activity (backfill) | [Arctic Shift](https://arctic-shift.photon-reddit.com) | no |
| Posts per hour matching keywords | Bluesky public search | no |
| Original posts, reposts and replies per hour for the same keywords (counts only) | Twitter API post counts | Bearer Token, pay-per-use |

Communities are tagged `political-right`, `political-left`, `narratives`, `anti-trans`, `framing`, `political`, `regional`, `south-america`, `russia` or `control` in [config/sources.toml](config/sources.toml). The **control** group of non-political communities is the point of the exercise: a drop that also shows up there is not evidence of bot removal. The tags are editorial judgements and are documented on the site.

Only timestamps and aggregate counts are stored. No usernames, account IDs or post content are stored.

## Run it locally

Requires Python 3.11 or newer.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` elsewhere
pip install -e ".[dev]"
cp .env.example .env          # optional: add API keys
python -m tracker backfill --days 45          # IODA, Cloudflare and Reddit history
python -m tracker serve                       # site + API on http://127.0.0.1:8000, collects every 15 min
```

Other commands:

- `python -m tracker collect` runs one collection pass, the alert check and today's report if it is missing, for cron.
- `python -m tracker report` builds or rebuilds today's shareable report.
- `python -m tracker publish --collect` collects, then pushes a static copy of the site to GitHub Pages. This is the free hosting mode.
- `python -m tracker serve --no-collect` serves the site without collecting.
- `python -m tracker backfill --platform reddit --days 90` backfills one platform.
- `python -m pytest` runs the tests.

The Reddit backfill is slow. Arctic Shift is a volunteer-run archive, and it times out on large subreddits such as r/Conservative and r/politics. The collector shrinks its requests and backs off when that happens, so allow several hours for the default list. Comment series go first. If the run is interrupted, resume it with `--missing-only`.

## The site

The UI follows the terminal design system in [terminal-design-system/](terminal-design-system/DESIGN_GUIDE.md).

- **Live** leads with the correlation. One chart puts Yandex Cloud reachability and the daily activity of each community group on the same scale, where 100 means the pre-strike average. It shows each group's correlation with Yandex (Pearson r), right-wing communities against the non-political control group by default. Below the chart are every infrastructure signal, the median change per group, data coverage and the latest alerts.
- **Groups** lists every tracked community, filterable by group, with its current rate, its change against the last 7 days and against the pre-strike reference, and its correlation with Yandex Cloud reachability.
- **History** shows any infrastructure series against any community series on a shared time axis, with the reference period and reported strikes marked. Series download as CSV.
- **Report** shows the latest dated report: the group headline table, infrastructure, and every community. It links to downloads (a zip bundle with a methods README, CSVs and JSON) and to the archive of earlier reports. It also prints cleanly to PDF.
- **Alerts** is the alert log, including whether each alert was posted.
- **About** covers methodology, caveats, sources and the theme switch.

## Event study

The headline question is tested the way an r/theydidthemath analysis (12 October 2026) tried to, with the checks its commenters asked for. The post was removed later that day (commenters said by moderators; no reason was posted that we could find); the text is in the [Arctic Shift archive](https://arctic-shift.photon-reddit.com/api/posts/ids?ids=1x3q43a&fields=title,created_utc,selftext) and the author's [data and code](https://files.catbox.moe/eqj4gh.zip) were still online in October 2026. The author disclosed the calculations were produced with ChatGPT. Independent checks are collected in [docs/DROP-CLAIMS.md](docs/DROP-CLAIMS.md).

- **Effect**: total activity in the 12 hours after each strike, compared with the same weekday and hour one, two and three weeks earlier. The strikes are averaged with equal weight. Strike times are in [config/events.toml](config/events.toml). Where IODA shows the outage, its measured time is used: Sasovo at 23:30 UTC on Oct 7, Vladimir at 01:50 UTC on Oct 11.
- **Placebo p-value**: the same statistic is computed for random start times before the first strike. p is the share of those that drop at least as much.
- **Robustness grid**: the effect is recomputed for windows of 6, 12 and 24 hours and for starts 3 hours early or late. A real effect should hold across the grid.
- **Controls**: non-political communities go through the same test. With many communities, about 5% pass p < 0.05 by chance.

Run as a sanity check on Yandex Cloud reachability itself, the test gives about −48% with p = 0.002 (the floor for 500 draws) in every cell of the grid.

## API

Interactive docs are at `/docs`. Main endpoints:

- `GET /api/correlation` returns daily indices (100 = pre-strike average) for Yandex Cloud and each group, with each group's r.
- `GET /api/snapshot` returns every series with its latest value, `change_7d`, `change_ref` and `r`, plus group medians, source health and events.
- `GET /api/series/{key}/points?days=30&bucket=hour|day|raw` returns a time series.
- `GET /api/series/{key}/event-study` returns the event study and its robustness grid.
- `GET /api/export/series.csv?key=…` and `GET /api/export/daily.csv` export the data.
- `GET /api/alerts` returns the alert log.

Responses carry `Cache-Control: public, max-age=60` so a CDN can absorb traffic.

## Alerts

An alert fires when either of these moves against its 7-day same-hour baseline:

- an infrastructure signal moves 25% or more
- a community group's median moves 30% or more (groups with at least 3 communities)

Each signal-direction pair has a 12-hour cooldown. Every alert also quotes the control group's change. Alerts are always logged on the site. To post them to Twitter, set the four `X_*` credentials and `TRACKER_POST_ALERTS=1`. Twitter charges per post, and much more for posts with links, so alerts leave the link out by default and are capped at `TRACKER_MAX_POSTS_PER_DAY`.

## Community labels

How Reddit communities are placed in groups, and how those labels compare with published classifications, is written up in [docs/SUBREDDIT-LABELS.md](docs/SUBREDDIT-LABELS.md), with the per-subreddit comparison in `docs/subreddit-label-check.csv`. To cite the project, see `CITATION.cff`.

## Reports

A report is built every day and saved under `data/reports/YYYY-MM-DD/`. Reports are never changed after their day, so each one can be cited. Each contains:

- `groups.csv`: the headline table, one row per research group, including the control group.
- `communities.csv`: one row per community, with pre-strike and recent rates, change, strike-window effect, placebo p, robustness and correlation.
- `infrastructure.csv` and `daily.csv`: the network signals and the daily data behind everything.
- `report.json`: all of the above in one file.
- `README.md`: methods, column definitions, sources and how to cite.
- `bot-traffic-report-YYYY-MM-DD.zip`: all of these files in one download.

## Deploying

See [docs/HOSTING.md](docs/HOSTING.md) for a step-by-step guide in two phases:

1. **Free, now.** Your computer collects every 30 minutes and publishes a static copy of the site to GitHub Pages.
2. **About $7 a month, later.** A VPS behind a Cloudflare Tunnel and cache, with Litestream backups and Twitter alerts.

## Caveats

Correlation is not attribution. Activity can fall after an outage for reasons other than bots going offline: news cycles, weekends, moderation, platform changes, or real users in Russia losing service. Cloudflare's bot share for AS13238 is mostly Yandex's own search crawler. Read the About tab before citing a number.

How raw source data becomes stored points, and every data bug found so far with how it was repaired, is in [docs/DATA.md](docs/DATA.md).

The narratives group, which follows talking points documented in Russian influence operations rather than party names, is explained with its sources in [docs/NARRATIVES.md](docs/NARRATIVES.md).

## Licence

The code is MIT licensed (see [LICENSE](LICENSE)). The data has its own terms: Cloudflare Radar data is CC BY-NC 4.0, so any published dataset that includes it is non-commercial only.
