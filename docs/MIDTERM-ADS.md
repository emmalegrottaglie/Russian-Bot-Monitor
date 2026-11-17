# Anti-trans political advertising in the 2026 US midterms

Background for the midterms study (general election 3 November 2026). Researched on 16 November 2026 by a research agent; not yet spot-checked by hand (see docs/NARRATIVES.md on checking agent research before citing it). "Checked" means the agent opened the page and found the claim there; "unverified" means it was seen only in a snippet or a secondary source, or the page was blocked.

## How much

The totals come from different sources with different scopes and dates. Do not add them up.

- **AdImpact, via AP (28 October 2026), checked:** Republicans across federal, state and local races aired transgender-themed general-election TV ads about 217,000 times, for an estimated $183M up to 25 October, against about $151M at the same point in 2024. Democrats spent about $11M on trans-related ads, mostly defensive. [news4jax copy of the AP story](https://www.news4jax.com/news/politics/2026/10/28/republicans-emphasize-transgender-ads-putting-cultural-issues-over-voters-economic-anxiety/)
- **Wesleyan Media Project (13 August 2026), checked:** attacks on transgender people appeared in 14% of pro-Republican House TV airings from 1 January 2025 to 2 August 2026, the tenth most common topic; lower in Senate ads. TV only. [release](https://mediaproject.wesleyan.edu/releases-081326/)
- **Advocacy estimates:** GLAAD, over $187M in nine battleground states (no data source named; checked on [Metro Weekly](https://www.metroweekly.com/2026/11/anti-trans-ads-midterm-voters/)). HRC, "nearly $400 million" this cycle (checked on Metro Weekly), and also $340M over two years and $280M+ on broadcast and connected TV (both unverified). Erin in the Morning's "nearly $200 million" appears to round up the AdImpact figure.

## Who paid and where

- **Texas PAC** (pro-Paxton, Texas Senate). AP describes it as largely funded by Elon Musk. Musk gave Senate Leadership Fund $75M on 9 September and $83M on 23 September, and SLF passed the same amounts to Texas PAC the next day each time (SLF's Q3 FEC report, committee C00571703; [CNN via KRDO](https://krdo.com/news/2026/10/16/musk-contributed-more-than-150-million-to-bolster-gop-in-texas-senate-race-filings-show/), checked). Trans-themed ads in the Texas Senate race: about $58M and more than 50,000 airings to 25 October (AdImpact via AP, checked); one ad alone aired nearly 17,000 times at more than $23M.
- **Senate Leadership Fund:** leads the trans attacks on Sherrod Brown in Ohio, nearly $26M (AdImpact via AP, checked).
- **America PAC** (Musk): its first midterm ads, from 9 September, all focused on trans issues, against Talarico (TX), Brown (OH), Turek (IA) and Peltola (AK) ([The Advocate](https://www.advocate.com/politics/election/elon-musk-pac-transgender-attacks), checked). More than $3.7M on "mostly digital or streaming" ads by 23 September ([FactCheck.org](https://www.factcheck.org/2026/09/america-pac-2/), checked). The often-quoted $100M is a planned field programme, not measured ad spending.
- Other races with trans-themed ads (AdImpact via AP, and [PolitiFact, 28 August](https://www.politifact.com/article/2026/aug/28/why-republicans-are-focusing-on-transgender-issues-in-competitive-2026-campaigns/), checked): South Carolina Senate (more than $5M), Kansas Senate (nearly $7M), Iowa, Mississippi, the Georgia Senate primary, the Florida governor's race, Michigan Senate, and a Pennsylvania House seat (NRCC, from 12 August, [Semafor](https://semafor.com/article/08/20/2026/in-pennsylvania-house-race-its-pink-heels-vs-drag-queens), checked).
- Spanish-language: Truth and Courage PAC, a seven-figure statewide streaming buy against Talarico from 16 October ([KSAT](https://www.ksat.com/news/texas/2026/10/16/pro-cruz-pac-launches-seven-figure-spanish-language-ad-buy-attacking-talarico/), checked).

No public month-by-month series of trans-themed spending was found; AdImpact figures reach the public as cumulative snapshots. There is indirect evidence of a September surge in Texas.

## What the ads said

- Gender-affirming care for minors, "taxpayer-funded": Texas PAC against Talarico and Ashley Hinson's ad were both rated False by PolitiFact (checked).
- Parents jailed or charged: a Texas PAC ad (AP, checked).
- Sports: SLF against Brown (AP, checked).
- Detransitioner testimony: two SLF ads against Brown (AP, checked).
- "They/them", echoing Trump's 2024 ad: Texas PAC and the NRCC "With Them" ad (AP, Semafor, checked).
- Bathrooms and locker rooms: America PAC against Turek; NRCC in Pennsylvania (checked).
- Drag: NRCC in Pennsylvania used a drag performer who says he is not transgender; a Kansas ad stitched a quote together from clips (checked).
- Made-up or AI people: an AI-generated Talarico ad by Citizens for Sanity in June ([OECD AI incidents](https://oecd.ai/en/incidents/2026-06-09-1803), checked); a Georgia ad with a male actor playing a trans woman (PolitiFact, checked). Whether America PAC used actors or AI composites to show trans women is unresolved: The 19th (paywalled) and The Nation's reading of it disagree.

## Effect

- Neutral: AP-NORC (October) found about 1 in 10 registered voters call trans issues one of the most important; the AP Voter Poll found Democrats with a wider advantage on "transgender issues and healthcare" (both checked).
- Advocacy-commissioned: GLAAD / Morning Consult (4 to 6 November, 2,026 registered voters): 37% less likely to back a sponsor of anti-trans ads, 18% more likely (checked on Metro Weekly).
- The only randomised test found is from 2024 (Ground Media / Swayable): no significant shift in vote choice, but a 3 to 4 point drop in acceptance of trans people ([Ground Media](https://ground.media/news/ground-media-study-finds-trumps-anti-trans-ad-fails-politically-but-dangerously-erodes-public-support-for-trans-people), checked).

## Data we could pull ourselves

- **Meta Ad Library API** (`ads_archive`, political and issue ads, US): search terms, delivery dates, spend and impression ranges, and for political ads the reach by age, gender and region. US ads show who was reached, not who was targeted. Needs identity confirmation and a developer app (Meta's own access page was blocked, so the steps are unconfirmed).
- **Google political ads** (BigQuery `bigquery-public-data.google_political_ads`): spend by advertiser, week, state and congressional district, with age, gender and geographic targeting per creative. No ad text, so finding trans-themed ads needs the creative itself.
- **FEC independent expenditures** (`/v1/schedules/schedule_e/`): who spent what on which candidate and when, but no topic field, so it has to be joined with creative data.
- AdImpact has no public dataset.

Ad text read from these sources stays in memory only; store aggregates (CLAUDE.md).

## Blocked during research

Axios (9 September), The 19th, HRC press releases, LGBTQ Nation, Puck, the Arkansas Advocate copy of the AP story, Meta's Ad Library API page, and Google's BigQuery marketplace page. The full list is in the research agent's report of 16 November 2026.
