"""Summaries of the traced AI calls for the usage page."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile: p95 is a latency that 95% of calls beat or match."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * p // 100))  # ceil without floats drifting
    return ordered[int(rank) - 1]


def _stats(calls: list[dict]) -> dict:
    latencies = [c["latency_ms"] for c in calls if c["ok"]]
    errors = sum(1 for c in calls if not c["ok"])
    return {
        "calls": len(calls),
        "errors": errors,
        "error_rate": errors / len(calls) if calls else None,
        "cost_usd": sum(c["cost_usd"] or 0 for c in calls),
        "input_tokens": sum(c["input_tokens"] or 0 for c in calls),
        "output_tokens": sum(c["output_tokens"] or 0 for c in calls),
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
    }


def _local_day(at: str, tz_minutes: int) -> str:
    """Traces are stored in UTC; group them by the viewer's day."""
    moment = datetime.fromisoformat(at)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (moment + timedelta(minutes=tz_minutes)).date().isoformat()


def summarize(calls: list[dict], days: int, today: date | None = None, tz_minutes: int = 0) -> dict:
    """tz_minutes: the viewer's offset from UTC (e.g. 180 for UTC+3)."""
    today = today or (datetime.now(UTC) + timedelta(minutes=tz_minutes)).date()
    by_feature = defaultdict(list)
    for c in calls:
        by_feature[c["feature"]].append(c)

    per_day = {(today - timedelta(days=i)).isoformat(): 0.0 for i in range(days)}
    for c in calls:
        day = _local_day(c["at"], tz_minutes)
        if day in per_day:
            per_day[day] += c["cost_usd"] or 0

    linked = [c for c in calls if c.get("lead_id")]
    leads = {c["lead_id"] for c in linked}
    errors = [c for c in calls if not c["ok"]]
    return {
        "days": days,
        "total": _stats(calls),
        "by_feature": {f: _stats(cs) for f, cs in sorted(by_feature.items())},
        "cost_by_day": [{"day": d, "cost_usd": per_day[d]} for d in sorted(per_day)],
        "cost_per_lead": sum(c["cost_usd"] or 0 for c in linked) / len(leads) if leads else None,
        # How often the chat guardrail had to rewrite a reply (one rewrite call each).
        "guard_rewrites": len(by_feature.get("chat_rewrite", [])),
        "recent_errors": [
            {"at": c["at"], "feature": c["feature"], "error": c["error"]} for c in errors[-10:]
        ][::-1],
    }
