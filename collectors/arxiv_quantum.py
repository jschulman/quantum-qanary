#!/usr/bin/env python3
"""
Quantum Qanary - arXiv Quantum Paper Collector

Fetches quantum computing paper counts from the arXiv Atom API.
Tracks three search categories over the last 3 years, counting papers per month.

Categories:
  - shor_implementation: Shor's algorithm AND (implementation OR factoring) in quant-ph
  - pqc_deployment: post-quantum AND (migration OR deployment) in cs.CR
  - error_correction: quantum error correction AND logical qubit in quant-ph

Usage:
  python collectors/arxiv_quantum.py          # Live API fetch
  python collectors/arxiv_quantum.py --mock   # Generate realistic mock data
"""

import argparse
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "arxiv", "processed")
RAW_DIR = os.path.join(BASE_DIR, "data", "arxiv", "raw")

ARXIV_API_URL = "http://export.arxiv.org/api/query"
RATE_LIMIT_SECONDS = 3
MAX_ATTEMPTS = 6
MAX_BACKOFF_SECONDS = 120
# arXiv 429s often carry no Retry-After. The old 3/6/12s ladder gave up
# while the block was still in place (run 38263106111, 2026-10-12).
RETRY_429_FLOOR_SECONDS = 30
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(Exception):
    """A paper count could not be fetched; never record it as 0."""

# Atom XML namespace
OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"

CATEGORIES = {
    "shor_implementation": {
        "label": "Shor's Algorithm Implementation",
        "query": 'all:"Shor\'s algorithm" AND (all:implementation OR all:factoring)',
        "arxiv_cat": "quant-ph",
    },
    "pqc_deployment": {
        "label": "PQC Migration & Deployment",
        "query": "all:post-quantum AND (all:migration OR all:deployment)",
        "arxiv_cat": "cs.CR",
    },
    "error_correction": {
        "label": "Quantum Error Correction",
        "query": 'all:"quantum error correction" AND all:"logical qubit"',
        "arxiv_cat": "quant-ph",
    },
}


def generate_month_range(years_back=3):
    """Generate a list of (year, month) tuples for the last N years."""
    today = datetime.now()
    months = []
    for i in range(years_back * 12):
        dt = today - timedelta(days=i * 30.44)
        ym = (dt.year, dt.month)
        if ym not in [m for m in months]:
            months.append(ym)
    months.sort()
    return months


def format_month(year, month):
    """Format year/month as YYYY-MM string."""
    return f"{year:04d}-{month:02d}"


def build_arxiv_query(category_key, year, month):
    """Build an arXiv API query URL for a specific category and month."""
    cat_info = CATEGORIES[category_key]
    search_query = cat_info["query"]
    arxiv_cat = cat_info["arxiv_cat"]

    # Calculate date range for the month
    start_date = f"{year:04d}{month:02d}01"
    if month == 12:
        end_year = year + 1
        end_month = 1
    else:
        end_year = year
        end_month = month + 1
    end_date = f"{end_year:04d}{end_month:02d}01"

    # arXiv uses submittedDate for date range filtering
    date_filter = f" AND submittedDate:[{start_date}0000 TO {end_date}0000]"
    full_query = f"cat:{arxiv_cat} AND {search_query}{date_filter}"

    params = urllib.parse.urlencode({
        "search_query": full_query,
        "start": 0,
        "max_results": 1,  # We only need totalResults; arXiv returns HTTP 500 for max_results=0
    })
    return f"{ARXIV_API_URL}?{params}"


def retry_delay(attempt, retry_after, status=None):
    """Exponential backoff from the 3s politeness delay, raised to honor Retry-After.

    A 429 with no Retry-After still waits at least RETRY_429_FLOOR_SECONDS.
    """
    delay = RATE_LIMIT_SECONDS * 2 ** attempt
    if status == 429:
        delay = max(delay, RETRY_429_FLOOR_SECONDS * 2 ** attempt)
    if retry_after and str(retry_after).strip().isdigit():
        delay = max(delay, int(str(retry_after).strip()))
    return min(delay, MAX_BACKOFF_SECONDS)


def fetch_paper_count(url):
    """Fetch paper count from arXiv API for a given query URL. Raises FetchError on failure."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "QuantumQanary/1.0 (research dashboard; https://github.com/quantum-qanary)"
    })
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read().decode("utf-8")
            break
        except urllib.error.HTTPError as e:
            if e.code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS - 1:
                raise FetchError(f"HTTP {e.code} after {attempt + 1} attempt(s)") from e
            delay = retry_delay(attempt, e.headers.get("Retry-After"), e.code)
            reason = f"HTTP {e.code}"
        except OSError as e:  # URLError, timeouts, connection resets
            if attempt == MAX_ATTEMPTS - 1:
                raise FetchError(f"{e} after {attempt + 1} attempt(s)") from e
            delay = retry_delay(attempt, None)
            reason = str(e)
        print(f"  [WARN] {reason}; retrying in {delay:.0f}s", file=sys.stderr)
        time.sleep(delay)

    # Parse total results from Atom feed
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        raise FetchError(f"XML parse error: {e}") from e
    total_el = root.find(f"{OPENSEARCH_NS}totalResults")
    if total_el is None:
        raise FetchError("response has no opensearch:totalResults")
    return int(total_el.text), xml_data


def month_is_open(year, month, today):
    """True for the current month and the one before it.

    submittedDate is fixed once arXiv has announced the paper, so older
    months do not change. The previous month stays open because a paper
    submitted at the end of the month can miss that day's snapshot.
    """
    serial = year * 12 + (month - 1)
    current = today.year * 12 + (today.month - 1)
    return serial >= current - 1


def load_stored_counts(path):
    """Return {category: {YYYY-MM: count}} from the last good snapshot.

    A missing or unreadable file yields {}. Counts are reused only for
    closed months; a failed fetch never invents a 0.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    stored = {}
    for cat_key, cat in data.get("categories", {}).items():
        if cat_key not in CATEGORIES or not isinstance(cat, dict):
            continue
        counts = {}
        for row in cat.get("monthly", []):
            if not isinstance(row, dict):
                continue
            date = row.get("date")
            count = row.get("count")
            if isinstance(date, str) and isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                counts[date] = count
        stored[cat_key] = counts
    return stored


def count_live_requests(months, stored, today):
    """How many API calls this run will make."""
    total = 0
    for cat_key in CATEGORIES:
        for year, month in months:
            cached = stored.get(cat_key, {}).get(format_month(year, month))
            if cached is None or month_is_open(year, month, today):
                total += 1
    return total


def fetch_live_data(months, stored, today):
    """Fetch live data from arXiv. Closed months with a stored count are reused."""
    results = {cat_key: {} for cat_key in CATEGORIES}
    reused = 0
    for cat_key in CATEGORIES:
        print(f"Fetching category: {CATEGORIES[cat_key]['label']}")

        for year, month in months:
            month_str = format_month(year, month)
            cached = stored.get(cat_key, {}).get(month_str)
            if cached is not None and not month_is_open(year, month, today):
                results[cat_key][month_str] = cached
                reused += 1
                continue
            url = build_arxiv_query(cat_key, year, month)
            count, raw_xml = fetch_paper_count(url)
            results[cat_key][month_str] = count
            print(f"  {month_str}: {count} papers")

            # Save raw response
            if raw_xml:
                raw_path = os.path.join(
                    RAW_DIR,
                    f"{cat_key}_{month_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                )
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(raw_xml)

            # Rate limit: 1 request per 3 seconds
            time.sleep(RATE_LIMIT_SECONDS)

    print(f"Reused {reused} stored closed-month counts")
    return results


def generate_mock_data(months):
    """Generate realistic mock data for testing without API calls."""
    random.seed(42)
    results = {}

    # Base rates and growth curves per category
    profiles = {
        "shor_implementation": {
            "base": 3,
            "growth": 0.02,
            "variance": 0.4,
            "seasonal": True,
        },
        "pqc_deployment": {
            "base": 8,
            "growth": 0.05,
            "variance": 0.3,
            "seasonal": True,
        },
        "error_correction": {
            "base": 5,
            "growth": 0.04,
            "variance": 0.35,
            "seasonal": True,
        },
    }

    for cat_key, profile in profiles.items():
        results[cat_key] = {}
        for idx, (year, month) in enumerate(months):
            month_str = format_month(year, month)

            # Growth trend (exponential-ish)
            trend = profile["base"] * (1 + profile["growth"]) ** idx

            # Seasonal dip in summer months and December
            seasonal = 1.0
            if profile["seasonal"]:
                if month in (6, 7, 8):
                    seasonal = 0.7
                elif month == 12:
                    seasonal = 0.8
                elif month in (1, 9, 10):
                    seasonal = 1.15

            # Random variance
            noise = random.gauss(1.0, profile["variance"])
            noise = max(0.3, noise)

            count = max(0, round(trend * seasonal * noise))
            results[cat_key][month_str] = count

    return results


def build_output(results, months, is_mock):
    """Build the output JSON structure from collected results."""
    today = datetime.now().strftime("%Y-%m-%d")

    categories = {}
    for cat_key, cat_info in CATEGORIES.items():
        monthly = []
        for year, month in months:
            month_str = format_month(year, month)
            count = results.get(cat_key, {}).get(month_str, 0)
            monthly.append({"date": month_str, "count": count})
        categories[cat_key] = {
            "label": cat_info["label"],
            "monthly": monthly,
        }

    # Aggregate across all categories
    aggregate = []
    for year, month in months:
        month_str = format_month(year, month)
        total = sum(
            results.get(cat_key, {}).get(month_str, 0)
            for cat_key in CATEGORIES
        )
        aggregate.append({"date": month_str, "total": total})

    return {
        "metadata": {
            "source": "arxiv API",
            "last_updated": today,
            "mock": is_mock,
        },
        "categories": categories,
        "aggregate": aggregate,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch quantum computing paper counts from arXiv"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate realistic mock data instead of calling the API",
    )
    args = parser.parse_args()

    # Ensure output directories exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    months = generate_month_range(years_back=3)

    if args.mock:
        print("Running in MOCK mode -- generating realistic test data")
        results = generate_mock_data(months)
    else:
        print("Running in LIVE mode -- fetching from arXiv API")
        print(f"Rate limit: {RATE_LIMIT_SECONDS}s between requests")
        today = datetime.now()
        output_path = os.path.join(OUTPUT_DIR, "paper_counts.json")
        stored = load_stored_counts(output_path)
        print(f"Total requests: {count_live_requests(months, stored, today)}")
        try:
            results = fetch_live_data(months, stored, today)
        except FetchError as e:
            print(f"\n[ERROR] arXiv fetch failed: {e}", file=sys.stderr)
            print("Previous paper_counts.json left unchanged.", file=sys.stderr)
            sys.exit(1)

    output = build_output(results, months, is_mock=args.mock)

    output_path = os.path.join(OUTPUT_DIR, "paper_counts.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nOutput written to {output_path}")

    # Print summary
    for cat_key, cat_data in output["categories"].items():
        total = sum(m["count"] for m in cat_data["monthly"])
        print(f"  {cat_data['label']}: {total} papers over {len(cat_data['monthly'])} months")

    agg_total = sum(m["total"] for m in output["aggregate"])
    print(f"  Aggregate total: {agg_total}")


if __name__ == "__main__":
    main()
