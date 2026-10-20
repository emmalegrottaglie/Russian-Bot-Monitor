# Subreddit candidates from the r/theydidthemath study

`subreddit-candidates.csv` lists the 221 political and regional subreddits that the r/theydidthemath study (12 October 2026; see docs/SYFTEN-CHECK.md) grouped by type, as candidates to add to this tracker. They were chosen by that study's author by topic, not by how they moved after the strikes, which keeps the selection honest. Its other 1,000 subreddits are general popular communities and are not proposed here.

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

## After review

Added subreddits will be collected for comments only (the main metric) and from the archive only, through the daily catch-up, about 2 days late. Reddit's live feeds already run out of time with the current 42 subreddits.
