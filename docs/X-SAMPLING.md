# Twitter: costed measurement plan

October 2026. How to bring Twitter into the monitor within a small budget, including a sampled version of the coordination prototype (docs/BOT-SIGNALS.md).

## Prices and limits (Twitter API pay-per-use, checked October 2026)

| Item | Cost | Notes |
|---|---|---|
| Counts, last 7 days | $0.005 per request | Hourly or per-minute volumes, no posts returned |
| Counts, full archive | $0.010 per request | One request returns up to 31 days, even per minute |
| Post read | $0.005 per post | Full-archive search returns up to 500 posts per request. The same post read again on the same UTC day is not charged twice |
| User read | $0.010 per user | Probably charged for author details attached to search results. Not yet confirmed |
| Monthly cap | 3 million post reads | |

Source: [Twitter API pricing](https://docs.x.com/x-api/getting-started/pricing), [counts](https://docs.x.com/x-api/posts/counts/introduction), [search](https://docs.x.com/x-api/posts/search/introduction).

## Measured volumes, 20 September to 16 October 2026

From 8 full-archive count requests, $0.08 in total:

| Search | Posts a day before the strikes | Oct 8 to 11 | Oct 12 to 16 | Reposts before (range) | Reposts on strike days |
|---|---|---|---|---|---|
| MAGA, English | 152,844 | 170,372 | 223,823 | 64.6% (61.7 to 68.9) | 62.5 to 64.9% |
| AfD, German | 50,224 | 57,884 | 43,105 | 66.1% (60.7 to 70.3) | 66.3 to 68.3% |
| Zelensky, English | 24,537 | 113,667 | 130,252 | 81.6% (73.4 to 87.2) | 75.1 to 83.4% |
| weather, English | 71,576 | 72,624 | 60,063 | 49.0% (40.0 to 58.3) | 48.3 to 51.1% |

On every strike day, the share of reposts stayed within its range on pre-strike days. Zelensky volume rose about fivefold from the strikes on. That matches the news, not a drop.

## Tier 1: counts only (recommended now)

For each keyword, the hourly counts of all posts, reposts, replies and quotes, plus per-minute counts of all posts. Measures:
- **Volume:** the same as the Bluesky and Reddit series.
- **Repost share:** amplification.
- **Reply share.**
- **Burstiness:** the share of volume in minutes far above the local median. Synchronised bursts are a weak coordination signal on their own.

No posts are read, so nothing personal is processed.

| | Requests | Cost |
|---|---|---|
| History, 20 keywords, one 31-day window | 20 × 5 full-archive requests | about $1 |
| Daily update, 20 keywords | 20 × 5 recent requests a day | about $0.50 a day, about $15 a month |

## Tier 2: sampled pilot of the coordination measures

- **Keywords:** Zelensky (English) and AfD (German), both documented targets of Russian operations, plus "weather" (English) as the control.
- **Days:** the four strike days (8 to 11 October) and the same weekdays one, two and three weeks earlier, so 16 days.
- **Sample:** original posts only (reposts are covered by tier 1), read in full in three randomly placed 10-minute blocks a day, one in each 8-hour third of the day.

Reading every post in a block, rather than random posts, keeps clusters of near-identical posts intact. A random sample would split them up.

| Keyword | Original posts per 10 minutes | Posts a day (3 blocks) |
|---|---|---|
| AfD | about 120 | about 355 |
| Zelensky | about 30 before the strikes, 160 after | about 95 to 475 |
| weather | about 250 | about 760 |

- **Posts:** about 1,200 to 1,600 a day, so $6 to $8 a day, or **about $100 to $130 for the 16 days**.
- **Account age without paying for user details.** Twitter account IDs created since about 2015 encode their creation time, so a post's author ID gives the account's age without a user read. Before relying on this, a $0.10 check compares 10 decoded IDs with Twitter's own creation dates. If it fails, user details would add up to $10 to $14 a day, roughly tripling the cost. The pilot would then measure coordination only, not new-account share.
- **Storage:** as on Bluesky, text and IDs stay in memory, and only hourly totals are written.

Also set a spending limit in the Twitter Developer Console at, say, $150, as a hard stop.

## Tier 3: daily sampling (not yet)

The same sampling, run every day for three keywords, would cost about $7 a day, around $210 a month. It's worth it only if the pilot finds a coordination signal that stands out from the control and from ordinary days.
