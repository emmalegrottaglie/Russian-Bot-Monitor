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
# Terms whose ordinary meaning dominates: not counted until a hand check shows most
# uses are coded (Emma, 21 Oct 2026: "it's gonna create a lot of bad data").
AMBIGUOUS = {
    "bankers", "banksters", "central bankers", "international bankers", "Federal Reserve", "Rothschilds", "shekels",
    "global elite", "globalism", "globalist", "cabal", "deep state", "New World Order", "Illuminati",
    "Trilateral Commission", "puppet masters", "pulling strings", "string puller", "octopus", "controlled media",
    "special interests", "cosmopolitan", "cosmopolitan elite", "cosmopolitanism", "rootless cosmopolitan",
    "citizens of nowhere", "Hollywood elite", "New York elite", "New York intellectuals", "New York values",
    "coastal elite", "cultural Marxism", "cultural Marxists", "coincidence", "poisoning the well", "Judas", "pilpul",
    "Khazars", "America First", "blueish", "Skype", "YKW", "goy", "oy vey",
}

NOTES = {
    "dual loyalty": "Kept after review (Emma, 20 Oct 2026)",
    "open borders for Israel": "Kept after review (Emma, 20 Oct 2026)",
    "troon": "Also counted on Twitter since October 2026 (docs/NARRATIVES.md); listed as a slur in Beth's Transphobia Glossary",
    "gender ideology": "Erin in the Morning (5 Feb 2026) calls it a far-right dog whistle, citing Human Rights Watch",
    "surgical wound": "See the 'gaping wound' check in docs/NARRATIVES.md: too rare on Twitter to track",
}

FIELDS = ["term", "variants", "category", "type", "register", "status", "source", "source_url", "note", "precision"]

# Terms from other checked sources. "proposed" means suggested by Emma and still
# needing a documenting source before it is used. "framing" (Emma, 29 October 2026)
# marks the UK single-sex framing: counted on its own to show how often it comes up,
# never part of the coded-language score, because legal, policy and news discussion
# uses the same words.
EXTRA = [
    ("no such thing as trans", "no such thing as trans; no such thing as a trans; no such thing as trans kids",
     "transphobic", "candidate", "The 74, 14 Dec 2023",
     "https://www.the74million.org/article/in-private-texts-ny-ed-council-reps-congressional-candidate-demean-lgbtq-kids/",
     "Counted on Twitter since October 2026 (docs/NARRATIVES.md)"),
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
    ("single-sex spaces", "single-sex spaces; single sex spaces; single-sex space", "transphobic", "framing",
     "Emma, 20 Oct 2026; framing since 29 Oct 2026", "", "Framing: counted on its own, never part of the coded-language score; legal, policy and news discussion uses the same words. The campaign phrase 'protect single-sex spaces' is documented (Edinburgh SPN, Transvox) and listed separately as a candidate; the bare legal term is not"),
    ("single-sex rights", "single-sex rights; single sex rights", "transphobic", "framing",
     "Emma, 20 Oct 2026; framing since 29 Oct 2026", "", "Framing: counted on its own, never part of the coded-language score; legal, policy and news discussion uses the same words. Related to 'sex-based rights' (Mendelsohn), which is a candidate"),
    ("biology-based rights", "biology-based rights; biology based rights", "transphobic", "framing",
     "Emma, 20 Oct 2026; framing since 29 Oct 2026", "", "Framing: counted on its own, never part of the coded-language score; legal, policy and news discussion uses the same words. Related to 'sex-based rights' (Mendelsohn), which is a candidate"),
]

GLAAD = "GLAAD Guide to Anti-LGBTQ Online Hate and Disinformation (read 21 Oct 2026)"
GLAAD_URL = "https://glaad.org/smsi/anti-lgbtq-online-hate-speech-disinformation-guide/"
# (term, variants, category, note). Terms already in the list get GLAAD added as a source.
GLAAD_TERMS = [
    ("41%", "", "transphobic", "A coded call for self-harm aimed at trans people"),
    ("biological man", "biological pronouns", "transphobic", "Used to misgender trans women and men"),
    ("biological woman", "", "transphobic", "Used to misgender trans women and men"),
    ("gender ideology", "", "transphobic", "Frames trans people as an ideology"),
    ("transgender ideology", "trans agenda", "transphobic", "Frames trans people as an ideology or a coordinated movement"),
    ("transgenderism", "", "transphobic", "A dog whistle for contempt of trans people"),
    ("groomers", "", "anti-LGBTQ", "Slur casting LGBTQ people as predators"),
    ("troon", "", "transphobic", "Slur; spread from Kiwi Farms"),
    ("womanface", "", "transphobic", "Equates trans women and drag with blackface"),
    ("globohomo", "globohomo; globo homo", "anti-LGBTQ", "Combines homophobia and antisemitism"),
    ("LGBTP", "LGBTP; LGBTQP", "anti-LGBTQ", "Fake acronym claiming a 'P' for paedophiles"),
    ("CloverGender", "CloverGender; clover gender", "anti-LGBTQ", "4chan hoax tying trans people to paedophilia (in GLAAD's LGBTP entry)"),
    ("LGBTS", "LGBTS; LGBTQIAS", "anti-LGBTQ", "False claim that 'S' for Satanist was added"),
    ("rapid onset gender dysphoria", "rapid onset gender dysphoria; ROGD", "transphobic", "Pseudoscientific term; not a diagnosis"),
    ("super straight", "super straight; superstraight; #SuperStraight", "transphobic", "Transphobic meme from February 2021; r/superstraight was banned"),
    ("trans terrorism", "trans terrorism; trans terrorist; trans terrorists", "transphobic", "Fearmongering trope; no evidence of a threat, per experts cited"),
    ("transtrender", "transtrender; transtrenders", "transphobic", "Claims trans people follow a trend"),
    ("transvestigation", "transvestigation; transvestigator; transvestigators", "transphobic", "Conspiracy theory 'investigating' public figures as trans"),
    ("unwanted same-sex attraction", "unwanted same-sex attraction; overcome same-sex attraction; ex-gay", "homophobic", "Conversion-therapy phrasing; GLAAD lists many more variants"),
]


EDINBURGH = "Robert Court, 'Decoding the Hidden Messages', University of Edinburgh Staff Pride Network blog, 5 Jul 2023 (cites no sources)"
EDINBURGH_URL = "https://blogs.ed.ac.uk/staffpridenetwork/2023/07/05/decoding-the-hidden-messages-a-look-at-dog-whistles-in-the-gender-critical-movement/"
EDINBURGH_TERMS = [
    ("protect single-sex spaces", "protect single-sex spaces; protect single sex spaces; protecting single-sex spaces; protecting single sex spaces",
     "transphobic", "Used to exclude trans people from single-sex spaces"),
    ("sex-based rights", "defending sex-based rights; defend sex-based rights; defending sex based rights", "transphobic",
     "Used to argue against rights for trans people"),
    ("keep prisons single sex", "keep prisons single sex; keep prisons single-sex", "transphobic",
     "Used to argue for placing trans women in men's prisons"),
    ("sex matters", "sex matters; #SexMatters", "transphobic",
     "Used to deny trans identities. Also the name of a UK campaign group, so counts include mentions of the group"),
    ("homosexual means same-sex attracted", "homosexual means same-sex attracted; homosexual means same sex attracted", "transphobic",
     "Used to deny trans women's identities"),
    ("defend women's sports", "defend women's sports; defend women's sport", "transphobic",
     "Used to exclude trans women and girls from sport at every level"),
    ("adult human female", "", "transphobic", "Asserts trans women are men"),
    ("watchful waiting", "watchful waiting", "transphobic",
     "Used to delay medical transition. Also an ordinary clinical term, so precision will be low"),
    ("exploratory therapy", "exploratory therapy; gender exploratory therapy; exploration therapy", "anti-LGBTQ",
     "Euphemism for conversion therapy; GLAAD lists 'gender exploratory/exploration therapy' among conversion-therapy phrases"),
]

TRANSVOX = "Transvox podcast, 'Understanding Dog Whistles in Anti-Trans Discourse', Gillian Russell and Jenny Harvey, 22 Mar 2025"
TRANSVOX_URL = "https://transvox.co.uk/episode/transvox-understanding-dog-whistles-in-anti-trans-discourse"
TRANSVOX_TERMS = [
    ("protect single-sex spaces", "", "transphobic", "Questions about protecting single-sex spaces are often not asked in good faith"),
    ("sex matters", "", "transphobic", "Implies gender does not matter"),
    ("sex is real", "", "transphobic", "Implies gender does not matter"),
    ("biological sex", "biological sex", "transphobic",
     "Hosts argue it effectively means 'cisgender'. Also ordinary scientific usage; TransActual says it would not use the term"),
    ("protecting women and girls", "", "transphobic",
     "Hosts say 'women and girls' implies trans women are a threat; context matters, and the bare phrase is very common"),
    ("gender ideology", "", "transphobic", "Frames gender as an ideology"),
    ("adult human female", "", "transphobic", "Slogan implying trans women are not women"),
    ("transgenderism", "", "transphobic", "Casts gender identity as a political belief"),
    ("Trans Identified Male", "trans identifying; trans-identifying", "transphobic", "Used dismissively"),
    ("dark side of trans activism", "dark side of trans activism", "transphobic", "Signals to an already receptive audience"),
    ("family values", "", "homophobic", "An attack on the whole LGBTQ+ community"),
]

TRANSACTUAL = "TransActual, 'Transphobia' (undated page, © 2026)"
TRANSACTUAL_URL = "https://transactual.org.uk/transphobia/"
TRANSACTUAL_TERMS = [
    ("adult human female", "", "transphobic", "Given as an example of dogwhistle transphobia"),
    ("protect women's rights", "protect women's rights; protecting women's rights", "transphobic",
     "Label used by campaigns against trans women's access to toilets. Also very common in unrelated contexts"),
    ("Trans Identified Male", "trans identified males", "transphobic", "Misgenders trans women"),
    ("social contagion", "social contagion; gender contagion", "transphobic",
     "'Contagion' applied to trans young people; GLAAD's 'transtrender' entry also names the 'social contagion' theory"),
]

BARNARD = "Barnard College Library, 'TERFs in the Stacks' guide FAQ, updated 13 May 2026 (keyword list; no sources or definitions)"
BARNARD_URL = "https://guides.library.barnard.edu/terf/faq"
BARNARD_TERMS = [
    ("gender critical", "", "transphobic", "Listed as a keyword for identifying TERF materials"),
    ("transgenderism", "", "transphobic", "Listed as a keyword for identifying TERF materials"),
    ("sex-based feminism", "sex-based feminism; sex based feminism", "transphobic", "Listed as a keyword; not defined"),
    ("sex realist feminism", "sex realist feminism; sex-realist feminism", "transphobic", "Listed as a keyword; not defined"),
    ("gender eugenics", "gender eugenics", "transphobic", "Listed as a keyword; not defined"),
]

SOURCED = [
    ("GLAAD", GLAAD, GLAAD_URL, GLAAD_TERMS),
    ("Edinburgh SPN", EDINBURGH, EDINBURGH_URL, EDINBURGH_TERMS),
    ("Transvox", TRANSVOX, TRANSVOX_URL, TRANSVOX_TERMS),
    ("TransActual", TRANSACTUAL, TRANSACTUAL_URL, TRANSACTUAL_TERMS),
    ("Barnard", BARNARD, BARNARD_URL, BARNARD_TERMS),
]


def add_sourced(rows: list[dict]) -> None:
    """Add terms from further checked lists; a term already listed gains the list as a second source."""
    by_term = {r["term"].lower(): r for r in rows}
    for label, source, url, terms in SOURCED:
        for term, variants, category, note in terms:
            row = by_term.get(term.lower())
            if row:
                row["source"] += f"; {source}"
                row["note"] = "; ".join(x for x in (row["note"], f"{label}: {note}") if x)
                if variants:
                    have = {v.strip().lower() for v in row["variants"].split(";")}
                    extra = [v for v in variants.split("; ") if v.lower() not in have]
                    row["variants"] = "; ".join(x for x in (row["variants"], "; ".join(extra)) if x)
                continue
            row = {"term": term, "variants": variants or term, "category": category, "type": "", "register": "",
                   "status": "candidate", "source": source, "source_url": url, "note": note, "precision": ""}
            rows.append(row)
            by_term[term.lower()] = row


def main() -> None:
    csv.field_size_limit(10**7)
    with GLOSSARY.open(encoding="utf-8") as f:
        glossary = list(csv.DictReader(f, delimiter="\t"))
    rows = []
    for g in glossary:
        term, persona = g["Dogwhistle"].strip(), g["Persona/In-Group"].strip()
        status = ("excluded" if term in EXCLUDED else "out of scope" if persona in OUT_OF_SCOPE
                  else "ambiguous" if term in AMBIGUOUS else "candidate")
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
            "note": EXCLUDED.get(term) or NOTES.get(term, "") or ("Ordinary meaning dominates: not counted until a hand check" if term in AMBIGUOUS else ""),
            "precision": "",
        })
    for term, variants, category, status, source, url, note in EXTRA:
        rows.append({"term": term, "variants": variants, "category": category, "type": "", "register": "",
                     "status": status, "source": source, "source_url": url, "note": note, "precision": ""})
    add_sourced(rows)
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
