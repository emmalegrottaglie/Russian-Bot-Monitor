"""The Twitter request counter, shared with the transphobia monitor through one file."""

import json
import multiprocessing
import time

import pytest

from tracker.collectors import SourceSkipped
from tracker.collectors.x import _Budget


def test_take_counts_per_utc_day_and_stops_at_cap(tmp_path):
    path = tmp_path / "usage.json"
    _Budget(path, cap=2).take()
    _Budget(path, cap=2).take()  # the count survives a restart
    with pytest.raises(SourceSkipped, match="cap"):
        _Budget(path, cap=2).take()
    day = time.strftime("%Y-%m-%d", time.gmtime())
    assert json.loads(path.read_text(encoding="utf-8")) == {day: 2}
    assert not (tmp_path / "usage.json.lock").exists()  # the lock is released after a refusal too


def _worker(path, cap, calls, queue):
    budget = _Budget(path, cap)
    ok = 0
    for _ in range(calls):
        try:
            budget.take()
            ok += 1
        except SourceSkipped:
            pass
    queue.put(ok)


def test_two_processes_never_exceed_cap(tmp_path):
    path = tmp_path / "usage.json"
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    procs = [ctx.Process(target=_worker, args=(path, 12, 10, queue)) for _ in range(2)]
    for p in procs:
        p.start()
    results = [queue.get(timeout=60) for _ in procs]
    for p in procs:
        p.join(timeout=60)
    assert sum(results) == 12
    day = time.strftime("%Y-%m-%d", time.gmtime())
    assert json.loads(path.read_text(encoding="utf-8")) == {day: 12}


def test_unreadable_file_counts_as_cap_reached(tmp_path):
    path = tmp_path / "usage.json"
    path.write_bytes(b"not json")
    with pytest.raises(SourceSkipped):
        _Budget(path, cap=100).take()
    assert path.read_bytes() == b"not json"
    assert not (tmp_path / "usage.json.lock").exists()
