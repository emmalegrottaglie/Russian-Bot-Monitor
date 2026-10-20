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

**Antisemitism is not anti-Zionism** (Emma, 20 October 2026). The antisemitic category counts only terms whose coded use targets Jews as Jews: conspiracy, control and blood-libel tropes, Holocaust references, slurs and in-group signals. Vocabulary of political speech about Israel, Zionism or its lobby is not counted, whoever uses it. From the Mendelsohn glossary this excludes "Zionist(s)" (with "Zio" and "Zios"), "Israel Lobby", "deadly exchange" (a campaign against US–Israel police exchanges) and "dual citizen". "Dual loyalty" and "open borders for Israel" were reviewed and kept as far-right antisemitic tropes (Emma, 20 October 2026). "Zionist Occupation Government" (ZOG) and "Zioworld" stay: they are neo-Nazi conspiracy terms about Jewish control, not criticism of a state. The glossary's named bogeymen (for example Bernie Sanders and Volodymyr Zelensky) are not counted as coded signals; Zelensky remains a separate narratives keyword.

**The term list** is `config/lexicon.csv`, built by `python -m research.lexicon` (attribution and licence in `config/lexicon-NOTICE.md`). The glossary file holds 337 entries, three fewer than the paper reports. As of 20 October 2026 the list has 348 terms: 320 candidates, 7 excluded by the decisions above, 18 out of scope (personae such as anti-vax, climate change denier and religious, which are not part of this measure) and 3 proposed. Each row has its category, the source that documents it and a link; `precision` stays empty until measured. Terms added beyond the glossary:

- "no such thing as (a) trans" (The 74); "transgender ideology" and "trans ideology", "boys in girls' sports" (Erin in the Morning); "zippertits" (Beth's glossary).
- "transgender extremist", described as a right-wing media dog whistle ([Transitics, 19 September 2025](https://www.transiticsnews.com/p/this-week-theres-been-a-massive-escalation), Aleksandra Vaca); "trans violence" and "trans shooter", "Trantifa" and "transgenderism" ([Transitics, 11 February 2026](https://www.transiticsnews.com/p/conservatives-escalate-false-claims), which calls the "trans violence" narrative a hoax and cites [FactCheck.org](https://www.factcheck.org/2025/09/few-mass-shooters-have-been-transgender/)). Checked.
- [GLAAD's Guide to Anti-LGBTQ Online Hate and Disinformation](https://glaad.org/smsi/anti-lgbtq-online-hate-speech-disinformation-guide/) (read on 21 October 2026; an ongoing, non-exhaustive list with cited sources): 16 entries. New to the list: "globohomo", "LGBTP" and "CloverGender", "LGBTS" or "LGBTQIAS", "rapid onset gender dysphoria" (ROGD), "super straight", "trans terrorism", "transtrender", "transvestigation", "trans agenda" and "unwanted same-sex attraction" (conversion-therapy phrasing). Its entries for "41%", "biological male/female" (and "biological pronouns"), "gender ideology", "transgenderism", "groomer", "troon" and "womanface" are added as a second source for existing terms. GLAAD notes that context matters and that some slurs are reclaimed.
- Further lists, read on 21 October 2026 (all checked on the original page):
  - Robert Court, ["Decoding the Hidden Messages"](https://blogs.ed.ac.uk/staffpridenetwork/2023/07/05/decoding-the-hidden-messages-a-look-at-dog-whistles-in-the-gender-critical-movement/), University of Edinburgh Staff Pride Network blog, 5 July 2023: nine gender-critical dog whistles, including "Protect Single Sex Spaces", "Defending Sex Based Rights", "Keep Prisons Single Sex", "Sex Matters", "Defend Women's Sports", "Watchful Waiting" and "Exploratory therapy". It cites no sources and speaks for its author, not the university.
  - [Transvox, "Understanding Dog Whistles in Anti-Trans Discourse"](https://transvox.co.uk/episode/transvox-understanding-dog-whistles-in-anti-trans-discourse) (podcast with transcript, Gillian Russell and Jenny Harvey, 22 March 2025): "women and girls", "sex matters", "biological sex", "sex is real", "adult human female", "trans identifying", "dark side of trans activism", and questions about "protecting single-sex spaces" that are often not asked in good faith.
  - TransActual, [Transphobia](https://transactual.org.uk/transphobia/): "adult human female" as dogwhistle transphobia, "protect women's rights" as a campaign label against trans women's toilet access, "trans identified males", and "contagion" applied to trans young people.
  - Barnard College Library, [TERFs in the Stacks FAQ](https://guides.library.barnard.edu/terf/faq) (updated 13 May 2026): keywords "gender critical", "sex-based feminism", "transgenderism", "gender eugenics" and "sex realist feminism", without definitions or sources.
  - Kruk et al. (2024), [Silent Signals](https://arxiv.org/html/2406.06840v2): its dataset (16,550 instances of 298 dog whistles, at huggingface.co/datasets/SALT-NLP/silent_signals) states no licence and contains real comments, so it is not downloaded; the paper names no transphobic terms.
  - Terms only one of these sources lists are added as candidates; terms already listed gain a second source. The bare phrase "women and girls" is recorded as a note on "protecting women and girls", not counted, because it is far too common.
- **Proposed by Emma:** "single-sex spaces", "single-sex rights" and "biology-based rights", alongside the glossary's "sex-based rights". Update, 21 October 2026: the campaign phrases "protect single-sex spaces" and "defending sex-based rights" are now documented as dog whistles (Edinburgh Staff Pride Network blog; Transvox) and are candidates; the bare phrases below stay proposed. They are not used until a source documents them as anti-trans framing and their precision is measured; "single-sex spaces" also appears in ordinary discussion of toilets, changing rooms and services. A search on 21 October 2026 found no source that calls these phrases dog whistles. "Single-sex spaces" and "single-sex services" are terms of UK equality law, so counting them would mostly measure legal and policy debate. Mermaids' [analysis of the EHRC guidance](https://mermaidsuk.org.uk/news/our-analysis-on-the-ehrcs-single-sex-spaces-guidance/) (6 April 2022) criticises the weight the guidance gives "biological sex", not the term itself. TransActual's [Know Your Rights](https://transactual.org.uk/know-your-rights/) (updated 12 September 2026) explains "single-sex" and "separate-sex" services as provisions of the Equality Act 2010 after the April 2025 Supreme Court ruling, and notes that "biological sex" is a term it would not use; it does not describe the phrases as dog whistles. GLAAD's "biological male" entry documents the related false narrative that trans women threaten women's spaces. A University of Southampton study of "protect women" frames (eprints.soton.ac.uk/470556) could not be read: the site blocks automated access.

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

## First look on X (21 October 2026)

`research/coded_x.py`, approved by Emma: hourly counts on X (English, 1 September to 20 October 2026) for five categories of hand-picked high-specificity terms, original posts and reposts separately, plus X's general-volume probe. 22 full-archive count requests, about $0.22. No posts or accounts were read. Then the site's strike-aligned index (each hour against the same weekday-hour 1-3 weeks earlier, three strikes lined up, 3-hour smoothing, 5-95% band from 500 random pre-strike starts; pool of 456 hours).

| Category | Median a day (originals / reposts) | Originals, mean index 0-48 h after | Reposts, mean index 0-48 h after |
|---|---|---|---|
| Anti-trans slurs and memes | 3,204 / 2,779 | 118, inside the band | 179, above the band in 31 of 49 hours |
| Anti-trans framing | 1,692 / 2,210 | 95, inside | 188, above in 5 |
| Anti-LGBTQ | 127 / 29 | 118, below in 4 | 120, below in 3 |
| Antisemitic (coded) | 1,302 / 1,371 | 90, below in 15 by count, 5 as a rate | 94, inside |
| Racist and white supremacist | 1,227 / 1,280 | 105 | 87, below in 15 by count, 12 as a rate |

General English volume on X (the probe) averaged 99 after the strikes; its band is so narrow that it sat just below it in 45 of 49 hours, a dip of about 1%.

**Reading.** No category of coded language fell after the strikes in a way that stands out, except reposts of the racist and white-supremacist terms (index 87, below the band in 12 to 15 of 49 hours, where about 2 to 3 would be expected by chance). Anti-trans reposts rose instead. Hours are not independent, so 12 hours may be one event. Before anything is read into it: which terms drive it, and whether their matches are coded uses, need checking (a per-term count for that category costs about $0.26). Precision has not been measured for any term.
