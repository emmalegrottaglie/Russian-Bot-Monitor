"""Check this tracker's subreddit labels against two published classifications.

- Waller and Anderson (2021), "Quantifying social organization and political
  polarization in online platforms", Nature 600: a partisan score for the 10,006
  largest subreddits, from who comments where, 2005 to 2018.
  https://github.com/CSSLab/social-dimensions (data/scores.csv; no licence stated,
  so the file is kept locally and only per-subreddit results are published).
- Hofmann, Schütze and Pierrehumbert (2022), "The Reddit Politosphere", ICWSM:
  605 political subreddits, 2008 to 2019, tagged banned, party, politician, region
  and gun. https://doi.org/10.5281/zenodo.5851729 (CC BY 4.0).

Download both into data/external/ (see docs/SUBREDDIT-LABELS.md), then:

    python -m research.subreddit_labels

Writes docs/subreddit-label-check.csv and prints a summary. Method and limits:
docs/SUBREDDIT-LABELS.md.
"""

from __future__ import annotations

import bisect
import csv
import json
import statistics
from pathlib import Path

from tracker.config import load_config

ROOT = Path(__file__).resolve().parent.parent
WALLER = ROOT / "data" / "external" / "waller-anderson-2021" / "scores.csv"
POLITOSPHERE = ROOT / "data" / "external" / "politosphere-2022" / "subreddits_metadata.json"
OUT = ROOT / "docs" / "subreddit-label-check.csv"

# Thresholds on the partisan score, in standard deviations from the mean of all
# 10,006 subreddits. Every right-wing subreddit this tracker started with scores
# above +2.7 and r/democrats -4.7, while the four non-political controls stay within
# ±1.4, so ±2 separates organised partisan communities from ordinary ones. 1.5 to 2
# is reported as a lean, for review only.
STRONG, LEAN = 2.0, 1.5


def waller_scores() -> tuple[dict[str, float], list[float]]:
    with WALLER.open(encoding="utf-8") as f:
        raw = {r["community"].lower(): float(r["partisan"]) for r in csv.DictReader(f)}
    mu, sd = statistics.mean(raw.values()), statistics.pstdev(raw.values())
    z = {k: (v - mu) / sd for k, v in raw.items()}
    return z, sorted(z.values())


def politosphere() -> dict[str, dict]:
    with POLITOSPHERE.open(encoding="utf-8") as f:
        return {d["subreddit"].lower(): d for d in map(json.loads, f) if d}


def reading(z: float | None) -> str:
    if z is None:
        return "not scored"
    if abs(z) >= STRONG:
        return "right" if z > 0 else "left"
    if abs(z) >= LEAN:
        return "leans right" if z > 0 else "leans left"
    return "no lean"


def check(ours: str, waller: str, polito: dict | None) -> str:
    """Where a published source disagrees with our label, or suggests one."""
    party = (polito or {}).get("party")
    notes = []
    if ours == "political-right" and waller in ("left", "leans left", "no lean"):
        notes.append("Waller does not place it on the right")
    if ours == "political-left" and waller in ("right", "leans right", "no lean"):
        notes.append("Waller does not place it on the left")
    if ours == "political-right" and party == "dem" or ours == "political-left" and party == "rep":
        notes.append("Politosphere party tag contradicts our label")
    if ours not in ("political-right", "political-left") and waller in ("right", "left"):
        # Outside political communities the score reflects who the audience is, not a
        # politics the community is organised around (docs/SUBREDDIT-LABELS.md).
        audience = "" if polito or ours != "unlabelled" else " (not a Politosphere political subreddit: reflects its audience)"
        notes.append(f"Waller places it strongly {waller}{audience}")
    if ours not in ("political-right", "political-left") and party:
        notes.append(f"Politosphere tags it {'Democratic' if party == 'dem' else 'Republican'}")
    if polito and polito.get("banned"):
        notes.append("banned by 2022 (Politosphere)")
    return "; ".join(notes)


def ours() -> dict[str, tuple[str, str]]:
    """Every subreddit we track or listed, with our label and where the label comes from."""
    out: dict[str, tuple[str, str]] = {}
    for name, label in (("subreddit-candidates-general.csv", None), ("subreddit-candidates.csv", None)):
        with (ROOT / "docs" / name).open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[r["subreddit"].lower()] = (r["your_decision"] or "unlabelled", f"candidate list ({name})")
    for s in load_config().series:
        if s.platform == "reddit":
            tag = next((t for t in s.tags), "")
            out[s.params["subreddit"].lower()] = (tag, "tracked")
    return out


def main() -> None:
    z, dist = waller_scores()
    polito = politosphere()
    rows = []
    for sub, (label, origin) in sorted(ours().items()):
        zs = z.get(sub)
        p = polito.get(sub)
        w = reading(zs)
        rows.append({
            "subreddit": sub,
            "our_label": label,
            "in": origin,
            "waller_partisan_z": "" if zs is None else f"{zs:+.2f}",
            "waller_percentile": "" if zs is None else f"{100 * bisect.bisect_left(dist, zs) / len(dist):.1f}",
            "waller_reading": w,
            "politosphere_party": (p or {}).get("party", "") if p else "",
            "politosphere_banned": "" if p is None else str(p.get("banned", "")),
            "politosphere_listed": "yes" if p else "no",
            "flag": check(label, w, p),
        })
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    # Calibration: how the ±2 rule sorts the Politosphere's party-affiliated subreddits.
    for party, side in (("rep", "right"), ("dem", "left")):
        names = [k for k, d in polito.items() if d.get("party") == party]
        scored = [reading(z[k]) for k in names if k in z]
        print(f"Politosphere {party}: {len(names)} listed, {len(scored)} scored by Waller, "
              f"{sum(r == side for r in scored)} read '{side}', {sum(r == 'leans ' + side for r in scored)} 'leans {side}'")
    flagged = [r for r in rows if r["flag"]]
    print(f"{len(rows)} subreddits checked, {sum(r['waller_reading'] != 'not scored' for r in rows)} scored by Waller, "
          f"{len(flagged)} flagged. Written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
