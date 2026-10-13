# Hosting

There are two phases:

- **Phase 1 is free.** Your own computer collects the data and publishes a static copy of the site to GitHub Pages every 30 minutes.
- **Phase 2 costs about $7 a month.** A small server collects around the clock, the site updates live, and alerts post to X.

Do phase 1 now. Phase 2 can wait until there is money for it. Nothing in phase 1 is thrown away: the database moves to the server as-is.

## Phase 1: free

### What you get

- A public site at `https://<your-username>.github.io/<repo>/` with every tab working, including dated downloadable reports.
- Data refreshed every 30 minutes, but only while your computer is on and awake. Gaps show as gaps on the charts; nothing is invented to fill them.
- Reddit data without waiting for API approval. Reddit's public feeds work from a home connection, though they are refused from servers.

### Limits

- **Freshness:** if the computer sleeps, the site freezes at its last publish. The header shows `● SNAPSHOT` and the time it was made.
- **Bandwidth:** GitHub Pages has a soft limit of 100 GB a month, which is plenty unless a post goes very viral. Phase 2 adds Cloudflare caching for that.
- **Alerts:** logged on the site's Alerts tab, but not posted to X, because X charges per post.
- **Public repository:** a free GitHub Pages site needs one. Keep the database and `.env` out of it; `.gitignore` already does this.

### Steps

1. **Put the code on GitHub.** Create an empty **public** repository on github.com with no README and no licence. Then, in the project folder:
   ```bash
   git add -A
   git commit -m "Initial commit"
   git remote add origin https://github.com/<your-username>/<repo>.git
   git push -u origin main
   ```

2. **Get a free Cloudflare Radar token.** This is optional, and adds the Yandex bot-traffic signal.
   1. Create a free Cloudflare account.
   2. Go to *My Profile → API Tokens → Create Token → Custom token* and give it the permission *Account · Radar · Read*.
   3. Copy `.env.example` to `.env` and paste the token into `CLOUDFLARE_API_TOKEN`.

3. **Apply for Reddit API access now.** Approval takes about a week, so start early. You don't need it for phase 1, but phase 2 will.
   1. Read the Responsible Builder Policy.
   2. Ask for research access through r/reddit4researchers. Describe the project as non-commercial research that stores aggregate counts only.
   3. When approved, put the client ID and secret in `.env`.

4. **Load the history.** IODA takes about a minute. Reddit takes hours, and big subreddits are slow; let it run overnight. If it stops, run the same command again with `--missing-only`.
   ```bash
   .venv/Scripts/python -m tracker backfill --days 50
   ```

5. **Publish once by hand.** This collects, builds today's report, exports the site and pushes it to a `gh-pages` branch. Each push replaces the branch with a single new commit, so the repository doesn't grow.
   ```bash
   .venv/Scripts/python -m tracker publish --collect
   ```

6. **Turn on GitHub Pages.** In the repository, go to *Settings → Pages* and set *Source: Deploy from a branch*, *Branch: `gh-pages` / root*. The site appears at `https://<your-username>.github.io/<repo>/` after a minute or two. Put that address in `.env` as `TRACKER_PUBLIC_URL`.

7. **Schedule it every 30 minutes.** Run this once in PowerShell, with your own path:
   ```powershell
   $action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument '--headless cmd.exe /c "C:\Russian bot tracker\scripts\collect-and-publish.cmd"' -WorkingDirectory 'C:\Russian bot tracker'
   $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
   Register-ScheduledTask -TaskName 'BotTrafficMonitor' -Action $action -Trigger $trigger
   ```
   - `conhost --headless` runs it without a window. With a visible window, closing it stops that run (`0xC000013A`).
   - Don't use `schtasks /TR` with a path containing spaces: PowerShell drops the inner quotes, and the task then tries to run `C:\Russian` and fails with "file not found" (`0x80070002`).
   - Check it works: `Get-ScheduledTaskInfo -TaskName BotTrafficMonitor` should show `LastTaskResult : 0` after a run, and `data\publish.log` should exist.
   - Output goes to `data\publish.log`.
   - In *Settings → System → Power*, set sleep to *Never* while the computer is plugged in.
   - To stop the schedule: `schtasks /Delete /TN "BotTrafficMonitor" /F`.

8. **Optional, still free:** create an X developer account and an app for the alert account now, so the keys are ready. Posting stays off (`TRACKER_POST_ALERTS=0`) until phase 2.

Checklist: the repository is public, Pages serves `gh-pages`, the scheduled task exists, `data\publish.log` shows a push every 30 minutes, and the site's REPORT tab lists today's report.

## Phase 2: paid, about $7 a month

### What changes

- Collection runs around the clock on a server.
- The site is live, with a working API at `/api` and `/docs`.
- Traffic spikes are absorbed by the Cloudflare cache.
- Alerts post to X.

### Cost

| Item | Cost |
|---|---|
| VPS, DigitalOcean 1 GB droplet | $6 a month |
| Domain name, registered through Cloudflare | about $10 a year |
| X posts, capped at 4 a day without links | under $2 a month |
| Cloudflare proxy, Tunnel and cache; R2 backup under 10 GB | free |

### Steps

1. **Domain.** Buy a domain through Cloudflare Registrar, which sells at cost. That puts it on Cloudflare's free plan automatically.

2. **Server.** Create a DigitalOcean droplet: Ubuntu LTS, 1 GB RAM, $6 a month. Add your SSH key, then install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```

3. **Code and settings.** On the server:
   1. `git clone` your repository.
   2. Copy your `.env` across. It must now include the Reddit OAuth keys, because servers can't use the public feeds.
   3. Set `TRACKER_PUBLIC_URL` to your domain.

4. **Move your data.** Stop the scheduled task on your computer first (`schtasks /Delete /TN "BotTrafficMonitor" /F`), so nothing writes to the database while you copy it. Then start the stack once so Docker creates its data volume, and copy the database into it:
   ```bash
   docker compose up -d
   docker compose cp data/tracker.db app:/data/tracker.db
   docker compose cp data/reports app:/data/
   docker compose restart app
   ```

5. **Cloudflare Tunnel.** This gives the server no open ports.
   1. In Cloudflare *Zero Trust → Networks → Tunnels*, create a tunnel and copy its token into `.env` as `TUNNEL_TOKEN`.
   2. Add a public hostname, for example `yourdomain.org`, pointing at `http://app:8000`.
   3. Run `docker compose --profile tunnel up -d`.

6. **Cache rule.** In the Cloudflare dashboard, go to *Caching → Cache Rules* and create a rule with these settings:
   - URI path starts with `/api/`
   - Eligible for cache
   - Edge TTL 2 minutes

7. **Backups.** Set up [Litestream](https://litestream.io) to stream `tracker.db` to a Cloudflare R2 bucket (free under 10 GB).

8. **Alerts.**
   1. Add credit and a spend cap in the X developer portal.
   2. Fill in the four `X_*` keys in `.env` and set `TRACKER_POST_ALERTS=1`.
   3. Run `docker compose up -d` to apply the change.
   4. In the X profile settings, label the account as automated.

9. **Retire or keep the free mirror.** Delete the scheduled task on your computer if you haven't already. Then either point GitHub Pages visitors at the new domain, or keep `gh-pages` as a mirror by running `docker compose exec app python -m tracker publish` from the server on a cron schedule.

## Research notes (October 2026)

Prices change; check them before buying.

### Why a VPS for phase 2

- **Reddit:** it refuses unauthenticated requests from most datacentre IP ranges. New OAuth keys need approval under its Responsible Builder Policy, which takes about a week and can be refused. A fixed VPS IP with an approved key is the most reliable setup.
- **DigitalOcean:** the $6 droplet (1 GB RAM, 25 GB disk, 1 TB transfer) is the default choice.
- **Hetzner:** cheaper, but its Cost-Optimized (CX/CAX) line was unavailable in October 2026. Its orderable CPX12 costs about €11.49.

### Options ruled out

| Option | Why not |
|---|---|
| Render free tier | Sleeps after 15 minutes idle and has an ephemeral disk, so the SQLite file is lost. |
| Oracle Cloud Always Free | The ARM allowance was cut in June 2026, idle instances get reclaimed, and popular regions are often out of capacity. |
| Railway Hobby | $5 a month with volumes capped at 5 GB, which this data could reach. |
| Fly.io | No free allowance for new organisations, and volumes are pinned to one host. |
| Cloudflare Workers + D1 | Needs a rewrite out of Python. D1 allows 500 MB free and 10 GB paid. |
| GitHub Actions as the collector | Schedules run 5 to 30+ minutes late or get dropped, they stop after 60 days without repository activity, and Reddit blocks the runners. A home PC is the better free collector. |

### X (Twitter)

- No free API tier for new developers since February 2026. It is pay-per-use: about $0.015 per post, and **$0.20 for a post that contains a URL**. Alerts leave the link out by default.
- Posting needs OAuth 1.0a user context: an API key and secret plus an access token and secret.
- A 403 when posting usually means the account has no credit.

### Data sources

| Source | Key | Notes |
|---|---|---|
| IODA | none | Only BGP visibility for AS13238. Active probing is available for Yandex Cloud, AS200350. |
| Cloudflare Radar | free token | CC BY-NC 4.0, so non-commercial use only. |
| Reddit | OAuth, approval required | Public feeds work from home connections only. |
| Bluesky | none | Public AppView search. |
| Arctic Shift | none | Backfill only. Slow for large subreddits. Its hourly bucket labels run 2 hours early; the collector corrects this. |
