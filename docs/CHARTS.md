# Chart specs

Status, 2026-10-18: charts 1, 2 and 3 and PNG export (chart 4) are built; chart 5 has its endpoint only. The values that waited on the backfill are settled under [Decisions from the backfill](#decisions-from-the-backfill), using the data loaded by then: 50 days for Bluesky and Twitter, and for Reddit comments; the Reddit post counts and the 8 narratives Bluesky searches were still loading.

Charts in build order:

1. [Strike-aligned chart](#1-strike-aligned-chart) (Live)
2. [Community heatmap](#2-community-heatmap) (Groups)
3. [Group minus control](#3-group-minus-control) (Live)
4. [Chart images for sharing](#4-chart-images-for-sharing) (every chart)
5. [Strike hour heatmap](#5-strike-hour-heatmap) (History)

## Principles for every chart

These apply to every chart, current and future.

- **The context is part of the image.** Each chart that makes a claim also draws what the claim is measured against: the control group, the range of ordinary days, or both. A screenshot cropped to the chart alone must still carry that context. The title, a one-line caption, the data date and the source sit inside the chart's frame.
- **Gaps are not zeros.** A missing hour or day is drawn as missing: a break in a line, a hatched cell. It is never drawn as a value. This follows the project rule that collectors never invent points.
- **Show everything, or say what was left out.** No chart picks its communities by how dramatic they look. A chart that shows a subset says which subset and why.
- **Same baseline everywhere.** "Index 100" always means the series' mean over the pre-strike reference period (`[analysis] reference_start` to `reference_end`). "Change after a strike" always means the event-study comparison: the same weekday and hour, 1 to 3 weeks earlier.
- **Design system.** SVG only, drawn by `web/app.js` with no chart library, styled by the accent roles (a1 chrome, a2 data, a3 highlight). No colour may be the only way to tell two things apart. The kit's green phosphor palette rules out a red/green scale.
- **Accessibility, as for the existing charts.** The SVG is focusable, arrow keys move through the data, a polite live readout announces the value, and a "Data table" disclosure under the chart lists every number.
- **Static mode.** Every new API endpoint gets a JSON file in `tracker/static.py` so the GitHub Pages copy works.

## 1. Strike-aligned chart

**Question it answers:** around the moment of each strike, did right-wing community activity fall outside its normal range while the control group stayed inside it?

**Audience:** everyone. This is the site's main exhibit and should be the first chart on Live, above the existing correlation chart.

### Data

For each community with a primary metric and enough history:

1. Take the hourly series `hours` (as in `analysis.hourly`).
2. For each strike time `t` and each offset `k` from −48 h to +48 h, the ratio is `hours[t + k] / baseline(t + k)`, where the baseline is the mean of the same hour 1, 2 and 3 weeks earlier. It needs at least 2 of those 3 weeks, the same rule as `window_effect`.
3. Average the ratio over strikes at each offset, weighting each strike equally. Express it as an index, ratio × 100.

A group's curve is the median, at each offset, of its communities' curves, using only offsets where at least 2 communities have a value. This is the same median rule as `correlation_view`.

**Chance band.** This is what makes the chart honest. Draw placebo start times from the hours before the first strike, using the same pool rule as `placebo_pool`: the whole ±48 h span must end before the first strike. For each of 500 draws, pick as many placebo starts as there are strikes and build the group curve exactly as above. At each offset, the band runs from the 5th to the 95th percentile of the 500 placebo curves. Seed it per group, as `event_study` does, so the band is reproducible.

**Smoothing:** a centred rolling mean over **3 hours**, applied to both the curves and the band (decided; see below).

**Endpoint:** `GET /api/strike-aligned` (built; the span and smoothing are `ALIGNED_SPAN` and `ALIGNED_SMOOTH` in `tracker/analysis.py`, not query parameters, so the response can be cached) returns:

```json
{
  "offsets": [-48, ..., 48],
  "events": [{"short": "SASOVO", "ts": 0, "timed": true}],
  "groups": [{"tag": "political-right", "values": [...], "n": [...],
              "band": {"lo": [...], "hi": [...], "draws": 500, "pool": 812}}],
  "smoothing_h": 3
}
```

`values` and the band are indices (100 = normal for that weekday-hour). `null` marks an offset with too little data.

### Visual

- **X axis:** hours from the strike, −48 to +48, labelled every 12 h. A vertical rule at 0 is labelled "STRIKE".
- **Y axis:** index, with a horizontal rule at 100 labelled "NORMAL".
- **Lines:** the selected group in a3 (highlight); control in `l-muted`, dashed. Other groups appear only when switched on in the legend, as on the correlation chart.
- **Band:** the selected group's chance band is a light a3 tint. The control group's band appears only when control is the selected group.
- **Caption inside the frame:** "Shaded: range of 90% of ordinary days (500 random pre-strike windows). Averaged over N strikes. Kaluga time unknown, starts at midnight UTC."
- **Group picker:** right / political / regional / russia, as a `.switch` group. Default: right. Control is always drawn.

### States

- Fewer than 50 placebo windows: draw the lines without a band, with the note "NOT ENOUGH PRE-STRIKE HISTORY FOR A CHANCE BAND". This is the same 50-window floor as `event_study`.
- No group with 2 or more communities: "NO DATA YET".

### Accessibility

Arrow keys step by hour. The readout gives "+6 H: right 84, control 98, normal range 88 to 112". The data table has one row per hour.

### Acceptance

- A unit test with a synthetic series that drops 40% for 12 h after each strike: the curve leaves the band.
- A unit test with flat noise: the curve stays inside the band for at least 90% of offsets.
- With the band switched off, the chart must not render. The band is not optional styling.

### Decided after backfill

See [Decisions from the backfill](#decisions-from-the-backfill): ±48 h, 3-hour smoothing, and the band is narrow enough to read for every group except the 3-community Russia group.

## 2. Community heatmap

**Question it answers:** is any drop broad, or driven by a few communities? Did the control communities drop too?

**Audience:** skeptics, researchers, and anyone replying "but what about the other subs?". It goes at the top of the Groups tab, above the table.

### Data

Each community's daily index, 100 = pre-strike mean: the per-series `index()` already computed inside `correlation_view`, which currently throws it away after taking group medians. Return it instead of recomputing it.

**Endpoint:** `GET /api/heatmap` (built; 50 days) returns:

```json
{
  "days": [...],
  "events": [...],
  "rows": [{"key": "reddit.conservative.comments", "label": "r/Conservative",
            "group": "political-right", "values": [101.2, null, ...],
            "coverage": 0.96}]
}
```

### Visual

- **Rows:** one per community (primary metric only), grouped in the order right, political, regional, russia, control. A group heading row separates the groups. A community with several tags appears once, under its first tag in `config/sources.toml`. Sort by name within a group. Sorting by change after the strike is not offered: it invites cherry-picking, and the group order already answers "is it broad?".
- **Columns:** one per UTC day. Strike days get a marker above the column and a thin vertical rule through it.
- **Colour:** binned, not continuous, so the legend can be read off exactly.

  | Index | Colour |
  |---|---|
  | below 50 | a2, strong |
  | 50–67 | a2, mid |
  | 67–80 | a2, faint |
  | 80–125 | `--term-faint` (neutral) |
  | 125–150 | a3, faint |
  | 150–200 | a3, mid |
  | above 200 | a3, strong |

  The edges are symmetric as ratios (80 and 125, 67 and 150, 50 and 200), so halving reads as far from normal as doubling, and they come from the spread of real daily indices (see below). The end bins are open, so one tiny community swinging +400% does not stretch the scale for the rest.
- **Missing days:** a hatched cell with no fill. The legend shows it as "NO DATA".
- **Columns by screen width:** 21 days on screens narrower than 480 px, 50 days otherwise.
- **Hover and focus:** "r/Conservative · 10-09 · index 78 (−22% vs pre-strike)".

### Accessibility

The SVG has the `grid` role pattern. Arrow keys move between cells, and Home/End jump to the row ends. The data table has communities as rows and days as columns, the same as the CSV export.

### Acceptance

- Every primary community appears, including ones with no data (as an all-hatched row with "NO DATA YET").
- A day with no points renders hatched, never neutral.
- An export of the heatmap's data matches `daily.csv` for the same days.

## 3. Group minus control

**Question it answers:** in one line, is political activity moving differently from non-political activity?

**Audience:** Twitter followers and journalists. It is the one-line summary of chart 1. It goes on Live directly under chart 1.

### Data

From `correlation_view`: for each day, the selected group's index minus the control index, in percentage points. Days where either is `null` are `null`.

**Normal range:** the 5th to 95th percentile of the daily difference over the pre-strike reference period. This is a simple descriptive band, not a significance test, and the caption says so.

No new endpoint: computed in the browser from `/api/correlation`, which already returns both series. **Built** and on Live; it shows "no data yet" until the control group has history.

### Visual

- One line in a3, with a horizontal rule at 0 labelled "NO DIFFERENCE".
- The normal range is shaded, and strike days are marked as on the other charts.
- **Caption inside the frame:** "Right-wing communities minus non-political control, percentage points of their pre-strike level. Shaded: range of 90% of pre-strike days."
- **Group picker:** shares state with chart 1, so switching group there switches it here.

### Acceptance

- If either index is missing, the line has a gap, never a zero.
- If the reference period has fewer than 10 days with both indices, there is no band and a note says why.

## 4. Chart images for sharing

**Goal:** any chart becomes a PNG someone can post, with its context baked in.

### Behaviour

- Each chart gets a `▼ PNG` chip next to its data table.
- **The image is the chart plus a caption block:** title, the caption from the spec above, "Data to 10-12 20:00 UTC", the sources, and the site address as plain text. A link costs extra on Twitter; plain text does not.
- **Size:** 1200 × 675 (16:9, Twitter's in-feed ratio), drawn at 2× for sharp text.
- **Palette:** the viewer's current palette. CRT scanlines are never included.
- **File name:** `bot-monitor-<chart>-<YYYY-MM-DD>.png`.

### Implementation

Client-side only: serialise the SVG with its computed styles inlined, draw it to a canvas, then `canvas.toBlob`. Fonts must be embedded in the serialised SVG as data URIs, or the canvas falls back to a system font. The JetBrains Mono subset used is small enough to embed.

This is why every chart must be SVG. An HTML-grid heatmap could not be exported this way.

### Out of scope for now

Attaching images to Twitter alerts needs the image rendered on the server, where there is no browser. Revisit in phase 2, when there is a server.

### Acceptance

- The exported image contains the caption text and date. Check by reading it back in a test page.
- An export taken with CRT on shows no scanlines.

## 5. Strike hour heatmap

**Question it answers:** for one community, does any drop start sharply at the strike hour, as servers going offline would cause, or fade in gradually, as a news cycle would?

**Audience:** researchers. It goes on the History tab under the event-study grid, for the community selected there.

### Data

- **Rows:** hour of day, 0 to 23 UTC.
- **Columns:** days from 7 before to 7 after the selected strike.
- **Cell:** that hour's activity vs the same weekday and hour 1 to 3 weeks earlier, using the same baseline as the event study.

**Endpoint:** `GET /api/series/{key}/strike-hours?event=<index>` (and a static file per series and event).

### Visual

- The same colour bins and missing-cell hatching as chart 2.
- The strike hour is outlined. For Kaluga, which has no known time, the whole day is outlined, with the note "TIME UNKNOWN".
- **Strike picker:** a `.switch` group, one chip per strike.

### Acceptance

The same gap and accessibility rules as chart 2.

## Build plan

| Step | Can start now | Waits for backfill |
|---|---|---|
| Shared pieces: gap hatching, binned colour legend, grid keyboard pattern, SVG-to-PNG export | yes | no |
| Endpoints and analysis functions, with synthetic-data unit tests | yes | no |
| Chart 1 smoothing, span and band review | no | yes |
| Chart 2 colour bins and phone day count | no | yes |
| Chart 3 | yes, it reuses existing data | review the band |
| Chart 5 | after chart 2 | yes |

Once the backfill is done, look at the real data for one right-wing group and the control group, and settle every **decide after backfill** item in this file before any of these charts ships on Live. Done on 2026-10-18; see below.

## Decisions from the backfill

Settled on 2026-10-18 from the data loaded by then (see Status at the top).

**Chart 1, span and smoothing.** The chart was computed for spans of ±48 h and ±72 h and smoothing of 1, 3 and 6 hours (300 placebo draws each). Median width of the 90% band, in index points:

| Group | Communities | 1 h | 3 h | 6 h |
|---|---|---|---|---|
| Right-wing | 22 | 28 | 22 | 20 |
| Political | 17 | 40 | 32 | 27 |
| Regional | 10 | 47 | 36 | 30 |
| South America | 11 | 70 | 54 | 48 |
| Russia | 3 | 86 | 65 | 55 |
| Control | 12 | 31 | 25 | 21 |

- **3 hours.** One hour leaves the band so wide that only large moves could show; 6 hours narrows it a little more but blurs a short drop of a few hours, which is the size of effect the claims describe. The band is smoothed with the curve, so smoothing does not make a result easier to get.
- **±48 h.** ±72 h gave the same picture for every group and has a smaller placebo pool (624 windows instead of 672 for the right-wing group). The first two strikes are 24 h apart, so either span mixes the hours after one strike with the next; the chart says so.
- **The band is usable** for every group except Russia (3 communities, 65 points wide at 3 h), which can only show very large changes. That is stated, not fixed by rescaling.

**Chart 2, bins.** Daily indices on pre-strike days (2,965 community-days): 5th percentile 47, 25th 74, median 93, 75th 112, 95th 167. Half of ordinary days fall outside 85 to 115, so the draft bins would have coloured most of the map. The neutral bin is now 80 to 125, and the strongest bins hold about 1 in 20 ordinary days on the low side and fewer on the high side.

**What the first look showed** (not a finding until the remaining backfill is in and it has been checked by hand): in the 48 hours after the strikes the right-wing curve sat above its normal range in 37 of 49 hours (median index 116), the control curve below its range in 38 (median 89), and the narratives group, which then held only the Twitter searches, about 80% above normal, driven by Zelensky news. Neither is a drop in right-wing activity.

## Not planned

- **A "comments that didn't happen" counter.** It states the cause as fact.
- **A map of the regional communities.** It suggests geography means something here, and it doesn't.
- **Hour-of-week heatmap.** It explains the weekday-hour baseline, but answers no question about the strikes. It may go on About later as an explainer.
