import unittest

from orbitdesk_support_agent.trace import record_trace_event, request_trace


class RequestTraceTests(unittest.TestCase):
    def test_truncates_untrusted_string_attributes(self):
        with request_trace("trace-string-limit") as trace:
            record_trace_event("provider.response", request_id="x" * 500)

        self.assertEqual(
            len(trace.events[0].attributes["request_id"]),
            200,
        )

    def test_rejects_non_positive_deadline(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            with request_trace(timeout_seconds=0):
                pass

    def test_records_ordered_events_for_one_request(self):
        with request_trace("trace-fixed") as trace:
            record_trace_event("request.started", route="support")
            record_trace_event("request.finished", classification="answerable")

        data = trace.to_dict()
        self.assertEqual(data["trace_id"], "trace-fixed")
        self.assertEqual(
            [event["name"] for event in data["events"]],
            ["request.started", "request.finished"],
        )

    def test_redacts_sensitive_attributes(self):
        with request_trace("trace-fixed") as trace:
            record_trace_event(
                "llm.request",
                api_key="secret",
                prompt="private question",
                attempt=1,
            )

        attributes = trace.to_dict()["events"][0]["attributes"]
        self.assertEqual(attributes["api_key"], "[REDACTED]")
        self.assertEqual(attributes["prompt"], "[REDACTED]")
        self.assertEqual(attributes["attempt"], 1)


if __name__ == "__main__":
    unittest.main()
