# Bot Traffic Monitor

UI must follow `terminal-design-system/DESIGN_GUIDE.md` and use `terminal-design-system/terminal.css` (served at `/design/terminal.css`). Label every number, never show fabricated data (unknown values render as `—`), keep border-radius 0. Page-specific styles go in `web/app.css`.

This repo holds the canonical copy of the terminal design system shared with Weather Terminal and the retro speed test. Any design decision that adds or changes one of its rules must be written into `terminal-design-system/DESIGN_GUIDE.md` and synced to the other repos in the same piece of work; follow `terminal-design-system/AGENTS.md`.

- Backend: Python, `tracker/` package. FastAPI + SQLite + httpx. No other runtime dependencies without a good reason.
- Sources and research tags live in `config/sources.toml`; chart annotations in `config/events.toml`. Every event needs a source and a status.
- Collectors must never invent points: a failed or empty fetch records an error, not a zero.
- Store timestamps and aggregate counts only. Collectors may read post text and account metadata in memory to compute aggregate measures; only hourly totals are stored. Never store or log usernames, account IDs or post text.
- Exception for the coded-communities catalogue (docs/CODED-COMMUNITIES.md): per-community aggregates may also be stored, namely counts of commenters shared between two communities and counts of glossary terms per community. They must never let an individual be identified: no usernames, no per-user rows, no pair counts below 10 commenters.
- Tests: `python -m pytest`.
