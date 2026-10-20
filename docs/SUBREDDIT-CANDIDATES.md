# Subreddit candidates from the r/theydidthemath study

`subreddit-candidates.csv` lists the 221 political and regional subreddits that the r/theydidthemath study (12 October 2026; see docs/SYFTEN-CHECK.md) grouped by type, as candidates to add to this tracker. They were chosen by that study's author by topic, not by how they moved after the strikes, which keeps the selection honest. Its other 1,000 subreddits, general popular communities, are in `subreddit-candidates-general.csv`, busiest first, so right-wing or political ones among them can be picked out by hand.

## Columns

- **study_type, study_region**: the study's own labels.
- **posts_plus_comments_per_day**: the study's baseline, 12 September to 6 October 2026, from Syften.
- **suggested_group**: a first suggestion, to be reviewed before anything is added.
  - `regional`: US states and European countries.
  - `political`: politics and candidate subreddits across the spectrum.
  - `political-right`: only communities explicitly organised around a right-wing party, figure or movement; the note says why.
  - `skip`: under 100 posts and comments a day, the study's own eligibility rule. Too few to show a change.
  - `already tracked`: in config/sources.toml already.
- **note**: the reason for a suggestion, or a point to check.
- **your_decision**: the reviewer fills this in: a group name, or `skip`.

## Review, 20 October 2026

135 subreddits were added to config/sources.toml, comments only and from the archive only, through the daily catch-up, about 2 days late (Reddit's live feeds already run out of time with the original 42 subreddits).

- **political-right (3):** askconservatives, trump, walkaway, as suggested.
- **political-left (15), a new group:** from the 221, democrats, democraticparty, votedem, askaliberal, political_revolution, 50501, trumpvirus and labouruk; from the general list, latestagecapitalism, shitliberalssay, socialism, tankiejerk, democraticsocialism, socialdemocracy and anarchism. Each was checked against the community's own description in the Arctic Shift archive. r/shitliberalssay describes itself as communist, satirising liberals from the far left, despite a name that reads as right-wing.
- **political (39):** the remaining suggested political subreddits, plus geopolitics, politicaldebate and enoughcommiespam from the general list.
- **regional (78):** as suggested. US states have region `US`; countries have their ISO code (`UK` for the United Kingdom, as elsewhere in the file).

A community moved to a left or right group only when its leaning was at least about 85% certain. Communities that lean one way but are not organised around it (r/wayofthebern describes itself as neither left nor right; r/greenandpleasant, r/politicalhumor, r/leopardsatemyface, r/whitepeopletwitter) stay in `political`.

### Left for review

Not added; `your_decision` is blank. From the general list: antiwork, workreform, marchagainstnazis, conspiracy, joerogan, elonmusk, enoughmuskspam, 4chan, and every other general community. Right-leaning boards often use meme or code-word names, so the general list is worth reading for those; a name alone is not enough to tag one (see r/shitliberalssay above).
