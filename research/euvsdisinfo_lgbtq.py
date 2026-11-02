"""Pro-Kremlin disinformation about LGBTQ+ people in the EUvsDisinfo database.

Reads the open copy of the database by Barbaro and Skumanich (Mendeley Data,
doi:10.17632/yhdtkszvgp.3, CC BY 4.0: 14,497 cases, January 2015 to November 2022),
kept in data/external/euvsdisinfo/ (not in git). Finds cases about LGBTQ+ people by
the words in their title and disinformation summary, tags each with the themes it
uses, and writes docs/euvsdisinfo-lgbtq-cases.csv (date, link, title, outlets,
target countries, themes) plus counts by year, theme and country.

With --mcp it reads instead the full database downloaded through EUvsDisinfo's MCP
server (research/euvsdisinfo_mcp.py: every case from 2015 to now, with EUvsDisinfo's
own keyword tags) and writes docs/euvsdisinfo-lgbtq-cases-mcp.csv. A case then counts
if its words match or EUvsDisinfo tagged it with one of TAGS; the `tags` column shows
which tags it has, so the two ways of finding cases can be compared.

Matching is by words, so it is checked by hand: every matched case's title is
printed, and cases whose only match is ambiguous are listed separately.

    python -m research.euvsdisinfo_lgbtq          # Mendeley copy, 2015 to 2022
    python -m research.euvsdisinfo_lgbtq --mcp    # MCP download, 2015 to now
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "external" / "euvsdisinfo" / "euvsdisinfo_all_texts_rename.csv"
OUT = ROOT / "docs" / "euvsdisinfo-lgbtq-cases.csv"
MCP_SRC = ROOT / "data" / "external" / "euvsdisinfo" / "mcp" / "cases.jsonl"
MCP_OUT = ROOT / "docs" / "euvsdisinfo-lgbtq-cases-mcp.csv"
# EUvsDisinfo's own keyword tag for cases about LGBTQ+ people. Of its 619 tags (MCP
# download, 2 November 2026) the others that come close are not counted: of 45 cases
# tagged "Perversion", 27 neither carry LGBTIQ+ nor name LGBTQ+ people, and most of those
# are about paedophilia or incest; "Gender issues" (9 cases) is about men and women.
TAGS = {"lgbtiq+"}
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
    return date[:4]


def mendeley_cases() -> list[dict]:
    """The Mendeley copy, in the common shape: date (YYYY-MM-DD), link, title, text,
    outlets, countries, tags."""
    if not SRC.exists():
        sys.exit(f"missing {SRC}: download it from doi:10.17632/yhdtkszvgp.3")
    out = []
    for r in csv.DictReader(SRC.open(encoding="utf-8")):
        d, m, y = r["Date"].split(".")
        out.append({"date": f"{y}-{int(m):02}-{int(d):02}", "link": BASE + r["Links"], "title": r["Title"],
                    "text": f"{r['Title']} {r['Disinformation']}", "outlets": r["Outlets"],
                    "countries": r["Country"], "tags": []})
    return out


def _plain(markup: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))


def mcp_cases() -> list[dict]:
    """The MCP download, in the same shape. The disinformation summary is the case's
    `claim`; outlets are the web domains of its links to the disinformation."""
    if not MCP_SRC.exists():
        sys.exit(f"missing {MCP_SRC}: run python -m research.euvsdisinfo_mcp first")
    out = []
    for line in MCP_SRC.read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        domains = []
        for link in c.get("linksToDisinformation") or []:
            host = urlparse(link.get("url") or link.get("link") or "").netloc.removeprefix("www.")
            if host and host not in domains:
                domains.append(host)
        out.append({"date": datetime.fromtimestamp(c["date"], timezone.utc).strftime("%Y-%m-%d"), "link": c["url"],
                    "title": c["title"], "text": f"{c['title']} {_plain(c.get('claim'))}",
                    "outlets": ", ".join(domains), "countries": ", ".join(k["title"] for k in c.get("countries") or []),
                    "tags": [k["title"] for k in c.get("keywords") or []]})
    return out


def main() -> None:
    use_mcp = "--mcp" in sys.argv[1:]
    rows = mcp_cases() if use_mcp else mendeley_cases()
    out_path = MCP_OUT if use_mcp else OUT
    hits = []
    for r in rows:
        words = {m.group(0).lower() for m in LGBTQ.finditer(r["text"])}
        tagged = [t for t in r["tags"] if t.lower() in TAGS]
        if not words and not tagged:
            continue
        themes = [k for k, rx in THEMES.items() if rx.search(r["text"])]
        hits.append({**r, "themes": "; ".join(themes), "matched": "; ".join(sorted(words)),
                     "tags": "; ".join(tagged), "_ambiguous": not tagged and all(AMBIGUOUS.match(w) for w in words)})
    hits.sort(key=lambda h: h["date"])
    fields = ["date", "link", "title", "outlets", "countries", "themes", "matched"] + (["tags"] if use_mcp else [])
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(hits)

    print(f"{len(hits)} of {len(rows)} cases ({100 * len(hits) / len(rows):.1f}%) are about LGBTQ+ people; written to {out_path.relative_to(ROOT)}")
    if use_mcp:
        both = sum(1 for h in hits if h["matched"] and h["tags"])
        print(f"found by words and by tag: {both}; by words only: {sum(1 for h in hits if not h['tags'])}; "
              f"by tag only: {sum(1 for h in hits if not h['matched'])}")
    by_year, all_year = Counter(year(h["date"]) for h in hits), Counter(year(r["date"]) for r in rows)
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
