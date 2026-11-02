"""Pro-Kremlin disinformation about LGBTQ+ people in the EUvsDisinfo database.

Reads the open copy of the database by Barbaro and Skumanich (Mendeley Data,
doi:10.17632/yhdtkszvgp.3, CC BY 4.0: 14,497 cases, January 2015 to November 2022),
kept in data/external/euvsdisinfo/ (not in git). Finds cases about LGBTQ+ people by
the words in their title and disinformation summary, tags each with the themes it
uses, and writes docs/euvsdisinfo-lgbtq-cases.csv (date, link, title, outlets,
target countries, themes) plus counts by year, theme and country.

Matching is by words, so it is checked by hand: every matched case's title is
printed, and cases whose only match is ambiguous are listed separately.

    python -m research.euvsdisinfo_lgbtq
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "external" / "euvsdisinfo" / "euvsdisinfo_all_texts_rename.csv"
OUT = ROOT / "docs" / "euvsdisinfo-lgbtq-cases.csv"
BASE = "https://euvsdisinfo.eu"

# A case is about LGBTQ+ people if its title or disinformation summary uses one of these.
LGBTQ = re.compile(
    r"\b(lgbt\w*|lgbtq\w*|lgbtiq\w*|gay\w*|homosexual\w*|lesbian\w*|transgender\w*|transsexual\w*|"
    r"queer\w*|bisexual\w*|same[- ]sex|sodom\w*|gayropa|gay[- ]?pride|pride (?:parade|march|month)|"
    r"gender ideology|gender[- ]neutral|sex(?:ual)? minorit\w*|non-binary|drag queen\w*|"
    r"sex change|gender reassignment|third gender|genderless)\b", re.I)

# Themes, by the words that signal them in the same text.
THEMES = {
    "children": r"\b(child\w*|kids?|school\w*|minors?|paedophil\w*|pedophil\w*|grooming|juvenile|parents?|sex education)\b",
    "family and traditional values": r"\b(traditional values?|family|families|marriage|christian\w*|church|orthodox|moral\w*|spiritual\w*)\b",
    "Western decline": r"\b(decline|decay\w*|degenera\w*|decaden\w*|perver\w*|sick|satan\w*|gayropa|liberal fascis\w*|depravity|sodom\w*|end of (?:europe|the west))\b",
    "imposed by the West": r"\b(impos\w*|force[sd]?|forcing|agenda|propaganda|dictat\w*|totalitarian|brussels|soros|globalis\w*|nato|washington)\b",
    "sport": r"\b(sport\w*|olympic\w*|athlet\w*|boxing|football|swimm\w*|competition)\b",
    "Ukraine": r"\b(ukrain\w*|kyiv|kiev|zelensk\w*|maidan|donbas\w*)\b",
    "elections and politics": r"\b(election\w*|vote|voting|referendum|candidate\w*|parliament\w*|president\w*|party)\b",
    "transgender people": r"\b(transgender\w*|transsexual\w*|sex change|gender reassignment|non-binary|third gender|genderless|gender[- ]neutral)\b",
}
THEMES = {k: re.compile(v, re.I) for k, v in THEMES.items()}
# Words that match LGBTQ but often mean something else; such cases are reported for a check.
AMBIGUOUS = re.compile(r"^(gay\w*|pride (?:parade|march|month)|sodom\w*)$", re.I)


def year(date: str) -> str:
    return date.split(".")[-1]


def main() -> None:
    if not SRC.exists():
        sys.exit(f"missing {SRC}: download it from doi:10.17632/yhdtkszvgp.3")
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    hits = []
    for r in rows:
        text = f"{r['Title']} {r['Disinformation']}"
        words = {m.group(0).lower() for m in LGBTQ.finditer(text)}
        if not words:
            continue
        themes = [k for k, rx in THEMES.items() if rx.search(text)]
        hits.append({"date": r["Date"], "link": BASE + r["Links"], "title": r["Title"], "outlets": r["Outlets"],
                     "countries": r["Country"], "themes": "; ".join(themes), "matched": "; ".join(sorted(words)),
                     "_ambiguous": all(AMBIGUOUS.match(w) for w in words)})
    hits.sort(key=lambda h: h["date"].split(".")[::-1])
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "link", "title", "outlets", "countries", "themes", "matched"],
                           lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(hits)

    print(f"{len(hits)} of {len(rows)} cases ({100 * len(hits) / len(rows):.1f}%) mention LGBTQ+ people; written to {OUT.relative_to(ROOT)}")
    by_year, all_year = Counter(year(h["date"]) for h in hits), Counter(year(r["Date"]) for r in rows)
    print("by year (cases, share of all cases that year):")
    for y in sorted(all_year):
        print(f"  {y}: {by_year[y]:4} ({100 * by_year[y] / all_year[y]:.1f}%)")
    print("themes:", Counter(t for h in hits for t in h["themes"].split("; ") if t).most_common())
    print("target countries:", Counter(c.strip() for h in hits for c in h["countries"].split(",") if c.strip()).most_common(15))
    print("outlets:", Counter(o.strip() for h in hits for o in h["outlets"].split(",") if o.strip()).most_common(12))
    amb = [h for h in hits if h["_ambiguous"]]
    print(f"{len(amb)} cases matched only an ambiguous word; check them:")
    for h in amb:
        print(f"  {h['date']} [{h['matched']}] {h['title']}")


if __name__ == "__main__":
    main()
