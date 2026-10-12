# Bot Traffic Monitor

UI must follow `terminal-design-guide/DESIGN_GUIDE.md` and use `terminal-design-guide/terminal.css` (served at `/design/terminal.css`). Label every number, never show fabricated data (unknown values render as `—`), keep border-radius 0. Page-specific styles go in `web/app.css`.

- Backend: Python, `tracker/` package. FastAPI + SQLite + httpx. No other runtime dependencies without a good reason.
- Sources and research tags live in `config/sources.toml`; chart annotations in `config/events.toml`. Every event needs a source and a status.
- Collectors must never invent points: a failed or empty fetch records an error, not a zero.
- Store timestamps only. No usernames or post content.
- Tests: `python -m pytest`.
