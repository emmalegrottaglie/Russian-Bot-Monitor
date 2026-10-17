# Bot-like activity in aggregate: research and proposed method

October 2026. Question: can the monitor estimate how much of a keyword's volume comes from automated or coordinated accounts, without storing anyone's identity, and test whether that part fell at the Yandex outages more than the rest?

A research agent ran 23 searches and read 19 pages. The two findings this plan relies on most were then checked on the original pages: Rauchfleisch & Kaiser's error rates, and Botometer's status. Sources seen only in search snippets are marked.

## What the research says

### Bot classifiers are not reliable enough to label accounts

- **Rauchfleisch & Kaiser, PLOS ONE 2020** ([link](https://pmc.ncbi.nlm.nih.gov/articles/PMC7580919/)), checked. They tested Botometer, the most used bot classifier, at the common cutoff of 0.76. At a realistic 15% bot share, only about 59% of the accounts it flagged were bots. On German politicians and bots, only 24% were: 76% of the flagged accounts were humans, and about 90% of the real bots were missed. Scores also drifted from day to day.
- **Hays et al., WWW 2023** ([arXiv 2301.07015](https://arxiv.org/abs/2301.07015)). Very simple decision trees match published detectors on the benchmark datasets. But a detector trained on one dataset does poorly on another (accuracy from 0.32 to 0.87). The authors conclude that benchmark accuracy reflects how the datasets were collected and labelled, not real-world bot detection.
- **Gallwitz & Kreil, 2022** (preprint, [arXiv 2207.11474](https://arxiv.org/abs/2207.11474)). In a manual check of 109 accounts Botometer had flagged as bots, none were bots. Known bots were often scored as human.
- **Varol et al., ICWSM 2017** ([arXiv 1703.03107](https://arxiv.org/abs/1703.03107)). On 3,000 hand-labelled accounts: 0.85 AUC, 15% false positives. The human annotators themselves agreed only moderately (kappa 0.41).
- **Botometer no longer scores current accounts**, checked ([Indiana University OSoMe](https://osome.iu.edu/research/blog/introducing-botometer-x)). Botometer X is archival: no records exist for accounts created after 31 May 2023, it has no API yet, and it can't detect AI-driven bots.

**Conclusion:** no per-account bot label, from Botometer or a classifier of our own. Account traits such as age or a missing avatar can be shown only as descriptive shares ("posts from accounts under 30 days old"), never as "bots".

### Coordination is the stronger signal, with known false alarms

- **Pacheco et al., ICWSM 2021** ([arXiv 2001.05658](https://arxiv.org/abs/2001.05658)). This finds accounts that act together: shared retweets, identical hashtag sequences, posting in the same 30-minute bins, shared images. Each account needs a minimum amount of activity (5 to 8 posts), and only the strongest 0.5% to 1% of links between accounts are kept. The authors warn that similar content alone does not prove coordination: news share buttons produce identical text, and real activists coordinate hashtags.
- **Nizzoli et al., ICWSM 2021** ([arXiv 2008.08370](https://arxiv.org/abs/2008.08370)). Coordination measured on the 2019 UK election. Coordination was "almost completely uncorrelated" with Botometer scores and with account suspensions. The method cannot separate authentic coordination, such as a grassroots campaign, from inauthentic coordination.
- **Time window.** Published tools use windows from 10 to 60 seconds; a 2026 preprint finds that the window length decides which patterns can be detected (abstract only). The window should be fixed before looking at the strike days.

### Aggregate bot share over time has been measured before

- **Bruno, Lambiotte & Saracco, EPJ Data Science 2022** ([link](https://pmc.ncbi.nlm.nih.gov/articles/PMC8938738/)). This is the closest design to ours. They tracked the share of bot-scored accounts in "Brexit" tweets day by day: about 2% before 6 December 2019 and about 11% on election day. Changing the threshold changed the level but not the pattern. It used Botometer, which is no longer available.

### Timing signatures are weak evidence

- Clemson researchers, reported by ProPublica, found a suspected troll network posting on weekdays and pausing on weekends and Russian holidays. There was no statistical test, and the attribution was hedged. No published test of Moscow office hours was found. So timing is not used as a signal.

### Bluesky

- No study measuring bot prevalence on Bluesky was found. One 2025 paper detects coordinated reposting on Bluesky in real time (full text not readable).

### Privacy

- Under GDPR, pseudonymised data is still personal data, so hashing account IDs does not take it out of scope (UK ICO guidance, snippet only). Data minimisation says to keep only what the purpose needs. Account IDs should exist only in memory, for the length of a detection window, with only hourly totals stored.

## Proposed prototype, Bluesky only

Four weeks of history around the strikes, for 3 to 4 political keywords and one control keyword. Nothing goes on the site.

1. **Read** the public posts for each keyword, in memory. Store only hourly totals: all posts, posts in duplicate-text clusters, and posts from accounts under 30 days old. Store no account IDs, handles or text.
2. **Duplicate-text clusters.** Normalise the text and compare posts within a short window. A cluster is near-identical text from at least 3 different accounts. Run three windows (10, 30 and 60 seconds) and fix one before looking at the strike days.
3. **Check what the clusters are.** Hand-sample flagged clusters and sort them into news shares, quote campaigns, memes and bot-like content, storing nothing. This gives the share of real coordination behind the number, the same way the anti-trans keywords were checked.
4. **Test the strikes.** Did the coordination share and the new-account share fall after the strikes more than the rest of the volume, and more than in the control keyword, and more than on random pre-strike dates?
5. **Wording.** Results are "coordination-like share" and "share from new accounts", never "bot share".

**Known limit:** past searches only show accounts that still exist. Bluesky says it removed 4,907 state-linked accounts in 2026, so the measure undercounts any network that was later removed.

**Needs a decision first:** the project rule says to store timestamps only. This method reads post text and account traits in memory and stores only hourly totals derived from them. If adopted, CLAUDE.md should say so explicitly.
