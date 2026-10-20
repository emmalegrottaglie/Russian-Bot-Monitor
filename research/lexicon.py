"""Build the coded-language term list, config/lexicon.csv.

Starts from the dog-whistle glossary of Mendelsohn, Le Bras, Choi and Sap (2023),
data/glossary.tsv in https://github.com/juliamendelsohn/dogwhistles (MIT licence;
notice in config/lexicon-NOTICE.md), downloaded to data/external/mendelsohn-2023/.
Only each entry's term, surface forms, persona, type, register and source are
taken; its usage examples, which quote real posts, are not. Terms documented by
other checked sources are added, and the review decisions recorded in
docs/CODED-COMMUNITIES.md are applied.

    python -m research.lexicon

Method: docs/CODED-COMMUNITIES.md.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "data" / "external" / "mendelsohn-2023" / "glossary.tsv"
OUT = ROOT / "config" / "lexicon.csv"
MENDELSOHN = "Mendelsohn et al. 2023 glossary"
MENDELSOHN_URL = "https://github.com/juliamendelsohn/dogwhistles"

# Personae outside the measure's scope (anti-trans, anti-LGBTQ and far-right language).
OUT_OF_SCOPE = {"liberal", "religious", "anti-vax", "climate change denier", "anti-GMO"}

# Review decisions (docs/CODED-COMMUNITIES.md). Antisemitism is not anti-Zionism:
# vocabulary of political speech about Israel is not counted; nor are named people.
EXCLUDED = {
    "Zionist": "Political speech about Israel and Zionism, not a coded term for Jews (Zio and Zios included; Emma, 20 Oct 2026)",
    "Israel Lobby": "Political speech about Israel and its lobby",
    "deadly exchange": "Name of a campaign against US-Israel police exchanges: anti-Zionist speech",
    "dual citizen": "Ordinary meaning dominates; political speech about Israel",
    "attacks on or imagery of Jewish financial leaders": "Named people, not a coded term",
    "attacks on or imagery of Jewish political leaders": "Named people, not a coded term",
    "George Soros": "Named person, not a coded term",
}
NOTES = {
    "dual loyalty": "Kept after review (Emma, 20 Oct 2026)",
    "open borders for Israel": "Kept after review (Emma, 20 Oct 2026)",
    "troon": "Also counted on X since October 2026 (docs/NARRATIVES.md); listed as a slur in Beth's Transphobia Glossary",
    "gender ideology": "Erin in the Morning (5 Feb 2026) calls it a far-right dog whistle, citing Human Rights Watch",
    "surgical wound": "See the 'gaping wound' check in docs/NARRATIVES.md: too rare on X to track",
}

FIELDS = ["term", "variants", "category", "type", "register", "status", "source", "source_url", "note", "precision"]

# Terms from other checked sources. "proposed" means suggested by Emma and still
# needing a documenting source before it is used.
EXTRA = [
    ("no such thing as trans", "no such thing as trans; no such thing as a trans; no such thing as trans kids",
     "transphobic", "candidate", "The 74, 14 Dec 2023",
     "https://www.the74million.org/article/in-private-texts-ny-ed-council-reps-congressional-candidate-demean-lgbtq-kids/",
     "Counted on X since October 2026 (docs/NARRATIVES.md)"),
    ("transgender ideology", "transgender ideology; trans ideology", "transphobic", "candidate",
     "Erin in the Morning, s. baum, 5 Feb 2026", "https://www.erininthemorning.com/p/republican-senator-attacks-netflix",
     "Called a far-right dog whistle, citing Human Rights Watch"),
    ("boys in girls' sports", "boys in girls' sports; boys in girls sports; men in women's sports", "transphobic", "candidate",
     "Erin in the Morning, Erin Reed, 11 Oct 2024", "https://www.erininthemorning.com/p/tx-dem-collin-allred-responds-to",
     "Called a common Republican anti-trans dogwhistle; the article gives no source for the label"),
    ("transgender extremist", "transgender extremist; transgender extremists; trans extremist; trans extremists", "transphobic", "candidate",
     "Transitics, Aleksandra Vaca, 19 Sep 2025", "https://www.transiticsnews.com/p/this-week-theres-been-a-massive-escalation",
     "Described as a right-wing media dog whistle"),
    ("trans violence", "trans violence; transgender violence; trans shooter; transgender shooter", "transphobic", "candidate",
     "Transitics, Aleksandra Vaca, 11 Feb 2026", "https://www.transiticsnews.com/p/conservatives-escalate-false-claims",
     "Described as a right-wing hoax; Transitics cites FactCheck.org that trans people were behind under 0.1% of mass shootings since 2013. Counts will include reporting and rebuttals"),
    ("Trantifa", "Trantifa", "transphobic", "candidate",
     "Transitics, Aleksandra Vaca, 11 Feb 2026", "https://www.transiticsnews.com/p/conservatives-escalate-false-claims",
     "Used in a speech the article cites as escalating rhetoric"),
    ("transgenderism", "transgenderism", "transphobic", "candidate",
     "Transitics, Aleksandra Vaca, 11 Feb 2026; Erin in the Morning, s. baum, 28 Apr 2025",
     "https://www.transiticsnews.com/p/conservatives-escalate-false-claims",
     "Framing of trans identity as an ideology"),
    ("zippertits", "zippertits", "transphobic", "candidate",
     "Beth's Transphobia Glossary", "https://bethylamine.github.io/library/glossary/", "Slur for trans men"),
    ("single-sex spaces", "single-sex spaces; single sex spaces; single-sex space", "transphobic", "proposed",
     "Emma, 20 Oct 2026", "", "Related to 'sex-based rights' (Mendelsohn); needs a documenting source"),
    ("single-sex rights", "single-sex rights; single sex rights", "transphobic", "proposed",
     "Emma, 20 Oct 2026", "", "Related to 'sex-based rights' (Mendelsohn); needs a documenting source"),
    ("biology-based rights", "biology-based rights; biology based rights", "transphobic", "proposed",
     "Emma, 20 Oct 2026", "", "Related to 'sex-based rights' (Mendelsohn); needs a documenting source"),
]


def main() -> None:
    csv.field_size_limit(10**7)
    with GLOSSARY.open(encoding="utf-8") as f:
        glossary = list(csv.DictReader(f, delimiter="\t"))
    rows = []
    for g in glossary:
        term, persona = g["Dogwhistle"].strip(), g["Persona/In-Group"].strip()
        status = "excluded" if term in EXCLUDED else "out of scope" if persona in OUT_OF_SCOPE else "candidate"
        source = g["Source"].strip()
        link = g["Link"].strip()
        if link and not link.startswith(("http://", "https://")):  # a few glossary links omit the scheme
            link = "https://" + link
        rows.append({
            "term": term,
            "variants": g["Surface Forms"].strip(),
            "category": persona,
            "type": g["Type"].strip(),
            "register": g["Register"].strip(),
            "status": status,
            "source": f"{MENDELSOHN}; cites {source}" if source else MENDELSOHN,
            "source_url": link or MENDELSOHN_URL,
            "note": EXCLUDED.get(term) or NOTES.get(term, ""),
            "precision": "",
        })
    for term, variants, category, status, source, url, note in EXTRA:
        rows.append({"term": term, "variants": variants, "category": category, "type": "", "register": "",
                     "status": status, "source": source, "source_url": url, "note": note, "precision": ""})
    rows.sort(key=lambda r: (r["category"], r["term"].lower()))
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"{len(rows)} terms written to {OUT.relative_to(ROOT)}: {by}")


if __name__ == "__main__":
    main()
