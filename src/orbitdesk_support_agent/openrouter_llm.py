"""Reliable OpenRouter chat-completion client for OrbitDesk."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import random
import socket
from time import perf_counter, sleep as default_sleep
from typing import Any, Callable, Mapping, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from orbitdesk_support_agent.trace import current_trace, record_trace_event


DEFAULT_OPENROUTER_MODEL = "z-ai/glm-4.5-air"
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RESPONSE_BYTES = 1_000_000
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class OpenRouterError(RuntimeError):
    """A safe error that never embeds provider bodies or credentials."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RetryableTransportError(OSError):
    """A transient network failure which may be retried."""


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> HttpResponse:
        ...


class UrllibTransport:
    """Minimal HTTPS transport with bounded reads and socket timeouts."""

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> HttpResponse:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib_request.Request(
            url=url,
            data=body,
            headers=dict(headers),
            method="POST",
        )

        try:
            with urllib_request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                response_body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(response_body) > MAX_RESPONSE_BYTES:
                    raise OpenRouterError(
                        "OpenRouter returned a response larger than the allowed limit."
                    )
                return HttpResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    body=response_body,
                )
        except urllib_error.HTTPError as error:
            response_body = error.read(MAX_RESPONSE_BYTES + 1)
            return HttpResponse(
                status_code=error.code,
                headers=dict(error.headers.items()) if error.headers else {},
                body=response_body[:MAX_RESPONSE_BYTES],
            )
        except (TimeoutError, socket.timeout, urllib_error.URLError) as error:
            raise RetryableTransportError("OpenRouter transport failed.") from error


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be numeric.") from error


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    model: str = DEFAULT_OPENROUTER_MODEL
    api_url: str = DEFAULT_OPENROUTER_URL
    request_timeout_seconds: float = 20.0
    total_timeout_seconds: float = 45.0
    max_attempts: int = 3
    base_retry_delay_seconds: float = 0.25
    max_retry_delay_seconds: float = 2.0
    max_input_chars: int = 16_000
    max_output_tokens: int = 256
    app_url: str | None = None
    app_title: str = "OrbitDesk Support Agent"

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("OPENROUTER_API_KEY must not be empty.")
        if not self.model.strip():
            raise ValueError("OPENROUTER_MODEL must not be empty.")
        if self.api_url != DEFAULT_OPENROUTER_URL:
            raise ValueError(
                "OpenRouter requests must use the official HTTPS endpoint."
            )
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5.")
        if self.request_timeout_seconds <= 0 or self.total_timeout_seconds <= 0:
            raise ValueError("Timeouts must be positive.")
        if self.max_input_chars <= 0 or self.max_output_tokens <= 0:
            raise ValueError("Input and output limits must be positive.")

    @classmethod
    def from_env(cls) -> "OpenRouterConfig":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key.strip():
            raise ValueError(
                "OPENROUTER_API_KEY is required to use the OrbitDesk model."
            )

        return cls(
            api_key=api_key,
            model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
            api_url=DEFAULT_OPENROUTER_URL,
            request_timeout_seconds=_env_float(
                "OPENROUTER_REQUEST_TIMEOUT_SECONDS",
                20.0,
            ),
            total_timeout_seconds=_env_float(
                "OPENROUTER_TOTAL_TIMEOUT_SECONDS",
                45.0,
            ),
            max_attempts=_env_int("OPENROUTER_MAX_ATTEMPTS", 3),
            max_input_chars=_env_int("ORBITDESK_MAX_LLM_INPUT_CHARS", 16_000),
            max_output_tokens=_env_int("ORBITDESK_MAX_OUTPUT_TOKENS", 256),
            app_url=os.getenv("OPENROUTER_APP_URL") or None,
            app_title=os.getenv(
                "OPENROUTER_APP_TITLE",
                "OrbitDesk Support Agent",
            ),
        )


def _parse_json_object(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OpenRouterError("OpenRouter returned invalid JSON.") from error
    if not isinstance(value, dict):
        raise OpenRouterError("OpenRouter returned an invalid response object.")
    return value


def _assistant_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError(
            "OpenRouter did not return a valid assistant message."
        )

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenRouterError(
            "OpenRouter did not return a valid assistant message."
        )
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenRouterError(
            "OpenRouter did not return a valid assistant message."
        )

    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        text = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ).strip()
    else:
        text = ""

    if not text:
        raise OpenRouterError(
            "OpenRouter did not return a valid assistant message."
        )
    return text


class OpenRouterLanguageModel:
    def __init__(
        self,
        config: OpenRouterConfig | None = None,
        *,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = default_sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self.config = config or OpenRouterConfig.from_env()
        self.transport = transport or UrllibTransport()
        self._sleep = sleep
        self._random_value = random_value

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Metadata": "enabled",
            "X-OpenRouter-Title": self.config.app_title,
        }
        if self.config.app_url:
            headers["HTTP-Referer"] = self.config.app_url
        return headers

    def _retry_delay(self, attempt: int, response: HttpResponse | None) -> float:
        if response is not None:
            retry_after = next(
                (
                    value
                    for key, value in response.headers.items()
                    if key.lower() == "retry-after"
                ),
                None,
            )
            if retry_after is not None:
                try:
                    return min(
                        max(float(retry_after), 0.0),
                        self.config.max_retry_delay_seconds,
                    )
                except ValueError:
                    pass

        base = min(
            self.config.base_retry_delay_seconds * (2 ** (attempt - 1)),
            self.config.max_retry_delay_seconds,
        )
        jitter = 0.75 + (self._random_value() * 0.5)
        return min(base * jitter, self.config.max_retry_delay_seconds)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        total_chars = len(system_prompt) + len(user_prompt)
        if total_chars > self.config.max_input_chars:
            raise ValueError(
                "The assembled prompt exceeds the configured input limit."
            )

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": self.config.max_output_tokens,
            "reasoning": {"enabled": False},
        }

        started_at = perf_counter()
        last_status: int | None = None

        for attempt in range(1, self.config.max_attempts + 1):
            elapsed = perf_counter() - started_at
            remaining = self.config.total_timeout_seconds - elapsed
            trace = current_trace()
            if trace is not None:
                trace_remaining = trace.remaining_seconds()
                if trace_remaining is not None:
                    remaining = min(remaining, trace_remaining)
            if remaining <= 0:
                raise OpenRouterError(
                    "OpenRouter request exceeded its total timeout."
                )
            attempt_timeout = min(
                self.config.request_timeout_seconds,
                remaining,
            )

            record_trace_event(
                "llm.attempt.started",
                attempt=attempt,
                model=self.config.model,
                timeout_seconds=round(attempt_timeout, 3),
            )

            response: HttpResponse | None = None
            try:
                response = self.transport.post_json(
                    url=self.config.api_url,
                    headers=self._headers(),
                    payload=payload,
                    timeout_seconds=attempt_timeout,
                )
            except RetryableTransportError:
                record_trace_event(
                    "llm.attempt.failed",
                    attempt=attempt,
                    failure="transport",
                    retryable=True,
                )
                if attempt == self.config.max_attempts:
                    raise OpenRouterError(
                        "OpenRouter request failed after "
                        f"{self.config.max_attempts} attempts."
                    )
            else:
                last_status = response.status_code
                if response.status_code == 200:
                    response_payload = _parse_json_object(response.body)
                    text = _assistant_text(response_payload)
                    record_trace_event(
                        "llm.attempt.succeeded",
                        attempt=attempt,
                        status_code=200,
                        provider_request_id=response_payload.get("id"),
                        duration_ms=round(
                            (perf_counter() - started_at) * 1000,
                            3,
                        ),
                    )
                    return text

                retryable = response.status_code in RETRYABLE_STATUS_CODES
                record_trace_event(
                    "llm.attempt.failed",
                    attempt=attempt,
                    status_code=response.status_code,
                    retryable=retryable,
                )
                if not retryable:
                    raise OpenRouterError(
                        "OpenRouter rejected the request.",
                        status_code=response.status_code,
                    )
                if attempt == self.config.max_attempts:
                    break

            delay = self._retry_delay(attempt, response)
            remaining_after_attempt = (
                self.config.total_timeout_seconds
                - (perf_counter() - started_at)
            )
            trace = current_trace()
            if trace is not None:
                trace_remaining = trace.remaining_seconds()
                if trace_remaining is not None:
                    remaining_after_attempt = min(
                        remaining_after_attempt,
                        trace_remaining,
                    )
            if delay >= remaining_after_attempt:
                raise OpenRouterError(
                    "OpenRouter request exceeded its total timeout."
                )
            self._sleep(delay)

        raise OpenRouterError(
            "OpenRouter request failed after "
            f"{self.config.max_attempts} attempts.",
            status_code=last_status,
        )
