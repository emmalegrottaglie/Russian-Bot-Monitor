# Data rules and fixes

How the tracker turns source data into stored points, and a log of the bugs found in that process, why they mattered, and how the stored data was repaired.

## Rules every collector follows

- **No invented points.** A failed or empty fetch is recorded as an error and shows as a gap, never as a zero.
- **Quiet hours count as zero only inside data.** An hour with no activity is filled with zero only on a UTC day that has some data, and only inside the time range that was actually requested.
- **Stamped at the end.** Every point is stamped at the end of the period it measures. A count for 12:00–13:00 is stored at 13:00. Hourly buckets are labelled by their start, `(ts - 1) // 3600 * 3600`, so that point belongs to the 12:00 hour.
- **Complete days only.** A daily mean needs at least 20 hourly values (`analysis.MIN_DAY_HOURS`). A partial day's mean reflects the time of day its hours were collected, not the day's activity. This applies to every daily view, export and report.
- **Exact counts replace estimates.** History that counts each hour exactly (the Reddit archive, Bluesky search by hour) replaces any live estimate taken inside the same hour. The live Reddit feeds give an estimate from a sample of recent posts, and averaging it with an exact count would only add noise.
- **Repairs re-fetch, never patch.** Bad stored values are fixed by correcting the code and collecting the affected stretch again from the source (`python -m tracker refetch`). Rows are never deleted or rewritten by a rule of thumb. `refetch` replaces a stretch only when it came back complete, and only as far as the source reached.

## Source quirks

- **Arctic Shift (Reddit history):**
  - The hourly aggregate labels each hour early by the Central European offset at the label: 2 hours in summer, 1 in winter. This was checked against single comment timestamps on ordinary days and around both 2025–26 clock changes.
  - When clocks go back, no data is lost; one label is skipped.
  - When clocks go forward, two hours get the same label and cannot be told apart, so both are left as a gap.
  - The parser stops with an error if the labels ever stop being offset.
  - It runs about 2 days behind and answers 422 when overloaded.
- **Bluesky search:** without a login only the first page (100 posts) of any search is returned. History is therefore read one hour at a time. An hour with fewer than 100 posts is an exact count; a busier hour is extrapolated from the newest 100, the same method the live collector uses.
- **Cloudflare Radar:** refuses hourly data over long ranges ("aggregation interval is too low for date range"). 30 days works, 50 does not, so history is requested a week at a time. Radar labels a bucket by its start; the collector stamps its end.
- **IODA:** native bins (5 minutes for BGP, 10 for active probing), labelled by their start; the collector stamps their end.
- **Reddit API:** the research access request was refused in October 2026. Live Reddit numbers come from the public feeds, which only work from a home connection. A daily catch-up (`scripts/catch-up.cmd`) replaces them with exact archive counts about 2 days later.

## Fix log

### 2026-10-17: zero-filled hours before a backfill's start (commit 3c0ae1f)

- **Bug:** the quiet-hour fill zeroed the hours of a backfill's first day that came before the requested start. 251 hours across the first days of 22 Reddit series held zeros that were never measured.
- **Why it mattered:** fake zeros dragged down the first days of the reference period that every chart is indexed to.
- **Fix:** the fill only covers the requested range.
- **Repair:** those first days were collected again from the archive. The 33 zero hours left are the archive's own counts; r/republican, for example, had 7 comments that whole day.

### 2026-10-17: start and end timestamps mixed (commit 7abe750)

- **Bug:** IODA and Cloudflare stamped a period at its start, Reddit and Bluesky at its end. The infrastructure series therefore sat an hour off the community series, and hourly buckets mixed the two rules.
- **Fix:** every collector stamps the end; buckets are labelled by start using `ts - 1`.
- **Repair:** all 4 IODA series were collected again and replaced. Cloudflare had no stored data at the time.

### 2026-10-17: partial days averaged (commit 7abe750)

- **Bug:** a day with a handful of hourly values got a daily mean like a full day. The correlation tiles showed "TODAY", which was always a partial day.
- **Fix:** the 20-hour minimum above. The tiles now name the latest complete UTC day.

### 2026-10-17: archive labels around clock changes (commit 7abe750)

- **Bug:** the archive parser applied one fixed shift per request, worked out from the first bucket. Across a clock change every hour after the change would have been placed an hour wrong.
- **Fix:** each label is converted with the offset at that label (the rule above); colliding spring labels become a gap. Stored data was not affected, because everything loaded so far was in summer time.
- **Note:** the EU clock rule is coded directly, because Windows Python has no time zone database.

### 2026-10-17: post-strike Reddit days missing (commit 7abe750)

- **Bug:** the backfill stopped where the archive stopped (2 days before the run), and "missing only" runs never returned to a series. From October 11 on, Reddit had only a few live estimates a day.
- **Fix:** a daily catch-up reloads the last 7 days of Reddit and Bluesky. It runs as the scheduled task `BotTrafficMonitorCatchUp`.

### 2026-10-17: live estimates averaged with archive counts (commit 7abe750)

- **Bug:** 49 Reddit hours held both an exact archive count and a live estimate, and the charts averaged the two.
- **Fix:** exact hourly history replaces live samples inside its hours.

### 2026-10-17: daily means computed in Python (commit c83924f)

- **Bug:** daily views loaded every raw point of a range into Python. With IODA's 5-minute bins and a large `?days=`, a single request could pull a very large number of rows (flagged by a security review).
- **Fix:** daily means are computed in SQLite with the same complete-day rule; a test checks they match.

### 2026-10-17: unknown series in a repair run (commit 4ff4c4b)

- **Bug:** `refetch --series` silently skipped a key it did not recognise. During the first-day repair a stray carriage return left 4 series unrepaired.
- **Fix:** unknown keys are an error. The 4 series were then repaired.

### 2026-10-18: Cloudflare history refused (commit f26f63e)

- **Bug:** the first Cloudflare backfill asked for 50 days of hourly data in one request and got a 400.
- **Fix:** history is requested a week at a time, and a refused week is a gap instead of losing everything.
- **Result:** 1,200 hourly points from August 28, with no gaps.
