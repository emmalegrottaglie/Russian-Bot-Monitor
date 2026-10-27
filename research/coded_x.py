"""First look: coded anti-trans, anti-LGBTQ and far-right language on Twitter around the strikes.

Counts only (Twitter counts endpoints): no posts or accounts are read. For each category of
high-specificity terms from config/lexicon.csv, hourly English original posts and
reposts from 1 September 2026, plus Twitter's general-volume probe so a category can be read
as a rate. Then the strike-aligned index used on the site: each hour against the same
weekday-hour 1-3 weeks earlier, the three strikes lined up at hour 0, with a 5-95%
band from random pre-strike start times.

Only terms whose ordinary meaning is rare were chosen, by hand, because no term has a
measured precision yet. Treat the result as a first look, not a finding.

    python -m research.coded_x fetch      # spends Twitter credits: about $0.01 per request
    python -m research.coded_x analyze

Results (hourly totals only) go to data/research/coded_x.json. Approved by Emma on
21 October 2026, up to about $3. Method: docs/CODED-COMMUNITIES.md.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from tracker.analysis import HOUR, _quantile, _ratios, _smooth
from tracker.collectors import x
from tracker.config import Settings, load_config

OUT = Path(__file__).resolve().parent.parent / "data" / "research" / "coded_x.json"
START = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())
MAX_REQUESTS = 60  # hard stop for this run: $0.60 at full-archive prices
QUERY_LIMIT = 1024  # characters, full-archive counts

# Hand-picked from config/lexicon.csv: terms with little ordinary use. Grouped so each
# query stays under Twitter's length limit.
CATEGORIES = {
    "anti-trans slurs and memes": [
        "troon", "troons", "zippertits", "YWNBAW", '"you will never be a woman"', "transtrender", "transtrenders",
        "transvestigation", '"super straight"', "superstraight", "womanface", "Trantifa", '"trans terrorism"',
        "autogynephile", "autogynephilia", '"trans identified male"', '"trans identified males"',
    ],
    "anti-trans framing": [
        '"gender ideology"', '"trans ideology"', '"transgender ideology"', "transgenderism", '"trans agenda"',
        '"adult human female"', '"no such thing as trans"', '"no such thing as a trans"',
        '"rapid onset gender dysphoria"', '"sex-based rights"', '"protect single-sex spaces"',
        '"protect single sex spaces"',
    ],
    "anti-LGBTQ": [
        "globohomo", "LGBTP", "LGBTQP", "CloverGender", "LGBTQIAS", '"unwanted same-sex attraction"', '"ok groomer"',
    ],
    "antisemitic (coded)": [
        "6MWE", '"the goyim know"', "ZOG", "Zioworld", "Jwoke", "noticers", "#TheNoticing", '"Kalergi plan"',
        "kosherist", "Holocauster", "loxism", "countersemite", '"nose check"', "Cohencidence", '"dual loyalty"',
        '"open borders for Israel"',
    ],
    "racist and white supremacist": [
        "1488", '"it\'s okay to be white"', "RaHoWa", '"free helicopter rides"', '"physical removal"', "Amerimutt",
        '"clown world"', "magapede", "dindu", '"we wuz kangz"', '"bix nood"', "gibsmedat", '"coal burner"',
    ],
}
VARIANTS = {"orig": " -is:retweet", "rt": " is:retweet"}


def query(terms: list[str], variant: str) -> str:
    q = f"({' OR '.join(terms)}) lang:en{variant}"
    if len(q) > QUERY_LIMIT:
        raise ValueError(f"query too long ({len(q)} characters): {q[:60]}...")
    return q


async def fetch() -> None:
    settings = Settings.from_env()
    if not settings.x_bearer_token:
        sys.exit("X_BEARER_TOKEN not set")
    path = settings.db_path.parent / "x_usage.json"
    used = x._Budget(path, 0).state.get(time.strftime("%Y-%m-%d", time.gmtime()), 0)
    budget = x._Budget(path, used + MAX_REQUESTS)  # today's live use plus this run's ceiling
    stop = (int(time.time()) - 15) // HOUR * HOUR
    queries = {"probe": x.PROBE}
    for cat, terms in CATEGORIES.items():
        for v, suffix in VARIANTS.items():
            queries[f"{cat}|{v}"] = query(terms, suffix)
    out = {"start": START, "end": stop, "queries": queries, "hours": {}}
    async with httpx.AsyncClient(timeout=60) as client:
        for name, q in queries.items():
            got = await x._counts(client, budget, settings.x_bearer_token, x.ALL, q, START, stop, "hour")
            out["hours"][name] = {str(h): n for h, n in sorted(got.items())}
            print(f"{name}: {sum(got.values()):,} posts in {len(got)} hours")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out), encoding="utf-8")
    after = x._Budget(path, 0).state.get(time.strftime("%Y-%m-%d", time.gmtime()), 0)
    print(f"{after - used} requests, about ${0.01 * (after - used):.2f}. Saved to {OUT}")


async def breakdown(category: str, variant: str = "rt") -> None:
    """Per-term counts for one category, to see which terms drive its curve. Two
    full-archive requests per term (approved by Emma on 22 October 2026, about $0.26)."""
    settings = Settings.from_env()
    data = json.loads(OUT.read_text(encoding="utf-8"))
    path = settings.db_path.parent / "x_usage.json"
    used = x._Budget(path, 0).state.get(time.strftime("%Y-%m-%d", time.gmtime()), 0)
    budget = x._Budget(path, used + 2 * len(CATEGORIES[category]) + 2)
    stop = data["end"]
    terms = data.setdefault("terms", {})
    async with httpx.AsyncClient(timeout=60) as client:
        for term in CATEGORIES[category]:
            got = await x._counts(client, budget, settings.x_bearer_token, x.ALL, query([term], VARIANTS[variant]),
                                  START, stop, "hour")
            terms[f"{category}|{variant}|{term}"] = {str(h): n for h, n in sorted(got.items())}
            print(f"{term}: {sum(got.values()):,}")
    OUT.write_text(json.dumps(data), encoding="utf-8")
    after = x._Budget(path, 0).state.get(time.strftime("%Y-%m-%d", time.gmtime()), 0)
    print(f"{after - used} requests, about ${0.01 * (after - used):.2f}")


def analyze_terms() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    config = load_config()
    starts = [-(-e.ts // HOUR) * HOUR for e in config.events if e.ts <= data["end"] - 86400]
    gaps = {int(h) for h, n in data["hours"]["probe"].items() if n == 0}
    rows = []
    for name, hrs in data.get("terms", {}).items():
        counts = {int(h): float(n) for h, n in hrs.items() if int(h) not in gaps}
        total = sum(counts.values())
        pre = sum(n for h, n in counts.items() if h < min(starts)) / max(1, len({(h - 1) // 86400 for h in counts if h < min(starts)}))
        offsets, main, band, _ = aligned(counts, starts)
        after = [(v, lo) for o, v, (lo, hi) in zip(offsets, main, band) if o >= 0 and v is not None]
        below = sum(1 for v, lo in after if lo is not None and v < lo)
        mean_after = sum(v for v, _ in after) / len(after) if after else None
        rows.append((total, name.split("|")[-1], pre, mean_after, below, len(after)))
    grand = sum(r[0] for r in rows) or 1
    for total, term, pre, mean_after, below, n in sorted(rows, reverse=True):
        idx = f"{mean_after * 100:5.0f}" if mean_after else "    -"
        print(f"{term:28} {total:>8,.0f} ({100 * total / grand:4.1f}%)  {pre:7.1f}/day before  "
              f"index after {idx}  below band {below:2}/{n}")


def aligned(hours: dict[int, float], starts: list[int], span: int = 48, smooth: int = 3, draws: int = 500):
    """One series' strike-aligned index and its 5-95% placebo band (as on the site)."""
    r = _ratios(hours)
    offsets = list(range(-span, span + 1))

    def curve(ss):
        vals = []
        for o in offsets:
            vs = [r[s + o * HOUR] for s in ss if s + o * HOUR in r]
            vals.append(sum(vs) / len(vs) if vs else None)
        return _smooth(vals, smooth)

    main = curve(starts)
    pool = [h for h in range(min(r) + span * HOUR, min(starts) - span * HOUR, HOUR)] if r else []
    rng = random.Random("coded_x")
    sims = [curve([rng.choice(pool) for _ in starts]) for _ in range(draws)] if len(pool) >= 50 else []
    band = []
    for i in range(len(offsets)):
        vs = sorted(c[i] for c in sims if c[i] is not None)
        band.append((_quantile(vs, .05), _quantile(vs, .95)) if len(vs) >= 50 else (None, None))
    return offsets, main, band, len(pool)


def analyze() -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    config = load_config()
    starts = [-(-e.ts // HOUR) * HOUR for e in config.events if e.ts <= data["end"] - 86400]
    probe = {int(h): n for h, n in data["hours"]["probe"].items()}
    gaps = {h for h, n in probe.items() if n == 0}
    for name in data["hours"]:
        if name == "probe":
            continue
        counts = {int(h): float(n) for h, n in data["hours"][name].items() if int(h) not in gaps}
        days = {}
        for h, n in counts.items():
            days.setdefault((h - 1) // 86400, []).append(n)
        per_day = sorted(sum(v) for v in days.values() if len(v) >= 20)
        rate = {h: n / probe[h] * 1e6 for h, n in counts.items() if probe.get(h)}
        for label, series in (("count", counts), ("per million posts", rate)):
            offsets, main, band, pool = aligned(series, starts)
            after = [(v, lo, hi) for o, v, (lo, hi) in zip(offsets, main, band) if o >= 0 and v is not None]
            below = sum(1 for v, lo, hi in after if lo is not None and v < lo)
            above = sum(1 for v, lo, hi in after if hi is not None and v > hi)
            mean_after = sum(v for v, *_ in after) / len(after) if after else None
            print(f"{name:42} {label:18} median/day {per_day[len(per_day) // 2] if per_day else 0:>7,.0f}  "
                  f"index +0..48h mean {mean_after * 100 if mean_after else float('nan'):5.0f}  "
                  f"below band {below:2}/{len(after)}  above {above:2}/{len(after)}  (pool {pool} h)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fetch":
        asyncio.run(fetch())
    elif cmd == "analyze":
        analyze()
    elif cmd == "breakdown":
        asyncio.run(breakdown(sys.argv[2] if len(sys.argv) > 2 else "racist and white supremacist"))
    elif cmd == "terms":
        analyze_terms()
    else:
        sys.exit(__doc__)
