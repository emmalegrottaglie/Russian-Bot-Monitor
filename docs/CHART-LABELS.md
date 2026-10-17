# Chart labelling: research and proposals

October 2026. Prompted by feedback that the y axis of the correlation chart is not clearly labelled.

## How this was researched

A research agent ran 14 web searches and read 13 pages. Only pages that were actually read are cited as sources below. Some sources could not be read: the Urban Institute style guide, the FT Visual Vocabulary, Our World in Data's chart documentation, Schwabish's *Better Data Visualizations*, Stephen Few's essay on dual axes, and a chapter on uncertainty by Padilla, Kay and Hullman. Points that rest only on those are marked *unverified*.

## What the guidance says

### Axis labels and units

- **Say what the numbers are, next to the numbers.**
  - The EU Data Visualisation Guide calls axis labels indispensable unless enough points are labelled directly. It suggests 2 to 8 labels on a numeric axis. [data.europa.eu](https://data.europa.eu/apps/data-visualisation-guide/axes-grids-and-legends)
  - Datawrapper leaves out axis titles on most charts. It puts the measure in the title or description, the unit on the tick numbers (for example "%"), and uses a short text annotation as the axis label where needed. Avoid rotated text. [Datawrapper Academy](https://www.datawrapper.de/academy/why-datawrapper-does-not-include-axis-labels-for-many-charts)
  - The UK Government Analysis Function puts the unit in the chart title or at the top of the value axis, and keeps all text horizontal. [Analysis Function](https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-chart-examples)
- **The time axis needs no title. The value axis does.** No source requires titles on both axes.
- **Name the base period with its dates.** The US Bureau of Labor Statistics labels an index by its base period, for example "1982–84 = 100". [BLS Handbook of Methods](https://www.bls.gov/opub/hom/topic/index-number-formulae.htm)

### Index charts ("100 = normal")

- **What the numbers mean.** On an index, 100 is the average of the reference period: 110 is 10% above it and 90 is 10% below it. Describe changes in percent, not "index points". [BLS](https://www.bls.gov/opub/hom/topic/index-number-formulae.htm)
- **The reference line.** Draw it in grey, behind the data, and label it. [Datawrapper Academy](https://www.datawrapper.de/academy/what-to-consider-when-creating-line-charts)
- **Indexing instead of two y axes.** Indexing every series to its own reference is the usual alternative to dual axes (Few, *unverified*). This site already does this.
- **Percent and percentage points are different units.** The gap between two percentages is in percentage points, and the difference chart should say so on its axis.

### Lines, events, titles

- **Label lines directly**, at their right-hand end, instead of using a legend. Legends make the eye travel back and forth, and fail in greyscale and for colour-blind readers. [EU guide](https://data.europa.eu/apps/data-visualisation-guide/direct-labelling)
- **Event marks.** Use dashed vertical lines with short labels. Put longer text in a lettered note or a box that gridlines don't show through. [Analysis Function](https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-chart-examples)
- **Title, subtitle, source.** The Analysis Function pairs a headline title with a subtitle giving the measure, place and dates, plus a source line naming who owns the data.

### Y-axis range

- **Starting above zero exaggerates.** Correll, Bertini and Franconeri (CHI 2020) found that a y axis starting above zero made people see bigger effects, for line charts as well as bars. Warning cues such as broken axes did not remove the effect. [arXiv 1907.02035](https://arxiv.org/abs/1907.02035)
- **No universal rule.** Datawrapper says line charts need not start at zero but should include it when values are near it. [Datawrapper blog](https://www.datawrapper.de/blog/line-charts) Correll et al. give no blanket rule either: the scale should match the size of effect you mean to show.
- **Avoid two y axes.** Whoever draws the chart decides where the lines cross.

### Uncertainty and gaps

- **Bands get misread.** People tend to read error bars and overlapping bands as real differences (Padilla, Kay and Hullman, *unverified*). A band needs words that say what it is, not only a shade.
- **No source rule for gaps.** No source found sets a rule for showing gaps or small samples. This project's own rule applies: missing data is a break in the line, never a zero.

### Accessibility

- **Colour can't be the only cue** (WCAG 1.4.1). Each line also needs a label, dash or marker. [W3C](https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html)
- **Lines need contrast.** Each line needs 3:1 contrast against the background (WCAG 1.4.11). [W3C](https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html)
- **Complex charts need two text alternatives:** a short text alternative plus a longer description or data table nearby. [W3C WAI tutorial](https://www.w3.org/WAI/tutorials/images/complex/)

## Where this site stands

| Point | Now | Guidance | Verdict |
|---|---|---|---|
| Value axis unit | Bare tick numbers (0 / 100 / 200). The unit is only in the hover readout and the screen-reader label | Unit or definition at the top of the axis or on the ticks | **Fix.** This also breaks our own design guide: "every number is labeled" |
| Meaning of 100 | "100 = PRE-STRIKE" written on the baseline, where it can collide with line labels | Name the base period by its dates | **Fix.** Say "100 = AVERAGE 09-15 TO 10-07" |
| Number of ticks | 3 (zero, middle, top) | 2 to 8 | **Improve.** Use 5, always including 100 on index charts |
| Value axis starts at | 0 | Starting above zero exaggerates change | **Keep** |
| Dual axes | None; series are indexed | Avoid | **Keep** |
| Line labels | Direct, at the line's end | Direct labels | **Keep**; check that they don't collide on phones |
| Events | Dashed lines with short vertical labels | Same | **Keep** |
| Difference chart unit | "PTS VS CONTROL" in the readout only | Percentage points on the axis | **Fix.** Ticks like "+20 PP", axis note "PERCENTAGE POINTS, GROUP MINUS CONTROL" |
| Normal-range band | Labelled "NORMAL RANGE" | Explain the band in words | **Improve.** Say "90% OF PRE-STRIKE DAYS FELL HERE" |
| Subtitle and source line | Captions exist only on the shared PNG | Measure, place, dates, source under every chart | **Improve.** Show the caption under each chart on the page too |
| Title states the takeaway | Neutral titles | Headline titles recommended | **Deliberately not followed.** The effect is contested, and a headline title would state a conclusion the data doesn't support yet |
| Text alternatives | Short label, keyboard readout, data table | Short alternative plus long description or table | **Keep** |

## Proposed changes, most useful first

1. **Axis title on every chart.** A short line in small muted capitals, above the top-left of the plot and never rotated, naming the unit. Examples: "% OF PRE-STRIKE AVERAGE", "PERCENTAGE POINTS VS CONTROL", "POSTS / H".
2. **Name the reference period by its dates on index charts.** The baseline label becomes "100 = AVERAGE 09-15 TO 10-07", taken from the config rather than hard-coded.
3. **Put the unit on the tick numbers where it is short**: "%" on index charts, a sign plus "PP" on the difference chart.
4. **Five value ticks**, with 100 always one of them on index charts, so a reader can see "150 = half again above normal" at a glance.
5. **Show each chart's caption on the page**, not only in the shared PNG. It says what was measured, how often, the timezone and the source.
6. **Explain the normal-range band in words** on the chart.
7. **Write changes as percent in readouts and tiles**, e.g. "+47% VS PRE-STRIKE" next to the index value 147, so nobody has to do the arithmetic.

Items 1 to 4 are a contained change to the shared `chart()` function in `web/app.js`, so every chart gets them at once. Items 5 to 7 are copy changes.

**Status:** all seven were built on 2026-10-18. Tick labels on plain-unit charts also take their decimals from the tick step (0, 25, 50 rather than 0.00, 25.0, 50.0), and the reference-line and band labels have a background halo, because they sit over the data.
