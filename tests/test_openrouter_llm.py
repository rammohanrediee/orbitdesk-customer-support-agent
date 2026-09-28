import json
import os
import unittest
from unittest.mock import patch

from orbitdesk_support_agent.openrouter_llm import (
    HttpResponse,
    OpenRouterConfig,
    OpenRouterError,
    OpenRouterLanguageModel,
    RetryableTransportError,
)
from orbitdesk_support_agent.trace import request_trace


class FakeTransport:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def post_json(self, *, url, headers, payload, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(status_code, payload, headers=None):
    return HttpResponse(
        status_code=status_code,
        headers=headers or {},
        body=json.dumps(payload).encode("utf-8"),
    )


class OpenRouterConfigTests(unittest.TestCase):
    def test_rejects_non_official_api_endpoint(self):
        with self.assertRaisesRegex(ValueError, "official HTTPS endpoint"):
            OpenRouterConfig(
                api_key="secret",
                api_url="https://example.invalid/chat/completions",
            )

    def test_from_env_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
                OpenRouterConfig.from_env()

    def test_from_env_uses_requested_glm_default(self):
        with patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-key"},
            clear=True,
        ):
            config = OpenRouterConfig.from_env()

        self.assertEqual(config.model, "z-ai/glm-4.5-air")

    def test_rejects_unbounded_attempt_configuration(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 5"):
            OpenRouterConfig(api_key="test", max_attempts=6)

    def test_rejects_invalid_numeric_environment_value(self):
        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
                "OPENROUTER_MAX_ATTEMPTS": "many",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "must be an integer"):
                OpenRouterConfig.from_env()


class OpenRouterLanguageModelTests(unittest.TestCase):
    def make_config(self, **overrides):
        values = {
            "api_key": "test-key",
            "max_attempts": 3,
            "request_timeout_seconds": 4.0,
            "max_input_chars": 2_000,
            "base_retry_delay_seconds": 0.01,
            "max_retry_delay_seconds": 0.1,
        }
        values.update(overrides)
        return OpenRouterConfig(**values)

    def test_generate_sends_glm_request_and_returns_text(self):
        transport = FakeTransport(
            [
                response(
                    200,
                    {
                        "id": "generation-123",
                        "choices": [
                            {"message": {"content": "Use the workspace timezone."}}
                        ],
                    },
                )
            ]
        )
        model = OpenRouterLanguageModel(
            self.make_config(),
            transport=transport,
            sleep=lambda _: None,
        )

        with request_trace("trace-123") as trace:
            result = model.generate("system", "question")

        self.assertEqual(result, "Use the workspace timezone.")
        self.assertEqual(transport.calls[0]["payload"]["model"], "z-ai/glm-4.5-air")
        self.assertEqual(transport.calls[0]["payload"]["temperature"], 0)
        self.assertEqual(transport.calls[0]["timeout_seconds"], 4.0)
        self.assertNotIn("test-key", json.dumps(trace.to_dict()))

    def test_retries_only_retryable_statuses_with_a_bound(self):
        transport = FakeTransport(
            [
                response(429, {"error": {"message": "slow down"}}),
                response(503, {"error": {"message": "unavailable"}}),
                response(
                    200,
                    {"choices": [{"message": {"content": "ok"}}]},
                ),
            ]
        )
        delays = []
        model = OpenRouterLanguageModel(
            self.make_config(),
            transport=transport,
            sleep=delays.append,
        )

        self.assertEqual(model.generate("system", "question"), "ok")
        self.assertEqual(len(transport.calls), 3)
        self.assertEqual(len(delays), 2)

    def test_honors_bounded_retry_after_header(self):
        transport = FakeTransport(
            [
                response(
                    429,
                    {"error": {}},
                    headers={"Retry-After": "10"},
                ),
                response(
                    200,
                    {"choices": [{"message": {"content": "ok"}}]},
                ),
            ]
        )
        delays = []
        model = OpenRouterLanguageModel(
            self.make_config(max_retry_delay_seconds=0.1),
            transport=transport,
            sleep=delays.append,
        )

        model.generate("system", "question")

        self.assertEqual(delays, [0.1])

    def test_does_not_retry_authentication_failure(self):
        transport = FakeTransport(
            [response(401, {"error": {"message": "bad key"}})]
        )
        model = OpenRouterLanguageModel(
            self.make_config(),
            transport=transport,
            sleep=lambda _: None,
        )

        with self.assertRaises(OpenRouterError) as error:
            model.generate("system", "question")

        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(len(transport.calls), 1)
        self.assertNotIn("bad key", str(error.exception))

    def test_retries_transport_timeout_but_stops_at_max_attempts(self):
        transport = FakeTransport(
            [
                RetryableTransportError("timed out"),
                RetryableTransportError("timed out"),
            ]
        )
        model = OpenRouterLanguageModel(
            self.make_config(max_attempts=2),
            transport=transport,
            sleep=lambda _: None,
        )

        with self.assertRaisesRegex(OpenRouterError, "after 2 attempts"):
            model.generate("system", "question")

        self.assertEqual(len(transport.calls), 2)

    def test_rejects_oversized_prompt_before_network_call(self):
        transport = FakeTransport([])
        model = OpenRouterLanguageModel(
            self.make_config(max_input_chars=10),
            transport=transport,
        )

        with self.assertRaisesRegex(ValueError, "input limit"):
            model.generate("123456", "78901")

        self.assertEqual(transport.calls, [])

    def test_rejects_malformed_success_response(self):
        transport = FakeTransport([response(200, {"choices": []})])
        model = OpenRouterLanguageModel(
            self.make_config(),
            transport=transport,
        )

        with self.assertRaisesRegex(OpenRouterError, "valid assistant message"):
            model.generate("system", "question")

    def test_accepts_text_content_blocks(self):
        transport = FakeTransport(
            [
                response(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": [
                                        {"type": "text", "text": "hello "},
                                        {"type": "text", "text": "world"},
                                    ]
                                }
                            }
                        ]
                    },
                )
            ]
        )
        model = OpenRouterLanguageModel(
            self.make_config(),
            transport=transport,
        )

        self.assertEqual(model.generate("system", "question"), "hello world")

    def test_clamps_network_timeout_to_request_trace_deadline(self):
        transport = FakeTransport(
            [
                response(
                    200,
                    {"choices": [{"message": {"content": "ok"}}]},
                )
            ]
        )
        model = OpenRouterLanguageModel(
            self.make_config(request_timeout_seconds=4.0),
            transport=transport,
        )

        with request_trace("trace-deadline", timeout_seconds=1.0):
            model.generate("system", "question")

        self.assertGreater(transport.calls[0]["timeout_seconds"], 0)
        self.assertLessEqual(transport.calls[0]["timeout_seconds"], 1.0)


if __name__ == "__main__":
    unittest.main()
