# The r/theydidthemath package: an independent check

October 2026. The analysis this tracker's event study follows was posted to r/theydidthemath on 12 October 2026 and removed later that day. Commenters on the post said moderators had removed it; no reason was posted that we could find, and the author did not say they had deleted it. Its text is kept in the [Arctic Shift archive](https://arctic-shift.photon-reddit.com/api/posts/ids?ids=1x3q43a&fields=title,created_utc,selftext). The author's data, methods and code were published as [a zip on catbox](https://files.catbox.moe/eqj4gh.zip).

## The copy

- Downloaded on 20 October 2026: `eqj4gh.zip`, 24,602,672 bytes, SHA-256 `bf93862bd93b17bc5fdea74e1dae84024b96e0dfa33010e057e678afbf8a5ed2`.
- Kept locally under `data/external/theydidthemath-1x3q43a/` (not in git, not republished). The post was removed; whether to rehost the package is left open.
- Its code was read, not run. Only its data files were opened.

## What the package holds

- **Data:** hourly posts plus comments for 1,221 subreddits, 12 September to 12 October 2026 (744 hours each, 908,424 cells), read from Syften's public subreddit pages. The exact pages are included, with hashes and retrieval times.
- **Method:** for each strike, the 12 hours after a chosen start against the 12 hours before, each hour adjusted by the same weekday and hour 7, 14 and 21 days earlier. Timing checks sweep the start hour and use 10-hour windows. A "broad Reddit" adjustment is a sensitivity check.
- **Disclosure:** the author states the calculations and code were produced with ChatGPT, that it is an exploratory screen, not a significance test, and that it makes no causal claim.
- **Result:** 968 subreddits met the volume rules; 90 declined in all three nominal windows; none kept that pattern across every timing check.

## Check 1: the counts agree with ours

For the 30 subreddits both sources cover, Syften's hourly posts plus comments were compared with this tracker's Arctic Shift comments plus posts, hour by hour.

| Alignment | Median hourly correlation | Median ratio of totals, Syften / ours |
|---|---|---|
| Same hour | 0.958 | 1.004 (10th to 90th percentile 0.983 to 1.060) |
| Shifted 1 hour either way | 0.76 | 1.004 |

- Two independent providers agree to within a few percent, so neither is badly incomplete.
- The best agreement is with no shift. This confirms that the Arctic Shift clock correction (docs/DATA.md, "archive labels around clock changes") puts every hour in the right place.
- Our totals run slightly low in some subreddits (r/askarussian, r/aww, r/spain: 6 to 9%) because their post counts were still loading.
- r/argentina and r/brasil overlap for only 50 hours: their comment history was still loading when this was run.

## Check 2: 90 of 968 is about what chance gives

Among the 968 eligible subreddits, the share that declined (negative r and negative percentage) in each nominal window was 45.4% at Sasovo, 47.4% at Kaluga and 45.5% at Vladimir. If a subreddit's direction at one strike told you nothing about the next, about 95 would decline in all three by chance. The package found 90. In the same data, 77 rose in all three.

This is a rough check: the three windows are close together and share news and weekdays, so they are not fully independent. It answers the question the post's commenters asked, though. A count of 90 is not more declines than chance would produce, which agrees with the author's own finding that none survives the timing checks.

## Why the data is not merged into the tracker

- **Different measure.** Syften gives posts and comments combined; the tracker keeps them as separate series, and the charts use comments. They cannot fill each other's gaps.
- **A fixed snapshot.** It ends on 12 October 2026 and will not update.
- **Our own rule.** Stored data comes from one documented source per series and is repaired by re-fetching from that source (docs/DATA.md). Mixing providers within a series would break that.

The package's 1,221-subreddit list is broader than ours (42 subreddits). It could suggest communities to add, chosen in advance by topic, never by how much they dropped.
