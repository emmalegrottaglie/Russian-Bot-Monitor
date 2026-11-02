import json

import pytest

from research import euvsdisinfo_mcp as m


def test_responses_parse_as_json_or_server_sent_events():
    message = {"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {"cases": [{"id": "a"}]}}}
    assert m.parse_response(json.dumps(message)) == message
    assert m.parse_response(f"event: message\ndata: {json.dumps(message)}\n\n") == message
    assert m.cases_of(m.tool_result(message)) == [{"id": "a"}]
    text = {"result": {"content": [{"type": "text", "text": json.dumps({"cases": [{"id": "b"}]})}]}}
    assert m.cases_of(m.tool_result(text)) == [{"id": "b"}]


def test_a_malformed_case_is_skipped_and_its_page_still_read(monkeypatch):
    bad = 7  # the server fails any page that includes this offset
    monkeypatch.setattr(m, "PAUSE_S", 0)

    def fake_call(client, name, arguments):
        start, limit = arguments["offset"], arguments["limit"]
        if start <= bad < start + limit:
            raise m.ToolError("Cannot read properties of null (reading 'title')")
        return {"cases": [{"id": str(i)} for i in range(start, start + limit)]}

    monkeypatch.setattr(m, "call", fake_call)
    skipped = []
    got = m.fetch(None, 0, 100, skipped)
    assert skipped == [bad] and len(got) == 99 and {"id": str(bad)} not in got


def test_a_refused_key_stops_with_a_message():
    class Refused:
        def post(self, *args, **kwargs):
            class R:
                status_code = 401
            return R()

    with pytest.raises(SystemExit, match="EUVSDISINFO_API_KEY"):
        m.call(Refused(), "cases", {"limit": 1, "offset": 0})
