# Bot Traffic Monitor report, 2026-10-24

Generated 2026-10-24T23:24:30Z. Cite as: *Bot Traffic Monitor, report of 2026-10-24, https://emmalegrottaglie.github.io/Russian-Bot-Monitor.*

This bundle records how activity in online communities moved around reported strikes on Yandex
data centres, next to measurements of Yandex's network. It is a snapshot: later reports may revise
numbers as more history is collected, and this one will not change.

## Files

- `groups.csv`: one row per research group, the headline table.
- `communities.csv`: one row per community series.
- `infrastructure.csv`: one row per network signal.
- `daily.csv`: daily mean of every series, for your own analysis. Only days with at least 20 hourly values are listed.
- `report.json`: all of the above plus the correlation chart data.

## Method

- **Pre-strike reference period**: 2026-09-15 to 2026-10-07.
- **Strike-window change**: total activity in the 12 hours after each strike, compared with the same weekday and hour one, two and three weeks earlier. Strikes are averaged with equal weight.
- **Placebo p-value**: the same statistic for random start times before the first strike (500 draws). It estimates how often a drop that size happens without a strike. Placebo windows overlap, so treat it as approximate. With many communities, about 5% will show p < 0.05 by chance.
- **Robustness**: the test is repeated for 6, 12 and 24 hour windows, each starting 3 hours early, on time and 3 hours late. `robust_cells` counts how many of the 9 show a decline of at least 5% at p < 0.05.
- **Correlation (r)**: Pearson correlation of daily values with `ioda.asn200350.ping-slash24` (IODA active probing of Yandex Cloud).
- **Groups** are editorial tags. The `control` group is non-political communities: a change that also shows up there is not specific to politics.

Correlation shows that activity moved with Yandex's outage; it does not by itself show why.

## Events

- 2026-10-07T23:30:00Z: Strike reported: Yandex Sasovo (Ryazan) (reported). Social media reports. Time: IODA active probing of Yandex Cloud (AS200350) falls from 23:30 UTC on Oct 7 (02:30 Moscow time, Oct 8)
- 2026-10-09T00:00:00Z: Strike reported: Yandex Kaluga (reported). Social media reports. Time unknown: no matching step in IODA signals, so windows start at midnight UTC
- 2026-10-11T01:50:00Z: Strike reported: Yandex Vladimir (reported). Social media reports. Time: second step down in IODA Yandex Cloud reachability at 01:50 UTC

## Columns

### groups.csv

| Column | Meaning |
|---|---|
| `group` | Research tag |
| `communities` | Communities in the group (main metric only) |
| `median_change_vs_pre_strike` | Median of members' change_vs_pre_strike |
| `median_strike_window_change` | Median of members' strike_window_change |
| `share_p_below_0_05` | Share of members with strike_window_p < 0.05 (about 0.05 expected by chance) |
| `share_robust` | Share of members with a decline of at least 5% at p < 0.05 in at least 5 of 9 grid cells |
| `r_vs_infrastructure` | Pearson r of the group's daily median index with the reference infrastructure series |
| `r_days` | Days used for r |
| `latest_index` | Group's latest daily index, 100 = pre-strike mean |

### communities.csv

| Column | Meaning |
|---|---|
| `community` | Community name (r/… for Reddit, BSKY "…" and X "…" for a keyword search, with its language) |
| `series` | Series key used by the API |
| `platform` | reddit or bluesky |
| `region` | Country or region the community is about |
| `groups` | Research tags, | separated (political-right, political-left, narratives, anti-trans, political, regional, south-america, russia, control) |
| `unit` | What is counted |
| `main_metric` | yes for the series group statistics use (Reddit comments, Bluesky posts) |
| `pre_strike_mean` | Mean hourly rate over the pre-strike reference period |
| `last_7d_mean` | Mean hourly rate over the last 7 days |
| `change_vs_pre_strike` | Last 24 h vs pre-strike mean, as a fraction (-0.25 = 25% lower) |
| `change_vs_7d` | Last 3 h vs the same hours on the previous 7 days (median) |
| `strike_window_change` | Activity in the 12 h after each strike vs the same weekday-hours 1–3 weeks earlier, averaged over strikes |
| `strike_window_p` | Placebo p-value: share of random pre-strike windows with a drop at least as large |
| `robust_cells` | Grid cells (of 9: windows 6/12/24 h × start −3/0/+3 h) with a decline of at least 5% at p < 0.05 |
| `r_vs_infrastructure` | Pearson correlation of daily means with the reference infrastructure series, last 30 days |
| `r_days` | Days used for r |
| `first_data_utc` | Earliest data point |
| `hours_of_data` | Hours with at least one data point since the first |

### infrastructure.csv

| Column | Meaning |
|---|---|
| `signal` | Network and measurement |
| `series` | Series key |
| `unit` | What is measured |
| `latest` | Latest value |
| `latest_utc` | Time of latest value |
| `pre_strike_mean` | Mean over the pre-strike reference period |
| `change_vs_pre_strike` | Last 3 h vs pre-strike mean |
| `strike_window_change` | 12 h after each strike vs same weekday-hours 1–3 weeks earlier |
| `strike_window_p` | Placebo p-value |

## Sources and licences

- IODA, Georgia Tech Internet Intelligence Lab: Internet outage signals.
- Cloudflare Radar: CC BY-NC 4.0 (non-commercial use only).
- Reddit: activity counts from the Reddit Data API or public feeds, and history from the Arctic Shift archive. Only counts are included: no usernames or content.
- Bluesky: public AppView search, post counts only.
