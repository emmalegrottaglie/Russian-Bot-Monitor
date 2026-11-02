# Studies

Emma, 2 November 2026: instead of constant updates, the site shows **studies**, each a fixed window around an event, so the question (did activity change before and after?) stays in view and the charts stay anchored to the event. The rolling data stays on the History tab.

## What a study is

- **One event, or a cluster of them**, named in `config/studies.toml` by their `short` labels in `config/events.toml`.
- **Window:** 14 days before the UTC day of the first event to 14 days after the UTC day of the last (Emma agreed 14 days each side). The strikes study runs from 23 September to 25 October 2026: the first strike, at Sasovo, was at 23:30 UTC on 7 October.
- **Phases:** before (the 14 days), during (the event days, 7 to 11 October for the strikes) and after (the 14 days).
- **Reference ("normal", index 100):** the 21 days before the first event's day, 16 September to 6 October for the strikes. It gives the hour-by-hour index (each hour against the same weekday-hour 1 to 3 weeks earlier) its full comparison period. The rolling site used 15 September to 7 October, so study numbers differ slightly from what the site showed before.

## Building and freezing

```
python -m tracker study build            # the newest study, printed, nothing saved
python -m tracker study build strikes-2026-10 --freeze --note "First version: ..."
python -m tracker study list
```

`build` runs the same analysis as the live site with "now" set to the window's end, so a closed study's numbers do not change as new data arrives (tested). `--freeze` stores the build as `studies/<id>/v<N>.json` with the build time, the code commit and the note. Freezing is refused while the window is still open.

The site shows the newest frozen version, or a provisional build marked as such while there is none. A new version is deliberate: when data is repaired or the method changes, build again, freeze with a note saying what changed, and keep the old version for comparison.

**When to freeze.** Only when the window's data is complete: the Reddit archive has caught up (it runs about 2 days behind), every community's history covers the reference period, refused archive windows have been refetched, and the Twitter gap is filled. For the strikes study that means the 60-day Reddit backfill started on 2 November 2026 has to finish first.

## Collection around studies

Emma, 2 November 2026: collection should pause when a study's window has its data and analysis, and come back when a major event that fits the research happens. The machinery is in `tracker/pause.py` and `tracker/study.py` (docs/HOSTING.md, "Pausing between developments"):

- **Opening.** Resuming with an event (the daily watch when Yandex Cloud recovers, the daily news check after a major event, or `tracker resume --event-...` by hand) appends the event to `config/events.toml` with its source and status, and a study around it to `config/studies.toml`: 14 days each side, 21-day reference, so the newest study becomes the main page. The paused period, including the study's before-days, is reloaded from history.
- **Closing.** After each collection pass, `close_if_done` looks at the newest study. Once its window has ended and 3 more days have passed (the Reddit archive runs about 2 days behind), it builds the study; if every group that has its before-period also has its after-period (one missing day allowed), it freezes version 1 with an automatic note and collection pauses with the reason "Study complete". If some groups are still short, it waits, and 10 days after the window it freezes anyway, naming those groups in the note.
- A resume without an event re-enables collection only. The newest study is then closed by the same rule, so if it is still unfrozen it will be frozen and collection paused again at the next pass.
