"""Download the EUvsDisinfo cases through the database's MCP server.

The server (https://mcp.euvsd.info/mcp, run for EUvsDisinfo) has a `cases` tool that
pages through every case, newest first, 100 at a time. This script calls it in
stateless mode, one request a second, and keeps the cases in
data/external/euvsdisinfo/mcp/cases.jsonl (not in git). A later run stops at the first
page whose cases it already has, so only new cases are fetched; an interrupted
download carries on where it stopped (data/external/euvsdisinfo/mcp/state.json).
`--all` fetches everything again (about 200 requests for 20,000 cases). The server
fails a whole page when one case in it is malformed; such pages are fetched in
smaller pieces and the cases it cannot return are skipped and counted.

The API key comes from EUVSDISINFO_API_KEY in .env and is sent in the X-API-Key header,
never in the URL. Access was requested from EUvsDisinfo by Emma on 2 November 2026.

    python -m research.euvsdisinfo_mcp            # new cases only
    python -m research.euvsdisinfo_mcp --all

The cases are then read by research/euvsdisinfo_lgbtq.py --mcp.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

from tracker.config import ROOT, load_dotenv

URL = "https://mcp.euvsd.info/mcp"
CACHE = ROOT / "data" / "external" / "euvsdisinfo" / "mcp" / "cases.jsonl"
STATE = CACHE.with_name("state.json")  # where an interrupted download stopped, and skipped cases
PAGE = 100
PAUSE_S = 1.0


def parse_response(body: str) -> dict:
    """The JSON-RPC message in a response, which comes either as plain JSON or as
    server-sent events ("data: {...}" lines)."""
    body = body.strip()
    if body.startswith("{"):
        return json.loads(body)
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise ValueError(f"no JSON-RPC message in response: {body[:200]!r}")


def tool_result(message: dict):
    """The data a tools/call returned: structured content when the server gives it,
    otherwise the JSON in its text content."""
    if "error" in message:
        raise RuntimeError(f"EUvsDisinfo MCP error {message['error'].get('code')}: {message['error'].get('message')}")
    result = message["result"]
    if result.get("isError"):
        raise ToolError(f"EUvsDisinfo MCP tool error: {result.get('content')}")
    if "structuredContent" in result:
        return result["structuredContent"]
    text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
    return json.loads(text)


def call(client: httpx.Client, name: str, arguments: dict):
    r = client.post(URL, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": name, "arguments": arguments}})
    if r.status_code == 401:
        sys.exit("EUvsDisinfo refused the API key (401): check EUVSDISINFO_API_KEY in .env")
    r.raise_for_status()
    return tool_result(parse_response(r.text))


def cases_of(data) -> list[dict]:
    """The list of cases in a `cases` result, which may be the list itself or wrap it."""
    if isinstance(data, list):
        return data
    for key in ("cases", "items", "data", "results"):
        if isinstance(data.get(key), list):
            return data[key]
    raise ValueError(f"unexpected `cases` result with keys {sorted(data)}")


class ToolError(RuntimeError):
    pass


def load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    return {str(c["id"]): c for c in map(json.loads, CACHE.read_text(encoding="utf-8").splitlines()) if c}


def save(cases: dict[str, dict], state: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(cases.values(), key=lambda c: (c.get("date") or 0, str(c["id"])))
    CACHE.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in ordered), encoding="utf-8")
    STATE.write_text(json.dumps(state), encoding="utf-8")


def fetch(client: httpx.Client, offset: int, limit: int, skipped: list[int]) -> list[dict]:
    """Cases offset to offset + limit. The server fails a whole page when one case in it
    is malformed, so a failing page is fetched again in smaller pieces, down to single
    cases; a case that fails on its own is skipped and its offset recorded."""
    try:
        return cases_of(call(client, "cases", {"limit": limit, "offset": offset}))
    except ToolError as e:
        if limit == 1:
            print(f"offset {offset}: skipped, the server cannot return this case ({e})", flush=True)
            skipped.append(offset)
            return []
    step = max(1, limit // 10)
    out = []
    for start in range(offset, offset + limit, step):
        time.sleep(PAUSE_S)
        out += fetch(client, start, step, skipped)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="fetch every case again")
    args = parser.parse_args()
    load_dotenv()
    key = os.environ.get("EUVSDISINFO_API_KEY")
    if not key:
        sys.exit("set EUVSDISINFO_API_KEY in .env first")
    cases = {} if args.all else load_cache()
    state = {} if args.all or not STATE.exists() else json.loads(STATE.read_text(encoding="utf-8"))
    # An interrupted download carries on where it stopped; a complete one only looks for new cases.
    complete = state.get("complete", False)
    offset = 0 if complete else state.get("next_offset", 0)
    skipped = [] if complete else state.get("skipped", [])
    headers = {"X-API-Key": key, "Accept": "application/json, text/event-stream",
               "mcp-session-id": str(uuid.uuid4())}  # stateless mode: a client-made id, no initialize
    before = len(cases)
    with httpx.Client(headers=headers, timeout=60) as client:
        total = call(client, "cases", {"limit": 1, "offset": 0}).get("total")
        while total is None or offset < total:
            page = fetch(client, offset, PAGE, skipped)
            new = [c for c in page if str(c["id"]) not in cases]
            cases.update((str(c["id"]), c) for c in page)
            offset += PAGE
            print(f"offset {offset - PAGE} of {total}: {len(page)} cases, {len(new)} new", flush=True)
            save(cases, {"complete": False, "next_offset": offset, "skipped": skipped})
            if (complete and not new) or (total is None and not page):
                break
            time.sleep(PAUSE_S)
    save(cases, {"complete": True, "skipped": skipped, "total_reported": total,
                 "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(f"{len(cases)} cases in {CACHE.relative_to(ROOT)} ({len(cases) - before} new); "
          f"{len(skipped)} the server could not return, at offsets {skipped}")


if __name__ == "__main__":
    main()
