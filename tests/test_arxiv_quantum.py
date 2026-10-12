"""Tests for collectors/arxiv_quantum.py. Run: python -m unittest discover tests"""

import email.message
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "collectors"))
import arxiv_quantum as aq  # noqa: E402

FEED = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
    b"<opensearch:totalResults>17</opensearch:totalResults></feed>"
)


def http_error(code, retry_after=None):
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x", code, "err", headers, io.BytesIO(b""))


class QueryTest(unittest.TestCase):
    def test_only_current_and_previous_month_are_open(self):
        today = aq.datetime(2026, 10, 12)
        self.assertTrue(aq.month_is_open(2026, 10, today))
        self.assertTrue(aq.month_is_open(2026, 9, today))
        self.assertFalse(aq.month_is_open(2026, 8, today))
        new_year = aq.datetime(2026, 1, 2)
        self.assertTrue(aq.month_is_open(2025, 12, new_year))
        self.assertFalse(aq.month_is_open(2025, 11, new_year))

    def test_429_without_retry_after_waits_out_the_block(self):
        # Run 38263106111 gave up after 3s+6s+12s because arXiv sent no Retry-After.
        self.assertEqual(aq.retry_delay(0, None, 429), aq.RETRY_429_FLOOR_SECONDS)
        self.assertEqual(aq.retry_delay(1, None, 429), 60)
        self.assertEqual(aq.retry_delay(4, None, 429), aq.MAX_BACKOFF_SECONDS)
        self.assertEqual(aq.retry_delay(0, "90", 429), 90)
        self.assertEqual(aq.retry_delay(0, None, 503), aq.RATE_LIMIT_SECONDS)

    def test_query_does_not_use_max_results_zero(self):
        # arXiv's API answers max_results=0 with HTTP 500 (root cause of the all-zero data).
        url = aq.build_arxiv_query("error_correction", 2026, 9)
        self.assertNotIn("max_results=0", url)
        self.assertIn("max_results=1", url)


@mock.patch.object(aq.time, "sleep")
class FetchPaperCountTest(unittest.TestCase):
    def test_429_without_retry_after_sleeps_at_least_the_floor(self, sleep):
        with mock.patch.object(aq.urllib.request, "urlopen",
                               side_effect=[http_error(429), io.BytesIO(FEED)]):
            count, _ = aq.fetch_paper_count("http://x")
        self.assertEqual(count, 17)
        self.assertGreaterEqual(sleep.call_args_list[0].args[0], aq.RETRY_429_FLOOR_SECONDS)

    def test_retries_429_honoring_retry_after_then_succeeds(self, sleep):
        with mock.patch.object(aq.urllib.request, "urlopen",
                               side_effect=[http_error(429, "30"), io.BytesIO(FEED)]) as urlopen:
            count, _ = aq.fetch_paper_count("http://x")
        self.assertEqual(count, 17)
        self.assertEqual(urlopen.call_count, 2)
        self.assertGreaterEqual(sleep.call_args_list[0].args[0], 30)

    def test_backoff_is_at_least_politeness_delay(self, sleep):
        with mock.patch.object(aq.urllib.request, "urlopen",
                               side_effect=[http_error(503), io.BytesIO(FEED)]):
            aq.fetch_paper_count("http://x")
        self.assertGreaterEqual(sleep.call_args_list[0].args[0], aq.RATE_LIMIT_SECONDS)

    def test_persistent_server_error_raises_instead_of_returning_zero(self, sleep):
        with mock.patch.object(aq.urllib.request, "urlopen",
                               side_effect=http_error(500)) as urlopen:
            with self.assertRaises(aq.FetchError):
                aq.fetch_paper_count("http://x")
        self.assertEqual(urlopen.call_count, aq.MAX_ATTEMPTS)

    def test_client_error_is_not_retried(self, sleep):
        with mock.patch.object(aq.urllib.request, "urlopen",
                               side_effect=http_error(400)) as urlopen:
            with self.assertRaises(aq.FetchError):
                aq.fetch_paper_count("http://x")
        self.assertEqual(urlopen.call_count, 1)

    def test_feed_without_total_results_raises(self, sleep):
        bad = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with mock.patch.object(aq.urllib.request, "urlopen", return_value=io.BytesIO(bad)):
            with self.assertRaises(aq.FetchError):
                aq.fetch_paper_count("http://x")


@mock.patch.object(aq.time, "sleep")
@mock.patch.object(aq, "generate_month_range", return_value=[(2026, 8), (2026, 9)])
class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name, sub in (("OUTPUT_DIR", "processed"), ("RAW_DIR", "raw")):
            patcher = mock.patch.object(aq, name, os.path.join(self.tmp.name, sub))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = os.path.join(self.tmp.name, "processed", "paper_counts.json")
        os.makedirs(os.path.dirname(self.output))
        self.argv = mock.patch.object(sys, "argv", ["arxiv_quantum.py"])
        self.argv.start()
        self.addCleanup(self.argv.stop)

    def test_failure_keeps_previous_file_and_exits_nonzero(self, _months, _sleep):
        previous = '{"previous": "good data"}'
        with open(self.output, "w") as f:
            f.write(previous)
        responses = [(5, None), aq.FetchError("HTTP 500")] * len(aq.CATEGORIES)
        with mock.patch.object(aq, "fetch_paper_count", side_effect=responses):
            with self.assertRaises(SystemExit) as exit_ctx:
                aq.main()
        self.assertNotEqual(exit_ctx.exception.code, 0)
        with open(self.output) as f:
            self.assertEqual(f.read(), previous)

    def test_closed_months_reuse_stored_counts(self, months, _sleep):
        months.return_value = [(2025, 1), (2026, 9), (2026, 10)]
        prior = {"categories": {}}
        for cat_key, cat_info in aq.CATEGORIES.items():
            prior["categories"][cat_key] = {
                "label": cat_info["label"],
                "monthly": [
                    {"date": "2025-01", "count": 4},
                    {"date": "2026-09", "count": 1},
                    {"date": "2026-10", "count": 1},
                ],
            }
        with open(self.output, "w") as f:
            json.dump(prior, f)
        frozen = aq.datetime(2026, 10, 12)
        with mock.patch.object(aq, "datetime") as clock:
            clock.now.return_value = frozen
            with mock.patch.object(aq, "fetch_paper_count", return_value=(9, None)) as fetch:
                aq.main()
        # January is closed. September and October are refetched: 2 * 3 categories.
        self.assertEqual(fetch.call_count, 2 * len(aq.CATEGORIES))
        with open(self.output) as f:
            data = json.load(f)
        january = next(m for m in data["categories"]["error_correction"]["monthly"] if m["date"] == "2025-01")
        october = next(m for m in data["categories"]["error_correction"]["monthly"] if m["date"] == "2026-10")
        self.assertEqual(january["count"], 4)
        self.assertEqual(october["count"], 9)

    def test_success_writes_real_counts(self, _months, _sleep):
        with mock.patch.object(aq, "fetch_paper_count", return_value=(7, None)):
            aq.main()
        with open(self.output) as f:
            data = json.load(f)
        self.assertFalse(data["metadata"]["mock"])
        self.assertEqual(data["aggregate"][0]["total"], 7 * len(aq.CATEGORIES))


if __name__ == "__main__":
    unittest.main()
