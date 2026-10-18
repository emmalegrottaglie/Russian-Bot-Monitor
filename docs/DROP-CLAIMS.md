# What people said dropped after the strikes

October 2026. What was claimed to have gone quiet after the Yandex data-centre strikes (Sasovo, Kaluga and Vladimir, 8 to 11 October), what evidence was offered, and what measurements found. Compiled from a research agent's search; items marked **checked** were confirmed on the original page. The rest are second-hand and should not be cited without checking.

## Bottom line

- The strikes and the drop in traffic from Yandex networks are real.
- No measurement found shows political bots on social media going quiet. Every measured check of social platforms found normal activity, apart from a 5 to 15% dip on Russian-language Telegram channels, whose cause is unclear.
- The viral claims rested on one Cloudflare Radar chart of web traffic and on how social media felt.

## What was claimed

| Claim | Evidence offered | Status |
|---|---|---|
| "Russian bots went silent" | Cloudflare Radar chart of automated traffic from Yandex's network (AS13238): 0.3% of the chart's recent maximum at 02:00 UTC on 11 October, against 88.2% a week earlier | Chart real, reading wrong: the drop was almost all search crawlers. **Checked** (Lawfare, Cloudflare) |
| MAGA and pro-Trump accounts went quiet | Viral X posts and screenshots. One pointed at accounts with "Veteran, Christian, Father, MAGA" bios; others named "reply guys", Quebec, conspiracy and Polish anti-EU accounts | No account data offered. **Checked** (IBTimes) |
| AfD bot activity collapsed | Chart posted on X by Czech MEP Tomáš Zdechovský, seen more than 4 million times | Posted 11 October but holds data to 15 October, inconsistent axes, no source. Zdechovský told ZDF he has no verifiable data. **Checked** (ZDFheute) |
| Fewer bots, "a little easier to breathe" | President Zelensky, Warsaw Security Forum, 12 October | No data. Not checked on the original |
| Russian bot activity "virtually ceased worldwide" | Polish minister Tomasz Siemoniak, 12 October, citing ABW | Traced to an AI-generated graph; he said next day he hadn't known. Not checked (Brussels Signal, Spidersweb) |
| About 90 of 1,000 subreddits declined | Analysis by the account "Reddit Lies" | Other explanations given for several. Not checked (Coin Edition) |
| "Operation Quiet Piggy" | Meme name, after a Trump remark | Not an official name. **Checked** (IBTimes) |

## What measurements found

- **Cloudflare (blog, 14 October, checked):**
  - AS13238 (Yandex Search) was 99% below baseline on 11 October. 78.1% of its sampled requests were the verified YandexBot crawler.
  - AS200350 (Yandex.Cloud) was 90% below; its bot traffic fell about 40%.
  - Bot requests from Yandex.Cloud to one gambling site stopped after 8 October and identical requests reappeared from other Russian hosts (Radist, Selectel). Russian bot traffic to gambling sites rose 1.4%.
  - Bot traffic from Russia to the post, reply and like endpoints of one social platform fell 5.7%; globally it rose 1.1%.
  - The global bot share of traffic was flat (39.4% before, 39.5% on 13 October).
  - The post's own figures for the Russian bot share disagree with each other (table 50.4% to 42.1%, text 35.8% before), so that figure is not usable.
- **Graphika (via Texty, 14 October, checked; moderate confidence):**
  - MAGA mentions on X rose 25% in the 8 hours after the Vladimir strike, compared with the same hours on the previous four Sundays.
  - AfD communities on X: 40,365 posts from 1,022 accounts on 11 October, against 42,040 from 1,037 a week earlier, about 4% lower, within normal variation.
  - Russian-language Telegram channels posted 5 to 15% less over the two days after the Vladimir strike. Ukrainian, Iranian and Romanian channels barely changed.
  - Reform UK communities and Reddit were also checked; r/askarussian declined.
- **ZDFheute (13 October, checked):** accounts that repeatedly spread content from the Russian Storm-1516 campaign stayed active.
- **Second-hand, not checked:** CAT-UA saw no significant drop in about 10,000 daily mentions (via IBTimes, checked page, but the original not read); NASK-PIB found no overall decline among monitored X accounts; Common Consultancy found no unusual change in Facebook comments under 76 AfD politicians and 136 MAGA profiles.

## How this compares with the monitor

The monitor's X counts agree with Graphika. Original posts a day on 8 to 11 October were higher than before the strikes for MAGA (170,372 against 152,844) and AfD (57,884 against 50,224), and the repost share stayed inside its pre-strike range on every strike day (docs/X-SAMPLING.md).

## Searches worth adding

Only keywords tied to a sourced claim:
- **Reform UK** (English): one of the three communities Graphika checked.
- A Polish anti-EU search: named in the viral claims (IBTimes), but no specific phrase was given, so it needs a sourced term first.

Account bios ("Veteran, Christian, Father") cannot be measured with counts and would need post reads.

## Sources

- Cloudflare: https://blog.cloudflare.com/yandex-outage/
- Lawfare (Renée DiResta): https://www.lawfaremedia.org/article/the-russian-bots-went-silent.-or-did-they
- Texty (Graphika): https://texty.org.ua/fragments/118487/chy-zmusyly-udary-po-data-centrax-yandeksu-zamovknuty-rosijskyx-botiv-analiz-graphika/
- ZDFheute: https://www.zdfheute.de/politik/ausland/faktencheck-yandex-angriffe-ukraine-russland-social-bots-100.html
- IBTimes: https://www.ibtimes.co.uk/ukraine-yandex-strikes-maga-bots-claim-1825176
- Not checked: Brussels Signal https://brusselssignal.eu/2026/10/polish-minister-caught-citing-fake-story-about-russian-bots-demise-after-ukrainian-attack/ , Coin Edition https://coinedition.com/reddit-activity-fell-amid-yandex-strikes-russian-bots-or-coincidence/ , Gizmodo https://gizmodo.com/ukraines-zelenskyy-claims-strikes-on-russian-data-centers-silenced-social-media-bots-2000825044
