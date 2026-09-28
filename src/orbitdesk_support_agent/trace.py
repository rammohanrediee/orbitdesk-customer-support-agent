"""Small, dependency-free request tracing for the OrbitDesk workflow."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Iterator
from uuid import uuid4


_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "content",
    "cookie",
    "password",
    "prompt",
    "question",
    "secret",
    "token",
)


def _safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}

    for key, value in attributes.items():
        normalized_key = key.lower()
        if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
            safe[key] = "[REDACTED]"
        elif isinstance(value, str):
            safe[key] = value[:200]
        elif value is None or isinstance(value, (bool, float, int)):
            safe[key] = value
        else:
            safe[key] = repr(value)[:200]

    return safe


@dataclass(frozen=True)
class TraceEvent:
    name: str
    timestamp: str
    elapsed_ms: float
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "elapsed_ms": self.elapsed_ms,
            "attributes": dict(self.attributes),
        }


@dataclass
class RequestTrace:
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    timeout_seconds: float | None = None
    _started_at: float = field(default_factory=perf_counter, repr=False)
    _events: list[TraceEvent] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("Trace timeout must be positive.")

    def record(self, name: str, **attributes: Any) -> TraceEvent:
        if not name or not name.strip():
            raise ValueError("Trace event name must not be empty.")

        event = TraceEvent(
            name=name.strip(),
            timestamp=datetime.now(UTC).isoformat(),
            elapsed_ms=round((perf_counter() - self._started_at) * 1000, 3),
            attributes=_safe_attributes(attributes),
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def remaining_seconds(self) -> float | None:
        if self.timeout_seconds is None:
            return None
        return max(
            self.timeout_seconds - (perf_counter() - self._started_at),
            0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "events": [event.to_dict() for event in self._events],
        }


_CURRENT_TRACE: ContextVar[RequestTrace | None] = ContextVar(
    "orbitdesk_request_trace",
    default=None,
)


@contextmanager
def request_trace(
    trace_id: str | None = None,
    *,
    timeout_seconds: float | None = None,
) -> Iterator[RequestTrace]:
    trace = RequestTrace(
        trace_id=trace_id or uuid4().hex,
        timeout_seconds=timeout_seconds,
    )
    token = _CURRENT_TRACE.set(trace)
    try:
        yield trace
    finally:
        _CURRENT_TRACE.reset(token)


def current_trace() -> RequestTrace | None:
    return _CURRENT_TRACE.get()


def record_trace_event(name: str, **attributes: Any) -> TraceEvent | None:
    trace = current_trace()
    if trace is None:
        return None
    return trace.record(name, **attributes)
