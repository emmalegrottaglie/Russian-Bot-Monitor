# Labelling subreddits by political orientation: method, external checks and limits

**Emma Legrottaglie** · Bot Traffic Monitor · 20 October 2026 · version 1

Repository: https://github.com/emmalegrottaglie/Russian-Bot-Monitor · Site: https://emmalegrottaglie.github.io/Russian-Bot-Monitor/

**AI disclosure:** the analysis code, the comparison and the drafting of this paper were done with an AI assistant (Claude). Every source cited here was read on its original page, and every label decision is reviewed by the author.

## Abstract

The Bot Traffic Monitor compares activity in online political communities around the October 2026 strikes on Yandex data centres. Its results depend on which communities are placed in which group, so the groups need to be chosen openly and checked. This paper documents how 177 Reddit communities were placed into groups (right-wing, left-wing, general political, regional, South American, Russian and a non-political control) and checks those labels against two published classifications: the partisan scores of Waller and Anderson (2021) for 10,006 subreddits and the Reddit Politosphere of Hofmann, Schütze and Pierrehumbert (2022) for 605 political subreddits. Where the published data covers our communities, it agrees with every right-wing label and with most left-wing ones; the exceptions are explained by what the published measure can and cannot see. It also shows that a partisan score alone cannot label a community, because ordinary hobby communities score as strongly as political ones. The full per-subreddit comparison is published as a CSV for reuse.

## 1. Why the labels matter

Claims that bot networks "went quiet" after the strikes are claims about particular kinds of community. Testing them means comparing right-wing communities with left-wing, general and non-political ones. If a group is chosen after looking at how its members moved, any difference it shows is circular. Every community here was therefore chosen by topic, before looking at its activity around the strikes, and the reasons are written down.

## 2. Where the communities come from

- **The original 42 subreddits** (October 2026): communities named in the r/theydidthemath analysis of 12 October 2026 (post 1x3q43a, removed from Reddit the same day, apparently by moderators, and kept in the Arctic Shift archive), plus explicitly right-wing communities and non-political controls. See `config/sources.toml`.
- **135 added subreddits** (20 October 2026): taken from the subreddit list in that study's published package (docs/SYFTEN-CHECK.md). From its 221 political and regional subreddits, those with at least 100 posts and comments a day, the study's own rule; and from its 1,000 general subreddits, those that are clearly political. Candidate lists and every decision: `docs/subreddit-candidates.csv` and `docs/subreddit-candidates-general.csv`.

## 3. Labelling rules

| Group | Meaning |
|---|---|
| `political-right` | Organised around right-wing or conservative politics: a party, figure or movement |
| `political-left` | Organised around left-wing, liberal or socialist politics: a party, campaign, or socialist or anarchist movement |
| `political` | Politics and news across the spectrum, or communities that lean one way without being organised around it |
| `regional` | US states, and European and neighbouring countries |
| `south-america`, `russia` | Country communities in South America; communities about Russia or in Russian |
| `control` | Hobby and lifestyle communities with no political focus |

1. **A community is labelled by what it says it is.** Each left or right label was checked against the community's own description, read from the Arctic Shift archive.
2. **Certainty threshold.** A community goes into a left or right group only if that placement is at least about 85% certain. Communities that lean one way but are not organised around it stay in `political`. Anything less certain is left unlabelled for the author to review.
3. **Names are not evidence.** Right-leaning boards often use meme, shorthand or code-word names, so candidate lists are read for those. But a name can mislead in either direction: r/shitliberalssay reads as right-wing and describes itself as communist, satirising liberals from the far left.
4. **Labels are claims.** They are editorial judgements, published so they can be challenged, not findings about the people who post.

## 4. External sources

### 4.1 Waller and Anderson (2021)

Waller and Anderson built a 150-dimensional embedding of the 10,006 largest subreddits from which users comment where, using all Reddit comments from 2005 to 2018 (Pushshift). Their partisan dimension is seeded with r/democrats and r/Conservative plus nine similar pairs; a community's score is how much more its membership resembles the right-hand seeds than the left-hand ones. They validate it against communities that state their party affiliation in their description (correlation 0.92) and against the 2016 vote in city subreddits (0.39). They stress that scores measure social association, not individual identity.

The scores (`data/scores.csv` in the CSSLab/social-dimensions repository, column `partisan`) were downloaded on 20 October 2026 (SHA-256 `ee36cb5c3850fadb571c57059bc4afe159adaa292be6dfa5aee6947fadd36491`). The repository states no licence, so the file is kept locally; only per-subreddit results for the communities checked here are published.

### 4.2 The Reddit Politosphere (Hofmann, Schütze and Pierrehumbert, 2022)

The Politosphere covers 605 political subreddits from 2008 to 2019. Political subreddits were found with year-specific classifiers and then cleaned by hand (an independent re-check of 100 agreed with Cohen's κ 0.78). Its metadata marks subreddits banned by 2022 (38), explicitly Democratic (43) or Republican (20), devoted to a politician (85), regional (101) and about gun control (13). It does not place subreddits on a left-right scale beyond party affiliation.

`subreddits_metadata.json` was downloaded from Zenodo record 5851729 (CC BY 4.0) on 20 October 2026 (SHA-256 `734905ff1c487f69e3c90c0832f8681e67f528f10f56c2fa0c8c2edec622af7c`).

### 4.3 Sources considered but not used

- **Silent Signals** (Kruk et al., 2024) collects coded-language data from 45 "controversial" subreddits, left and right mixed, with no orientation labels.
- **Mendelsohn et al. (2023)** compiled a glossary of over 300 dog whistles. It concerns words rather than communities, so it may help with keyword tracking and reading community names; it was not used for labels.
- **Labelling by linked news sources** (for example with Media Bias/Fact Check ratings) is used in some studies. It was not used: the most common rating source is not openly licensed, and a community may link to an article in order to mock it.

## 5. Method

`research/subreddit_labels.py` reads both files and every subreddit this tracker follows or listed as a candidate (1,233 in all), and writes `docs/subreddit-label-check.csv`.

- **Partisan reading.** Each Waller score is converted to a z-score against all 10,006 subreddits (mean 0.0057, standard deviation 0.0754). A z of +2 or more reads "right", -2 or less "left", 1.5 to 2 either way "leans", otherwise "no lean". The ±2 cut-off was set from known cases before looking at the candidates: every right-wing community the tracker began with scores +2.7 or more, r/democrats -4.7, and the four non-political controls stay within ±1.4.
- **Calibration.** Of the Politosphere's Republican-affiliated subreddits that Waller scores, 5 of 7 read "right" and 2 "leans right". Of the Democratic-affiliated ones, 11 of 18 read "left", 4 "leans left" and 3 "no lean": r/AskBernieSupporters (+0.24), r/ThanksObama and r/tulsi (both -1.09). Question communities and those around figures who split their own party draw from both sides.
- **Flags.** A row is flagged when a published source disagrees with our label (our left or right community reads "no lean" or the other side, or carries the other party's tag), when a community outside our left and right groups reads strongly left or right, when the Politosphere tags it with a party, or when it was banned.

## 6. Results

### 6.1 Coverage

Of the 177 tracked subreddits, Waller scores 132 and the Politosphere lists 35. Communities created after 2018, such as r/50501, named after a 2025 protest movement, are in neither.

### 6.2 Right-wing group

| Subreddit | Waller z | Reading | Politosphere |
|---|---|---|---|
| Conservative | +5.82 | right | listed |
| conservatives | +3.56 | right | listed |
| asktrumpsupporters | +3.08 | right | Republican |
| Republican | +2.73 | right | Republican |
| trump | +1.75 | leans right | Republican |
| askconservatives, walkaway | — | not scored | askconservatives, walkaway listed, no party tag |

Every scored right-wing label is confirmed. No source places any of them elsewhere.

### 6.3 Left-wing group

| Subreddit | Waller z | Reading | Politosphere |
|---|---|---|---|
| democrats | -4.67 | left | Democratic |
| enough_sanders_spam | -3.96 | left | listed |
| latestagecapitalism | -2.91 | left | — |
| shitliberalssay | -2.77 | left | listed |
| political_revolution | -2.54 | left | Democratic |
| socialism | -2.34 | left | listed |
| anarchism | -1.44 | no lean | listed |
| labouruk | -1.40 | no lean | listed |
| askaliberal | -0.28 | no lean | listed |
| 50501, democraticparty, democraticsocialism, socialdemocracy, tankiejerk, trumpvirus, votedem | — | not scored | democraticparty Democratic; democraticsocialism, socialdemocracy listed |

Three left-wing labels read "no lean", each for a reason the measure cannot see past. The partisan axis runs between American Democrats and Republicans, so it does not capture anarchists, who reject both parties, or a British party (r/labouruk). Like r/AskBernieSupporters in the calibration set, r/askaliberal is a question community whose posters include the people asking. The labels are kept, and these three are listed as weakly supported.

**One change followed from the check:** r/enough_sanders_spam ("Flame of the Establishment", a Democratic-establishment community) was moved from `political` to `political-left`. Its score of -3.96 is among the strongest on the left, and its description places it with the Democratic Party.

### 6.4 Other groups

Among general political communities, r/askeurope (-2.27) reads strongly left and r/neoliberal, r/wayofthebern and r/yurop lean left. The Politosphere tags r/wayofthebern Democratic (it was a Sanders community up to 2019); it now describes itself as rejecting a left-right divide, so it stays in `political`. Among regional communities, r/latvia reads right (+2.45). An American partisan axis says little about European communities, so these are not acted on.

### 6.5 Communities we might have missed

Of the 798 scored communities in the study's general list, 4 read strongly right and 10 strongly left. The four on the right are r/4chan (+3.11), r/2007scape (+2.22), r/watches (+2.16) and r/stocks (+2.04). Apart from r/4chan, a culture and meme community whose audience strongly resembles the right-wing seeds, none is political. The general list contains no right-wing political community that our labels missed. r/4chan is left for the author to decide.

Communities left unlabelled for review mostly have no clear reading: r/conspiracy +1.36, r/joerogan +0.83, r/elonmusk -0.17. r/antiwork, r/workreform, r/marchagainstnazis and r/enoughmuskspam are not scored.

## 7. Limits

1. **A partisan score is not a label.** Many hobby communities score as strongly as political ones: r/2007scape +2.22 and r/stocks +2.04 on the right; r/lgbt -3.51, r/rupaulsdragrace -2.65 and r/chinesefood -2.16 on the left. The score reflects who a community's audience is, which correlates with age and gender as well as politics. It can support a label for a community that is already political; it cannot make an ordinary community political.
2. **The axis is American.** It is seeded with US party communities and says little about European, Latin American or Russian communities, or about movements outside the two-party frame.
3. **The data is old.** Waller covers 2005 to 2018 and the Politosphere 2008 to 2019. Communities change; several of ours did not exist then.
4. **Coded and banned communities are underrepresented.** The most extreme communities were banned (38 in the Politosphere by 2022), and new ones often begin small and with innocuous names. No public source catalogues current coded right-wing communities. Our own lists come from an earlier study's topic choices, which may miss them.
5. **Judgement remains.** Thresholds (85% certainty, z of ±2) are choices. They are published so they can be changed and the results recomputed.

## 8. Reproduce and reuse

1. Download `data/scores.csv` from https://github.com/CSSLab/social-dimensions into `data/external/waller-anderson-2021/`, and `subreddits_metadata.json` from https://doi.org/10.5281/zenodo.5851729 into `data/external/politosphere-2022/`. Check them against the hashes in section 4.
2. Run `python -m research.subreddit_labels`.

`docs/subreddit-label-check.csv` has one row per subreddit: `subreddit`, `our_label` (a group, `skip`, `already tracked` or `unlabelled`), `in` (tracked or which candidate list), `waller_partisan_z`, `waller_percentile`, `waller_reading`, `politosphere_party` (`dem`, `rep` or blank), `politosphere_banned`, `politosphere_listed` and `flag`. The groups themselves are in `config/sources.toml`. Code is MIT-licensed. If you reuse the Waller or Politosphere values, cite those papers too.

**Corrections.** Open an issue or a pull request against `config/sources.toml` with the community, the proposed group and a source. This paper will be versioned when labels change.

## How to cite

Legrottaglie, E. (2026). *Labelling subreddits by political orientation: method, external checks and limits* (version 1, 20 October 2026). Bot Traffic Monitor. https://github.com/emmalegrottaglie/Russian-Bot-Monitor/blob/main/docs/SUBREDDIT-LABELS.md

## References

- Hofmann, V., Schütze, H. and Pierrehumbert, J. B. (2022). The Reddit Politosphere: a large-scale text and network resource of online political discourse. *Proceedings of the International AAAI Conference on Web and Social Media* 16(1), 1259–1267. https://ojs.aaai.org/index.php/ICWSM/article/view/19377. Data: https://doi.org/10.5281/zenodo.5851729
- Kruk, J. et al. (2024). Silent signals, loud impact: LLMs for word-sense disambiguation of coded dog whistles. https://arxiv.org/abs/2406.06840
- Mendelsohn, J., Le Bras, R., Choi, Y. and Sap, M. (2023). From dogwhistles to bullhorns: unveiling coded rhetoric with language models. *Proceedings of ACL 2023*, 15162–15180. https://aclanthology.org/2023.acl-long.845
- Waller, I. and Anderson, A. (2021). Quantifying social organization and political polarization in online platforms. *Nature* 600, 264–268. https://doi.org/10.1038/s41586-021-04167-x. Preprint: https://arxiv.org/abs/2010.00590. Code and data: https://github.com/CSSLab/social-dimensions
- r/theydidthemath analysis, 12 October 2026 (post 1x3q43a, removed from Reddit on 12 October 2026): https://arctic-shift.photon-reddit.com/api/posts/ids?ids=1x3q43a&fields=title,created_utc,selftext. See docs/SYFTEN-CHECK.md.
