import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orca.core.worktrees.events import emit_event, read_events, EVENT_VOCAB


class TestEmitEvent:
    def test_appends_jsonl_line(self, tmp_path):
        emit_event(tmp_path, event="lane.created",
                   lane_id="015-wiz", branch="feature/015-wiz")
        log = (tmp_path / "events.jsonl").read_text()
        line = json.loads(log.strip())
        assert line["event"] == "lane.created"
        assert line["lane_id"] == "015-wiz"
        assert "ts" in line  # ISO-8601 timestamp injected

    def test_appends_not_overwrites(self, tmp_path):
        emit_event(tmp_path, event="lane.created", lane_id="a")
        emit_event(tmp_path, event="lane.removed", lane_id="a")
        lines = [json.loads(l) for l in
                 (tmp_path / "events.jsonl").read_text().splitlines()]
        assert len(lines) == 2
        assert lines[0]["event"] == "lane.created"
        assert lines[1]["event"] == "lane.removed"

    def test_unknown_event_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not in event vocabulary"):
            emit_event(tmp_path, event="lane.exploded", lane_id="x")

    def test_extra_fields_pass_through(self, tmp_path):
        emit_event(tmp_path, event="setup.after_create.completed",
                   lane_id="x", duration_ms=2340, exit_code=0)
        line = json.loads((tmp_path / "events.jsonl").read_text())
        assert line["duration_ms"] == 2340
        assert line["exit_code"] == 0


class TestReadEvents:
    def test_empty_log_returns_empty(self, tmp_path):
        assert read_events(tmp_path) == []

    def test_skips_corrupt_lines(self, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text(
            json.dumps({"ts": "x", "event": "lane.created", "lane_id": "a"}) +
            "\n{not json\n" +
            json.dumps({"ts": "y", "event": "lane.removed", "lane_id": "a"}) +
            "\n"
        )
        events = read_events(tmp_path)
        assert len(events) == 2


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX lock test")
def test_concurrent_emits_do_not_interleave(tmp_path):
    """N threads each emit M events; assert all N*M lines are valid JSON."""
    import threading
    N, M = 4, 25

    def worker(i):
        for j in range(M):
            emit_event(tmp_path, event="lane.created",
                       lane_id=f"t{i}-{j}", branch=f"feat-{i}-{j}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log = (tmp_path / "events.jsonl").read_text().splitlines()
    assert len(log) == N * M
    for line in log:
        json.loads(line)  # each line is valid JSON
