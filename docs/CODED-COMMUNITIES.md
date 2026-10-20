# Coded communities: a catalogue and a coded-language measure (plan)

Status: planning, 20 October 2026. Nothing has been collected yet.

## Aim

Build a current, sourced catalogue of online communities organised around right-wing, anti-trans or anti-LGBTQ politics, including those that use meme, shorthand or code-word names, and a measure of how much documented coded language each community uses. This extends docs/SUBREDDIT-LABELS.md, which found that the public classifications stop in 2018 and 2019 and that existing hate-community lists are mostly of banned communities.

## Decisions (Emma, 20 October 2026)

- **Storage.** Per-community aggregates may be stored: commenters shared between two communities, and glossary-term counts per community. No usernames, no per-user rows, no pair counts below 10 commenters. Recorded in CLAUDE.md.
- **Publication.** The method and high-confidence entries are published. Lower-confidence candidates stay local (under `data/`, not in git) until reviewed, because a public list of communities can be used for brigading or harassment.
- **Location.** This repository, next to the labelling paper.
- **Timing.** Collection waits until the current Reddit backfill finishes; the archive is already refusing requests.

## Prior catalogues (search of 20 October 2026)

| Source | What it lists | Status |
|---|---|---|
| Hickey, Fessler, Lerman and Burghardt (2024), [The Peripatetic Hater](https://arxiv.org/abs/2405.17410), data at [github.com/dan-hickey1/peripatetic-hater](https://github.com/dan-hickey1/peripatetic-hater) | 168 hate subreddits, collected October 2023 to April 2024 from earlier research and lists posted on r/AgainstHateSubreddits, each with one category: general hate 58, xenophobic 35, misogynistic 32, anti-LGBTQ 16, racist 15, Islamophobic 7, antisemitic 4, ableist 1. No licence; the datasheet warns that many names contain slurs and that the data must not be used to train text generators | Checked (paper, datasheet and CSV) |
| Horta Ribeiro et al. (2021), [The Evolution of the Manosphere across the Web](https://ojs.aaai.org/index.php/ICWSM/article/view/18053), data on [Zenodo](https://zenodo.org/record/4007913) | 51 subreddits and 6 forums of the manosphere, by movement (incels, MGTOW, pick-up artists, men's rights) | *Unverified*: the list itself has not been opened |
| Waller and Anderson (2021); Hofmann et al. (2022) | Partisan scores to 2018; 605 political subreddits to 2019 | Checked: see docs/SUBREDDIT-LABELS.md |
| r/AgainstHateSubreddits | Crowdsourced posts documenting hate subreddits; a source for Hickey et al. | Not used directly: activist, uneven, and posts name users |
| [Erin in the Morning, 28 April 2025](https://www.erininthemorning.com/p/extremist-online-forum-connected) | Ovarit, the invite-only forum that grew out of r/GenderCritical after Reddit banned it in 2020, closed on 27 April 2025; its forums gave rise to the HeCheated and SheWon athlete lists | Checked |

**Conclusion.** Existing lists are of hate communities, most of them since banned, built between 2020 and 2024. None tracks current, active political communities with coded names, or measures the coded language they use. That is the gap this catalogue addresses.

## The coded-language measure

**Lexicon.** Each term enters a lexicon file with: the term and its variants, its category (anti-trans, homophobic, antisemitic, racist, alt-right general), the source that documents it as coded or hateful, and its measured precision. Starting sources:

- Terms already counted for the anti-trans group (docs/NARRATIVES.md) and documented in the Trans Rhetoric Library: "troon(s)", "no such thing as (a) trans", "gender ideology", "groomer", "AGP" and "autogynephilia", "TRA", "protect women", "biological male", "adult human female", "what is a woman", "zippertits".
- Erin in the Morning: "boys in girls' sports" described as a common Republican anti-trans dogwhistle ([11 October 2024](https://www.erininthemorning.com/p/tx-dem-collin-allred-responds-to), Erin Reed); "transgender ideology" and "gender ideology" as far-right dog whistles, citing Human Rights Watch ([5 February 2026](https://www.erininthemorning.com/p/republican-senator-attacks-netflix), s. baum). Checked.
- Beth's Transphobia Glossary (checked; already cited in the Trans Rhetoric Library).
- Mendelsohn, Le Bras, Choi and Sap (2023), [From Dogwhistles to Bullhorns](https://aclanthology.org/2023.acl-long.845), ACL 2023 (paper CC BY 4.0). A glossary of 340 English-language dog whistles, mostly from US politics, each with its register (193 formal or offline, 147 informal or online), type, the persona it signals, an explanation from a cited source and real examples. Personae include racist (76), transphobic (73), antisemitic (73), white supremacist (48), Islamophobic (16), homophobic (6) and anti-LGBTQ (3). The glossary is `data/glossary.tsv` in the authors' repository, [juliamendelsohn/dogwhistles](https://github.com/juliamendelsohn/dogwhistles), under the MIT licence; dogwhistles.allen.ai, the paper's home for it, refused connections on 20 October 2026. Checked (paper read in full; repository listing read).
  - The authors warn that most glossary terms have ordinary meanings that are more common than the coded one, that some terms were appropriated from the targeted group, that the glossary is not exhaustive, and that they are outsiders to the communities that use the terms. This is why every term gets a measured precision below.
  - Only terms, variants, persona and type, and the source of each explanation are taken from it. Its usage examples are not copied.
  - They also found that hateful sentences using dog whistles score as less toxic than the same sentences with slurs or plain group labels, and that GPT-3 recognised transphobic dog whistles least well of all personae. Both support counting terms directly rather than relying on toxicity models.

**Antisemitism is not anti-Zionism** (Emma, 20 October 2026). The antisemitic category counts only terms whose coded use targets Jews as Jews: conspiracy, control and blood-libel tropes, Holocaust references, slurs and in-group signals. Vocabulary of political speech about Israel, Zionism or its lobby is not counted, whoever uses it. From the Mendelsohn glossary this excludes "Zionist(s)", "Israel Lobby", "deadly exchange" (a campaign against US–Israel police exchanges) and "dual citizen"; "Zio", "dual loyalty" and "open borders for Israel" are held for Emma's review. "Zionist Occupation Government" (ZOG) and "Zioworld" stay: they are neo-Nazi conspiracy terms about Jewish control, not criticism of a state. The glossary's named bogeymen (for example Bernie Sanders and Volodymyr Zelensky) are not counted as coded signals; Zelensky remains a separate narratives keyword.

**Precision.** Many terms have ordinary meanings ("groomer" is mostly pet grooming on Bluesky; "TRAs" matches Spanish "tras") or are quoted by people objecting. For each term, a sample of matches is read by hand, in memory and never stored, and the share used in the coded sense is recorded as its precision. Terms below 50% precision are dropped or replaced by narrower phrases.

**Measure.** For each community and period: matches per 10,000 comments, each weighted by its term's precision, reported by category and in total, alongside the same rate in the control communities and across Reddit as a baseline. A community is never labelled from this measure alone; it is one piece of evidence next to the community's own description, rules and commenter overlap.

**Validation.** The measure should rank the anti-LGBTQ communities from Hickey et al. that still exist, and our right-wing group, above the control group. If it does not, it is not used.

**Limits.** It measures language, not people or intent. Coded terms change quickly, and a community that knows it is being watched changes them. Quoting to object inflates counts in communities that argue against the rhetoric.

## Finding candidate communities

1. Start from communities with a checked label: our right-wing group, and anti-LGBTQ communities from Hickey et al. that are still active.
2. From archive comments, count commenters shared between each seed and other communities, in memory, storing only pair counts of 10 or more. Rank communities by overlap relative to their size.
3. For each candidate, record its own description and rules, its overlap with the seeds, its coded-language rate, and Waller or Politosphere values where they exist. Assign a confidence level; Emma reviews each entry.

## Other platforms

The same measure could be applied to Bluesky (free search counts) and X (paid; each run needs Emma's approval). Forums built for harassment are not collected from; they are cited through reporting such as Erin in the Morning's.

## Journalism to cite

- **Erin in the Morning** (Erin Reed): reporting on anti-trans legislation, online spaces and coded language. Articles are cited individually once read.
- **Transitics** (Aleksandra Vaca): news on policy and courts affecting trans people. Its recent archive (August to October 2026) covers policy rather than online communities; it is cited where it reports on the rhetoric measured here.
