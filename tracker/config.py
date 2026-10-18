"""Settings from the environment and series definitions from config/*.toml."""

from __future__ import annotations

import os
import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

IODA_UNITS = {
    "ping-slash24": "/24 BLOCKS ANSWERING",
    "bgp": "PREFIXES ROUTED",
    "merit-nt": "TELESCOPE SOURCES",
}


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader: KEY=VALUE lines, existing environment wins."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    db_path: Path
    public_url: str
    interval_min: int
    cloudflare_token: str
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str
    x_api_key: str
    x_api_secret: str
    x_access_token: str
    x_access_secret: str
    x_bearer_token: str
    x_max_requests_per_day: int
    post_alerts: bool
    max_posts_per_day: int

    @property
    def x_configured(self) -> bool:
        return all((self.x_api_key, self.x_api_secret, self.x_access_token, self.x_access_secret))

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        env = os.environ.get
        db = Path(env("TRACKER_DB", "data/tracker.db"))
        return cls(
            db_path=db if db.is_absolute() else ROOT / db,
            public_url=env("TRACKER_PUBLIC_URL", "").rstrip("/"),
            interval_min=int(env("TRACKER_INTERVAL_MIN", "15")),
            cloudflare_token=env("CLOUDFLARE_API_TOKEN", ""),
            reddit_client_id=env("REDDIT_CLIENT_ID", ""),
            reddit_client_secret=env("REDDIT_CLIENT_SECRET", ""),
            reddit_user_agent=env("REDDIT_USER_AGENT", "web:bot-traffic-monitor:0.1"),
            x_api_key=env("X_API_KEY", ""),
            x_api_secret=env("X_API_SECRET", ""),
            x_access_token=env("X_ACCESS_TOKEN", ""),
            x_access_secret=env("X_ACCESS_TOKEN_SECRET", ""),
            x_bearer_token=env("X_BEARER_TOKEN", ""),
            x_max_requests_per_day=int(env("X_MAX_REQUESTS_PER_DAY", "150")),
            post_alerts=env("TRACKER_POST_ALERTS", "0") == "1",
            max_posts_per_day=int(env("TRACKER_MAX_POSTS_PER_DAY", "4")),
        )


# X series per keyword. "posts" (original posts) is the one group statistics use.
X_METRICS = (("posts", "POSTS / H"), ("reposts", "REPOSTS / H"), ("repost-share", "% REPOSTS"),
             ("replies", "REPLIES / H"), ("burst", "% IN BUSIEST 5 MIN"))

@dataclass(frozen=True)
class SeriesSpec:
    key: str
    kind: str  # "infrastructure" | "community"
    platform: str  # "ioda" | "cloudflare" | "reddit" | "bluesky" | "x"
    label: str
    unit: str
    region: str
    tags: tuple[str, ...]
    params: dict = field(default_factory=dict, hash=False, compare=False)


@dataclass(frozen=True)
class Event:
    ts: int
    timed: bool  # True when `at` gives a measured time, False for midnight of `date`
    short: str
    label: str
    status: str
    source: str


@dataclass(frozen=True)
class Config:
    series: tuple[SeriesSpec, ...]
    events: tuple[Event, ...]
    reference_start: int
    reference_end: int
    correlation_ref: str

    def by_platform(self, platform: str) -> list[SeriesSpec]:
        return [s for s in self.series if s.platform == platform]


def _day_ts(value: str | date, end: bool = False) -> int:
    d = value if isinstance(value, date) else date.fromisoformat(value)
    ts = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
    return ts + 86400 - 1 if end else ts


def _event_ts(e: dict) -> int:
    if "at" in e:
        at = e["at"] if isinstance(e["at"], datetime) else datetime.fromisoformat(str(e["at"]).replace("Z", "+00:00"))
        return int(at.timestamp())
    return _day_ts(e["date"])


def slug(text: str) -> str:
    # Accents are dropped first, so "fútbol" becomes "futbol" rather than "f-tbol".
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def parse_config(sources: dict, events: dict) -> Config:
    specs: list[SeriesSpec] = []

    for item in sources.get("infrastructure", []):
        asn, name = item["asn"], item["name"]
        if item["source"] == "ioda":
            for signal in item.get("signals", list(IODA_UNITS)):
                specs.append(SeriesSpec(
                    key=f"ioda.asn{asn}.{signal}", kind="infrastructure", platform="ioda",
                    label=f"{name} AS{asn}", unit=IODA_UNITS[signal], region="RU", tags=("infrastructure",),
                    params={"asn": asn, "signal": signal},
                ))
        elif item["source"] == "cloudflare":
            specs.append(SeriesSpec(
                key=f"cloudflare.asn{asn}.bot-pct", kind="infrastructure", platform="cloudflare",
                label=f"{name} AS{asn}", unit="% HTTP REQUESTS FROM BOTS", region="RU", tags=("infrastructure",),
                params={"asn": asn},
            ))
        else:
            raise ValueError(f"unknown infrastructure source {item['source']!r}")

    for group in sources.get("reddit", []):
        for sub in group["subreddits"]:
            for metric, unit in (("comments", "COMMENTS / H"), ("posts", "POSTS / H")):
                specs.append(SeriesSpec(
                    key=f"reddit.{sub.lower()}.{metric}", kind="community", platform="reddit",
                    label=f"r/{sub}", unit=unit, region=group["region"], tags=tuple(group["tags"]),
                    params={"subreddit": sub, "metric": metric},
                ))

    for item in sources.get("bluesky", []):
        lang = item.get("lang", "")
        specs.append(SeriesSpec(
            key=f"bluesky.{slug(item['query'])}{'.' + lang if lang else ''}.posts", kind="community",
            platform="bluesky", label=f'BSKY "{item["query"]}"', unit="POSTS / H",
            region=item["region"], tags=tuple(item["tags"]),
            params={"query": item["query"], "lang": lang},
        ))

    # X: the same searches as Bluesky, counted with the X API (tracker/collectors/x.py).
    if sources.get("x", {}).get("mirror_bluesky"):
        for item in sources.get("bluesky", []):
            lang = item.get("lang", "")
            for metric, unit in X_METRICS:
                specs.append(SeriesSpec(
                    key=f"x.{slug(item['query'])}{'.' + lang if lang else ''}.{metric}", kind="community",
                    platform="x", label=f'X "{item["query"]}"', unit=unit,
                    region=item["region"], tags=tuple(item["tags"]),
                    params={"query": item["query"], "lang": lang, "metric": metric},
                ))

    keys = [s.key for s in specs]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        raise ValueError(f"duplicate series keys in config: {sorted(dupes)}")

    analysis = sources.get("analysis", {})
    return Config(
        series=tuple(specs),
        events=tuple(
            Event(ts=_event_ts(e), timed="at" in e, short=e.get("short", e["label"][:12]), label=e["label"],
                  status=e.get("status", "reported"), source=e.get("source", ""))
            for e in events.get("event", [])
        ),
        reference_start=_day_ts(analysis["reference_start"]),
        reference_end=_day_ts(analysis["reference_end"], end=True),
        correlation_ref=analysis.get("correlation_ref", ""),
    )


def load_config(directory: Path = CONFIG_DIR) -> Config:
    sources = tomllib.loads((directory / "sources.toml").read_text(encoding="utf-8"))
    events_path = directory / "events.toml"
    events = tomllib.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else {}
    return parse_config(sources, events)
