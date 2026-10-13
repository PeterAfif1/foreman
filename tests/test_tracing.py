from datetime import date
from types import SimpleNamespace

import pytest

from foreman import tracing
from foreman.usage import percentile, summarize


class ListSink:
    def __init__(self):
        self.calls = []

    def record_ai_call(self, call):
        self.calls.append(call)


@pytest.fixture
def sink():
    s = ListSink()
    tracing.set_sink(s)
    yield s
    tracing.set_sink(None)


def completion(tokens_in=100, tokens_out=20):
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out)
    )


def cost(model, i, o):
    return (i + o) / 1000


def test_successful_call_is_recorded(sink):
    tracing.traced("extract", "m", "v3", cost, lambda: completion(), lambda c: {"x": 1})
    [call] = sink.calls
    assert call["feature"] == "extract" and call["ok"] is True
    assert (call["input_tokens"], call["output_tokens"], call["cost_usd"]) == (100, 20, 0.12)
    assert call["detail"] == {"x": 1}
    assert call["latency_ms"] >= 0


def test_failed_call_is_recorded_and_still_raises(sink):
    def boom():
        raise TimeoutError("slow")

    with pytest.raises(TimeoutError):
        tracing.traced("reply", "m", "r2", cost, boom)
    [call] = sink.calls
    assert call["ok"] is False and call["error"] == "TimeoutError: slow"


def test_broken_detail_does_not_break_the_call(sink):
    out = tracing.traced("chat", "m", "a4", cost, lambda: completion(), lambda c: 1 / 0)
    assert out.usage.prompt_tokens == 100
    assert sink.calls[0]["detail"] == {}


def test_broken_sink_does_not_break_the_call():
    class Bad:
        def record_ai_call(self, call):
            raise RuntimeError("db locked")

    tracing.set_sink(Bad())
    try:
        assert tracing.traced("extract", "m", "v3", cost, lambda: completion()) is not None
    finally:
        tracing.set_sink(None)


def test_no_sink_records_nothing():
    tracing.set_sink(None)
    tracing.record("extract", "m", "v3", 10.0)  # no error


def test_request_context_tags_calls(sink):
    with tracing.request_context(chat_id="abc") as rid:
        tracing.record("chat", "m", "a4", 5.0)
    tracing.record("chat", "m", "a4", 5.0)
    assert sink.calls[0]["request_id"] == rid and sink.calls[0]["chat_id"] == "abc"
    assert sink.calls[1]["request_id"] is None


def test_percentile():
    assert percentile([], 95) is None
    assert percentile([5], 95) == 5
    values = list(range(1, 101))
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95


def test_summary():
    calls = [
        {
            "at": "2026-10-14T10:00:00",
            "feature": "extract",
            "ok": True,
            "latency_ms": 900,
            "cost_usd": 0.0002,
            "input_tokens": 500,
            "output_tokens": 80,
            "error": None,
            "lead_id": 1,
        },
        {
            "at": "2026-10-14T10:01:00",
            "feature": "chat",
            "ok": True,
            "latency_ms": 1200,
            "cost_usd": 0.0003,
            "input_tokens": 700,
            "output_tokens": 40,
            "error": None,
            "lead_id": 2,
        },
        {
            "at": "2026-10-13T09:00:00",
            "feature": "chat_rewrite",
            "ok": True,
            "latency_ms": 800,
            "cost_usd": 0.0001,
            "input_tokens": 300,
            "output_tokens": 30,
            "error": None,
            "lead_id": 2,
        },
        {
            "at": "2026-10-13T09:05:00",
            "feature": "chat",
            "ok": False,
            "latency_ms": 30000,
            "cost_usd": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "Timeout",
            "lead_id": None,
        },
    ]
    s = summarize(calls, days=3, today=date(2026, 10, 14))
    assert s["total"]["calls"] == 4 and s["total"]["errors"] == 1
    assert s["by_feature"]["chat"]["error_rate"] == 0.5
    assert s["by_feature"]["chat"]["p95_ms"] == 1200  # failed calls don't count toward latency
    assert s["cost_per_lead"] == pytest.approx(0.0003)  # (0.0002 + 0.0003 + 0.0001) / 2 leads
    assert s["guard_rewrites"] == 1
    assert [d["day"] for d in s["cost_by_day"]] == ["2026-10-12", "2026-10-13", "2026-10-14"]
    assert s["cost_by_day"][0]["cost_usd"] == 0
    assert s["recent_errors"] == [
        {"at": "2026-10-13T09:05:00", "feature": "chat", "error": "Timeout"}
    ]
