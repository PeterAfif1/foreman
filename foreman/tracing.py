"""Tracing for every AI call: what it was for, cost, latency, and whether it failed.

Library code (extract, reply, agent) calls `record(...)`. The app plugs in a sink
(the database) at startup; without one, recording does nothing, so tests and
scripts don't need a database.

Traces hold metadata only, never message text. The text is customer data and
already lives on the card.
"""

import contextvars
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

# Which request and which card or chat the current calls belong to.
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_chat_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("chat_id", default=None)


class Sink(Protocol):
    def record_ai_call(self, call: dict) -> None: ...


_sink: Sink | None = None


def set_sink(sink: Sink | None) -> None:
    global _sink
    _sink = sink


@contextmanager
def request_context(chat_id: str | None = None) -> Iterator[str]:
    """Group the AI calls of one request, so they can be linked to the card it creates."""
    rid = uuid.uuid4().hex
    t1, t2 = _request_id.set(rid), _chat_id.set(chat_id)
    try:
        yield rid
    finally:
        _request_id.reset(t1)
        _chat_id.reset(t2)


def record(
    feature: str,
    model: str,
    prompt_version: str | None,
    latency_ms: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float | None = None,
    error: str | None = None,
    detail: dict | None = None,
) -> None:
    if _sink is None:
        return
    try:
        _sink.record_ai_call(
            {
                "feature": feature,
                "model": model,
                "prompt_version": prompt_version,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
                "ok": error is None,
                "error": error,
                "request_id": _request_id.get(),
                "chat_id": _chat_id.get(),
                "detail": detail or {},
            }
        )
    except Exception:  # noqa: BLE001 - tracing must never break the feature it watches
        pass


def traced(feature: str, model: str, prompt_version: str | None, cost_fn, call, detail_fn=None):
    """Run one model call and record it, failures included. Returns the completion."""
    start = time.perf_counter()
    try:
        completion = call()
    except Exception as e:
        record(
            feature,
            model,
            prompt_version,
            (time.perf_counter() - start) * 1000,
            error=f"{type(e).__name__}: {e}"[:300],
        )
        raise
    usage = getattr(completion, "usage", None)
    tokens_in = getattr(usage, "prompt_tokens", 0) or 0
    tokens_out = getattr(usage, "completion_tokens", 0) or 0
    record(
        feature,
        model,
        prompt_version,
        (time.perf_counter() - start) * 1000,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_usd=cost_fn(model, tokens_in, tokens_out),
        detail=_safe(detail_fn, completion),
    )
    return completion


def _safe(fn, arg) -> dict | None:
    if fn is None:
        return None
    try:
        return fn(arg)
    except Exception:  # noqa: BLE001
        return None
